"""Deterministic orchestration guards, independent of classifier confidence."""
import re
from evolv_nlp.entities import normalize_text
from evolv_nlp.risk_rules_v12 import _Detector, _pattern
from evolv_nlp.risk_rules_v14 import detect_risks
from evolv_nlp.entities_v12 import _normalize


_URGENT_VARIANTS = _pattern(
    r"(?:aperto|pressao|peso) no (?:peito|torax)|"
    r"(?:to|estou) (?:sem ar|com (?:muita )?dificuldade (?:para|de) respirar)|"
    r"nao consigo puxar (?:o )?ar|"
    r"garganta (?:(?:esta |ta )?fechando|comecou a fechar|fechou)|"
    r"desmaiou[^!?;\n]{0,100}?\b(?:nao acorda|nao (?:esta |ta )?respond(?:e|endo)|"
    r"continua desacordad[oa])"
)
_CRITICAL = {"emergency_symptom", "food_allergy_or_reaction"}
_INGESTION = _pattern(r"comi|ingeri|depois de comer|apos comer")
_TONGUE_SWELLING = _pattern(r"lingua (?:esta |ta )?inchad[ao]|lingua inchou")
_PRIVACY = re.compile(
    r"\b(?:privacidade|lgpd|consentimento)\b|"
    r"\b(?:apag|exclu|delet|remov)\w*\b.{0,36}\b(?:meus dados|historico|conversas?|chat|minha conta)\b|"
    r"\b(?:treinamento|treinar (?:o|um|seu) modelo|treina (?:o|seu) modelo)\b.{0,60}\b(?:conversas?|chat|papo|historico)\b|"
    r"\b(?:conversas?|chat|papo|historico)\b.{0,60}\b(?:treinamento|treinam|treina (?:o|seu) modelo|"
    r"treinar (?:o|um|seu) modelo|(?:para|pra) treinar)\b"
)


def terse_urgent_report(text):
    # Preserve sentence punctuation, which normalize_text intentionally removes.
    folded = _normalize(text)[0].strip()
    return bool(re.match(r"^(?:dor no peito\s*(?:e|,)\s*falta de ar|falta de ar\s*(?:e|,)\s*dor no peito)"
                         r"(?:\s+agora)?\s*(?:[.!]|$)", folded))


def _urgent_variant(text):
    detector = _Detector(text)
    # The same assertion, educational and negation checks used by the risk rules.
    detector.lexical("emergency_symptom", "colloquial_urgent_report", _URGENT_VARIANTS, personal=True)
    if any(not detector.suppression(m.start(), m.end()) for m in _INGESTION.finditer(detector.normalized)):
        detector.lexical("emergency_symptom", "swelling_after_ingestion", _TONGUE_SWELLING, personal=True)
    return any(item.status == "matched" for item in detector.evidence)


def _risk_labels(text):
    risks = set(detect_risks(text).risks)
    if "emergency_symptom" not in risks and (terse_urgent_report(text) or _urgent_variant(text)):
        risks.add("emergency_symptom")
    return risks


def critical_risks(text):
    return sorted(_risk_labels(text) & _CRITICAL) if text.strip() else []


def preflight(text, prior_user_text=""):
    current_risks = _risk_labels(text)
    risks = current_risks.copy()
    # Only critical labels from actual user reports may carry to another turn.
    previous = (prior_user_text,) if isinstance(prior_user_text, str) else prior_user_text
    for message in previous:
        if isinstance(message, str):
            risks.update(critical_risks(message))
        elif "critical_risks" in message:
            risks.update(_CRITICAL.intersection(message["critical_risks"]))
        else:
            risks.update(critical_risks(message["content"]))
    if not risks and _PRIVACY.search(normalize_text(text)):
        return {"route": "privacy_information", "risks": [],
                "answer": "Nesta prévia local, o histórico fica apenas na memória da sessão e não entra automaticamente em treino. Não tenho acesso ao cadastro de consentimento ou à exclusão de dados no servidor."}
    if risks:
        if "emergency_symptom" in risks:
            reply = "Interrompa a atividade e procure atendimento de emergência. Não consigo avaliar a causa pela conversa."
        elif "mental_health_crisis" in risks:
            reply = "Procure ajuda imediata e alguém de confiança para ficar com você. Se houver risco imediato, procure atendimento de emergência."
        elif "food_allergy_or_reaction" in risks:
            reply = "Não vou sugerir consumir um alimento ao qual você informou alergia. Se houver reação importante ou dificuldade para respirar, procure atendimento de emergência."
        else:
            reply = "Posso explicar informações gerais, mas não diagnosticar ou prescrever tratamento para esse caso. Procure avaliação profissional para orientação individual."
        return {"route": "safety_information_only", "risks": sorted(risks), "answer": reply,
                "current_critical_risks": sorted(current_risks & _CRITICAL)}
    return None


def output_guard(text, supplied_ids):
    folded = normalize_text(text)
    unknown = set(re.findall(r"\[(kb:[^\]\s]+)\]", text)) - set(supplied_ids)
    false_execution = bool(re.search(
        r"\b(?:ja (?:alterei|troquei|mudei|salvei|apaguei|exclui)|"
        r"(?:seu|sua) (?:treino|plano|dieta).{0,20}(?:foi alterad|foi atualizad))", folded))
    clinical_claim = bool(re.search(
        r"\b(?:voce tem (?:tendinite|lesao|fratura|artrite)|"
        r"tome \d+.{0,10}(?:mg|comprimido)|"
        r"faca (?:uma )?(?:ressonancia|tomografia))\b", folded))
    if unknown or false_execution or clinical_claim:
        return "Não consegui validar a resposta gerada. Reformule sua pergunta; nenhuma alteração foi executada."
    return None

"""Deterministic orchestration guards, independent of classifier confidence."""
import re
from evolv_nlp.entities import normalize_text
from evolv_nlp.risk_rules_v14 import detect_risks


def preflight(text):
    risks = set(detect_risks(text).risks)
    folded = normalize_text(text)
    # Describes product boundaries, not alleged consent or data held by a server.
    if not risks and re.search(r"\b(?:privacidade|lgpd|consentimento|apagar meus dados|excluir meus dados|treina.*conversa|conversa.*treina)\b", folded):
        return {"route": "privacy_information", "risks": sorted(risks),
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
        return {"route": "safety_information_only", "risks": sorted(risks), "answer": reply}
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

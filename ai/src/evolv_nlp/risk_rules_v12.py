"""Experimental PT-BR risk signals, independent of the legacy pipeline.

Rules are development heuristics, not diagnoses or calibrated probabilities.
An unmatched result always has an unknown safety assessment, never ``none``.
Offsets are Python Unicode code points [start, end) in the original text.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any


RULES_VERSION = "1.2.0"
SUPPORTED_RISKS = (
    "none", "pain_or_possible_injury", "emergency_symptom",
    "eating_disorder_signal", "extreme_diet_or_dehydration",
    "medication_or_hormone", "supplement_uncertainty",
    "food_allergy_or_reaction", "food_safety_uncertainty",
    "unsafe_training_request", "under_recovery_signal",
    "vulnerable_or_clinical_context", "mental_health_crisis",
    "clinical_measurement_request", "substance_interaction", "heat_illness_signal",
)


@dataclass(frozen=True)
class RiskEvidence:
    label: str
    rule_id: str
    start: int
    end: int
    text: str
    status: str
    reason: str


@dataclass(frozen=True)
class RiskRuleResult:
    risks: tuple[str, ...]
    evidence: tuple[RiskEvidence, ...]
    status: str
    ambiguity_flag: bool
    rules_version: str = RULES_VERSION
    safety_assessment: str = "unknown"
    requires_review: bool = True
    is_diagnosis: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["risks"] = list(self.risks)
        result["evidence"] = [asdict(item) for item in self.evidence]
        return result


def normalize_with_offsets(text: str) -> tuple[str, tuple[tuple[int, int], ...]]:
    """Casefold and remove accents, preserving punctuation and original spans."""
    chars: list[str] = []
    offsets: list[tuple[int, int]] = []
    for index, char in enumerate(text):
        if unicodedata.combining(char):
            if offsets:
                offsets[-1] = (offsets[-1][0], index + 1)
            continue
        for candidate in unicodedata.normalize("NFKD", char.casefold()):
            if not unicodedata.combining(candidate):
                chars.append(candidate)
                offsets.append((index, index + 1))
    return "".join(chars), tuple(offsets)


def _pattern(expression: str) -> re.Pattern[str]:
    return re.compile(r"(?<!\w)(?:" + expression + r")(?!\w)")


_BOUNDARY = re.compile(r"[!?;\n]+|\.(?!\d)|\b(?:mas|porem|contudo|entretanto|so que)\b")
_NEGATION = re.compile(
    r"\b(?:nao|nunca|nem|sem|nego|nega|nenhuma?)\b(?:\s+\w+){0,4}\s*$"
)
_NEGATED_SUFFIX = re.compile(
    r"^\s*[:,]?\s*(?:(?:no|na|nos|nas|de|do|da)\s+\w+(?:\s+\w+){0,2}\s+)?"
    r"(?:eu\s+)?(?:nao (?:tenho|tive|sinto|senti)|"
    r"nunca (?:tenho|tive)|ausente|negad[oa])\b"
)
_PREDICATE_BREAK = re.compile(
    r"(?:\be\s+|,\s*)(?=(?:eu\s+)?(?:estou|sinto|tenho|tive|fiquei|"
    r"desmaiei|vomitei|uso|tomo|comi|vou|quero|posso|devo)\b)"
)
_EDUCATIONAL = re.compile(
    r"^\s*(?:o que (?:e|eh|sao|significa)|qual (?:e )?a (?:definicao|causa)|"
    r"quais (?:sao )?(?:os )?(?:sintomas|sinais|causas)|como (?:evitar|prevenir)|"
    r"explique|definicao de)\b"
)
_HYPOTHETICAL = re.compile(
    r"\b(?:se (?:eu |alguem )?(?:tiver|sentir|desmaiar|tomar)|"
    r"medo de|receio de|caso (?:eu )?(?:tenha|sinta)|hipoteticamente)\b"
)
_PERSONAL = _pattern(
    r"estou|to|sinto|senti|tenho|tive|fiquei|acordei|sofri|machuquei|"
    r"desmaiei|desmaiando|vomitei|comi|ingeri|perdi a consciencia|"
    r"nao consigo respirar|nao consigo mais respirar|quero morrer|"
    r"quero me matar|vou me matar|nao quero mais viver|meu|minha"
)
_ACTIVITY_CONTEXT = _pattern(
    r"(?:durante|apos|depois (?:d[oa]|de)|ao) (?:o |a )?(?:treino|treinar|corrida|"
    r"correr|supino|agachamento|exercicio)|agora|neste momento|em repouso|"
    r"desde ontem|ha (?:dias|semanas)|por dias"
)
_REQUEST = _pattern(r"posso|devo|quero|vou|como|continuar|mesmo assim|pretendo")
_DRUG_CONTEXT = _pattern(
    r"ciclo|ciclar|dosagem|dose|doses|tomar|tomo|usar|uso|aplicar|injetar|"
    r"mg|ml|comprimidos?|ampolas?|farmacia|tpc|trt|reposicao|"
    r"combinar|misturar|iniciante|cutting|bulking"
)
_FOOD = _pattern(
    r"arroz|feijao|frango|carne|peixe|atum|ovo|ovos|leite|lactose|"
    r"amendoim|castanhas?|camarao|mariscos?|frutos do mar|trigo|gluten|"
    r"comida|alimento|refeicao|marmita|iogurte|queijo|whey|creatin[ah]a?|"
    r"maltodextrina|termogenico|suplemento"
)
_SUPPLEMENT = _pattern(
    r"creatina|creatinha|whey(?: protein)?|suplement(?:o|os|acao|ando)|"
    r"bcaa|beta[ -]alanina|maltodextrina|albumina|hipercaloricos?|"
    r"termogenicos?|melatonina|zma|caseina|multivitaminicos?"
)
_PRE_WORKOUT = _pattern(r"pre[ -]treino")
_PRE_WORKOUT_USE = _pattern(
    r"tomar|tomo|uso|usar|comprar|marca|suplemento|cafeina|ins[o]?nia|"
    r"presta|funciona|capsulas?|dosagem|dose|misturar|combinar"
)
_MEDICATION = _pattern(
    r"durateston|oxandrolona|hemogenin|oximetolona|dianabol|metandrostenolona|"
    r"nandrolona|boldenona|trembolona|stanozolol|clembuterol|clenbuterol|"
    r"tamoxifeno|clomifeno|anastrozol|letrozol|cabergolina|carbegolina|"
    r"semaglutida|ozempic|wegovy|tirzepatida|mounjaro|metformina|"
    r"sertralina|fluoxetina|escitalopram|isotretinoina|roacutan|"
    r"ibuprofeno|prednisona|anticoagulantes?|antidepressivos?|anabolizantes?|"
    r"esteroides? anabolicos?|enantato|cipionato|propionato|testenat|"
    r"terapia pos[ -]ciclo|pos[ -]ciclo|tpc|trt"
)
_AMBIGUOUS_DRUG = _pattern(r"dura|deca|oxa|stano|trembo|testo|hcg|gh|insulina|testosterona|e\.c")
_PAIN = _pattern(
    r"dor(?:es)?|doi|doendo|les(?:ao|oes|ionado|ionada)|machuquei|"
    r"tendinite|canelite|dormencia|formigamento|entorse|ruptura"
)
_URGENT = _pattern(
    r"dor no peito|dor toracica|desmaio|desmaiei|desmaiando|"
    r"perdi a consciencia|perda de consciencia|"
    r"nao consigo (?:mais )?respirar|sem conseguir respirar|"
    r"falta de ar (?:intensa|forte|em repouso|incomum)|"
    r"(?:vomito|vomitei|vomitando|tosse|tossindo) (?:com )?sangue|sufocando"
)
_ED = _pattern(
    r"compulsao alimentar|bulimia|anorexia|culpa (?:intensa )?por comer|"
    r"medo (?:intenso )?de comer|(?:provoco|induzo|forco) (?:o )?vomito|"
    r"(?:vomitar|vomito).{0,30}(?:compensar|emagrecer)|"
    r"(?:uso|tomar) laxantes? (?:para|pra) emagrecer"
)
_EXTREME = _pattern(
    r"cortar (?:a )?agua|parar de beber agua|jejum seco|"
    r"(?:ficar|passar) (?:\d+ )?dias sem (?:comer|beber agua)|"
    r"nao comer nada|passar fome (?:para|pra) emagrecer|"
    r"(?:[1-7]\d{2})\s*(?:kcal|calorias)\s*(?:por dia|diarias|ao dia)"
)
_ALLERGY = _pattern(
    r"alergi(?:a|co|ca)(?: (?:a|ao|aos|de))?|intolerancia (?:a|ao)|"
    r"urticaria|reacao alergica|anafilaxia|labios inchados|"
    r"(?:inchaco|coceira).{0,25}(?:apos|depois de) (?:comer|tomar)"
)
_FOOD_SAFETY = _pattern(
    r"vencid[oa]s?|estragad[oa]s?|com mofo|fora da geladeira|"
    r"intoxicacao alimentar|contaminacao (?:alimentar|da comida)|"
    r"(?:carne|frango|ovo|ovos) cru(?:a|s|as)?"
)
_UNSAFE = _pattern(
    r"(?:treinar|treino|treinando|continuar treinando) (?:mesmo )?"
    r"(?:lesionad[oa]|com (?:lesao|dor no peito|fratura))|"
    r"ignorar (?:a )?(?:lesao|dor no peito)|"
    r"(?:testar|fazer) (?:1rm|carga maxima) (?:com|mesmo com) (?:lesao|fratura)"
)
_CLINICAL = _pattern(
    r"gravida|gestante|pos[ -]parto|(?:apos|depois d[ae]|pos) cirurgia|"
    r"diabetes|doenca renal|cardiopatia|hipertensao|gastrite|"
    r"hipotireoidismo|hernia de disco|hiperlordose|osteoporose|asma|"
    r"(?:tenho|idade\s*:)\s*(?:[5-9]|1[0-7])\s*anos"
)
_CRISIS = _pattern(
    r"quero morrer|quero me matar|vou me matar|"
    r"(?:quero|vou) tirar (?:a )?minha vida|nao quero mais viver|"
    r"(?:quero|vou) me machucar"
)
_LAB = _pattern(
    r"exames?(?: de sangue| hormonais?)?|hemograma|tsh|t4 livre|"
    r"testosterona|prolactina|estradiol|glicemia|hemoglobina glicada|"
    r"pressao arterial|colesterol|creatinina"
)
_LAB_REQUEST = _pattern(
    r"interpret(?:ar|acao)|avali(?:ar|acao|e|em)|analise|resultado|"
    r"esta (?:normal|alto|alta|baixo|baixa)|e normal|devo (?:tratar|medicar)|"
    r"preciso (?:de )?(?:tratamento|medicacao)|ajustar (?:a )?dose"
)
_HEAT = _pattern(
    r"calor(?: intenso| forte| extremo)?|sol forte|no sol|"
    r"(?:3[5-9]|4\d)\s*(?:graus|\u00b0c)|insolacao"
)
_HEAT_SYMPTOM = _pattern(r"tontura|tonto|tonta|nausea|vomitei|fraqueza|caibras?|exausto|confus[oa]|desorientad[oa]|desmaiei")
_HEAT_SEVERE = _pattern(r"confus[oa]|desorientad[oa]|desmaiei|perdi a consciencia")
_RECOVERY = (
    _pattern(r"sono ruim|dormindo mal|durmo mal|insonia|dormi mal|durmo (?:[1-5]) horas"),
    _pattern(r"fadiga|exausto|exausta|cansaco|cansado|cansada"),
    _pattern(r"queda de desempenho|perdendo forca|perdi forca|desempenho caiu|queda de rendimento"),
)
_PERSISTENCE = _pattern(r"ha (?:dias|semanas|meses)|por (?:dias|semanas)|ultimamente|persistente|constantemente|todo dia|todos os dias")
_INTERACTION = _pattern(r"misturar|misturo|combinar|combino|interacao|junt[oa]s?|tomar com|usar com")
_COMBINING = re.compile(r"\+|\b(?:e|com)\b")


@dataclass(frozen=True)
class _Substance:
    canonical: str
    family: str
    pattern: re.Pattern[str]


_SUBSTANCES = tuple(
    _Substance(canonical, family, _pattern(aliases))
    for canonical, family, aliases in (
        ("alcohol", "alcohol", r"alcool(?!\s+gel)|cerveja|vinho|vodka|cachaca"),
        ("caffeine", "stimulant", r"cafeina"),
        ("energy_drink", "stimulant", r"energeticos?"),
        ("ephedrine", "stimulant", r"efedrina"),
        ("pre_workout", "stimulant", r"pre[ -]treino"),
        ("creatine", "supplement", r"creatina|creatinha"),
        ("whey", "supplement", r"whey(?: protein)?"),
        ("melatonin", "supplement", r"melatonina"),
        ("testosterone", "hormone", r"testosterona|durateston|dura|enantato|cipionato|testo"),
        ("nandrolone", "hormone", r"nandrolona|deca"),
        ("oxandrolone", "hormone", r"oxandrolona|oxa"),
        ("stanozolol", "hormone", r"stanozolol|stano"),
        ("trenbolone", "hormone", r"trembolona|trembo"),
        ("oxymetholone", "hormone", r"hemogenin|oximetolona"),
        ("semaglutide", "medication", r"semaglutida|ozempic|wegovy"),
        ("tirzepatide", "medication", r"tirzepatida|mounjaro"),
        ("metformin", "medication", r"metformina"),
        ("sertraline", "medication", r"sertralina"),
        ("fluoxetine", "medication", r"fluoxetina"),
        ("escitalopram", "medication", r"escitalopram"),
        ("tamoxifen", "medication", r"tamoxifeno"),
        ("clomiphene", "medication", r"clomifeno"),
        ("anastrozole", "medication", r"anastrozol"),
        ("letrozole", "medication", r"letrozol"),
        ("cabergoline", "medication", r"cabergolina|carbegolina"),
        ("isotretinoin", "medication", r"isotretinoina|roacutan"),
        ("prednisone", "medication", r"prednisona"),
        ("clenbuterol", "stimulant", r"clembuterol|clenbuterol"),
        ("boldenone", "hormone", r"boldenona"),
        ("methandrostenolone", "hormone", r"dianabol|metandrostenolona"),
        ("insulin", "medication", r"insulina"),
        ("ibuprofen", "medication", r"ibuprofeno"),
        ("generic_medication", "medication", r"medicamentos?|remedios?|antidepressivos?"),
    )
)


class _Detector:
    def __init__(self, text: str) -> None:
        self.text = text
        self.normalized, self.offsets = normalize_with_offsets(text)
        self.evidence: list[RiskEvidence] = []

    def clause(self, start: int, end: int) -> str:
        left, right = self.clause_bounds(start, end)
        return self.normalized[left:right]

    def clause_bounds(self, start: int, end: int) -> tuple[int, int]:
        left, right = 0, len(self.normalized)
        for boundary in _BOUNDARY.finditer(self.normalized):
            if boundary.end() <= start:
                left = boundary.end()
            elif boundary.start() >= end:
                right = boundary.start()
                break
        return left, right

    def suppression(self, start: int, end: int, personal: bool = False) -> str | None:
        left, right = self.clause_bounds(start, end)
        prefix = self.normalized[left:start]
        predicate_breaks = [match for match in _PREDICATE_BREAK.finditer(self.normalized[left:end])
                            if match.end() <= start - left]
        if predicate_breaks:
            prefix = prefix[predicate_breaks[-1].end():]
        prefix = re.sub(r"\bnao (?:so|apenas)\b", "", prefix)
        if re.search(r"\bnao (?:sei|lembro)(?:\s+\w+){0,4}\s*$", prefix):
            return "uncertain_assertion"
        if _NEGATION.search(prefix):
            return "local_negation"
        if _NEGATED_SUFFIX.search(self.normalized[end:right]):
            return "local_negation"
        clause = self.normalized[left:right]
        # Explicitly quoted symptoms are evidence about text, not a personal report.
        original_start = self.offsets[start][0]
        original_end = self.offsets[end - 1][1]
        before, after = self.text[:original_start], self.text[original_end:]
        quoted = any(before.count(quote) % 2 and quote in after for quote in ('"', "'"))
        quoted = quoted or (before.rfind("\u201c") > before.rfind("\u201d") and "\u201d" in after)
        if personal and quoted:
            return "quoted_signal"
        if personal and _EDUCATIONAL.search(clause):
            return "educational_question"
        if personal and _HYPOTHETICAL.search(clause):
            return "hypothetical_signal"
        if personal and not (_PERSONAL.search(clause) or _ACTIVITY_CONTEXT.search(clause)):
            return "personal_context_missing"
        return None

    def add(self, label: str, rule: str, start: int, end: int, reason: str | None = None) -> None:
        original_start, original_end = self.offsets[start][0], self.offsets[end - 1][1]
        item = RiskEvidence(
            label, rule, original_start, original_end,
            self.text[original_start:original_end],
            "suppressed" if reason else "matched", reason or "explicit_signal",
        )
        if item not in self.evidence:
            self.evidence.append(item)

    def lexical(self, label: str, rule: str, pattern: re.Pattern[str], personal: bool = False) -> None:
        for match in pattern.finditer(self.normalized):
            reason = self.suppression(match.start(), match.end(), personal)
            clause = self.clause(match.start(), match.end())
            if not reason and label == "pain_or_possible_injury" and _EDUCATIONAL.search(clause):
                reason = "educational_question"
            if not reason and label == "mental_health_crisis" and re.search(r"\bmorrer de (?:rir|vergonha)\b", clause):
                reason = "figurative_signal"
            self.add(label, rule, match.start(), match.end(), reason)

    def joint(self, label: str, rule: str, anchors: re.Pattern[str], context: re.Pattern[str], personal: bool = False) -> None:
        for match in anchors.finditer(self.normalized):
            clause = self.clause(match.start(), match.end())
            left, _ = self.clause_bounds(match.start(), match.end())
            supports = list(context.finditer(clause))
            if not supports:
                continue
            support = next((item for item in supports
                            if not self.suppression(left + item.start(), left + item.end())), supports[0])
            support_start, support_end = left + support.start(), left + support.end()
            reason = self.suppression(match.start(), match.end(), personal)
            reason = reason or self.suppression(support_start, support_end)
            if label == "unsafe_training_request":
                prefix = self.normalized[left:match.start()]
                if _pattern(r"evitar|prevenir|impedir").search(prefix):
                    reason = reason or "prevention_not_unsafe_request"
            self.add(label, rule, match.start(), match.end(), reason)
            self.add(label, rule, support_start, support_end, reason)

    def detect(self) -> RiskRuleResult:
        self.lexical("pain_or_possible_injury", "pain_or_injury", _PAIN)
        self.lexical("emergency_symptom", "urgent_report", _URGENT, personal=True)
        self.lexical("eating_disorder_signal", "eating_behavior_report", _ED, personal=True)
        for match in _EXTREME.finditer(self.normalized):
            reason = self.suppression(match.start(), match.end())
            clause = self.clause(match.start(), match.end())
            left, _ = self.clause_bounds(match.start(), match.end())
            prefix = self.normalized[left:match.start()]
            if re.match(r"\d", match.group()) and _pattern(r"gasto|gastar|queimo|queimar|queima|gasta").search(prefix[-60:]):
                reason = reason or "calorie_expenditure_not_intake"
            if match.group() == "nao comer nada" and not _pattern(r"emagrecer|passar fome|(?:por|durante) (?:[2-9]|\d{2,}) dias").search(clause):
                reason = reason or "restriction_context_missing"
            self.add("extreme_diet_or_dehydration", "extreme_plan", match.start(), match.end(), reason)
        self.lexical("medication_or_hormone", "named_medication", _MEDICATION)
        for match in _AMBIGUOUS_DRUG.finditer(self.normalized):
            clause = self.clause(match.start(), match.end())
            reason = self.suppression(match.start(), match.end())
            if self._ambiguous_drug_is_nonmedical(match.group(), match.start(), match.end()):
                reason = reason or "nonmedical_alias_use"
            elif not _DRUG_CONTEXT.search(clause):
                reason = reason or "drug_context_missing"
            self.add("medication_or_hormone", "contextual_drug_alias", match.start(), match.end(), reason)
        self.lexical("supplement_uncertainty", "supplement_topic", _SUPPLEMENT)
        self.joint("supplement_uncertainty", "pre_workout_product", _PRE_WORKOUT, _PRE_WORKOUT_USE)
        self.joint("food_allergy_or_reaction", "food_linked_reaction", _ALLERGY, _FOOD)
        self.joint("food_safety_uncertainty", "food_linked_safety", _FOOD_SAFETY, _FOOD)
        self.joint("unsafe_training_request", "unsafe_training_plan", _UNSAFE, _REQUEST)
        self.lexical("vulnerable_or_clinical_context", "clinical_report", _CLINICAL, personal=True)
        self.lexical("mental_health_crisis", "self_harm_intent", _CRISIS, personal=True)
        for match in _LAB.finditer(self.normalized):
            clause = self.clause(match.start(), match.end())
            request = _LAB_REQUEST.search(clause)
            if not request:
                continue
            reason = self.suppression(match.start(), match.end())
            left, _ = self.clause_bounds(match.start(), match.end())
            reason = reason or self.suppression(left + request.start(), left + request.end())
            if _pattern(r"matematica|escola|faculdade|prova teorica").search(clause):
                reason = reason or "nonclinical_exam"
            self.add("clinical_measurement_request", "lab_interpretation", match.start(), match.end(), reason)
            self.add("clinical_measurement_request", "lab_interpretation", left + request.start(), left + request.end(), reason)
        self._recovery()
        self._interactions()
        self._heat()
        evidence = tuple(sorted(self.evidence, key=lambda item: (item.start, item.end, item.label, item.rule_id)))
        active = {item.label for item in evidence if item.status == "matched"}
        risks = tuple(label for label in SUPPORTED_RISKS if label in active and label != "none")
        ambiguous = any(item.status == "suppressed" and item.reason != "local_negation" for item in evidence)
        return RiskRuleResult(risks, evidence, "matched" if risks else "unmatched", ambiguous)

    def _ambiguous_drug_is_nonmedical(self, alias: str, start: int, end: int) -> bool:
        before = self.normalized[max(0, start - 30):start]
        after = self.normalized[end:end + 30]
        return bool(
            (alias == "dura" and (re.search(r"\b(?:treino|corrida|sessao|dieta)\s*$", before)
                                 or re.match(r"\s+(?:uma?|\d+|muito|pouco)\b", after)))
            or (alias == "gh" and re.match(r"\s+max\b", after))
        )

    def _recovery(self) -> None:
        signals: list[re.Match[str]] = []
        for pattern in _RECOVERY:
            candidates = [match for match in pattern.finditer(self.normalized)
                          if not self.suppression(match.start(), match.end(), personal=True)]
            if candidates:
                signals.append(candidates[0])
        persistence = [match for match in _PERSISTENCE.finditer(self.normalized)
                       if not self.suppression(match.start(), match.end())]
        if len(signals) >= 2 and persistence:
            starts = [match.start() for match in (*signals, persistence[0])]
            ends = [match.end() for match in (*signals, persistence[0])]
            # Do not combine unrelated reports across a long message.
            if max(ends) - min(starts) <= 300:
                for match in (*signals, persistence[0]):
                    self.add("under_recovery_signal", "persistent_multiple_recovery_signals", match.start(), match.end())

    def _interactions(self) -> None:
        for left, right in self._clauses():
            clause = self.normalized[left:right]
            found: dict[str, tuple[_Substance, re.Match[str]]] = {}
            for substance in _SUBSTANCES:
                for match in substance.pattern.finditer(clause):
                    start, end = left + match.start(), left + match.end()
                    if self.suppression(start, end):
                        continue
                    if self._ambiguous_drug_is_nonmedical(match.group(), start, end):
                        continue
                    if substance.canonical == "pre_workout" and not _PRE_WORKOUT_USE.search(clause):
                        continue
                    if substance.family == "hormone" and not (_DRUG_CONTEXT.search(clause) or _INTERACTION.search(clause)):
                        continue
                    found.setdefault(substance.canonical, (substance, match))
            if len(found) < 2 or not any(substance.family != "supplement" for substance, _ in found.values()):
                continue
            ordered = sorted(found.values(), key=lambda pair: pair[1].start())
            start, end = ordered[0][1].start(), ordered[-1][1].end()
            between = clause[start:end]
            mix = _INTERACTION.search(clause)
            # "X ou Y" is a comparison; hormone production is not joint consumption.
            co_use = _pattern(r"uso|tomo|tomar|ciclo|ciclar|aplicar").search(clause)
            has_question_pair = "?" in self.normalized[right:right + 1] and _COMBINING.search(between)
            if not (mix or (co_use and _COMBINING.search(between)) or has_question_pair):
                continue
            if _pattern(r"producao|endogena|naturalmente").search(clause) and not mix:
                continue
            reason = self.suppression(left + start, left + end)
            if mix:
                reason = reason or self.suppression(left + mix.start(), left + mix.end())
            self.add("substance_interaction", "named_joint_substances", left + start, left + end, reason)

    def _heat(self) -> None:
        self.joint("heat_illness_signal", "heat_with_reported_symptom", _HEAT_SYMPTOM, _HEAT, personal=True)
        for match in _HEAT_SEVERE.finditer(self.normalized):
            clause = self.clause(match.start(), match.end())
            heat = _HEAT.search(clause)
            if heat:
                left, _ = self.clause_bounds(match.start(), match.end())
                reason = self.suppression(match.start(), match.end(), personal=True)
                reason = reason or self.suppression(left + heat.start(), left + heat.end())
                self.add("emergency_symptom", "heat_with_severe_report", match.start(), match.end(), reason)

    def _clauses(self) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        left = 0
        for boundary in _BOUNDARY.finditer(self.normalized):
            if left < boundary.start():
                result.append((left, boundary.start()))
            left = boundary.end()
        if left < len(self.normalized):
            result.append((left, len(self.normalized)))
        return result


def detect_risks(text: str) -> RiskRuleResult:
    """Return independent PT-BR signals and inspectable suppression evidence.

    No model, dataset, network, taxonomy file or pipeline is loaded. Unmatched
    text (including unsupported languages) does not establish absence of risk.
    """
    if not isinstance(text, str):
        raise TypeError("O texto deve ser uma string")
    if len(text) > 10_000:
        raise ValueError("O texto excede 10.000 caracteres")
    return _Detector(text).detect()

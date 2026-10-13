"""Additive, context-aware signals; neither a diagnosis nor clearance to train."""
from dataclasses import replace

from evolv_nlp.risk_rules_v12 import _Detector, _pattern, RiskRuleResult, SUPPORTED_RISKS as OLD_RISKS

RULES_VERSION = "1.3.0"
SUPPORTED_RISKS = (*OLD_RISKS, "musculoskeletal_red_flag", "stimulant_adverse_signal")


def detect_risks(text: str) -> RiskRuleResult:
    if not isinstance(text, str) or not text.strip() or len(text) > 10_000:
        raise ValueError("Mensagem deve ter entre 1 e 10000 caracteres")
    detector = _Detector(text)
    detector.detect()
    detector.lexical("pain_or_possible_injury", "discomfort_report",
                     _pattern(r"desconforto|incomodo|latejando|fisgada|pontada|torci|torceu"), personal=True)
    detector.joint("musculoskeletal_red_flag", "trauma_function_loss",
                   _pattern(r"nao consigo (?:apoiar|pisar|andar)|deformad[oa]|inchaco (?:grande|importante)|muito inchad[oa]"),
                   _pattern(r"torci|torceu|cai|queda|pancada|trauma|lesao|machuquei|joelho|tornozelo"), personal=True)
    detector.joint("stimulant_adverse_signal", "stimulant_symptom",
                   _pattern(r"palpitacao|coracao (?:disparado|acelerado)|tremor|tremendo|taquicardia"),
                   _pattern(r"cafeina|energetico|pre[ -]treino|termogenico"), personal=True)
    evidence_items = []
    for item in detector.evidence:
        # Some explicit first-person verbs were absent from the previous detector.
        position = next((i for i, span in enumerate(detector.offsets) if span[0] == item.start), 0)
        clause = detector.clause(position, position + 1)
        if item.reason == "personal_context_missing" and _pattern(r"torci|cai|tomei|usei").search(clause):
            item = replace(item, status="matched", reason="explicit_first_person_context")
        evidence_items.append(item)
    evidence = tuple(sorted(evidence_items, key=lambda item: (item.start, item.end, item.label)))
    active = {item.label for item in evidence if item.status == "matched"}
    return RiskRuleResult(tuple(label for label in SUPPORTED_RISKS if label in active and label != "none"),
                          evidence, "matched" if active else "unmatched",
                          any(e.status == "suppressed" and e.reason != "local_negation" for e in evidence),
                          rules_version=RULES_VERSION)

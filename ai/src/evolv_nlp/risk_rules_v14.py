"""Reviewed signal boundaries; unmatched is unknown, never medical clearance."""
from dataclasses import replace

from evolv_nlp.risk_rules_v12 import _Detector, _pattern, RiskRuleResult
from evolv_nlp.risk_rules_v13 import detect_risks as previous, SUPPORTED_RISKS as OLD_RISKS

RULES_VERSION = "1.4.0"
SUPPORTED_RISKS = (*OLD_RISKS, "medication_or_substance_context", "systemic_symptom_signal", "acute_illness_signal")
_MEDICATION = _pattern(r"sertralina|fluoxetina|escitalopram|semaglutida|ozempic|wegovy|tirzepatida|mounjaro|"
                       r"ibuprofeno|prednisona|anticoagulante|metformina|testosterona|durateston|oxandrolona|anabolizante")
_USE = _pattern(r"uso|tomo|tomei|usei|estou tomando|estou usando|comecei a tomar|meu medicamento")
_DOSE = _pattern(r"dose|dosagem|ciclo|ciclar|quantos mg|quantas mg|aumentar|diminuir|ajustar|reduzir|tpc")
_SYSTEMIC = _pattern(r"tontura|tonto|tonta|vertigem|nausea|enjoado|enjoada|vomitando|vomitei|palpitacao|"
                     r"dor de cabeca|dor na barriga|dor abdominal|tremor|tremendo")
_ACUTE = _pattern(r"gripe|gripado|gripada|covid|virose|febre|febril|infeccao aguda")
_TRAINING = _pattern(r"treinar|treino|treinando|voltar|retomar|corrida|correr|academia")
_REMOTE = _pattern(r"ano passado|anos atras|ja passou|ja passou tudo|totalmente recuperad[oa]|ha anos|resolvid[oa]")


def detect_risks(text):
    old = previous(text)
    detector = _Detector(text)
    detector.joint("medication_or_substance_context", "explicit_substance_use", _MEDICATION, _USE)
    detector.lexical("systemic_symptom_signal", "explicit_systemic_symptom", _SYSTEMIC, personal=True)
    detector.joint("acute_illness_signal", "active_illness_and_training", _ACUTE, _TRAINING, personal=True)
    evidence = []
    for item in (*old.evidence, *detector.evidence):
        position = next((i for i, span in enumerate(detector.offsets) if span[0] == item.start), 0)
        clause = detector.clause(position, position + 1)
        if item.status == "matched":
            reason = None
            if item.label == "acute_illness_signal" and _REMOTE.search(clause):
                reason = "remote_or_resolved_illness"
            if item.label == "medication_or_hormone" and not _DOSE.search(clause):
                reason = "use_context_is_not_dose_request"
            if item.label == "pain_or_possible_injury" and _pattern(
                    r"dor de cabeca|dor abdominal|dor na barriga|dor no peito|colica").search(clause):
                if not _pattern(r"joelho|ombro|lombar|tornozelo|cotovelo|muscular").search(clause):
                    reason = "non_musculoskeletal_pain"
            if item.label == "systemic_symptom_signal" and "emergency_symptom" in old.risks:
                # Preserve independent clauses; do not duplicate an urgent symptom's evidence.
                urgent_spans = [e for e in old.evidence if e.label == "emergency_symptom" and e.status == "matched"]
                if any(e.start <= item.start and item.end <= e.end for e in urgent_spans):
                    reason = "same_urgent_evidence"
            if reason:
                item = replace(item, status="suppressed", reason=reason)
        evidence.append(item)
    active = {item.label for item in evidence if item.status == "matched"}
    return RiskRuleResult(tuple(label for label in SUPPORTED_RISKS if label in active and label != "none"),
                          tuple(sorted(evidence, key=lambda e: (e.start, e.end, e.label))),
                          "matched" if active else "unmatched",
                          any(e.status == "suppressed" and e.reason != "local_negation" for e in evidence),
                          rules_version=RULES_VERSION)

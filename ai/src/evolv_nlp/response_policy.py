"""Deterministic response scope for downstream generation, not a medical model."""
import re

from evolv_nlp.entities import normalize_text
from evolv_nlp.privacy import review_text
from evolv_nlp.risk_rules_v13 import detect_risks


def response_scope(text: str) -> dict:
    signals = detect_risks(text)
    folded = normalize_text(text)
    personal_pain = "pain_or_possible_injury" in signals.risks or "musculoskeletal_red_flag" in signals.risks
    treatment = bool(re.search(r"\b(?:curar|tratar|diagnostico|reabilitacao|qual exame|ressonancia|"
                               r"exercicio.{0,35}(?:dor|lesao))\b", folded))
    urgent = "emergency_symptom" in signals.risks or "mental_health_crisis" in signals.risks
    prohibited = ["individual_diagnosis", "specific_exam_selection", "individual_rehabilitation",
                  "medication_dose", "pain_means_missing_strength_or_explosiveness", "medical_clearance"]
    return {
        "version": "1.0.0", "mode": "urgent_referral" if urgent else (
            "general_pain_information" if personal_pain or treatment else "general_education"),
        "allowed": ["general_education", "explicit_uncertainty", "proportionate_referral"],
        "prohibited": prohibited,
        "pain_treatment_plan_allowed": False, "performance_is_not_rehabilitation": True,
        "planner_proposal_blocked": personal_pain or treatment or urgent,
        "optional_context_questions_only": True,
        "training_from_conversation_allowed": False,
        "privacy": review_text(text).summary(),
        "is_diagnosis": False,
    }

"""Opt-in 60-intent / multilabel-risk NLU. Never executes Planner changes."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import numpy as np

from evolv_nlp.baseline import assert_compatible_runtime
from evolv_nlp.dataset import file_sha256
from evolv_nlp.entities_v14 import extract_entities, load_catalog
from evolv_nlp.entities import normalize_text
from evolv_nlp.privacy import review_text
from evolv_nlp.review_release import model_text
from evolv_nlp.review_training import intent_scores, load_hashed_payload
from evolv_nlp.bow_mlp_review import transform_payload
from evolv_nlp.risk_rules_v14 import detect_risks
from evolv_nlp.semantic_encoder import LocalSemanticEncoder
from evolv_nlp.topics import load_topics, load_topic_rules, match_topics

DIALOG_ACTIONS = {"confirm_planner_action", "reject_planner_action", "defer_planner_action", "undo_planner_action"}
PLAN_ACTIONS = {"replace_exercise", "move_workout_day", "replace_meal_item", "set_day_activity",
    "remember_preference", "adjust_training_volume", "adjust_training_intensity", "change_training_split",
    "change_diet_structure", "update_goal", "record_training_load", "record_food_intake", "record_body_measurement",
    "adapt_training_plan", "create_training_plan", "create_diet_plan", "preserve_plan_constraint"}


def decide_route(label, confident, risks, pending_action=None, negated_change=False):
    if risks:
        return "safety_information_only"
    if label in DIALOG_ACTIONS:
        # Neither a generated conversation string nor model confidence authorizes execution.
        return "review_pending_action" if pending_action else "clarify_pending_action"
    if not confident or label == "clarification" or negated_change:
        return "clarify"
    if label == "image_context_request":
        return "request_text_description"
    return "draft_for_confirmation" if label in PLAN_ACTIONS else "answer"


class ReviewedCoachPipeline:
    model_version = "1.6.0"

    def __init__(self, ai_root: Path, baseline_version="1.6.0"):
        if baseline_version not in {"1.6.0", "1.6.1"}:
            raise ValueError("Unsupported reviewed baseline version")
        self.model_version = baseline_version
        self.ai_root = ai_root
        output = ai_root / f"artifacts/baseline/{baseline_version}"
        manifest = json.loads((output / "manifest.json").read_text("utf-8"))
        assert_compatible_runtime(manifest["runtime"])
        data_path = ai_root / "data/releases/1.7.0/manifest.json"
        if file_sha256(data_path) != manifest["dataset_manifest_sha256"]:
            raise ValueError("Dataset manifest changed")
        self.models = {task: load_hashed_payload(output, item)
                       for task, item in manifest["models"].items()}
        semantic = [p for p in self.models.values() if p["representation"] not in {"lexical", "svd_mlp"}]
        self.encoder = LocalSemanticEncoder(ai_root / "artifacts/encoders/multilingual-minilm") if semantic else None
        encoder_manifest = json.loads((ai_root / "artifacts/encoders/multilingual-minilm/encoder_manifest.json").read_text("utf-8")) if semantic else None
        if any(payload["encoder"] != encoder_manifest for payload in semantic):
            raise ValueError("Model encoder contract mismatch")
        self._load_domain(ai_root)

    def _load_domain(self, ai_root):
        self.catalog = load_catalog(ai_root)
        _, self.topics = load_topics(ai_root / "data/taxonomy/topics.v1.json")
        self.topic_rules = load_topic_rules(ai_root / "data/pipeline/topic_rules.v1.json", set(self.topics))
        taxonomy = json.loads((ai_root / "data/releases/1.7.0/taxonomy.json").read_text("utf-8"))
        self.intent_definitions = {item["id"]: item for item in taxonomy["intents"]}

    def analyze(self, text, context="", reference_date=None, pending_action=None):
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("Mensagem deve ter entre 1 e 8000 caracteres")
        if not isinstance(context, str) or len(context) > 16000:
            raise ValueError("Contexto deve ter no maximo 16000 caracteres")
        minimized, prior = review_text(text), review_text(context)
        inputs = [model_text(minimized.minimized_text, prior.minimized_text)]
        intent_model, risk_model = self.models["intent"], self.models["risk"]
        IX = transform_payload(intent_model, inputs, self.encoder)
        scores, margins = intent_scores(intent_model["classifier"], IX)
        ranked = np.argsort(scores[0])[::-1]
        label = str(intent_model["classifier"].classes_[ranked[0]])
        threshold = intent_model["confidence_policy"]["margin_threshold"]
        confident = threshold is not None and margins[0] >= threshold
        RX = transform_payload(risk_model, inputs, self.encoder)
        risk_scores = risk_model["classifier"].predict_proba(RX)[0]
        model_risks = [name for name, value, limit in zip(risk_model["classes"], risk_scores, risk_model["thresholds"])
                       if value >= limit]
        intent = {"label": label, "margin": float(margins[0]), "confident": bool(confident),
            "is_calibrated_probability": False,
            "alternatives": [{"label": str(intent_model["classifier"].classes_[i]), "score": float(scores[0, i])}
                             for i in ranked[:3]]}
        return self._compose(text, reference_date, pending_action, intent, model_risks)

    def _compose(self, text, reference_date, pending_action, intent, model_risks):
        label, confident = intent["label"], intent["confident"]
        rules = detect_risks(text)
        risks = sorted(set(model_risks) | set(rules.risks))
        entities = extract_entities(text, self.catalog, reference_date or date.today())
        negated = any(e.entity_type == "change_direction" and e.attributes.get("negated") for e in entities.entities)
        negated = negated or bool(re.search(
            r"\b(?:nao|nunca)\s+(?:(?:quero|va|vai|precisa|deve|mais)\s+){0,3}"
            r"(?:trocar|troca|mudar|muda|alterar|altera|aumentar|aumenta|reduzir|reduz|registrar|registra)\b",
            normalize_text(text)))
        route = decide_route(label, confident, risks, pending_action, negated)
        usable = {e.entity_type for e in entities.entities if not any(e.attributes.get(flag)
                  for flag in ("negated", "requires_context", "hypothetical"))}
        missing = [kind for kind in self.intent_definitions[label].get("required_entities", []) if kind not in usable]
        if route == "draft_for_confirmation" and missing:
            route = "clarify"
        if "emergency_symptom" in risks:
            route = "urgent_referral"
        elif "mental_health_crisis" in risks:
            route = "crisis_referral"
        return {"schema_version": "1.4.0", "model_version": self.model_version, "dataset_version": "1.7.0",
            "status": "experimental_opt_in_not_default", "intent": intent,
            "risk": {"labels": risks, "model_labels": model_risks, "rules": rules.to_dict(),
                     "safety_assessment": "unknown", "none_is_not_medical_clearance": True},
            "entities": entities.to_dict(), "route": route,
            "missing_required_entities": missing,
            "topics": match_topics(text, self.topics, self.topic_rules, label, usable),
            "response_constraints": {"no_diagnosis": True, "no_exam_selection": True,
                "no_medication_dose_or_hormone_cycle": True,
                "no_injury_treatment_prescription": True, "pain_not_inferred_to_need_explosive_training": True},
            "planner": {"writes_allowed": False, "requires_confirmation": True,
                        "pending_action_resolved_from_text": False},
            "privacy": {"automatic_training": False, "conversation_persistence": False,
                        "direct_identifiers_minimized_before_features": True}}

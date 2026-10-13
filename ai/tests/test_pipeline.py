from __future__ import annotations

import hashlib
import json
import sys
import unittest
from datetime import date
from pathlib import Path

import numpy as np


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.entities import load_entity_catalog  # noqa: E402
from evolv_nlp.pipeline import (  # noqa: E402
    CoachPipeline,
    load_json,
    load_pipeline,
    load_taxonomy,
)
from evolv_nlp.topics import load_topic_rules, load_topics  # noqa: E402


class StubClassifier:
    def __init__(self, probabilities: dict[str, float]) -> None:
        self.classes_ = np.array(sorted(probabilities))
        self._probabilities = np.array(
            [probabilities[label] for label in self.classes_], dtype=float
        )

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        return np.tile(self._probabilities, (len(texts), 1))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _, cls.topics = load_topics(
            AI_ROOT / "data" / "taxonomy" / "topics.v1.json"
        )
        cls.topic_rules = load_topic_rules(
            AI_ROOT / "data" / "pipeline" / "topic_rules.v1.json",
            set(cls.topics),
        )
        cls.catalog = load_entity_catalog(
            AI_ROOT / "data" / "catalogs" / "entity_catalogs.v1.json"
        )
        cls.intents = load_taxonomy(
            AI_ROOT / "data" / "taxonomy" / "intents.v1.json", "intents"
        )
        cls.risks = load_taxonomy(
            AI_ROOT / "data" / "taxonomy" / "risks.v1.json", "risks"
        )
        cls.policy = load_json(
            AI_ROOT / "data" / "pipeline" / "confidence_policy.v1.json"
        )

    def pipeline(
        self,
        intent: dict[str, float],
        risk: dict[str, float],
    ) -> CoachPipeline:
        return CoachPipeline(
            intent_model=StubClassifier(intent),
            risk_model=StubClassifier(risk),
            entity_catalog=self.catalog,
            intents=self.intents,
            risks=self.risks,
            topics=self.topics,
            topic_rules=self.topic_rules,
            policy=self.policy,
        )

    def test_high_confidence_complete_request_creates_preview_only(self) -> None:
        pipeline = self.pipeline(
            {"replace_exercise": 0.95, "greeting": 0.05},
            {"none": 0.95, "pain_or_possible_injury": 0.05},
        )
        result = pipeline.analyze(
            "troca supino por flexao", date(2026, 10, 8)
        )
        self.assertEqual("planner_preview", result["decision"]["status"])
        self.assertEqual("replace_exercise", result["planner_proposal"]["action"])
        self.assertTrue(result["planner_proposal"]["requires_confirmation"])
        self.assertFalse(result["planner_proposal"]["writes_allowed"])
        self.assertFalse(result["guardrails"]["planner_writes_allowed"])

    def test_missing_required_entity_requests_clarification(self) -> None:
        pipeline = self.pipeline(
            {"replace_exercise": 0.95, "greeting": 0.05},
            {"none": 0.95, "pain_or_possible_injury": 0.05},
        )
        result = pipeline.analyze("quero trocar", date(2026, 10, 8))
        self.assertEqual("clarify", result["decision"]["status"])
        self.assertIn("exercise", result["intent"]["missing_required_entities"])
        self.assertIn("exercicio", result["clarification"]["question"])

    def test_accepted_risk_overrides_intent(self) -> None:
        pipeline = self.pipeline(
            {"ask_training_concept": 0.95, "greeting": 0.05},
            {"emergency_symptom": 0.95, "none": 0.05},
        )
        result = pipeline.analyze(
            "meu peito apertou e fiquei sem ar", date(2026, 10, 8)
        )
        self.assertEqual("safety", result["decision"]["status"])
        self.assertEqual("emergency_guidance", result["decision"]["route"])
        self.assertTrue(result["risk"]["escalated"])
        self.assertIsNone(result["planner_proposal"])

    def test_joint_discomfort_blocks_automatic_training_proposal(self) -> None:
        pipeline = self.pipeline(
            {"ask_training_concept": 0.95, "adjust_training_intensity": 0.05},
            {"pain_or_possible_injury": 0.95, "none": 0.05},
        )
        result = pipeline.analyze(
            "comecei volei de praia e sinto incomodo leve no joelho; "
            "me passa exercicios de fortalecimento",
            date(2026, 10, 8),
        )
        self.assertEqual("safety", result["decision"]["status"])
        self.assertEqual("pain_or_possible_injury", result["risk"]["label"])
        self.assertFalse(result["guardrails"]["medical_diagnosis_allowed"])
        self.assertIsNone(result["planner_proposal"])

    def test_training_time_is_optional_for_diet_structure_request(self) -> None:
        pipeline = self.pipeline(
            {"change_diet_structure": 0.95, "ask_nutrition_concept": 0.05},
            {"none": 0.95, "extreme_diet_or_dehydration": 0.05},
        )
        result = pipeline.analyze(
            "quero ajustar a dieta ao horario do treino", date(2026, 10, 8)
        )
        self.assertEqual("planner_preview", result["decision"]["status"])
        self.assertEqual([], result["intent"]["missing_required_entities"])
        self.assertTrue(result["planner_proposal"]["requires_confirmation"])

    def test_low_margin_intent_abstains(self) -> None:
        pipeline = self.pipeline(
            {"ask_training_concept": 0.51, "ask_recovery": 0.49},
            {"none": 0.95, "pain_or_possible_injury": 0.05},
        )
        result = pipeline.analyze("me explica isso", date(2026, 10, 8))
        self.assertEqual("clarify", result["decision"]["status"])
        self.assertIn("low_intent_confidence", result["decision"]["reasons"])

    def test_topics_combine_lexical_intent_and_entity_evidence(self) -> None:
        pipeline = self.pipeline(
            {"record_training_load": 0.95, "greeting": 0.05},
            {"none": 0.95, "pain_or_possible_injury": 0.05},
        )
        result = pipeline.analyze(
            "anota supino 4x10 com 30 kg", date(2026, 10, 8)
        )
        topics = {item["id"] for item in result["topics"]}
        self.assertIn("training_performance", topics)
        self.assertIn("sets_and_repetitions", topics)
        self.assertIn("training_intensity", topics)

    def test_real_pipeline_returns_complete_safe_contract(self) -> None:
        result = load_pipeline(AI_ROOT).analyze(
            "amanha troca supino por flexao", date(2026, 10, 8)
        )
        self.assertEqual(
            {
                "pipeline_version",
                "input",
                "decision",
                "intent",
                "risk",
                "entities",
                "topics",
                "clarification",
                "planner_proposal",
                "guardrails",
            },
            set(result),
        )
        self.assertFalse(result["input"]["text_stored"])
        self.assertFalse(result["guardrails"]["planner_writes_allowed"])

    def test_policy_uses_validation_only(self) -> None:
        derived = self.policy["derived_from"]
        self.assertEqual("validation", derived["split"])
        self.assertFalse(derived["test_used_for_threshold_selection"])
        self.assertFalse(derived["challenge_used_for_threshold_selection"])
        self.assertFalse(self.policy["planner"]["direct_writes_allowed"])

    def test_pipeline_artifact_manifest_hashes_are_current(self) -> None:
        root = AI_ROOT / "artifacts" / "pipeline" / "1.0.0"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["guardrails"]["direct_planner_writes"])
        self.assertFalse(
            manifest["guardrails"]["test_used_for_threshold_selection"]
        )
        for relative_path, value in manifest["outputs"].items():
            self.assertEqual(value["sha256"], sha256(AI_ROOT / relative_path))


if __name__ == "__main__":
    unittest.main()

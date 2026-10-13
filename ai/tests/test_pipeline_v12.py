from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.baseline import ClassificationResult, RankedLabel
from evolv_nlp.entities import load_entity_catalog
from evolv_nlp.pipeline import load_taxonomy
from evolv_nlp.pipeline_v12 import DevelopmentCoachPipeline
from evolv_nlp.topics import load_topic_rules, load_topics


def result(label, confidence=0.99):
    return ClassificationResult(label, confidence, (RankedLabel(label, confidence), RankedLabel("other", 1 - confidence)))


class DevelopmentPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = DevelopmentCoachPipeline.__new__(DevelopmentCoachPipeline)
        cls.pipeline.models = {"intent_classification": object(), "risk_classification": object()}
        cls.pipeline.policy = {task: {"minimum_confidence": 0.8, "minimum_margin": 0.2}
                               for task in cls.pipeline.models}
        cls.pipeline.catalog = load_entity_catalog(AI_ROOT / "data/catalogs/entity_catalogs.v1.json")
        cls.pipeline.intents = load_taxonomy(AI_ROOT / "data/taxonomy/intents.v1.json", "intents")
        cls.pipeline.risks = load_taxonomy(AI_ROOT / "data/taxonomy/risks.v1.json", "risks")
        extension = json.loads((AI_ROOT / "data/taxonomy/expansion.v1.1.json").read_text("utf-8"))
        for collection in ("intents", "risks"):
            getattr(cls.pipeline, collection).update({r["id"]: r for r in extension[collection]})
        _, cls.pipeline.topics = load_topics(AI_ROOT / "data/taxonomy/topics.v1.json")
        cls.pipeline.topic_rules = load_topic_rules(AI_ROOT / "data/pipeline/topic_rules.v1.json", set(cls.pipeline.topics))

    def analyze(self, text, intent="ask_training_concept", risk="none", confidence=0.99):
        with patch("evolv_nlp.pipeline_v12.classify", side_effect=[result(intent), result(risk, confidence)]):
            return self.pipeline.analyze(text, date(2026, 10, 10))

    def test_risk_overrides_confident_model_none(self):
        report = self.analyze("Sinto dor no peito agora")
        self.assertEqual("safety_review", report["decision"]["status"])
        self.assertFalse(report["writes_allowed"])
        self.assertIsNone(report["proposal"])

    def test_language_fallback_does_not_downgrade_explicit_safety(self):
        report = self.analyze("Can you ajudar? Estou com dor no peito agora")
        self.assertEqual("safety_review", report["decision"]["status"])

    def test_ambiguous_weight_requires_context_even_when_entity_not_usable(self):
        report = self.analyze("Iniciante, 80 kg")
        self.assertIn("ambiguous_weight", report["decision"]["reasons"])
        self.assertEqual("clarify", report["decision"]["status"])

    def test_negated_change_command_cannot_create_a_proposal(self):
        report = self.analyze("nao quero trocar supino", intent="replace_exercise")
        self.assertEqual("clarify", report["decision"]["status"])
        self.assertIn("negated_change_request", report["decision"]["reasons"])
        self.assertIsNone(report["proposal"])

    def test_uncertain_risk_blocks_plan_proposal(self):
        report = self.analyze("troca supino por flexao", intent="replace_exercise", confidence=0.55)
        self.assertIn("low_risk_confidence_for_proposal", report["decision"]["reasons"])
        self.assertIsNone(report["proposal"])

    def test_plan_is_preview_only_and_topics_serializable(self):
        report = self.analyze("troca supino por flexao", intent="replace_exercise")
        self.assertEqual("planner_preview", report["decision"]["status"])
        self.assertTrue(report["proposal"]["requires_confirmation"])
        self.assertFalse(report["proposal"]["writes_allowed"])
        json.dumps(report)

    def test_blank_and_oversize_text_are_rejected(self):
        for text in ("", " " , "x" * 8001):
            with self.assertRaises(ValueError):
                self.pipeline.analyze(text, date(2026, 10, 10))


if __name__ == "__main__":
    unittest.main()

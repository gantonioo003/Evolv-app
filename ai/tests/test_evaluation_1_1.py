from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.dataset import file_sha256, read_jsonl  # noqa: E402


class Evaluation11Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = AI_ROOT / "artifacts" / "evaluation" / "1.1.0"
        cls.metrics = json.loads(
            (cls.root / "metrics.json").read_text(encoding="utf-8")
        )
        cls.manifest = json.loads(
            (cls.root / "manifest.json").read_text(encoding="utf-8")
        )

    def test_evaluation_covers_frozen_test_and_human_holdout(self) -> None:
        self.assertEqual(90, self.metrics["test"]["intent_classification"]["rows"])
        self.assertEqual(39, self.metrics["test"]["risk_classification"]["rows"])
        self.assertEqual(10, self.metrics["real_human_holdout"]["rows"])
        self.assertEqual("completed", self.manifest["status"])

    def test_prediction_label_matches_highest_probability(self) -> None:
        for filename in (
            "intent_predictions.jsonl",
            "risk_predictions.jsonl",
            "real_human_intent_predictions.jsonl",
            "real_human_risk_predictions.jsonl",
        ):
            for row in read_jsonl(self.root / filename):
                with self.subTest(filename=filename, row=row["id"]):
                    self.assertEqual(row["predicted"], row["alternatives"][0]["label"])
                    self.assertEqual(row["confidence"], row["alternatives"][0]["confidence"])

    def test_manifest_hashes_outputs_and_preserves_guardrails(self) -> None:
        guardrails = self.manifest["guardrails"]
        self.assertTrue(guardrails["dataset_hashes_verified"])
        self.assertTrue(guardrails["model_hashes_verified"])
        self.assertFalse(guardrails["models_retrained_during_evaluation"])
        self.assertFalse(guardrails["test_used_for_model_selection"])
        for relative, metadata in self.manifest["outputs"].items():
            with self.subTest(relative=relative):
                self.assertEqual(metadata["sha256"], file_sha256(AI_ROOT / relative))


if __name__ == "__main__":
    unittest.main()

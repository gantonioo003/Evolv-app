from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.baseline import load_trusted_model  # noqa: E402


class Baseline11Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = AI_ROOT / "artifacts" / "baseline" / "1.1.0"
        cls.manifest = json.loads(
            (cls.root / "manifest.json").read_text(encoding="utf-8")
        )
        cls.metrics = json.loads(
            (cls.root / "metrics.json").read_text(encoding="utf-8")
        )

    def test_validation_metrics_clear_declared_learning_thresholds(self) -> None:
        tasks = self.metrics["tasks"]
        self.assertGreaterEqual(
            tasks["intent_classification"]["selected_validation"]["macro_f1"], 0.70
        )
        self.assertGreaterEqual(
            tasks["risk_classification"]["selected_validation"]["macro_f1"], 0.90
        )

    def test_models_load_with_manifest_hashes_and_predict(self) -> None:
        examples = {
            "intent_classification": "troca o supino por flexao amanha",
            "risk_classification": "meu joelho inchou e nao consigo apoiar o pe",
        }
        for task, text in examples.items():
            metadata = self.manifest["model_artifacts"][task]
            model = load_trusted_model(self.root / metadata["file"], metadata["sha256"])
            with self.subTest(task=task):
                self.assertIsInstance(str(model.predict([text])[0]), str)
                self.assertEqual(1, len(model.predict_proba([text])))

    def test_selection_never_used_test(self) -> None:
        self.assertIn(self.manifest["status"], {"trained_test_closed", "evaluated"})
        for report in self.metrics["tasks"].values():
            self.assertFalse(report["test_evaluated"])
            self.assertIn("test remains closed", report["selection_policy"])


if __name__ == "__main__":
    unittest.main()

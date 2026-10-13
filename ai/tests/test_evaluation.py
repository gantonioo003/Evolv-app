from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.evaluation import read_jsonl  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.protocol = json.loads(
            (AI_ROOT / "data" / "evaluation" / "protocol.v1.json").read_text(
                encoding="utf-8"
            )
        )
        cls.artifact_root = AI_ROOT / "artifacts" / "evaluation" / "1.0.0"
        cls.metrics = json.loads(
            (cls.artifact_root / "metrics.json").read_text(encoding="utf-8")
        )
        cls.manifest = json.loads(
            (cls.artifact_root / "manifest.json").read_text(encoding="utf-8")
        )

    def test_protocol_is_frozen_and_input_hashes_match(self) -> None:
        self.assertEqual("frozen", self.protocol["status"])
        paths = {
            "test/intent_examples.jsonl": AI_ROOT
            / "data"
            / "splits"
            / "test"
            / "intent_examples.jsonl",
            "test/risk_examples.jsonl": AI_ROOT
            / "data"
            / "splits"
            / "test"
            / "risk_examples.jsonl",
            "challenge/ambiguity_examples.jsonl": AI_ROOT
            / "data"
            / "splits"
            / "challenge"
            / "ambiguity_examples.jsonl",
            "entity_holdout.v1.jsonl": AI_ROOT
            / "data"
            / "evaluation"
            / "entity_holdout.v1.jsonl",
        }
        for name, path in paths.items():
            with self.subTest(name=name):
                self.assertEqual(
                    self.protocol["frozen_inputs"][name]["sha256"], sha256(path)
                )
                self.assertEqual(
                    self.protocol["frozen_inputs"][name]["rows"],
                    len(read_jsonl(path)),
                )

    def test_entity_holdout_does_not_duplicate_development_messages(self) -> None:
        development = read_jsonl(
            AI_ROOT / "data" / "entities" / "evaluation.v1.jsonl"
        )
        holdout = read_jsonl(
            AI_ROOT / "data" / "evaluation" / "entity_holdout.v1.jsonl"
        )
        development_texts = {row["text"].casefold().strip() for row in development}
        holdout_texts = {row["text"].casefold().strip() for row in holdout}
        self.assertFalse(development_texts & holdout_texts)
        self.assertEqual(40, len(holdout_texts))

    def test_metrics_cover_intent_risk_entities_and_challenge(self) -> None:
        self.assertEqual(30, self.metrics["test"]["intent"]["rows"])
        self.assertEqual(13, self.metrics["test"]["risk"]["rows"])
        self.assertEqual(40, self.metrics["entities"]["rows"])
        self.assertEqual(39, self.metrics["challenge"]["rows"])
        self.assertIn("safety_diagnostics", self.metrics["test"]["risk"])
        self.assertIn("macro", self.metrics["entities"])
        self.assertIn("micro", self.metrics["entities"])

    def test_confusion_matrices_are_square_and_count_all_rows(self) -> None:
        for task in ("intent", "risk"):
            report = self.metrics["test"][task]
            matrix = report["confusion_matrix"]
            size = len(matrix["labels"])
            self.assertEqual(size, len(matrix["values"]))
            self.assertTrue(all(len(row) == size for row in matrix["values"]))
            self.assertEqual(report["rows"], sum(map(sum, matrix["values"])))

    def test_error_counts_match_prediction_files(self) -> None:
        files = {
            "intent": "intent_predictions.jsonl",
            "risk": "risk_predictions.jsonl",
            "entities": "entity_predictions.jsonl",
        }
        for task, filename in files.items():
            rows = read_jsonl(self.artifact_root / filename)
            if task == "entities":
                observed = sum(not row["exact"] for row in rows)
                expected = self.metrics["entities"]["error_count"]
            else:
                observed = sum(not row["correct"] for row in rows)
                expected = self.metrics["test"][task]["error_count"]
            self.assertEqual(expected, observed)

    def test_manifest_hashes_all_outputs(self) -> None:
        self.assertFalse(self.manifest["guardrails"]["models_retrained"])
        self.assertFalse(self.manifest["guardrails"]["test_files_modified"])
        for relative_path, value in self.manifest["outputs"].items():
            path = AI_ROOT / relative_path
            self.assertEqual(value["sha256"], sha256(path))


if __name__ == "__main__":
    unittest.main()

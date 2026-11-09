import json
import sys
import unittest
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256, read_jsonl


class ExperimentClosureTests(unittest.TestCase):
    def test_recommendation_is_selected_from_validation_not_test(self):
        root = AI_ROOT / "artifacts/review/2026-10-19"
        recommendation = json.loads((root / "recommendation.json").read_text("utf-8"))
        self.assertFalse(recommendation["automatic_app_promotion"])
        for task in ("intent", "risk"):
            scores = {}
            for release in ("1.6.0", "1.6.1", "1.7.0"):
                metrics = json.loads((AI_ROOT / f"artifacts/baseline/{release}/evaluation.json").read_text("utf-8"))
                scores[release] = metrics["validation"][task]["macro_f1_supported"]
            self.assertEqual(max(scores, key=scores.get), recommendation["models"][task])

    def test_every_experiment_accounts_for_every_imported_record(self):
        expected = {r["id"] for r in read_jsonl(AI_ROOT / "data/releases/1.7.0/private/records.jsonl")}
        self.assertEqual(12179, len(expected))
        for release in ("1.6.0", "1.6.1", "1.7.0"):
            rows = read_jsonl(AI_ROOT / f"artifacts/baseline/{release}/private/predictions_all_12179.jsonl")
            self.assertEqual(12179, len(rows))
            self.assertEqual(expected, {r["id"] for r in rows})
            self.assertFalse(any("none" in r["predicted_risks"] and len(r["predicted_risks"]) > 1 for r in rows))

    def test_summary_and_neural_sources_match_hashes(self):
        manifest = json.loads((AI_ROOT / "artifacts/review/2026-10-19/manifest.json").read_text("utf-8"))
        for name, digest in manifest["files"].items():
            self.assertEqual(digest, file_sha256(AI_ROOT / name))
        neural = json.loads((AI_ROOT / "artifacts/baseline/1.7.0/manifest.json").read_text("utf-8"))
        self.assertEqual(neural["source_sha256"], file_sha256(AI_ROOT / "src/evolv_nlp/neural_review.py"))
        for task, metadata in neural["winners"].items():
            self.assertEqual(metadata["sha256"], file_sha256(AI_ROOT / "artifacts/baseline/1.7.0" / metadata["file"]))

    def test_entity_audit_preserves_legacy_regression_and_all_messages(self):
        manifest = json.loads((AI_ROOT / "artifacts/entities/1.3.0/manifest.json").read_text("utf-8"))
        self.assertEqual(12179, manifest["messages_processed"])
        self.assertEqual(80, manifest["supported_types_after"])
        self.assertEqual(manifest["historical_regression"]["before"], manifest["historical_regression"]["after"])
        for name, digest in manifest["sources"].items():
            self.assertEqual(digest, file_sha256(AI_ROOT / name))


if __name__ == "__main__":
    unittest.main()

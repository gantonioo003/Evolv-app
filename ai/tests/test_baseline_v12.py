from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.pipeline_v12 import DevelopmentCoachPipeline
from evolv_nlp.real_data import validate_external


class BaselineExpansionTests(unittest.TestCase):
    def test_models_reports_and_training_input_hashes_match_manifest(self):
        root = AI_ROOT / "artifacts/baseline/1.2.0"
        manifest = json.loads((root / "manifest.json").read_text("utf-8"))
        for row in [*manifest["model_artifacts"].values(), *manifest["reports"].values()]:
            self.assertEqual(row["sha256"], file_sha256(root / row["file"]))
        for relative, expected in manifest["source_files"].items():
            self.assertEqual(expected, file_sha256(AI_ROOT / relative))
        self.assertFalse(manifest["test_accessed"])
        self.assertEqual("experimental_not_default_pipeline", manifest["status"])

    def test_private_training_excludes_review_groups_and_external_holdouts(self):
        root = AI_ROOT / "data/releases/1.4.0"
        raw = read_jsonl(AI_ROOT / "data/external_private/ptbr-10000-1.0.0/mensagens.jsonl")
        index = {r["id_mensagem"]: r for r in raw}
        reviews = json.loads((root / "assistant_reviews.json").read_text("utf-8"))["reviews"]
        blocked_groups = {index[r["id"]]["split_group_id"] for r in reviews}
        for filename in ("intent_examples.jsonl", "risk_examples.jsonl"):
            for row in read_jsonl(root / "local/train" / filename):
                self.assertEqual("train", index[row["id"]]["split"])
                self.assertNotIn(row["group_id"], blocked_groups)
                self.assertEqual(0.15, row["sample_weight"])
                self.assertEqual("weak_web_candidate_not_gold", row["provenance"])
                if filename.startswith("risk"):
                    self.assertNotEqual("none", row["label"])

    def test_external_original_texts_spans_and_split_manifest_validate(self):
        rows, _ = validate_external(AI_ROOT / "data/external_private/ptbr-10000-1.0.0")
        self.assertEqual(10_000, len(rows))

    def test_real_models_and_topics_integrate_without_writes(self):
        pipeline = DevelopmentCoachPipeline(AI_ROOT)
        result = pipeline.analyze("amanha troca supino por flexao", date(2026, 10, 10))
        self.assertFalse(result["writes_allowed"])
        self.assertFalse(result["uses_lm"])
        self.assertEqual("experimental_not_default", result["status"])
        json.dumps(result)


if __name__ == "__main__":
    unittest.main()

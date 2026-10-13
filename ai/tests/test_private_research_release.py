import json
import sys
import unittest
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.privacy import training_permission
from evolv_nlp.research_data import RELEASE
from evolv_nlp.semantic_encoder import masked_mean
from evolv_nlp.training_v12 import TASKS

import numpy as np


class PrivateResearchReleaseTests(unittest.TestCase):
    def setUp(self):
        self.release = AI_ROOT / f"data/releases/{RELEASE}"
        if not (self.release / "manifest.json").exists():
            self.skipTest("Private research release not generated")

    def test_all_questions_and_replies_are_accounted_for(self):
        manifest = json.loads((self.release / "manifest.json").read_text("utf-8"))
        self.assertEqual(10000, sum(r["questions"] for r in manifest["partitions"].values()))
        self.assertEqual(7328, sum(r["community_replies"] for r in manifest["partitions"].values()))

    def test_questions_replies_and_threads_remain_in_same_partition(self):
        seen_ids, seen_threads = set(), set()
        for split in ("train", "validation", "test", "quarantine"):
            rows = read_jsonl(self.release / f"private/conversations/{split}.jsonl")
            self.assertFalse(seen_ids & {r["id"] for r in rows})
            self.assertFalse(seen_threads & {r["thread_id"] for r in rows})
            seen_ids.update(r["id"] for r in rows)
            seen_threads.update(r["thread_id"] for r in rows)
            for row in rows:
                self.assertFalse(row["lm_training_allowed"])
                self.assertFalse(row["production_training_allowed"])
                for reply in row["replies"]:
                    self.assertTrue(reply["id"].startswith(row["id"] + "-reply-"))
                    self.assertFalse(reply["approved_response_target"])

    def test_weak_training_uses_only_eligible_training_questions(self):
        eligible = {r["id"] for r in read_jsonl(self.release / "private/conversations/train.jsonl")
                    if r["private_research_eligible"]}
        for filename in TASKS.values():
            path = self.release / f"private/weak_train/{filename}"
            if not path.exists():
                continue
            for row in read_jsonl(path):
                self.assertIn(row["id"], eligible)
                self.assertFalse(row["production_training_allowed"])
                self.assertFalse(row["response_used_as_feature"])
                self.assertFalse(training_permission(row)["allowed"])

    def test_model_artifacts_are_hash_checked_and_private(self):
        for version in ("1.4.0", "1.5.0"):
            root = AI_ROOT / f"artifacts/baseline/{version}"
            if not (root / "manifest.json").exists():
                continue
            manifest = json.loads((root / "manifest.json").read_text("utf-8"))
            self.assertFalse(manifest["default_changed"])
            for metadata in manifest["model_artifacts"].values():
                self.assertTrue(metadata["file"].startswith("private"))
                self.assertEqual(metadata["sha256"], file_sha256(root / metadata["file"]))
            for name, digest in manifest["source_files"].items():
                self.assertEqual(digest, file_sha256(AI_ROOT / name))

    def test_pooling_does_not_include_padding(self):
        hidden = np.asarray([[[1., 3.], [3., 5.], [99., 99.]]])
        pooled = masked_mean(hidden, np.asarray([[1, 1, 0]]))
        np.testing.assert_allclose(pooled, [[2., 4.]])


if __name__ == "__main__":
    unittest.main()

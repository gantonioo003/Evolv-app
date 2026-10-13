import json
import sys
import unittest
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.context_data import frozen_fingerprints
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.real_data import normalized_key


class ContextReleaseTests(unittest.TestCase):
    def test_old_files_are_byte_identical(self):
        previous = json.loads((AI_ROOT / "data/releases/1.5.0/frozen_fingerprints.json").read_text("utf-8"))
        self.assertEqual(previous, frozen_fingerprints(AI_ROOT))

    def test_import_is_private_and_not_automatically_training(self):
        manifest = json.loads((AI_ROOT / "data/releases/1.5.0/external_manifest.json").read_text("utf-8"))
        self.assertEqual(10000, manifest["records"])
        self.assertEqual(0, manifest["external_training_rows_approved"])
        queue = read_jsonl(AI_ROOT / "data/external_private/ptbr-context-1.0.0/review_queue.jsonl")
        self.assertEqual(10000, len(queue))
        self.assertTrue(all(not row["training_permission"]["allowed"] and not row["lm_training_allowed"] for row in queue))

    def test_new_training_is_owned_and_separated(self):
        for name in ("intent_examples.jsonl", "risk_examples.jsonl"):
            splits = {s: read_jsonl(AI_ROOT / f"data/releases/1.5.0/splits/{s}/{name}") for s in ("train", "validation", "test")}
            keys = {s: {normalized_key(r["text"]) for r in rows} for s, rows in splits.items()}
            self.assertFalse(keys["train"] & keys["validation"])
            self.assertFalse(keys["train"] & keys["test"])
            self.assertFalse(keys["validation"] & keys["test"])
            self.assertTrue(all("source_url" not in r for rows in splits.values() for r in rows))

    def test_model_files_reports_and_code_have_matching_hashes(self):
        root = AI_ROOT / "artifacts/baseline/1.3.0"
        manifest = json.loads((root / "manifest.json").read_text("utf-8"))
        for meta in [*manifest["model_artifacts"].values(), *manifest["reports"].values()]:
            self.assertEqual(meta["sha256"], file_sha256(root / meta["file"]))
        for name, digest in manifest["source_files"].items():
            self.assertEqual(digest, file_sha256(AI_ROOT / name), name)
        self.assertFalse(manifest["default_changed"])

    def test_corpus_retains_holdout_bytes_and_excludes_external_questions(self):
        root = AI_ROOT / "data/lm_corpus/1.2.0"
        manifest = json.loads((root / "manifest.json").read_text("utf-8"))
        for name, metadata in manifest["files"].items():
            self.assertEqual(metadata["sha256"], file_sha256(root / name))
        for name in ("validation.jsonl", "validation.txt", "test.jsonl", "test.txt"):
            self.assertEqual(file_sha256(AI_ROOT / "data/lm_corpus/1.1.0" / name), file_sha256(root / name))
        self.assertEqual(0, manifest["external_dataset_questions_added"])
        self.assertFalse(manifest["model_or_tokenizer_trained"])


if __name__ == "__main__":
    unittest.main()

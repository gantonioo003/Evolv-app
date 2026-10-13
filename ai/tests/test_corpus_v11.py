from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256, read_jsonl


class CorpusExtensionTests(unittest.TestCase):
    def test_holdout_bytes_and_all_manifest_hashes_are_preserved(self):
        root = AI_ROOT / "data/lm_corpus/1.1.0"
        manifest = json.loads((root / "manifest.json").read_text("utf-8"))
        for filename, metadata in manifest["files"].items():
            self.assertEqual(metadata["sha256"], file_sha256(root / filename))
        for split in ("validation", "test"):
            for extension in ("jsonl", "txt"):
                filename = f"{split}.{extension}"
                self.assertEqual(file_sha256(root / filename), file_sha256(AI_ROOT / "data/lm_corpus/1.0.0" / filename))

    def test_additions_exclude_web_text_and_holdout_groups(self):
        root = AI_ROOT / "data/lm_corpus/1.1.0"
        rows = read_jsonl(root / "train.jsonl")
        old_ids = {r["doc_id"] for r in read_jsonl(AI_ROOT / "data/lm_corpus/1.0.0/train.jsonl")}
        additions = [r for r in rows if r["doc_id"] not in old_ids]
        blocked = {r["group_id"] for split in ("validation", "test") for r in read_jsonl(root / f"{split}.jsonl")}
        self.assertEqual(174, len(additions))
        self.assertFalse({r["group_id"] for r in rows} & blocked)
        self.assertTrue(all(r["source"] in ("evolv_v14_authored_train", "evolv_knowledge_qa") for r in additions))
        self.assertTrue(all(not r["human_generated"] for r in additions))


if __name__ == "__main__":
    unittest.main()

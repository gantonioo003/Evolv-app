from __future__ import annotations

import json
import sys
import unittest
from collections import defaultdict
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.dataset import file_sha256, read_jsonl  # noqa: E402


class TinyLmCorpusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = AI_ROOT / "data" / "lm_corpus" / "1.0.0"
        cls.manifest = json.loads(
            (cls.root / "manifest.json").read_text(encoding="utf-8")
        )
        cls.quality = json.loads(
            (cls.root / "quality_report.json").read_text(encoding="utf-8")
        )
        cls.sources = json.loads(
            (cls.root / "sources.json").read_text(encoding="utf-8")
        )

    def test_manifest_and_file_hashes(self) -> None:
        self.assertEqual("passed", self.manifest["status"])
        self.assertEqual("passed", self.quality["status"])
        for filename, metadata in self.manifest["files"].items():
            with self.subTest(filename=filename):
                self.assertEqual(metadata["sha256"], file_sha256(self.root / filename))

    def test_corpus_has_enough_material_for_educational_tinylm(self) -> None:
        self.assertGreaterEqual(self.quality["documents"], 6_000)
        self.assertGreaterEqual(self.quality["whitespace_tokens"], 1_500_000)
        self.assertGreaterEqual(self.quality["estimated_subword_tokens"], 2_000_000)
        self.assertGreaterEqual(
            self.quality["source_documents"]["oasst1_ptbr_human"], 1_000
        )

    def test_groups_do_not_leak_between_splits(self) -> None:
        observed: dict[str, set[str]] = defaultdict(set)
        for split in ("train", "validation", "test"):
            for row in read_jsonl(self.root / f"{split}.jsonl"):
                observed[str(row["group_id"])].add(split)
        self.assertFalse([group for group, splits in observed.items() if len(splits) > 1])
        self.assertEqual([], self.quality["group_leakage"])

    def test_sources_have_explicit_decisions_and_licenses(self) -> None:
        accepted = self.sources["accepted_sources"]
        self.assertEqual(
            {"evolv_knowledge", "evolv_nlu_train", "oasst1_ptbr_human", "wikipedia_pt"},
            set(accepted),
        )
        self.assertTrue(all(source["accepted"] for source in accepted.values()))
        self.assertTrue(all(source["license"] for source in accepted.values()))
        blocked_names = {source["name"] for source in self.sources["blocked_sources"]}
        self.assertIn("AKCIT/MedPT", blocked_names)
        self.assertIn("Reddit posts", blocked_names)

    def test_nlu_human_holdout_is_excluded_from_corpus(self) -> None:
        release = AI_ROOT / "data" / "releases" / "1.3.0"
        holdout = read_jsonl(release / "challenge" / "real_human_examples.jsonl")
        reserved_ids = {row["source_id"] for row in holdout}
        reserved_texts = {" ".join(row["text"].casefold().split()) for row in holdout}
        for split in ("train", "validation", "test"):
            for row in read_jsonl(self.root / f"{split}.jsonl"):
                self.assertNotIn(row["doc_id"], reserved_ids)
                self.assertNotIn(" ".join(row["text"].casefold().split()), reserved_texts)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.dataset import file_sha256, read_jsonl  # noqa: E402


class DatasetRelease13Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = AI_ROOT / "data" / "releases" / "1.3.0"
        cls.manifest = json.loads(
            (cls.root / "manifest.json").read_text(encoding="utf-8")
        )
        cls.quality = json.loads(
            (cls.root / "quality_report.json").read_text(encoding="utf-8")
        )

    def test_release_is_frozen_and_all_hashes_match(self) -> None:
        self.assertEqual("1.3.0", self.manifest["dataset_version"])
        self.assertEqual("frozen", self.manifest["status"])
        self.assertEqual("passed", self.quality["status"])
        for relative, metadata in self.manifest["files"].items():
            with self.subTest(path=relative):
                self.assertEqual(metadata["sha256"], file_sha256(self.root / relative))

    def test_train_validation_and_test_are_balanced(self) -> None:
        expected_labels = {"intent_examples.jsonl": 30, "risk_examples.jsonl": 13}
        expected_per_label = {
            "train": {"intent_examples.jsonl": 24, "risk_examples.jsonl": 23},
            "validation": {"intent_examples.jsonl": 3, "risk_examples.jsonl": 3},
            "test": {"intent_examples.jsonl": 3, "risk_examples.jsonl": 3},
        }
        for split, task_counts in expected_per_label.items():
            for filename, label_count in expected_labels.items():
                rows = read_jsonl(self.root / "splits" / split / filename)
                counts = Counter(str(row["label"]) for row in rows)
                with self.subTest(split=split, task=filename):
                    self.assertEqual(label_count, len(counts))
                    self.assertEqual({task_counts[filename]}, set(counts.values()))

    def test_no_text_or_group_leakage_between_splits(self) -> None:
        text_splits: dict[str, set[str]] = defaultdict(set)
        group_splits: dict[str, set[str]] = defaultdict(set)
        for split in ("train", "validation", "test"):
            for path in sorted((self.root / "splits" / split).glob("*.jsonl")):
                for row in read_jsonl(path):
                    normalized = " ".join(str(row["text"]).casefold().split())
                    text_splits[normalized].add(split)
                    group_splits[str(row.get("group_id", row["id"]))].add(split)
        self.assertFalse([text for text, splits in text_splits.items() if len(splits) > 1])
        self.assertFalse([group for group, splits in group_splits.items() if len(splits) > 1])

    def test_real_human_holdout_is_separate_and_attributed(self) -> None:
        rows = read_jsonl(self.root / "challenge" / "real_human_examples.jsonl")
        train_texts = {
            " ".join(str(row["text"]).casefold().split())
            for path in (self.root / "splits" / "train").glob("*.jsonl")
            for row in read_jsonl(path)
        }
        self.assertEqual(10, len(rows))
        self.assertTrue(all(row["source_type"] == "human_real_public" for row in rows))
        self.assertTrue(all(row["source_license"] == "Apache-2.0" for row in rows))
        self.assertTrue(
            all(" ".join(row["text"].casefold().split()) not in train_texts for row in rows)
        )


if __name__ == "__main__":
    unittest.main()

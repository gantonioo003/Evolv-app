from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "scripts"))

from audit_splits import audit_generated_dataset, audit_rows  # noqa: E402


def wrapped_row(
    row_id: str,
    split: str,
    text: str,
    label: str = "replace_exercise",
) -> dict[str, object]:
    return {
        "split": split,
        "file": f"{split}/intent_examples.jsonl",
        "row": {
            "id": row_id,
            "task": "intent_classification",
            "text": text,
            "label": label,
            "dataset_version": "1.2.0",
            "source_type": "synthetic_curated",
        },
    }


class SplitQualityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(
            (AI_ROOT / "data" / "splits" / "split_policy.v1.json").read_text(
                encoding="utf-8"
            )
        )

    def test_frozen_dataset_passes_the_full_audit(self) -> None:
        report = audit_generated_dataset(write_report=False)

        self.assertEqual("passed", report["status"])
        self.assertEqual(0, report["summary"]["blocking_findings"])
        self.assertEqual(383, report["summary"]["rows"])
        self.assertEqual(383, report["summary"]["unique_ids"])
        self.assertEqual(383, report["summary"]["unique_normalized_texts"])

    def test_exact_text_leak_is_blocked(self) -> None:
        rows = [
            wrapped_row("example_train", "train", "troque o supino por flexao"),
            wrapped_row("example_test", "test", "Troque o supino por flexão!"),
        ]

        report = audit_rows(rows, self.policy, "1.2.0")

        self.assertEqual("failed", report["status"])
        self.assertEqual(
            1,
            len(report["findings"]["exact_normalized_duplicates"]),
        )

    def test_near_duplicate_across_splits_is_blocked(self) -> None:
        rows = [
            wrapped_row(
                "example_train",
                "train",
                "quero trocar o supino inclinado de hoje por flexao",
            ),
            wrapped_row(
                "example_validation",
                "validation",
                "quero trocar o supino inclinado de hoje por flexoes",
            ),
        ]

        report = audit_rows(rows, self.policy, "1.2.0")

        self.assertEqual("failed", report["status"])
        self.assertEqual(
            1,
            len(report["findings"]["near_duplicates_across_splits"]),
        )

    def test_challenge_row_outside_challenge_split_is_blocked(self) -> None:
        item = wrapped_row("challenge_wrong_split", "train", "isso e seguro para mim")
        item["row"] = copy.deepcopy(item["row"])
        item["row"]["task"] = "challenge_evaluation"

        report = audit_rows([item], self.policy, "1.2.0")

        self.assertEqual("failed", report["status"])
        self.assertEqual(
            1,
            len(report["findings"]["challenge_policy_violations"]),
        )

    def test_assignment_registry_covers_every_generated_row(self) -> None:
        registry = json.loads(
            (AI_ROOT / "data" / "splits" / "assignments.v1.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual("frozen", registry["status"])
        self.assertEqual("1.2.0", registry["dataset_version"])
        self.assertEqual(383, len(registry["assignments"]))


if __name__ == "__main__":
    unittest.main()

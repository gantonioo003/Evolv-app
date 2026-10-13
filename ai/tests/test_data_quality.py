from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "scripts"))

from build_splits import build  # noqa: E402
from validate_data import validate  # noqa: E402


class DataQualityTest(unittest.TestCase):
    def test_phase_7_01_data_is_reproducible_and_valid(self) -> None:
        first_manifest = build()
        second_manifest = build()

        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual([], validate())

    def test_dataset_1_2_has_expected_coverage_and_provenance(self) -> None:
        splits_root = AI_ROOT / "data" / "splits"

        def read_jsonl(path: Path) -> list[dict[str, object]]:
            return [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        intent_rows = []
        risk_rows = []
        for split in ("train", "validation", "test"):
            intent_rows.extend(read_jsonl(splits_root / split / "intent_examples.jsonl"))
            risk_rows.extend(read_jsonl(splits_root / split / "risk_examples.jsonl"))
        challenge_rows = read_jsonl(
            splits_root / "challenge" / "ambiguity_examples.jsonl"
        )

        self.assertEqual(240, len(intent_rows))
        self.assertEqual(104, len(risk_rows))
        self.assertEqual(39, len(challenge_rows))
        self.assertEqual(
            {"synthetic_curated": 180, "real_pattern_rewrite": 60},
            dict(Counter(row["source_type"] for row in intent_rows)),
        )
        self.assertEqual(
            {"synthetic_curated": 78, "real_pattern_rewrite": 26},
            dict(Counter(row["source_type"] for row in risk_rows)),
        )
        self.assertTrue(
            all(
                row["source_type"] == "synthetic_adversarial_curated"
                for row in challenge_rows
            )
        )
        self.assertGreaterEqual(
            sum(
                row.get("style") == "informal_noisy"
                for row in intent_rows + risk_rows
            ),
            30,
        )
        self.assertTrue(
            all(
                row["dataset_version"] == "1.2.0"
                for row in intent_rows + risk_rows + challenge_rows
            )
        )


if __name__ == "__main__":
    unittest.main()

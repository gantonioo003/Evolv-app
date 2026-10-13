from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))


class DatasetResearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(
            (
                AI_ROOT
                / "data"
                / "research"
                / "dataset-expansion-candidates.v1.json"
            ).read_text(encoding="utf-8")
        )

    def test_research_does_not_modify_or_import_into_frozen_dataset(self) -> None:
        self.assertEqual("1.2.0", self.payload["current_dataset_unchanged"])
        self.assertEqual(0, self.payload["external_rows_imported"])
        self.assertEqual("1.3.0", self.payload["next_release"]["planned_version"])

    def test_candidates_have_unique_ids_and_documented_usage(self) -> None:
        candidates = self.payload["candidates"]
        ids = [item["id"] for item in candidates]
        self.assertEqual(len(ids), len(set(ids)))
        for item in candidates:
            self.assertTrue(item["url"].startswith("https://"))
            self.assertTrue(item["license_declared"])
            self.assertTrue(item["status"])
            self.assertTrue(item["not_for"])

    def test_private_conversation_content_is_not_stored(self) -> None:
        private = self.payload["derived_private_patterns"]
        self.assertFalse(private["raw_text_stored"])
        self.assertFalse(private["private_urls_stored"])
        self.assertGreaterEqual(len(private["patterns"]), 5)

    def test_new_product_scenarios_cover_schedule_and_pain_safety(self) -> None:
        scenarios = {
            item["id"]: item
            for item in self.payload["priority_scenarios_for_1_3"]
        }
        self.assertIn("optional_training_time_nutrition", scenarios)
        self.assertIn("sport_discomfort_and_strength_request", scenarios)
        self.assertIn(
            "pain_or_possible_injury_risk",
            scenarios["sport_discomfort_and_strength_request"][
                "expected_components"
            ],
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
import json
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "scripts"))

from validate_taxonomy import validate  # noqa: E402


class TaxonomyTest(unittest.TestCase):
    def test_taxonomy_is_consistent_with_current_planner_contracts(self) -> None:
        self.assertEqual([], validate())

    def test_every_intent_has_one_hierarchy_assignment(self) -> None:
        taxonomy_root = AI_ROOT / "data" / "taxonomy"
        intents = json.loads((taxonomy_root / "intents.v1.json").read_text(encoding="utf-8"))["intents"]
        assignments = json.loads((taxonomy_root / "hierarchy.v1.json").read_text(encoding="utf-8"))["intent_assignments"]
        self.assertEqual(
            {item["id"] for item in intents},
            {item["intent_id"] for item in assignments},
        )
        self.assertEqual(len(assignments), len({item["intent_id"] for item in assignments}))

    def test_topics_and_capabilities_have_professional_coverage(self) -> None:
        taxonomy_root = AI_ROOT / "data" / "taxonomy"
        topics = json.loads((taxonomy_root / "topics.v1.json").read_text(encoding="utf-8"))["topics"]
        capabilities = json.loads((taxonomy_root / "capabilities.v1.json").read_text(encoding="utf-8"))["capabilities"]
        self.assertGreaterEqual(len(topics), 70)
        self.assertGreaterEqual(len(capabilities), 40)
        self.assertTrue({"training", "nutrition", "recovery", "progress"} <= {item["domain"] for item in topics})


if __name__ == "__main__":
    unittest.main()

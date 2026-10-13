from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "scripts"))

from validate_data import validate  # noqa: E402


class KnowledgeBaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = json.loads(
            (AI_ROOT / "data" / "metadata" / "sources.v1.json").read_text(
                encoding="utf-8"
            )
        )["sources"]
        self.knowledge = json.loads(
            (
                AI_ROOT / "data" / "knowledge" / "knowledge_chunks.v1.json"
            ).read_text(encoding="utf-8")
        )["chunks"]
        self.coverage = json.loads(
            (AI_ROOT / "data" / "knowledge" / "coverage.v1.json").read_text(
                encoding="utf-8"
            )
        )

    def test_phase_7_01_3_has_expected_catalog_and_domain_coverage(self) -> None:
        self.assertEqual(27, len(self.sources))
        self.assertEqual(67, len(self.knowledge))
        self.assertEqual(
            {"training": 14, "nutrition": 23, "recovery": 11, "safety": 19},
            dict(Counter(chunk["domain"] for chunk in self.knowledge)),
        )
        self.assertEqual([], validate())

    def test_every_approved_source_is_used_and_forums_are_excluded(self) -> None:
        source_ids = {source["id"] for source in self.sources}
        used_sources = {
            source_id
            for chunk in self.knowledge
            for source_id in chunk["source_ids"]
        }
        self.assertEqual(source_ids, used_sources)
        self.assertTrue(all(source["status"] == "approved" for source in self.sources))
        self.assertFalse(
            set(self.coverage["forbidden_source_types"])
            & {source["type"] for source in self.sources}
        )

    def test_every_risk_route_and_response_mode_is_covered(self) -> None:
        observed_risks = {
            risk for chunk in self.knowledge for risk in chunk["risk_tags"]
        }
        observed_modes = {chunk["response_mode"] for chunk in self.knowledge}
        self.assertTrue(
            set(self.coverage["required_risk_coverage"]) <= observed_risks
        )
        self.assertTrue(
            set(self.coverage["required_response_modes"]) <= observed_modes
        )

    def test_scientific_claims_are_not_supported_only_by_product_contracts(self) -> None:
        source_map = {source["id"]: source for source in self.sources}
        for chunk in self.knowledge:
            if chunk["confidence"] == "policy":
                continue
            authorities = {
                source_map[source_id]["authority"]
                for source_id in chunk["source_ids"]
            }
            self.assertNotEqual(
                {"product_contract"},
                authorities,
                msg=f"{chunk['id']} depende apenas de regra interna",
            )


if __name__ == "__main__":
    unittest.main()

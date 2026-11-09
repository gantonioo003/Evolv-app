"""Versioned knowledge review: provenance, safety scopes and unchanged historical inputs."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI / "src"))
from evolv_rag.knowledge_review import AUTHORING, compile_review, publish_review, protected_hashes
from evolv_rag.preparation import prepare, read, write, digest


class KnowledgeReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.authoring = read(AI / AUTHORING)
        cls.content = compile_review(AI)

    def test_coverage_matches_current_taxonomy_without_claiming_quality(self):
        report = self.content["coverage.json"]
        self.assertEqual(67, report["before"]["documents"])
        self.assertEqual(107, report["after"]["documents"])
        self.assertEqual(15, len(report["closed_nominal_topic_gaps"]))
        self.assertEqual(8, len(report["newly_addressed_risk_tags"]))
        self.assertEqual([], report["remaining_risk_tag_gaps"])
        self.assertEqual([], report["remaining_nominal_topic_gaps"])
        self.assertEqual(20, len(report["after"]["risks"]))
        self.assertTrue(report["residual_scope_gaps"])
        self.assertFalse(report["app_index_promoted"])

    def test_all_boundaries_and_development_cases_reference_content(self):
        changes = self.content["changes.json"]
        self.assertEqual(6, len(changes["boundary_migrations"]))
        self.assertEqual(40, len(self.content["acceptance_cases.json"]["cases"]))
        self.assertEqual([], self.content["boundaries.json"]["chunks"])
        self.assertEqual(40, len(changes["new_documents"]))

    def test_inherited_dates_not_relabelled_as_full_new_review(self):
        ledger = {e["source_id"]: e for e in self.content["evidence.json"]["entries"]}
        self.assertEqual("inherited_not_reverified_in_this_phase", ledger["cvv_188_current"]["status"])
        self.assertNotIn("verified_at", ledger["cvv_188_current"])
        self.assertEqual("publisher_summary", ledger["acsm_resistance_training_2026"]["method"])
        self.assertEqual("publisher_search_excerpt", ledger["athlete_sleep_consensus_2021"]["method"])
        docs = {d["id"]: d for d in self.content["knowledge_chunks.json"]["chunks"]}
        self.assertEqual("1.1.0", docs["physical_activity_health"]["version"])
        self.assertEqual("1.2.0", docs["deload_meaning"]["version"])
        self.assertEqual("expert_consensus_not_effectiveness_trial", docs["deload_meaning"]["evidence_level"])
        self.assertEqual("policy", docs["history_not_automatic_training_policy"]["confidence"])

    def test_unknown_references_duplicate_text_and_unreviewed_science_are_rejected(self):
        changes = [lambda a: a["new_documents"][0].update(source_ids=["missing"]),
                   lambda a: a["new_documents"][0].update(topic_ids=["missing"]),
                   lambda a: a["new_documents"][0].update(risk_tags=["missing"]),
                   lambda a: a["new_documents"][0].update(text=a["new_documents"][1]["text"]),
                   lambda a: a["new_documents"][0].update(source_ids=["evolv_coach_runtime_2026_11"]),
                   lambda a: a["new_documents"][0].update(source_ids=["who_alcohol_2024"]),
                   lambda a: a["revisions"].append(a["revisions"][0]),
                   lambda a: a["acceptance_cases"][0].update(target_document_ids=["missing"]),
                   lambda a: a["boundary_migrations"].pop("pain_is_not_a_diagnosis"),
                   lambda a: a.update(review_date="2099-01-01")]
        for change in changes:
            with self.subTest(change=change):
                authoring = deepcopy(self.authoring)
                change(authoring)
                with self.assertRaises(ValueError):
                    compile_review(AI, authoring)

    def test_publish_reproducible_protected_and_no_overwrite(self):
        before = protected_hashes(AI)
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            publish_review(AI, a)
            publish_review(AI, b)
            for p in a.iterdir():
                self.assertEqual(p.read_bytes(), (b / p.name).read_bytes())
            with self.assertRaises(FileExistsError):
                publish_review(AI, a)
            for name, expected in read(a / "manifest.json")["outputs"].items():
                self.assertEqual(expected, digest(a / name))
        self.assertEqual(before, protected_hashes(AI))

    def test_preparation_keeps_evidence_scopes_and_detects_stale_contract(self):
        config = read(AI / "configs/rag.preparation.v2.json")
        with tempfile.TemporaryDirectory() as tmp:
            root, ai = Path(tmp), Path(tmp) / "ai"
            for rel in config["inputs"]:
                path = ai / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                name = Path(rel).name
                if rel.startswith("data/knowledge/1.2.0/"):
                    write(path, self.content[name])
                else:
                    path.write_bytes((AI / rel).read_bytes())
            for source in self.content["sources.json"]["sources"]:
                if source.get("path"):
                    p = root / source["path"]
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes((AI.parent / source["path"]).read_bytes())
            for entry in self.content["evidence.json"]["entries"]:
                for name in entry.get("local_sha256", {}):
                    p = root / name
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes((AI.parent / name).read_bytes())
            for rel in ["src/evolv_rag/preparation.py", "scripts/prepare_rag_base.py"]:
                p = ai / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes((AI / rel).read_bytes())
            with patch("evolv_rag.preparation.__file__", str(ai / "src/evolv_rag/preparation.py")):
                report = prepare(ai, root / "rag", config, date(2026, 11, 3))
                self.assertEqual(107, report["retrieval_chunks"])
                self.assertEqual(0, report["quarantined_records"])
                rows = [__import__("json").loads(s) for s in (root / "rag/chunks.jsonl").read_text(encoding="utf-8").splitlines()]
                row = next(r for r in rows if r["document_id"] == "deload_meaning")
                self.assertIn("evidence_ids", row["generation_context"])
                self.assertIn("Delphi", row["generation_context"]["evidence_notes"])
                (root / "backend/src/coach/coach.service.ts").write_text("changed", encoding="utf-8")
                with self.assertRaises(ValueError):
                    prepare(ai, root / "stale", config, date(2026, 11, 3))
                self.assertFalse((root / "stale").exists())

if __name__ == "__main__":
    unittest.main()

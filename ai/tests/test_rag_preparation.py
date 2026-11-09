from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.preparation import digest, prepare, read, spans, write


class RagPreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ai = self.root / "ai"
        self.config = read(AI_ROOT / "configs/rag.preparation.v1.json")
        for rel in self.config["inputs"]:
            path = self.ai / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((AI_ROOT / rel).read_bytes())
        for source in read(self.ai / "data/metadata/sources.v1.json")["sources"]:
            if "path" in source:
                path = self.root / source["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((AI_ROOT.parent / source["path"]).read_bytes())
        (self.ai / "scripts").mkdir()
        (self.ai / "scripts/prepare_rag_base.py").write_bytes((AI_ROOT / "scripts/prepare_rag_base.py").read_bytes())
        self.kb = self.ai / "data/knowledge/knowledge_chunks.v1.json"
        self.original = self.kb.read_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, name="release", on=date(2026, 11, 2)):
        target = self.ai / "src/evolv_rag/preparation.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((AI_ROOT / "src/evolv_rag/preparation.py").read_bytes())
        with patch("evolv_rag.preparation.__file__", str(target)):
            return prepare(self.ai, self.root / name, self.config, on)

    def mutate(self, change):
        kb = read(self.kb)
        change(kb["chunks"])
        write(self.kb, kb)

    def test_splits_preserve_every_character_and_respect_budget(self):
        text = "  João treina.\n" + " ".join(["repetição"] * 400) + " fim!  "
        parts = spans(text, 17)
        self.assertEqual(text, "".join(text[a:b] for a, b in parts))
        self.assertTrue(all(len(text[a:b].split()) <= 17 for a, b in parts))
        with self.assertRaises(ValueError):
            spans(" ", 17)

    def test_prepared_context_keeps_boundaries_citations_and_all_text(self):
        report = self.build()
        rows = [json.loads(line) for line in (self.root / "release/chunks.jsonl").read_text(encoding="utf-8").splitlines()]
        docs = {d["id"]: d for d in read(self.kb)["chunks"]}
        self.assertEqual(len(docs), report["eligible_documents"])
        for row in rows:
            original = docs[row["document_id"]]
            self.assertEqual(original["text"][row["char_start"]:row["char_end"]], row["text"])
            self.assertEqual(original["not_for"], row["generation_context"]["not_for"])
            self.assertEqual(original["source_ids"], [s["id"] for s in row["citations"]])
        manifest = read(self.root / "release/manifest.json")
        for name, sha in manifest["outputs"].items():
            self.assertEqual(sha, digest(self.root / "release" / name))

    def test_expired_or_unapproved_source_blocks_dependent_documents(self):
        path = self.ai / "data/metadata/sources.v1.json"
        sources = read(path)
        source = sources["sources"][0]
        source["status"] = "pending"
        source["review_due_at"] = "2026-11-02"
        write(path, sources)
        self.build()
        rows = [json.loads(x) for x in (self.root / "release/chunks.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(all(source["id"] not in c["source_ids"] for c in rows))
        held = read(self.root / "release/quarantine.json")
        self.assertTrue(any("source_review_due:" + source["id"] in x["reasons"] for x in held))

    def test_duplicate_text_unknown_sources_and_topics_fail_before_publish(self):
        changes = [lambda xs: xs[1].update(text=xs[0]["text"]),
                   lambda xs: xs[0].update(source_ids=["missing"]),
                   lambda xs: xs[0].update(topic_ids=["missing"])]
        for change in changes:
            self.kb.write_bytes(self.original)
            self.mutate(change)
            with self.assertRaises(ValueError):
                self.build()
            self.assertFalse((self.root / "release").exists())

    def test_build_is_reproducible_and_never_overwrites_release(self):
        self.build("a")
        self.build("b")
        for path in (self.root / "a").iterdir():
            self.assertEqual(path.read_bytes(), (self.root / "b" / path.name).read_bytes())
        with self.assertRaises(FileExistsError):
            self.build("a")

    def test_future_and_due_documents_are_quarantined_not_silently_deleted(self):
        self.mutate(lambda xs: xs[0].update(reviewed_at="2026-12-01"))
        self.mutate(lambda xs: xs[1].update(review_due_at="2026-11-02"))
        report = self.build()
        self.assertEqual(report["documents"] - 2, report["eligible_documents"])
        self.assertEqual(8, report["quarantined_records"])


if __name__ == "__main__":
    unittest.main()

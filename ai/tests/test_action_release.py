"""Data integrity and leakage regressions, not a new model-quality benchmark."""
from collections import Counter
import json
from pathlib import Path
import sys
import unittest
import tempfile

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.action_release import authored_rows, build, cross_split_collisions, load_partition, read_rows, sha
from evolv_nlp.review_release import validate_isolation


class ActionReleaseTests(unittest.TestCase):
    def test_loader_rejects_tampering_and_reserved_partitions(self):
        for name in ("test", "quarantine", "../test"):
            with self.assertRaises(ValueError):
                load_partition(AI_ROOT, name)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release = root / "data/releases/1.9.0"
            (release / "private").mkdir(parents=True)
            data = release / "private/train.jsonl"
            data.write_text('{"id":"fixture"}\n', encoding="utf-8")
            (release / "manifest.json").write_text(json.dumps({"files":{"private/train.jsonl":sha(data)}}), encoding="utf-8")
            self.assertEqual([{"id":"fixture"}], load_partition(root, "train"))
            data.write_text('{"id":"changed"}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_partition(root, "train")

    def test_parent_records_are_preserved_and_reserved_files_byte_identical(self):
        parent = AI_ROOT / "data/releases/1.8.0"
        root = AI_ROOT / "data/releases/1.9.0"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        old = read_rows(parent / "private/records.jsonl")
        new = read_rows(root / "private/records.jsonl")
        index = {r["id"]: r for r in new}
        self.assertTrue(all(index[r["id"]] == r for r in old))
        self.assertEqual(len(new), len(old) + manifest["added_records"])
        for name, checksum in manifest["parent_files_sha256_unchanged"].items():
            self.assertEqual(checksum, sha(parent / name))
        for part, checksum in manifest["reserved_byte_identical"].items():
            self.assertEqual(checksum, sha(root / f"private/{part}.jsonl"))
        validate_isolation(new)

    def test_synthetic_validation_is_separate_and_no_parent_validation_is_replaced(self):
        root = AI_ROOT / "data/releases/1.9.0/private"
        legacy = read_rows(root / "validation_legacy.jsonl")
        self.assertEqual(legacy, read_rows(AI_ROOT / "data/releases/1.8.0/private/validation.jsonl"))
        synthetic = read_rows(root / "validation_actions_synthetic.jsonl")
        self.assertTrue(all(r["is_synthetic"] and not r["human_gold"] for r in synthetic))
        self.assertEqual(read_rows(root / "validation.jsonl"), legacy + synthetic)
        targets = {r["label"] for r in authored_rows(AI_ROOT / "data/action_authoring/v1/examples.py")
                   if ":action:" in r["id"]}
        count = Counter(r["label"] for r in synthetic)
        self.assertTrue(all(count[label] >= 5 for label in targets))
        groups = [r["group_id"] for r in synthetic]
        self.assertEqual(len(groups), len(set(groups)))

    def test_text_and_context_not_metadata_are_the_only_model_input(self):
        records = authored_rows(AI_ROOT / "data/action_authoring/v1/examples.py")
        for r in records:
            expected = f"Contexto anterior: {r['context']}\nMensagem atual: {r['text']}" if r["context"] else r["text"]
            self.assertEqual(expected, r["input"])
            self.assertNotIn(r["id"], r["input"])
            self.assertNotIn(r["label"], r["input"])
            self.assertFalse(r["annotation"]["is_execution_authorization"])

    def test_near_duplicate_in_reserved_partition_excludes_new_candidate(self):
        old = [{"id": "reserved", "input": "quero trocar o dia do meu treino de pernas agora", "partition": "test"}]
        additions = [{"id": "new", "input": "quero trocar o dia do meu treino de pernas agora!", "partition": "train"},
                     {"id": "distinct", "input": "explique a diferença entre proteína e carboidrato", "partition": "validation"}]
        found = cross_split_collisions(old, additions)
        self.assertIn("new", found)
        self.assertNotIn("distinct", found)
        self.assertEqual("test", old[0]["partition"])

    def test_near_copy_between_new_train_and_validation_is_not_accepted(self):
        additions = [{"id": "a", "input": "substitua o exercício de remada do meu treino", "partition": "train"},
                     {"id": "b", "input": "substitua o exercicio de remada do meu treino!", "partition": "validation"}]
        found = cross_split_collisions([], additions)
        self.assertEqual({"a", "b"}, set(found))

    def test_existing_release_refuses_overwrite_and_all_checksums_match(self):
        with self.assertRaises(FileExistsError):
            build(AI_ROOT)
        root = AI_ROOT / "data/releases/1.9.0"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        for name, checksum in manifest["files"].items():
            self.assertEqual(checksum, sha(root / name))
        self.assertEqual(manifest["authoring_sha256"], sha(AI_ROOT / "data/action_authoring/v1/examples.py"))


if __name__ == "__main__":
    unittest.main()

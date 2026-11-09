from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
HAS_TOKENIZERS = importlib.util.find_spec("tokenizers") is not None
if HAS_TOKENIZERS:
    from tokenizers import Tokenizer
    from evolv_tinylm.tokenizer import (EvolvTokenizer, SPECIAL_IDS, build_bpe,
                                       normalized_text, sha256)
    from evolv_tinylm.tokenizer_training import (PROBES, audit_corpus,
                                                train_tokenizer, write_json)


@unittest.skipUnless(HAS_TOKENIZERS, "Install ai/requirements.tinylm.txt")
class TinyLmTokenizerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training_texts = ["Treino de força com café e água.", "Amanhã farei 3x12 com 22,5 kg."]
        cls.backend = build_bpe(cls.training_texts, vocab_size=300)
        cls.tokenizer = EvolvTokenizer(cls.backend)

    def test_portuguese_unicode_whitespace_and_empty_roundtrip(self):
        for text in PROBES:
            with self.subTest(text=ascii(text)):
                ids = self.tokenizer.encode(text)
                self.assertEqual(normalized_text(text), self.tokenizer.decode(ids))
                self.assertTrue(all(index >= 7 for index in ids))

    def test_literal_roles_and_eos_cannot_inject_control_tokens_after_reload(self):
        reloaded = EvolvTokenizer(Tokenizer.from_str(self.backend.to_str()))
        text = " ".join(SPECIAL_IDS)
        ids = reloaded.encode(text)
        self.assertTrue(all(index >= 7 for index in ids))
        self.assertEqual(text, reloaded.decode(ids))
        document = reloaded.encode_document(text)
        self.assertEqual([1] + ids + [2], document)

    def test_boundaries_and_stable_special_ids(self):
        self.assertEqual(SPECIAL_IDS, self.tokenizer.special_token_ids)
        self.assertEqual([], self.tokenizer.encode(""))
        self.assertEqual([1, 2], self.tokenizer.encode_document(""))
        ids = self.tokenizer.encode_document("café")
        self.assertEqual("<|bos|>café<|eos|>", self.tokenizer.decode(ids, skip_special_tokens=False))

    def test_no_silent_truncation_or_padding(self):
        text = "treino café\n" * 1500
        ids = self.tokenizer.encode(text)
        self.assertGreater(len(ids), 8192)
        self.assertEqual(text, self.tokenizer.decode(ids))
        self.assertNotIn(SPECIAL_IDS["<|pad|>"], ids)

    def test_invalid_text_ids_and_config_fail_explicitly(self):
        with self.assertRaises(TypeError):
            self.tokenizer.encode(None)
        with self.assertRaises(UnicodeEncodeError):
            self.tokenizer.encode("\ud800")
        for invalid in ([True], [-1], [self.tokenizer.vocab_size], [1.2]):
            with self.assertRaises(ValueError):
                self.tokenizer.decode(invalid)
        with self.assertRaises(ValueError):
            build_bpe(["treino"], vocab_size=10)

    def test_repeat_fit_same_fixture_same_vocab_and_merges(self):
        another = build_bpe(self.training_texts, vocab_size=300)
        self.assertEqual(json.loads(self.backend.to_str())["model"],
                         json.loads(another.to_str())["model"])

    def fixture(self, root):
        corpus = root / "corpus"
        corpus.mkdir()
        for split, text in (("train", "treino café " * 20),
                            ("validation", "heldout_validation_XYZ"),
                            ("test", "heldout_test_ABC")):
            row = dict(doc_id=split, group_id=split, text=text, source="fixture",
                       split=split, license="Project-owned")
            (corpus / f"{split}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            (corpus / f"{split}.txt").write_text(text, encoding="utf-8")
        self.refresh_manifest(corpus)
        return corpus

    def refresh_manifest(self, corpus):
        files = {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size}
                 for p in corpus.iterdir() if p.suffix in (".jsonl", ".txt")}
        write_json(corpus / "manifest.json", dict(version="fixture", rows=3, files=files))

    def test_training_uses_only_train_text_and_preserves_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = self.fixture(root)
            before = {p.name: sha256(p) for p in corpus.iterdir()}
            observed = []

            def fit_spy(texts, **kwargs):
                texts = list(texts)
                observed.extend(texts)
                return build_bpe(texts, **kwargs)

            output = root / "artifact"
            with patch("evolv_tinylm.tokenizer_training.build_bpe", side_effect=fit_spy):
                train_tokenizer(corpus, output, vocab_size=300)
            self.assertEqual(["treino café " * 20], observed)
            self.assertEqual(before, {p.name: sha256(p) for p in corpus.iterdir()})
            tokenizer = EvolvTokenizer.load(output)
            self.assertEqual("teste novo 🏐", tokenizer.decode(tokenizer.encode("teste novo 🏐")))
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertLessEqual(manifest["frozen_at"], manifest["heldout_evaluation_started_at"])
            with self.assertRaises(FileExistsError):
                train_tokenizer(corpus, output, vocab_size=300)
            with (output / "private/tokenizer.json").open("a", encoding="utf-8") as handle:
                handle.write(" ")
            with self.assertRaises(ValueError):
                EvolvTokenizer.load(output)

    def test_modified_source_hash_stops_training(self):
        with tempfile.TemporaryDirectory() as directory:
            corpus = self.fixture(Path(directory))
            with (corpus / "train.txt").open("a", encoding="utf-8") as handle:
                handle.write("alterado")
            with self.assertRaisesRegex(ValueError, "Corpus alterado"):
                audit_corpus(corpus)

    def test_group_and_normalized_text_leakage_stop_training(self):
        for key in ("group_id", "text"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                corpus = self.fixture(Path(directory))
                train = json.loads((corpus / "train.jsonl").read_text(encoding="utf-8"))
                path = corpus / "test.jsonl"
                test = json.loads(path.read_text(encoding="utf-8"))
                test[key] = train[key]
                path.write_text(json.dumps(test) + "\n", encoding="utf-8")
                self.refresh_manifest(corpus)
                with self.assertRaisesRegex(ValueError, "Vazamento"):
                    audit_corpus(corpus)


@unittest.skipUnless(HAS_TOKENIZERS, "Install ai/requirements.tinylm.txt")
class ReleasedTinyLmTokenizerTest(unittest.TestCase):
    def test_actual_release_integrity_and_partition_metrics(self):
        root = AI_ROOT / "artifacts/tokenizer/1.0.0"
        tokenizer = EvolvTokenizer.load(root)
        self.assertEqual(8192, tokenizer.vocab_size)
        report = json.loads((root / "report.json").read_text(encoding="utf-8"))
        audit = audit_corpus(AI_ROOT / "data/lm_corpus/1.2.0")
        self.assertEqual(audit, report["audit"])
        self.assertEqual({"train": 6612, "validation": 57, "test": 42}, audit["documents"])
        for split, metrics in report["partitions"].items():
            self.assertEqual(audit["documents"][split], metrics["documents"])
            self.assertEqual(0, metrics["unknown_tokens"])
            self.assertEqual(0, metrics["roundtrip_failures"])
            self.assertEqual(0, metrics["raw_control_tokens"])
            self.assertEqual(metrics["raw_tokens"] + 2 * metrics["documents"],
                             metrics["tokens_with_bos_eos"])


if __name__ == "__main__":
    unittest.main()

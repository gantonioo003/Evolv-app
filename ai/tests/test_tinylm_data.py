from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import pickle
import sys
import tempfile
import unittest

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
HAS_DATA = all(importlib.util.find_spec(name) for name in ("numpy", "tokenizers"))
HAS_TORCH = importlib.util.find_spec("torch") is not None
if HAS_DATA:
    import numpy as np
    from evolv_tinylm.data import (IGNORE_INDEX, load_prepared_data, partition_stats,
                                  prepare_data)
    from evolv_tinylm.tokenizer import EvolvTokenizer, sha256
    from evolv_tinylm.tokenizer_training import (SPLITS, audit_corpus, read_rows,
                                                train_tokenizer, write_json)
if HAS_DATA and HAS_TORCH:
    import torch
    from torch.utils.data import RandomSampler, SequentialSampler
    from evolv_tinylm.dataset import NextTokenDataset, make_dataloaders


def snapshot(root):
    return {str(path.relative_to(root)): sha256(path) for path in root.rglob("*") if path.is_file()}


def make_fixture(root):
    corpus = root / "corpus"
    corpus.mkdir()
    texts = {
        "train": ["Água e café.", "Treino de força com 3x12. " * 45 + "FIM!",
                  "Texto literal <|eos|> e <|assistant|>, sem controle extra."],
        "validation": ["Amanhã vou caminhar no parque.", "Durmo bem à noite."],
        "test": ["Como organizar as refeições?", "Prefiro jogar vôlei aos sábados."],
    }
    total = 0
    for split, values in texts.items():
        rows = [dict(doc_id=f"{split}-{i}", group_id=f"{split}-{i}", text=text,
                     source="fixture", split=split, license="Project-owned")
                for i, text in enumerate(values)]
        (corpus / f"{split}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        (corpus / f"{split}.txt").write_text("\n\n".join(values), encoding="utf-8")
        total += len(rows)
    files = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
             for path in corpus.iterdir()}
    write_json(corpus / "manifest.json", dict(version="fixture", rows=total, files=files))
    tokenizer = root / "tokenizer"
    train_tokenizer(corpus, tokenizer, vocab_size=300)
    return corpus, tokenizer


@unittest.skipUnless(HAS_DATA, "Install ai/requirements.tinylm.txt")
class PreparedDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.corpus, cls.tokenizer = make_fixture(cls.root)
        cls.before_corpus = snapshot(cls.corpus)
        cls.before_tokenizer = snapshot(cls.tokenizer)
        cls.artifact = cls.root / "prepared"
        prepare_data(cls.corpus, cls.tokenizer, cls.artifact, context_length=16)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_preparation_preserves_inputs_and_every_document_in_each_split(self):
        self.assertEqual(self.before_corpus, snapshot(self.corpus))
        self.assertEqual(self.before_tokenizer, snapshot(self.tokenizer))
        tokenizer = EvolvTokenizer.load(self.tokenizer)
        metadata = load_prepared_data(self.artifact)
        self.assertEqual(sha256(self.tokenizer / "manifest.json"),
                         metadata["manifest"]["tokenizer_manifest_sha256"])
        for split in SPLITS:
            tokens = np.load(self.artifact / f"private/{split}.tokens.npy", allow_pickle=False)
            offsets = np.load(self.artifact / f"private/{split}.offsets.npy", allow_pickle=False)
            rows = list(read_rows(self.corpus / f"{split}.jsonl"))
            for i, row in enumerate(rows):
                self.assertEqual(tokenizer.encode_document(row["text"]),
                                 tokens[offsets[i]:offsets[i + 1]].tolist())
            self.assertEqual(len(rows), metadata["report"]["partitions"][split]["documents"])

    def test_remainders_and_exact_context_multiples_have_no_empty_or_dropped_windows(self):
        stats = partition_stats(np.array([0, 5, 11, 13], dtype="<i8"), 4)
        self.assertEqual(4, stats["sequences"])
        self.assertEqual(10, stats["target_tokens"])
        self.assertEqual(6, stats["padded_positions"])
        self.assertEqual(0, stats["dropped_tokens"])

    def test_invalid_context_and_existing_artifacts_fail(self):
        for context in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                prepare_data(self.corpus, self.tokenizer, self.root / "invalid", context_length=context)
        with self.assertRaises(FileExistsError):
            prepare_data(self.corpus, self.tokenizer, self.artifact)

    def test_preparation_is_reproducible_and_corruption_is_detected(self):
        another = self.root / "replica"
        prepare_data(self.corpus, self.tokenizer, another, context_length=16)
        for split in SPLITS:
            for kind in ("tokens", "offsets"):
                name = f"private/{split}.{kind}.npy"
                self.assertEqual(sha256(self.artifact / name), sha256(another / name))
        with (another / "private/train.tokens.npy").open("ab") as handle:
            handle.write(b"alterado")
        with self.assertRaisesRegex(ValueError, "Dados preparados alterados"):
            load_prepared_data(another)

    def test_different_corpus_cannot_be_combined_with_this_tokenizer(self):
        different = self.root / "different"
        different.mkdir()
        corpus, _ = make_fixture(different)
        manifest_path = corpus / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["version"] = "different-version"
        write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "Corpus diferente"):
            prepare_data(corpus, self.tokenizer, self.root / "wrong")
        self.assertFalse((self.root / "wrong").exists())


@unittest.skipUnless(HAS_DATA and HAS_TORCH, "Install ai/requirements.tinylm-training.txt")
class NextTokenDatasetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        corpus, tokenizer = make_fixture(cls.root)
        cls.artifact = cls.root / "prepared"
        prepare_data(corpus, tokenizer, cls.artifact, context_length=16)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_exact_shift_all_targets_once_and_no_document_crossing(self):
        for split in SPLITS:
            dataset = NextTokenDataset(self.artifact, split)
            tokens = np.load(dataset.tokens_path, allow_pickle=False)
            seen = []
            for i in range(len(dataset)):
                sample = dataset[i]
                info = dataset.window_info(i)
                start, n, doc = info["start"], info["valid_targets"], info["document_index"]
                self.assertLessEqual(start + n + 1, dataset.offsets[doc + 1])
                self.assertGreater(n, 0)
                self.assertEqual(tokens[start:start + n].tolist(), sample["input_ids"][:n].tolist())
                self.assertEqual(tokens[start + 1:start + n + 1].tolist(), sample["labels"][:n].tolist())
                self.assertTrue(torch.equal(sample["labels"][:n - 1], sample["input_ids"][1:n]))
                self.assertTrue(torch.all(sample["input_ids"][n:] == 0))
                self.assertTrue(torch.all(sample["labels"][n:] == IGNORE_INDEX))
                self.assertEqual([True] * n + [False] * (16 - n), sample["attention_mask"].tolist())
                seen.extend(range(start + 1, start + n + 1))
            expected = [index for a, b in zip(dataset.offsets[:-1], dataset.offsets[1:])
                        for index in range(int(a) + 1, int(b))]
            self.assertEqual(expected, seen)
            dataset.close()

    def test_loaders_seed_train_shuffle_eval_order_and_keep_last_batch(self):
        a = make_dataloaders(self.artifact, batch_size=3, seed=42)
        b = make_dataloaders(self.artifact, batch_size=3, seed=42)
        self.assertIsInstance(a["train"].sampler, RandomSampler)
        for split in SPLITS:
            self.assertFalse(a[split].drop_last)
            self.assertEqual(list(a[split].sampler), list(b[split].sampler))
            if split != "train":
                self.assertIsInstance(a[split].sampler, SequentialSampler)
            total = 0
            for batch in a[split]:
                self.assertEqual(torch.long, batch["input_ids"].dtype)
                self.assertEqual(torch.long, batch["labels"].dtype)
                self.assertEqual(torch.bool, batch["attention_mask"].dtype)
                self.assertEqual(16, batch["input_ids"].shape[1])
                total += len(batch["input_ids"])
            self.assertEqual(len(a[split].dataset), total)
            a[split].dataset.close()
            b[split].dataset.close()

    def test_ignored_padding_contributes_no_loss_or_gradient(self):
        dataset = NextTokenDataset(self.artifact, "test")
        sample = next(dataset[i] for i in range(len(dataset))
                      if dataset.window_info(i)["valid_targets"] < dataset.context_length)
        self.assertTrue(torch.any(sample["labels"] == IGNORE_INDEX))
        logits = torch.zeros((16, dataset.vocab_size), requires_grad=True)
        loss = torch.nn.functional.cross_entropy(logits, sample["labels"], ignore_index=IGNORE_INDEX)
        self.assertAlmostEqual(math.log(dataset.vocab_size), float(loss.detach()), places=5)
        loss.backward()
        self.assertTrue(torch.all(logits.grad[~sample["attention_mask"]] == 0))
        dataset.close()

    def test_spawn_serialization_reopens_memmap_and_copies_tensor_data(self):
        dataset = NextTokenDataset(self.artifact, "train")
        original = dataset[0]
        restored = pickle.loads(pickle.dumps(dataset))
        self.assertIsNone(restored._tokens)
        self.assertTrue(torch.equal(original["input_ids"], restored[0]["input_ids"]))
        original["input_ids"][0] = 999
        self.assertEqual(1, int(dataset[0]["input_ids"][0]))
        self.assertTrue(torch.equal(dataset[-1]["labels"], dataset[len(dataset) - 1]["labels"]))
        with self.assertRaises(IndexError):
            dataset[len(dataset)]
        dataset.close()
        restored.close()


@unittest.skipUnless(HAS_DATA, "Install ai/requirements.tinylm.txt")
class ReleasedPreparedDataTest(unittest.TestCase):
    def test_real_release_counts_and_frozen_source_binding(self):
        root = AI_ROOT / "artifacts/tinylm_data/1.0.0"
        metadata = load_prepared_data(root)
        tokenizer = AI_ROOT / "artifacts/tokenizer/1.0.0"
        audit = audit_corpus(AI_ROOT / "data/lm_corpus/1.2.0")
        self.assertEqual(audit, metadata["report"]["source_audit"])
        self.assertEqual(sha256(tokenizer / "manifest.json"),
                         metadata["manifest"]["tokenizer_manifest_sha256"])
        self.assertEqual(sha256(tokenizer / "private/tokenizer.json"),
                         metadata["manifest"]["tokenizer_sha256"])
        expected = json.loads((tokenizer / "report.json").read_text(encoding="utf-8"))["partitions"]
        for split in SPLITS:
            actual = metadata["report"]["partitions"][split]
            self.assertEqual(expected[split]["documents"], actual["documents"])
            self.assertEqual(expected[split]["tokens_with_bos_eos"], actual["stored_tokens"])
            self.assertEqual(expected[split]["raw_tokens"] + actual["documents"], actual["target_tokens"])
            self.assertEqual(0, actual["dropped_tokens"])
            self.assertEqual(0, actual["cross_document_sequences"])


if __name__ == "__main__":
    unittest.main()

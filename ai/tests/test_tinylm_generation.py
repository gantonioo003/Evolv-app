from __future__ import annotations

from dataclasses import replace
import importlib.util
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
HAS_TORCH = importlib.util.find_spec("torch") is not None
if HAS_TORCH:
    import numpy as np
    import torch
    from evolv_tinylm.data import prepare_data
    from evolv_tinylm.dataset import NextTokenDataset
    from evolv_tinylm.generation import GenerationConfig, filter_logits, generate, text_diagnostics
    from evolv_tinylm.lm_evaluation import StridedEvaluationDataset, evaluate_partition, perplexity
    from evolv_tinylm.tokenizer import EvolvTokenizer
    from evolv_tinylm.tokenizer_training import read_rows
    from test_tinylm_data import make_fixture

    class FakeTokenizer:
        vocab_size = 16

        def encode(self, text):
            return [7 + ord(character) % 8 for character in text]

        def decode(self, ids):
            return "".join(chr(97 + (index - 7) % 26) for index in ids if index >= 7)

    class FixedModel(torch.nn.Module):
        def __init__(self, *, eos=False, vocab_size=16, context_length=4, uniform=False):
            super().__init__()
            self.anchor = torch.nn.Parameter(torch.tensor(0.0))
            self.config = SimpleNamespace(vocab_size=vocab_size, context_length=context_length)
            self.eos, self.uniform, self.seen = eos, uniform, []

        def forward(self, input_ids, attention_mask):
            self.seen.append(input_ids.detach().cpu().tolist())
            logits = torch.zeros((*input_ids.shape, self.config.vocab_size), device=input_ids.device)
            if not self.uniform:
                logits[..., 6] = 100  # Forbidden role token must never be emitted.
                logits[..., 7], logits[..., 8] = 3, 2
                logits[..., 2] = 10 if self.eos else -20
            return {"logits": logits + self.anchor * 0}


@unittest.skipUnless(HAS_TORCH, "Install ai/requirements.tinylm-training.txt")
class GenerationTest(unittest.TestCase):
    def test_topk_and_nucleus_keep_correct_candidates_and_crossing_token(self):
        logits = torch.tensor([0.6, 0.3, 0.1]).log()
        self.assertEqual([True, True, False], torch.isfinite(filter_logits(logits, top_p=0.7)).tolist())
        self.assertEqual([True, False, False], torch.isfinite(filter_logits(logits, top_p=0.1)).tolist())
        self.assertEqual([True, True, False], torch.isfinite(filter_logits(logits, top_k=2)).tolist())
        torch.testing.assert_close(logits, filter_logits(logits, top_k=100))
        with self.assertRaises(ValueError):
            filter_logits(torch.tensor([float("-inf"), float("-inf")]))
        with self.assertRaises(ValueError):
            filter_logits(torch.tensor([0.0, float("nan")]))

    def test_eos_stop_and_special_token_suppression(self):
        tokenizer = FakeTokenizer()
        model = FixedModel(eos=True).train()
        result = generate(model, tokenizer, "oi", GenerationConfig(do_sample=False))
        self.assertEqual([2], result["generated_ids"])
        self.assertEqual("eos", result["stop_reason"])
        self.assertEqual("", result["continuation"])
        self.assertTrue(model.training)
        self.assertEqual(1, len(model.seen))
        result = generate(FixedModel(), tokenizer, "oi", GenerationConfig(max_new_tokens=8, do_sample=False))
        self.assertEqual([7] * 8, result["generated_ids"])
        self.assertTrue(all(index not in (0, 1, 3, 4, 5, 6) for index in result["generated_ids"]))

    def test_seeded_sampling_is_repeatable_without_changing_global_rng(self):
        model, tokenizer = FixedModel(), FakeTokenizer()
        before = torch.get_rng_state().clone()
        config = GenerationConfig(max_new_tokens=12, seed=123, top_p=1)
        a, b = generate(model, tokenizer, "a", config), generate(model, tokenizer, "a", config)
        self.assertEqual(a["generated_ids"], b["generated_ids"])
        self.assertTrue(torch.equal(before, torch.get_rng_state()))
        top_one = generate(model, tokenizer, "a", replace(config, top_k=1))
        greedy = generate(model, tokenizer, "a", replace(config, do_sample=False))
        self.assertEqual(top_one["generated_ids"], greedy["generated_ids"])

    def test_temperature_is_applied_before_sampling(self):
        received = []

        def draw(probabilities, count, generator):
            received.append(probabilities.clone())
            return torch.tensor([7])

        model, tokenizer = FixedModel(), FakeTokenizer()
        with patch("evolv_tinylm.generation.torch.multinomial", side_effect=draw):
            generate(model, tokenizer, "a", GenerationConfig(max_new_tokens=1, temperature=0.5, top_p=1))
            generate(model, tokenizer, "a", GenerationConfig(max_new_tokens=1, temperature=1.3, top_p=1))
        self.assertGreater(float(received[0][7]), float(received[1][7]))
        self.assertEqual(0, float(received[0][6]))

    def test_context_cropping_empty_prompt_and_zero_budget_are_explicit(self):
        model, tokenizer = FixedModel(), FakeTokenizer()
        result = generate(model, tokenizer, "abcdefghij", GenerationConfig(max_new_tokens=3, do_sample=False))
        self.assertEqual(7, result["prompt_tokens_outside_first_window"])
        self.assertEqual(3, result["steps_with_context_cropping"])
        self.assertTrue(all(len(batch[0]) <= 4 for batch in model.seen))
        self.assertEqual(tokenizer.encode("abcdefghij")[-4:], model.seen[0][0])
        model.seen.clear()
        result = generate(model, tokenizer, "", GenerationConfig(max_new_tokens=0))
        self.assertEqual([], model.seen)
        self.assertEqual(0, result["generated_tokens"])
        generate(model, tokenizer, "", GenerationConfig(max_new_tokens=1, do_sample=False))
        self.assertEqual([[1]], model.seen[0])

    def test_invalid_config_and_repetition_diagnostics(self):
        for options in ({"temperature": 0}, {"temperature": float("nan")}, {"top_p": 0},
                        {"top_p": 1.1}, {"top_k": True}, {"max_new_tokens": -1}, {"seed": -1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                GenerationConfig(**options)
        diagnostic = text_diagnostics("treino treino treino", [7, 7, 7, 2])
        self.assertEqual(0.5, diagnostic["repeated_bigram_fraction"])
        self.assertEqual(3, diagnostic["content_tokens"])
        self.assertTrue(text_diagnostics("", [2])["empty_completion"])

    @unittest.skipUnless(HAS_TORCH and torch.cuda.is_available(), "CUDA unavailable")
    def test_saved_real_greedy_sample_is_reproducible_on_the_recorded_gpu(self):
        from evolv_tinylm.training import load_trained_model
        evaluation = AI_ROOT / "artifacts/tinylm_evaluation/1.0.0"
        samples = [json.loads(line) for line in (evaluation / "private/generations.jsonl").read_text().splitlines()]
        saved = next(row for row in samples if row["prompt_id"] == "p06" and row["strategy_id"] == "greedy")
        model, _ = load_trained_model(AI_ROOT / "artifacts/tinylm_training/1.0.0", device="cuda")
        tokenizer = EvolvTokenizer.load(AI_ROOT / "artifacts/tokenizer/1.0.0")
        actual = generate(model, tokenizer, saved["prompt"], GenerationConfig(**saved["config"]))
        self.assertEqual(saved["generated_ids"], actual["generated_ids"])
        self.assertEqual(saved["continuation"], actual["continuation"])


@unittest.skipUnless(HAS_TORCH, "Install ai/requirements.tinylm-training.txt")
class LMEvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        corpus, tokenizer = make_fixture(cls.root)
        cls.corpus, cls.tokenizer = corpus, EvolvTokenizer.load(tokenizer)
        cls.data = cls.root / "prepared"
        prepare_data(corpus, tokenizer, cls.data, context_length=16)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_perplexity_definition_and_overflow(self):
        self.assertAlmostEqual(1, perplexity(0))
        self.assertAlmostEqual(2, perplexity(math.log(2)))
        self.assertIsNone(perplexity(1000))
        with self.assertRaises(ValueError):
            perplexity(-1)

    def test_strided_windows_score_each_target_once_and_only_with_past_context(self):
        for stride in (1, 8, 16):
            dataset = StridedEvaluationDataset(self.data, "train", stride)
            tokens = np.load(dataset.tokens_path, allow_pickle=False)
            seen = []
            for index in range(len(dataset)):
                info = dataset.window_info(index)
                sample = dataset[index]
                start, n = info["start"], info["valid_targets"]
                self.assertLessEqual(start + n + 1, dataset.offsets[info["document_index"] + 1])
                for column in torch.where(sample["labels"] != -100)[0].tolist():
                    self.assertEqual(int(tokens[start + column + 1]), int(sample["labels"][column]))
                    seen.append(start + column + 1)
                self.assertEqual(tokens[start:start + n].tolist(), sample["input_ids"][:n].tolist())
            expected = [index for a, b in zip(dataset.offsets[:-1], dataset.offsets[1:])
                        for index in range(int(a) + 1, int(b))]
            self.assertEqual(expected, seen)
            dataset.close()

    def test_uniform_model_gives_vocab_perplexity_and_matching_counts_for_both_methods(self):
        model = FixedModel(vocab_size=self.tokenizer.vocab_size, context_length=16, uniform=True).train()
        rows = list(read_rows(self.corpus / "train.jsonl"))
        measured = []
        for dataset in (NextTokenDataset(self.data, "train"), StridedEvaluationDataset(self.data, "train", 8)):
            metrics, docs, errors = evaluate_partition(model, dataset, rows, self.tokenizer,
                                                       batch_size=3, keep_errors=4)
            self.assertAlmostEqual(math.log(self.tokenizer.vocab_size), metrics["loss"], places=5)
            self.assertAlmostEqual(self.tokenizer.vocab_size, metrics["perplexity"], places=3)
            self.assertEqual(0, metrics["next_token_accuracy"])
            self.assertEqual(metrics["tokens"], sum(row["tokens"] for row in docs))
            self.assertTrue(all(row["target_id"] != row["predicted_id"] for row in errors))
            self.assertTrue(model.training)
            measured.append(metrics)
        self.assertEqual(measured[0]["tokens"], measured[1]["tokens"])


class ReleasedLMEvaluationTest(unittest.TestCase):
    def test_recorded_evaluation_counts_metrics_protocol_and_integrity(self):
        root = AI_ROOT / "artifacts/tinylm_evaluation/1.0.0"
        for manifest_name in ("manifest.json", "report_manifest.json"):
            manifest = json.loads((root / manifest_name).read_text(encoding="utf-8"))
            for name, expected in manifest["files"].items():
                self.assertEqual(expected["sha256"], hashlib.sha256((root / name).read_bytes()).hexdigest())
        core = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in core["source_sha256"].items():
            self.assertEqual(expected, hashlib.sha256((AI_ROOT / "src/evolv_tinylm" / name).read_bytes()).hexdigest())
        report = json.loads((root / "evaluation.json").read_text(encoding="utf-8"))
        self.assertEqual(0, report["optimizer_steps"])
        self.assertTrue(report["test_evaluated_without_updates"])
        self.assertTrue(report["inputs_preserved"])
        self.assertEqual(128, report["generation_samples"])
        protocol = json.loads((root / "protocol.json").read_text(encoding="utf-8"))
        frozen = json.loads((root / "frozen_selection.json").read_text(encoding="utf-8"))
        self.assertEqual(frozen["protocol_sha256"],
                         hashlib.sha256((AI_ROOT / "configs/tinylm.evaluation.v1.json").read_bytes()).hexdigest())
        self.assertLessEqual(frozen["frozen_before_test_at"], report["completed_at"])
        self.assertEqual(protocol["checkpoint_sha256"], frozen["checkpoint_sha256"])
        metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
        for split, expected_tokens in (("train", 2953717), ("validation", 21588), ("test", 14880)):
            for name in ("initial", "trained"):
                row = metrics["primary"][name][split]
                self.assertEqual(expected_tokens, row["tokens"])
                self.assertAlmostEqual(row["loss"], row["nll_sum"] / row["tokens"])
                self.assertAlmostEqual(math.exp(row["loss"]), row["perplexity"])
                if split != "train":
                    self.assertEqual(expected_tokens, metrics["strided_context"][name][split]["tokens"])
        samples = [json.loads(line) for line in (root / "private/generations.jsonl").read_text().splitlines()]
        self.assertEqual(128, len(samples))
        for row in samples:
            self.assertLessEqual(len(row["generated_ids"]), 64)
            self.assertTrue(all(index not in (0, 1, 3, 4, 5, 6) for index in row["generated_ids"]))
            if 2 in row["generated_ids"]:
                self.assertEqual(2, row["generated_ids"][-1])
        reviewed = json.loads((root / "qualitative_review.json").read_text(encoding="utf-8"))["samples"]
        expected = {(row["prompt_id"], row["strategy_id"]) for row in samples
                    if row["strategy_id"] in protocol["qualitative_review"]["strategy_ids"]
                    and row["config"]["seed"] == protocol["qualitative_review"]["seed"]}
        self.assertEqual(24, len(reviewed))
        self.assertEqual(expected, {(row["prompt_id"], row["strategy_id"]) for row in reviewed})


if __name__ == "__main__":
    unittest.main()

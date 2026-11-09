from __future__ import annotations

from dataclasses import replace
from contextlib import redirect_stdout
import importlib.util
import io
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
HAS_TORCH = importlib.util.find_spec("torch") is not None
if HAS_TORCH:
    import torch
    from evolv_tinylm.data import prepare_data
    from evolv_tinylm.model import TinyLM, TinyLMConfig
    from evolv_tinylm.training import (TrainingConfig, build_optimizer, evaluate_loss,
                                      load_trained_model, lr_factor, read_checkpoint,
                                      resolve_precision, train)
    from test_tinylm_data import make_fixture


@unittest.skipUnless(HAS_TORCH, "Install ai/requirements.tinylm-training.txt")
class TinyLMTrainingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        corpus, tokenizer = make_fixture(cls.root)
        cls.data = cls.root / "data"
        prepare_data(corpus, tokenizer, cls.data, context_length=16)
        vocab = json.loads((tokenizer / "manifest.json").read_text())["actual_vocab_size"]
        cls.model_config = TinyLMConfig(vocab_size=vocab, context_length=16, d_model=24,
                                       num_layers=1, num_heads=4, ffn_dim=48, dropout=0.2)
        cls.training_config = TrainingConfig(epochs=2, batch_size=16, learning_rate=0.003,
                                             warmup_fraction=0, patience=10, cpu_threads=1, log_every=1000)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        silence = redirect_stdout(io.StringIO())
        silence.__enter__()
        self.addCleanup(silence.__exit__, None, None, None)

    def test_adamw_groups_are_unique_and_exclude_biases_and_norms_from_decay(self):
        model = TinyLM(self.model_config)
        optimizer = build_optimizer(model, self.training_config, torch.device("cpu"))
        params = [parameter for group in optimizer.param_groups for parameter in group["params"]]
        self.assertEqual(len(params), len({id(parameter) for parameter in params}))
        self.assertEqual({id(parameter) for parameter in model.parameters()}, {id(parameter) for parameter in params})
        for group in optimizer.param_groups:
            for parameter in group["params"]:
                self.assertEqual(parameter.ndim >= 2, group["weight_decay"] > 0)

    def test_warmup_and_cosine_schedule_boundaries(self):
        self.assertAlmostEqual(0.25, lr_factor(0, 20, 4, 0.1))
        self.assertAlmostEqual(1, lr_factor(3, 20, 4, 0.1))
        self.assertAlmostEqual(1, lr_factor(4, 20, 4, 0.1))
        self.assertAlmostEqual(0.1, lr_factor(19, 20, 4, 0.1))
        self.assertAlmostEqual(0.1, lr_factor(25, 20, 4, 0.1))
        self.assertTrue(math.isfinite(lr_factor(0, 1, 0, 0.1)))

    def test_evaluation_is_token_weighted_and_restores_training_mode(self):
        class FixedLoss(torch.nn.Module):
            def forward(self, input_ids, labels):
                self.assert_eval = not self.training
                tokens = labels.ne(-100).sum()
                return {"loss_sum": input_ids[0, 0].float() * tokens, "valid_tokens": tokens}

        model = FixedLoss().train()
        loader = [{"input_ids": torch.tensor([[2, 0, 0]]), "labels": torch.tensor([[1, 1, 1]])},
                  {"input_ids": torch.tensor([[4, 0, 0]]), "labels": torch.tensor([[1, -100, -100]])}]
        result = evaluate_loss(model, loader, torch.device("cpu"), "float32")
        self.assertEqual(2.5, result["loss"])
        self.assertEqual(4, result["valid_tokens"])
        self.assertTrue(model.assert_eval)
        self.assertTrue(model.training)

    def test_checkpoint_resume_matches_uninterrupted_cpu_training_exactly(self):
        full = self.root / "full"
        split = self.root / "split"
        a = train(self.data, self.model_config, self.training_config, full, device="cpu")
        stopped = train(self.data, self.model_config, self.training_config, split, device="cpu", stop_after_epoch=1)
        self.assertEqual("stopped_at_epoch_boundary", stopped["status"])
        b = train(self.data, self.model_config, self.training_config, split, device="cpu", resume=True)
        self.assertEqual(a["optimizer_steps"], b["optimizer_steps"])
        self.assertEqual(a["best_validation_loss"], b["best_validation_loss"])
        first, second = read_checkpoint(full, "last"), read_checkpoint(split, "last")
        self.assertEqual(first["history"], second["history"])
        for name, tensor in first["model"].items():
            self.assertTrue(torch.equal(tensor, second["model"][name]), name)
        self.assertEqual(0, a["skipped_optimizer_updates"])
        self.assertFalse(a["reserved_test_evaluated"])
        self.assertLess(first["history"][-1]["train_loss_online"], first["history"][1]["train_loss_online"])
        loaded, selected = load_trained_model(full)
        self.assertFalse(loaded.training)
        self.assertEqual(a["best_epoch"], selected["epoch"])
        self.assertIs(loaded.token_embedding.weight, loaded.lm_head.weight)
        with self.assertRaises(ValueError):
            train(self.data, self.model_config, replace(self.training_config, epochs=3), full,
                  device="cpu", resume=True)
        with self.assertRaises(FileExistsError):
            train(self.data, self.model_config, self.training_config, full, device="cpu")

    def test_early_stop_selects_actual_lowest_validation_loss(self):
        output = self.root / "early"
        config = replace(self.training_config, epochs=8, patience=1, min_delta=100)
        result = train(self.data, self.model_config, config, output, device="cpu")
        self.assertEqual("early_stopped", result["status"])
        self.assertEqual(1, result["completed_epochs"])
        state = read_checkpoint(output, "last")
        minimum = min(state["history"], key=lambda item: item["validation_loss"])
        self.assertEqual(minimum["epoch"], result["best_epoch"])
        self.assertAlmostEqual(minimum["validation_loss"], result["reloaded_best_validation_loss"])
        index = json.loads((output / "checkpoint_index.json").read_text())
        path = output / index["last"]["file"]
        with path.open("ab") as handle:
            handle.write(b"alterado")
        with self.assertRaises(ValueError):
            read_checkpoint(output, "last")

    def test_invalid_training_settings_are_rejected(self):
        for options in ({"epochs": 0}, {"batch_size": True}, {"learning_rate": 0},
                        {"weight_decay": -1}, {"warmup_fraction": 1}, {"beta2": 1},
                        {"grad_clip_norm": 0}, {"min_delta": float("nan")}, {"seed": -1},
                        {"precision": "int8"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                replace(self.training_config, **options)
        self.assertEqual("float32", resolve_precision("auto", torch.device("cpu")))
        with self.assertRaises(ValueError):
            resolve_precision("float16", torch.device("cpu"))


class ReleasedTrainingArtifactsTest(unittest.TestCase):
    def test_recorded_run_and_all_checkpoint_hashes(self):
        root = AI_ROOT / "artifacts/tinylm_training/1.0.0"
        results = json.loads((root / "results.json").read_text(encoding="utf-8"))
        history = json.loads((root / "history.json").read_text(encoding="utf-8"))
        index = json.loads((root / "checkpoint_index.json").read_text(encoding="utf-8"))
        self.assertEqual("completed", results["status"])
        self.assertEqual(8, results["completed_epochs"])
        self.assertEqual(7816, results["optimizer_steps"])
        self.assertFalse(results["reserved_test_evaluated"])
        self.assertTrue(results["inputs_preserved"])
        self.assertEqual(0, results["skipped_optimizer_updates"])
        self.assertLess(results["best_validation_loss"], results["initial_validation_loss"])
        best = min(history, key=lambda row: row["validation_loss"])
        self.assertEqual(best["epoch"], results["best_epoch"])
        self.assertEqual(best["validation_loss"], results["reloaded_best_validation_loss"])
        self.assertEqual(results["best_checkpoint"], index["best"])
        for record in index["epochs"]:
            path = root / record["file"]
            with path.open("rb") as handle:
                self.assertEqual(record["sha256"], hashlib.file_digest(handle, "sha256").hexdigest())
            self.assertEqual(record["bytes"], path.stat().st_size)
        for name, expected in results["binding"]["sources"].items():
            self.assertEqual(expected, hashlib.sha256((AI_ROOT / "src/evolv_tinylm" / name).read_bytes()).hexdigest())


@unittest.skipUnless(HAS_TORCH, "Install ai/requirements.tinylm-training.txt")
class ReleasedTrainedModelTest(unittest.TestCase):
    def test_real_best_checkpoint_loads_on_cpu_and_preserves_tied_weights(self):
        model, selected = load_trained_model(AI_ROOT / "artifacts/tinylm_training/1.0.0")
        self.assertEqual(8, selected["epoch"])
        self.assertIs(model.lm_head.weight, model.token_embedding.weight)
        self.assertFalse(model.training)
        with torch.no_grad():
            output = model(torch.tensor([[1, 2138, 7639]]))
        self.assertEqual((1, 3, 8192), tuple(output["logits"].shape))
        self.assertTrue(torch.isfinite(output["logits"]).all())


if __name__ == "__main__":
    unittest.main()

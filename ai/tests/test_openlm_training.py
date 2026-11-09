"""Meaningful loss, accumulation, checkpoint and resume checks on disposable models."""
import copy
import math
from pathlib import Path
import random
import sys
import tempfile
from types import SimpleNamespace
import unittest

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_openlm.lora import attach_lora, load_lora_settings
from evolv_openlm.sft_data import read_json
from evolv_openlm.sft_dataset import SFTCollator
from evolv_openlm.training import atomic_json, causal_nll, evaluate_nll, fit, forward_nll, read_checkpoint, restore_adapter


class LossTests(unittest.TestCase):
    def test_masked_positions_and_single_shift(self):
        import torch
        logits = torch.tensor([[[math.log(.8), math.log(.2)]] * 4])
        labels = torch.tensor([[-100, -100, 0, 1]])
        loss, count = causal_nll(logits, labels)
        self.assertEqual(count, 2)
        self.assertAlmostEqual(loss.item(), -math.log(.8) - math.log(.2), places=6)

    def test_all_masked_is_an_error(self):
        import torch
        with self.assertRaisesRegex(ValueError, "sem tokens"):
            causal_nll(torch.zeros(1, 3, 4), torch.full((1, 3), -100))

    def test_validation_is_weighted_by_tokens_not_batches(self):
        import torch
        from torch.utils.data import DataLoader

        class Constant(torch.nn.Module):
            def forward(self, input_ids, attention_mask, use_cache=False, logits_to_keep=0):
                length = logits_to_keep or input_ids.shape[1]
                probs = torch.tensor([math.log(.8), math.log(.2)])
                return SimpleNamespace(logits=probs.expand(input_ids.shape[0], length, 2))
        rows = [{"input_ids": [1, 0, 0], "attention_mask": [1, 1, 1], "labels": [-100, 0, 0]},
                {"input_ids": [1, 1], "attention_mask": [1, 1], "labels": [-100, 1]}]
        model = Constant()
        model.train()
        for batch_size in [1, 2]:
            loader = DataLoader(rows, batch_size=batch_size, collate_fn=SFTCollator(0))
            result = evaluate_nll(model, loader, "cpu")
            self.assertEqual(result["target_tokens"], 3)
            self.assertAlmostEqual(result["nll"], (-2 * math.log(.8) - math.log(.2)) / 3, places=6)
            self.assertTrue(model.training)

    def test_target_only_logits_equal_full_hf_loss(self):
        import torch
        from transformers import AutoModelForCausalLM, Qwen3Config
        torch.manual_seed(101)
        model = AutoModelForCausalLM.from_config(Qwen3Config(vocab_size=64, hidden_size=32,
            intermediate_size=64, num_hidden_layers=1, num_attention_heads=2,
            num_key_value_heads=1, head_dim=16, max_position_embeddings=64))
        model.eval()
        ids = torch.tensor([[1, 10, 11, 12, 13, 14]])
        batch = {"input_ids": ids, "attention_mask": torch.ones_like(ids),
                 "labels": torch.tensor([[-100, -100, -100, -100, 13, 14]])}
        with torch.no_grad():
            full = model(**batch).loss
            optimized, count = forward_nll(model, batch)
        self.assertEqual(count, 2)
        self.assertAlmostEqual(optimized.item() / count, full.item(), places=6)


class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        cls.previous_threads = torch.get_num_threads()
        torch.set_num_threads(2)

    @classmethod
    def tearDownClass(cls):
        import torch
        torch.set_num_threads(cls.previous_threads)

    def settings(self):
        settings = copy.deepcopy(load_lora_settings())
        settings["model_id"] = "random-tiny-qwen-test-only"
        settings["model_revision"] = "disposable"
        settings["training"].update(num_train_epochs=2, gradient_accumulation_steps=2,
            learning_rate=0.003, weight_decay=0.0, warmup_ratio=0.0, logging_steps=20)
        settings["early_stopping"]["patience"] = 10
        return settings

    def model(self, settings):
        import torch
        from transformers import AutoModelForCausalLM, Qwen3Config
        random.seed(42)
        torch.manual_seed(42)
        base = AutoModelForCausalLM.from_config(Qwen3Config(vocab_size=64, hidden_size=32,
            intermediate_size=64, num_hidden_layers=1, num_attention_heads=2,
            num_key_value_heads=1, head_dim=16, max_position_embeddings=64,
            pad_token_id=0, bos_token_id=1, eos_token_id=2, tie_word_embeddings=True))
        return attach_lora(base, settings, require_quantized=False)[0]

    def rows(self):
        result = []
        for i, targets in enumerate([1, 2, 3, 4, 2]):
            ids = [1, 10 + i, 20 + i] + [30 + i] * targets
            result.append({"input_ids": ids, "attention_mask": [1] * len(ids),
                           "labels": [-100] * 3 + ids[3:]})
        return result

    def test_resume_matches_uninterrupted_and_keeps_partial_group(self):
        import torch
        from safetensors.torch import load_file
        settings = self.settings()
        rows = self.rows()
        binding = {"fixture": "tiny", "settings": settings}
        with tempfile.TemporaryDirectory() as directory:
            full, resumed = Path(directory) / "full", Path(directory) / "resumed"
            model = self.model(settings)
            result = fit(model, rows, rows[:2], SFTCollator(0), settings, full, binding, device="cpu")
            self.assertEqual(result["optimizer_steps"], 6)
            self.assertEqual(result["plan"]["last_accumulation_microbatches"], 1)
            model = self.model(settings)
            partial = fit(model, rows, rows[:2], SFTCollator(0), settings, resumed, binding,
                          device="cpu", stop_after_epoch=1)
            self.assertEqual(partial["status"], "interrupted_for_resume")
            model = self.model(settings)
            done = fit(model, rows, rows[:2], SFTCollator(0), settings, resumed, binding,
                       device="cpu", resume=True)
            self.assertEqual(done["optimizer_steps"], 6)
            self.assertAlmostEqual(done["final_validation"]["nll"], result["final_validation"]["nll"], places=7)
            a, _ = read_checkpoint(full, "last")
            b, _ = read_checkpoint(resumed, "last")
            left, right = load_file(str(a / "adapter_model.safetensors")), load_file(str(b / "adapter_model.safetensors"))
            self.assertEqual(set(left), set(right))
            self.assertTrue(all(torch.equal(left[k], right[k]) for k in left))
            self.assertFalse(done["test_evaluated"])
            self.assertLessEqual(len(list((resumed / "private/checkpoints").glob("epoch_*"))), 2)
            with self.assertRaisesRegex(ValueError, "completo"):
                fit(model, rows, rows[:2], SFTCollator(0), settings, resumed, binding, device="cpu", resume=True)

    def test_checkpoint_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            atomic_json(Path(directory) / "checkpoint_index.json", {"last": {"path": "../outside", "files": {}}})
            with self.assertRaisesRegex(ValueError, "fora do diretório"):
                read_checkpoint(directory)

    def test_accumulation_matches_a_token_weighted_combined_batch(self):
        import torch
        from safetensors.torch import load_file
        from peft import get_peft_model_state_dict
        from evolv_openlm.lora import make_optimizer
        settings = self.settings()
        settings["training"].update(num_train_epochs=1, gradient_accumulation_steps=3)
        settings["adapter"]["lora_dropout"] = 0.0
        rows = self.rows()[:3]
        reference = self.model(settings)
        batch = SFTCollator(0)(rows)
        optimizer = make_optimizer(reference, settings)
        reference(**batch, use_cache=False).loss.backward()
        torch.nn.utils.clip_grad_norm_([p for p in reference.parameters() if p.requires_grad], settings["training"]["max_grad_norm"])
        optimizer.step()
        expected = get_peft_model_state_dict(reference)
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            fit(self.model(settings), rows, rows, SFTCollator(0), settings, run,
                {"fixture": "weighted-accumulation"}, device="cpu")
            path, _ = read_checkpoint(run, "last")
            actual = load_file(str(path / "adapter_model.safetensors"))
            self.assertEqual(set(expected), set(actual))
            self.assertTrue(all(torch.allclose(expected[k], actual[k], atol=2e-6, rtol=1e-5) for k in expected))

    def test_checkpoint_corruption_is_rejected_before_loading(self):
        from evolv_openlm.training import atomic_torch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "private/checkpoints/epoch_0000"
            path.mkdir(parents=True)
            atomic_torch(path / "trainer_state.pt", {"epoch": 0})
            atomic_json(root / "checkpoint_index.json", {"last": {"epoch": 0,
                "path": "private/checkpoints/epoch_0000", "files": {"trainer_state.pt": "wrong-hash"}}})
            with self.assertRaisesRegex(ValueError, "corrompido"):
                read_checkpoint(root)

    def test_changed_binding_is_rejected(self):
        settings = self.settings()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            root.mkdir()
            atomic_json(root / "binding.json", {"original": True})
            with self.assertRaisesRegex(ValueError, "mudaram"):
                fit(self.model(settings), self.rows(), self.rows()[:2], SFTCollator(0), settings,
                    root, {"changed": True}, device="cpu", resume=True)

    def test_no_validation_improvement_keeps_epoch_zero(self):
        settings = self.settings()
        settings["training"].update(num_train_epochs=4, learning_rate=1e-30)
        settings["early_stopping"]["patience"] = 2
        rows = self.rows()[:1]
        with tempfile.TemporaryDirectory() as directory:
            result = fit(self.model(settings), rows, rows, SFTCollator(0), settings,
                Path(directory) / "run", {"fixture": "no-promotion-without-improvement"}, device="cpu")
            self.assertEqual(result["selected_epoch"], 0)
            self.assertEqual(result["epochs_completed"], 2)
            self.assertTrue(result["early_stopped"])
            self.assertFalse(result["validation_improved_over_initial_adapter"])

    def test_report_uses_recorded_metrics_without_a_test_score(self):
        from evolv_openlm.training_report import render
        settings = self.settings()
        settings["training"]["num_train_epochs"] = 1
        rows = self.rows()[:1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            fit(self.model(settings), rows, rows, SFTCollator(0), settings, root,
                {"fixture": "report-only"}, device="cpu")
            render(root)
            report = (root / "RESULTS.md").read_text(encoding="utf-8")
            self.assertIn("teste reservado não foi avaliado", report)
            self.assertFalse(read_json(root / "report_manifest.json")["test_evaluated"])

    def test_native_loop_with_quantized_tiny_qwen_on_gpu(self):
        import gc
        import torch
        from transformers import AutoModelForCausalLM, BitsAndBytesConfig, Qwen3Config
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            self.skipTest("CUDA/BF16 não disponíveis.")
        settings = self.settings()
        settings["training"]["num_train_epochs"] = 1
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = Qwen3Config(vocab_size=64, hidden_size=32, intermediate_size=64,
                num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1,
                head_dim=16, max_position_embeddings=64, tie_word_embeddings=True,
                pad_token_id=0, bos_token_id=1, eos_token_id=2)
            base = AutoModelForCausalLM.from_config(config).to(torch.bfloat16)
            base.save_pretrained(root / "model", safe_serialization=True)
            del base
            model = AutoModelForCausalLM.from_pretrained(root / "model", local_files_only=True,
                device_map={"": 0}, dtype=torch.bfloat16, attn_implementation="sdpa",
                quantization_config=BitsAndBytesConfig(load_in_4bit=True,
                    bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=torch.bfloat16))
            model, _ = attach_lora(model, settings)
            rows = self.rows()[:3]
            result = fit(model, rows, rows[:1], SFTCollator(0), settings, root / "run",
                {"fixture": "NF4-BF16-native-loop-only"}, device="cuda")
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["optimizer_steps"], 2)
            self.assertTrue(math.isfinite(result["final_validation"]["nll"]))
            self.assertGreater(result["memory"]["peak_allocated_mib"], 0)
            del model
            gc.collect()
            torch.cuda.empty_cache()


if __name__ == "__main__":
    unittest.main()

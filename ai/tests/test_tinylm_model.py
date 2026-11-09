from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
HAS_TORCH = importlib.util.find_spec("torch") is not None
if HAS_TORCH:
    import torch
    from torch.nn import functional as F
    from evolv_tinylm.model import CausalSelfAttention, TinyLM, TinyLMConfig


@unittest.skipUnless(HAS_TORCH, "Install ai/requirements.tinylm-training.txt")
class TinyLMTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_threads = torch.get_num_threads()
        torch.set_num_threads(2)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.previous_threads)

    def setUp(self):
        torch.manual_seed(7)
        self.config = TinyLMConfig(vocab_size=64, context_length=8, d_model=24,
                                   num_layers=2, num_heads=4, ffn_dim=96, dropout=0.2)
        self.model = TinyLM(self.config).eval()

    def test_future_tokens_cannot_change_prefix_logits(self):
        x = torch.tensor([[1, 9, 10, 11, 12, 13]])
        changed = x.clone()
        changed[:, 3:] = torch.tensor([24, 25, 26])
        with torch.no_grad():
            before = self.model(x)["logits"]
            after = self.model(changed)["logits"]
        torch.testing.assert_close(before[:, :3], after[:, :3], rtol=0, atol=1e-7)
        self.assertGreater(float((before[:, 3:] - after[:, 3:]).abs().max()), 1e-4)

    def test_attention_gradient_cannot_reach_future_inputs(self):
        attention = CausalSelfAttention(self.config).eval()
        x = torch.randn(1, 6, self.config.d_model, requires_grad=True)
        mask = torch.ones((1, 6), dtype=torch.bool)
        attention(x, mask)[:, :3].square().sum().backward()
        self.assertTrue(torch.all(x.grad[:, 3:] == 0))
        self.assertGreater(float(x.grad[:, :3].abs().sum()), 0)

    def test_padding_and_masked_token_contents_cannot_affect_real_outputs(self):
        x = torch.tensor([[1, 9, 10]])
        padded = torch.tensor([[1, 9, 10, 0, 0, 0]])
        mask = torch.tensor([[True, True, True, False, False, False]])
        changed_padding = torch.tensor([[1, 9, 10, 40, 41, 42]])
        with torch.no_grad():
            short = self.model(x)["logits"]
            long = self.model(padded, mask)["logits"]
            changed = self.model(changed_padding, mask)["logits"]
            inferred_mask = self.model(padded)["logits"]
        torch.testing.assert_close(short, long[:, :3], rtol=1e-5, atol=1e-6)
        torch.testing.assert_close(long, changed, rtol=0, atol=0)
        torch.testing.assert_close(long, inferred_mask, rtol=0, atol=0)
        self.assertTrue(torch.all(long[:, 3:] == 0))

    def test_different_batch_rows_do_not_share_attention(self):
        x = torch.tensor([[1, 9, 10], [1, 20, 21]])
        changed = x.clone()
        changed[1] = torch.tensor([1, 30, 31])
        with torch.no_grad():
            before = self.model(x)["logits"]
            after = self.model(changed)["logits"]
        torch.testing.assert_close(before[0], after[0], rtol=0, atol=0)

    def test_pre_shifted_labels_loss_and_zero_gradient_at_ignored_positions(self):
        x = torch.tensor([[1, 9, 10, 0, 0], [1, 11, 12, 13, 0]])
        mask = x.ne(0)
        labels = torch.tensor([[9, -100, 2, 50, 51], [11, 12, 13, 2, 52]])
        output = self.model(x, mask, labels)
        targets = labels.masked_fill(~mask, -100)
        expected = F.cross_entropy(output["logits"].reshape(-1, 64), targets.reshape(-1),
                                   ignore_index=-100, reduction="sum")
        self.assertEqual(6, int(output["valid_tokens"]))
        torch.testing.assert_close(output["loss_sum"], expected)
        torch.testing.assert_close(output["loss"], expected / 6)
        output["logits"].retain_grad()
        output["loss"].backward()
        self.assertTrue(torch.all(output["logits"].grad[targets == -100] == 0))
        gradients = [parameter.grad for parameter in self.model.parameters()]
        self.assertTrue(all(grad is not None and torch.isfinite(grad).all() for grad in gradients))
        self.assertGreater(sum(float(grad.abs().sum()) for grad in gradients), 0)

    def test_all_ignored_labels_have_differentiable_zero_loss(self):
        x = torch.tensor([[1, 9, 10]])
        output = self.model(x, labels=torch.full_like(x, -100))
        self.assertEqual(0, int(output["valid_tokens"]))
        self.assertEqual(0, float(output["loss"].detach()))
        output["loss"].backward()
        self.assertTrue(all(parameter.grad is not None and torch.isfinite(parameter.grad).all()
                            for parameter in self.model.parameters()))

    def test_eval_disables_all_dropout_and_train_mode_activates_it(self):
        x = torch.tensor([[1, 9, 10, 11, 12]])
        with torch.no_grad():
            first = self.model(x)["logits"]
            second = self.model(x)["logits"]
            torch.testing.assert_close(first, second, rtol=0, atol=0)
            self.model.train()
            first_train = self.model(x)["logits"]
            second_train = self.model(x)["logits"]
        self.assertFalse(torch.equal(first_train, second_train))

    def test_shared_weights_and_state_dict_roundtrip(self):
        self.assertIs(self.model.token_embedding.weight, self.model.lm_head.weight)
        untied = TinyLM(replace(self.config, tie_embeddings=False))
        self.assertEqual(self.config.vocab_size * self.config.d_model,
                         untied.parameter_summary()["total"] - self.model.parameter_summary()["total"])
        buffer = io.BytesIO()
        torch.save(self.model.state_dict(), buffer)
        buffer.seek(0)
        restored = TinyLM(TinyLMConfig(**self.config.to_dict())).eval()
        restored.load_state_dict(torch.load(buffer, map_location="cpu", weights_only=True))
        self.assertIs(restored.token_embedding.weight, restored.lm_head.weight)
        x = torch.tensor([[1, 9, 10]])
        with torch.no_grad():
            torch.testing.assert_close(self.model(x)["logits"], restored(x)["logits"], rtol=0, atol=0)

    def test_configuration_and_context_limits_reject_invalid_values(self):
        for options in ({"d_model": 25}, {"num_heads": 0}, {"ffn_dim": -1},
                        {"num_layers": True}, {"dropout": float("nan")}, {"dropout": 1},
                        {"layer_norm_eps": 0}, {"tie_embeddings": 1},
                        {"pad_token_id": 64}, {"ignore_index": 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                replace(self.config, **options)
        for x in (torch.zeros((0, 3), dtype=torch.long), torch.zeros((1, 0), dtype=torch.long),
                  torch.ones((1, 9), dtype=torch.long), torch.ones((1, 3)),
                  torch.tensor([[1, 64]]), torch.tensor([[1, -1]])):
            with self.assertRaises(ValueError):
                self.model(x)
        self.assertEqual((1, 1, 64), tuple(self.model(torch.tensor([[1]]))["logits"].shape))
        self.assertEqual((1, 8, 64), tuple(self.model(torch.ones((1, 8), dtype=torch.long))["logits"].shape))

    def test_bad_masks_and_labels_are_rejected(self):
        x = torch.tensor([[1, 9, 10]])
        for mask in (torch.ones((1, 3)), torch.ones((1, 2), dtype=torch.bool),
                     torch.tensor([[False, True, True]]), torch.tensor([[True, False, True]]),
                     torch.zeros((1, 3), dtype=torch.bool)):
            with self.assertRaises(ValueError):
                self.model(x, mask)
        for labels in (torch.ones((1, 2), dtype=torch.long), torch.ones((1, 3)),
                       torch.tensor([[9, 10, 64]]), torch.tensor([[9, -1, 2]])):
            with self.assertRaises(ValueError):
                self.model(x, labels=labels)
        result = self.model(x)
        self.assertIsNone(result["loss"])
        self.assertIsNone(result["loss_sum"])
        self.assertIsNone(result["valid_tokens"])

    def test_released_config_parameter_count_and_data_compatibility(self):
        config = TinyLMConfig.load(AI_ROOT / "configs/tinylm.v1.json")
        model = TinyLM(config)
        summary = model.parameter_summary()
        self.assertEqual(3_401_856, summary["total"])
        self.assertEqual(summary["total"], sum(summary["by_component_unique_parameters"].values()))
        data = json.loads((AI_ROOT / "artifacts/tinylm_data/1.0.0/config.json").read_text(encoding="utf-8"))
        config.validate_data_config(data)
        for key, value in (("vocab_size", 100), ("context_length", 128),
                           ("ignore_index", -1), ("target_shift", 2), ("right_padding", False)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                config.validate_data_config({**data, key: value})

    @unittest.skipUnless(HAS_TORCH and torch.cuda.is_available(), "CUDA unavailable")
    def test_cuda_autocast_forward_backward_is_finite(self):
        model = TinyLM(self.config).to("cuda").train()
        x = torch.tensor([[1, 9, 10, 0]], device="cuda")
        labels = torch.tensor([[9, 10, 2, -100]], device="cuda")
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        with torch.autocast(device_type="cuda", dtype=dtype):
            output = model(x, labels=labels)
        self.assertTrue(torch.isfinite(output["loss"]))
        output["loss"].backward()
        self.assertTrue(all(parameter.grad is not None and torch.isfinite(parameter.grad).all()
                            for parameter in model.parameters()))


class ReleasedArchitectureTest(unittest.TestCase):
    def test_saved_smoke_report_and_inputs_match_current_files(self):
        def digest(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()

        root = AI_ROOT / "artifacts/tinylm/1.0.0"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("architecture_verified_untrained", manifest["status"])
        for name, expected in manifest["files"].items():
            self.assertEqual(expected["sha256"], digest(root / name))
        for name, expected in manifest["source_sha256"].items():
            self.assertEqual(expected, digest(AI_ROOT / name))
        report = json.loads((root / "smoke_report.json").read_text(encoding="utf-8"))
        self.assertEqual("train", report["data_partition_used"])
        self.assertEqual(report["config_sha256"], digest(AI_ROOT / "configs/tinylm.v1.json"))
        self.assertEqual(report["prepared_data_manifest_sha256"],
                         digest(AI_ROOT / "artifacts/tinylm_data/1.0.0/manifest.json"))
        for check in report["checks"]:
            self.assertEqual([16, 256, 8192], check["logits_shape"])
            self.assertEqual(3_401_856, check["parameter_summary"]["total"])
            self.assertEqual(0, check["optimizer_steps"])
            self.assertFalse(check["weights_saved"])
            self.assertTrue(check["gradients_finite"])
            self.assertLessEqual(check["causal_prefix_max_difference"], 2e-5)
            self.assertLessEqual(check["padding_prefix_max_difference"], 2e-5)


if __name__ == "__main__":
    unittest.main()

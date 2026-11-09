"""QLoRA recipe guards and provenance checks; no repeated GPU training probe."""
import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_openlm.lora import attach_lora, load_lora_settings, make_optimizer, target_geometry, training_plan
from evolv_openlm.sft_data import read_json, sha, write_json


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.settings = load_lora_settings()

    def invalid(self, change, message):
        config = copy.deepcopy(self.settings)
        change(config)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            write_json(path, config)
            with self.assertRaisesRegex(ValueError, message):
                load_lora_settings(path)

    def test_zero_rank_is_rejected(self):
        self.invalid(lambda c: c["adapter"].update(r=0), "Rank")

    def test_embeddings_are_not_adapter_targets(self):
        self.invalid(lambda c: c["adapter"].update(target_modules=["embed_tokens"]), "sete projeções")

    def test_base_bias_training_is_rejected(self):
        self.invalid(lambda c: c["adapter"].update(bias="all"), "Bias")

    def test_initial_nonidentity_is_rejected(self):
        self.invalid(lambda c: c["adapter"].update(init_lora_weights=False), "identidade")

    def test_nonfinite_lr_is_rejected(self):
        self.invalid(lambda c: c["training"].update(learning_rate=float("nan")), "Learning rate")

    def test_test_metric_cannot_choose_checkpoint(self):
        self.invalid(lambda c: c["training"].update(metric_for_best_model="test_loss"), "validação")

    def test_real_plan_preserves_partial_accumulation(self):
        plan = training_plan(335, self.settings)
        self.assertEqual(plan["optimizer_steps_per_epoch"], 21)
        self.assertEqual(plan["planned_optimizer_steps_max"], 63)
        self.assertEqual(plan["warmup_steps"], 7)
        self.assertEqual(plan["last_accumulation_microbatches"], 15)

    def test_single_example_still_updates_and_multi_gpu_is_rejected(self):
        self.assertEqual(training_plan(1, self.settings)["optimizer_steps_per_epoch"], 1)
        with self.assertRaisesRegex(ValueError, "única GPU"):
            training_plan(335, self.settings, world_size=2)

    def test_missing_projection_is_rejected(self):
        targets = self.settings["adapter"]["target_modules"][:-1]
        model = SimpleNamespace(config=SimpleNamespace(num_hidden_layers=1),
            named_modules=lambda: [("layer." + t, SimpleNamespace(in_features=64, out_features=64)) for t in targets])
        with self.assertRaisesRegex(ValueError, "Quantidade"):
            target_geometry(model, self.settings)

    def test_real_attach_requires_four_bit_loading(self):
        with self.assertRaisesRegex(ValueError, "4 bits"):
            attach_lora(SimpleNamespace(is_loaded_in_4bit=False), self.settings)

    def test_optimizer_refuses_ordinary_unfrozen_model(self):
        import torch
        with self.assertRaisesRegex(ValueError, "fora dos adaptadores"):
            make_optimizer(torch.nn.Linear(4, 4), self.settings)


class ConfigurationArtifactTests(unittest.TestCase):
    root = AI_ROOT / "artifacts/openlm_lora/1.0.0"

    def test_outputs_code_and_frozen_data_match_manifest(self):
        manifest = read_json(self.root / "manifest.json")
        for name, expected in manifest["outputs"].items():
            self.assertEqual(sha(self.root / name), expected, name)
        for name, expected in manifest["code"].items():
            self.assertEqual(sha(AI_ROOT / name), expected, name)
        self.assertEqual(sha(AI_ROOT / "data/sft/1.0.0/manifest.json"), manifest["inputs"]["data_manifest"])
        self.assertEqual(sha(AI_ROOT / "configs/openlm.lora.v1.json"), manifest["inputs"]["lora_config"])

    def test_metadata_geometry_and_exported_arguments(self):
        report = read_json(self.root / "configuration_report.json")
        self.assertEqual(report["structure"]["targeted_projections"], 252)
        self.assertEqual(report["structure"]["trainable_parameters"], 16515072)
        self.assertTrue(report["structure"]["all_parameters_on_meta"])
        self.assertFalse(report["structure"]["pretrained_weights_loaded"])
        arguments = read_json(self.root / "training_arguments.json")
        self.assertEqual(arguments["warmup_steps"], 7)
        self.assertEqual(arguments["metric_for_best_model"], "eval_token_nll")
        self.assertEqual(report["test_examples_loaded"], 0)

    def test_disposable_probe_never_claims_real_model_training(self):
        report = read_json(self.root / "configuration_report.json")
        probe = report["tiny_gpu_check"]
        self.assertTrue(probe["only_lora_trainable"])
        self.assertTrue(probe["frozen_base_unchanged_after_step"])
        self.assertEqual(probe["initial_identity_max_delta"], 0)
        self.assertGreater(probe["changed_adapter_tensors"], 0)
        self.assertEqual(probe["toy_optimizer_steps"], 1)
        self.assertEqual(report["real_model_optimizer_steps"], 0)
        self.assertFalse(report["real_model_vram_measured"])
        self.assertFalse(report["ready_to_start_real_training"])
        self.assertFalse((self.root / "adapter_model.safetensors").exists())


if __name__ == "__main__":
    unittest.main()

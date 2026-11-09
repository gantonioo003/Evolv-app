"""Inspect adapter structure and training settings without loading 4B weights."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_openlm.runtime import DEFAULT_CACHE, load_settings
from evolv_openlm.lora import DEFAULT_LORA_CONFIG, load_lora_settings, make_callbacks, make_peft_config, make_training_arguments, structural_report, training_plan
from evolv_openlm.sft_data import read_json, sha, write_json
from evolv_openlm.sft_dataset import SFTDataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_LORA_CONFIG)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=AI_ROOT / "artifacts/openlm_lora/1.0.0")
    parser.add_argument("--check-tiny-gpu", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Relatório já existe. Escolha uma pasta nova.")
    settings = load_lora_settings(args.config)
    model_settings = load_settings()
    data_root = AI_ROOT / settings["data_release"]
    manifest = read_json(data_root / "manifest.json")
    for path in ["configs/openlm.v1.json", "configs/openlm.data.v1.json"]:
        if sha(AI_ROOT / path) != manifest["sources"][path]:
            raise ValueError("Configuração base diferente da versão usada nos dados.")
    if sha(data_root / "report.json") != manifest["outputs"]["report.json"]:
        raise ValueError("Relatório de dados diferente do manifesto.")
    data_config = read_json(data_root / "config.json")
    if settings["max_sequence_length"] != data_config["max_sequence_length"]:
        raise ValueError("Limite de sequência diferente da versão de dados.")
    train, validation = SFTDataset(data_root, "train"), SFTDataset(data_root, "validation")
    plan = training_plan(len(train), settings)
    print("Conferindo estrutura do Qwen em meta (sem pesos)...", flush=True)
    structure = structural_report(settings, args.cache_dir)
    arguments = make_training_arguments(settings, "ai/artifacts/openlm_training/1.0.0", len(train))
    callbacks = make_callbacks(settings)
    toy = None
    if args.check_tiny_gpu:
        print("Testando QLoRA em um Qwen minúsculo descartável na GPU...", flush=True)
        from evolv_openlm.lora_checks import tiny_quantized_check
        toy = tiny_quantized_check(settings)
    snapshot = args.cache_dir / ("models--" + model_settings["model_id"].replace("/", "--")) / "snapshots" / model_settings["revision"]
    required_weights = [f"model-{i:05d}-of-00003.safetensors" for i in range(1, 4)]
    missing = [name for name in required_weights + ["model.safetensors.index.json"] if not (snapshot / name).exists()]
    report = {"phase": "7.04.3", "version": settings["version"],
              "created_at": datetime.now(timezone.utc).isoformat(),
              "model_id": settings["model_id"], "model_revision": settings["model_revision"],
              "adapter": settings["adapter"], "structure": structure, "training_plan": plan,
              "validation_conversations": len(validation), "test_examples_loaded": 0,
              "early_stopping": settings["early_stopping"], "callbacks": [type(c).__name__ for c in callbacks],
              "tiny_gpu_check": toy, "real_model_optimizer_steps": 0,
              "real_model_forward_executed": False, "real_model_vram_measured": False,
              "ready_to_start_real_training": False,
              "pending": ["Complete official weights", "Measure actual 4B forward/backward and optimizer memory", "Implement token-weighted validation loop in phase 7.04.4"],
              "missing_checkpoint_files": missing,
              "packages": {k: version(k) for k in ["torch", "transformers", "peft", "accelerate", "bitsandbytes"]}}
    args.output.mkdir(parents=True)
    make_peft_config(settings).save_pretrained(str(args.output))
    write_json(args.output / "training_arguments.json", arguments.to_dict())
    write_json(args.output / "recipe.json", settings)
    write_json(args.output / "configuration_report.json", report)
    files = {p.name: sha(p) for p in args.output.iterdir() if p.is_file()}
    write_json(args.output / "manifest.json", {
        "inputs": {"lora_config": sha(args.config), "model_config": sha(AI_ROOT / "configs/openlm.v1.json"),
                   "data_manifest": sha(data_root / "manifest.json"), "data_report": sha(data_root / "report.json"),
                   "qwen_architecture": sha(snapshot / "config.json")},
        "outputs": files,
        "code": {str(p.relative_to(AI_ROOT).as_posix()): sha(p) for p in [Path(__file__), AI_ROOT / "src/evolv_openlm/lora.py", AI_ROOT / "src/evolv_openlm/lora_checks.py"]}})
    print(json.dumps({"trainable_parameters": structure["trainable_parameters"],
                      "trainable_percent_of_base": structure["trainable_percent_of_base"],
                      "targeted_projections": structure["targeted_projections"], "training_plan": plan,
                      "tiny_gpu_check": toy, "missing_checkpoint_files": missing}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

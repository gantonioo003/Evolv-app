"""Train the pinned local QLoRA recipe; no frozen test evaluation or app writes."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import random
import sys
import time

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_openlm.runtime import DEFAULT_CACHE, load_model, load_settings
from evolv_openlm.lora import DEFAULT_LORA_CONFIG, attach_lora, load_lora_settings
from evolv_openlm.sft_data import read_json, sha
from evolv_openlm.sft_dataset import SFTCollator, SFTDataset
from evolv_openlm.training import atomic_json, evaluate_nll, fit


def train(args):
    import torch
    from torch.utils.data import DataLoader
    settings = load_lora_settings(args.config)
    if args.output.exists() and not args.resume:
        raise FileExistsError("Run existente. Use --resume ou escolha uma pasta nova.")
    if (args.output / "results.json").exists() and read_json(args.output / "results.json")["status"] == "complete":
        raise ValueError("Run já completo; não continuar treinando a mesma versão.")
    model_settings = load_settings()
    if (settings["model_id"], settings["model_revision"]) != (model_settings["model_id"], model_settings["revision"]):
        raise ValueError("Modelo/revisão da receita diferente do runtime.")
    snapshot = args.cache_dir / ("models--" + settings["model_id"].replace("/", "--")) / "snapshots" / settings["model_revision"]
    index_path = snapshot / "model.safetensors.index.json"
    if not index_path.exists():
        raise FileNotFoundError("Pesos incompletos. Execute com --download para completar antes de treinar.")
    weight_files = sorted(set(read_json(index_path)["weight_map"].values()))
    if not weight_files or any(Path(n).name != n or not (snapshot / n).is_file() for n in weight_files):
        raise FileNotFoundError("Faltam safetensors completos da revisão escolhida.")
    print("Conferindo hashes dos pesos e dos dados...", flush=True)
    weights = {name: sha(snapshot / name) for name in weight_files}
    expected = read_json(AI_ROOT / "configs/openlm.weights.v1.json")
    if (expected["model_id"], expected["revision"]) != (settings["model_id"], settings["model_revision"]):
        raise ValueError("Manifesto de pesos corresponde a outro modelo/revisão.")
    if set(weights) != set(expected["files"]) or any(weights[n] != expected["files"][n]["sha256"] or (snapshot/n).stat().st_size != expected["files"][n]["bytes"] for n in weights):
        raise ValueError("Pesos diferentes dos hashes oficiais selecionados.")
    data_root = AI_ROOT / settings["data_release"]
    manifest = read_json(data_root / "manifest.json")
    for name in ("configs/openlm.v1.json", "configs/openlm.data.v1.json"):
        if sha(AI_ROOT / name) != manifest["sources"][name]:
            raise ValueError("Configuração diferente da utilizada para preparar o SFT.")
    for name in ("tokenizer.json", "tokenizer_config.json"):
        if sha(snapshot / name) != manifest["tokenizer_files"][name]:
            raise ValueError("Tokenizador diferente da versão preparada.")
    if sha(data_root / "config.json") != manifest["outputs"]["config.json"]:
        raise ValueError("Configuração de dados alterada.")
    if read_json(data_root / "config.json")["max_sequence_length"] != settings["max_sequence_length"]:
        raise ValueError("Limite de contexto diverge do dataset.")
    train_data, validation_data = SFTDataset(data_root, "train"), SFTDataset(data_root, "validation")
    config = settings["training"]
    random.seed(config["seed"])
    torch.manual_seed(config["seed"])
    torch.cuda.manual_seed_all(config["seed"])
    print("Carregando Qwen3-4B em NF4 na GPU...", flush=True)
    base, tokenizer = load_model(model_settings, args.cache_dir, download=False)
    collator = SFTCollator(tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    original = None
    if not args.resume:
        print("Medindo o modelo original em treino e validação, sem usar o teste...", flush=True)
        original = {}
        for split, data in [("validation", validation_data), ("train", train_data)]:
            loader = DataLoader(data, batch_size=1, shuffle=False, collate_fn=collator,
                                generator=torch.Generator().manual_seed(2026), num_workers=0)
            original[split] = evaluate_nll(base, loader, "cuda")
            print("Original", split, original[split], flush=True)
    print("Preparando adaptadores e congelando a base...", flush=True)
    model, _ = attach_lora(base, settings)
    binding = {"model_id": settings["model_id"], "model_revision": settings["model_revision"],
               "model_config_sha256": sha(AI_ROOT / "configs/openlm.v1.json"),
               "recipe_sha256": sha(args.config), "data_manifest_sha256": sha(data_root / "manifest.json"),
               "weights_manifest_sha256": sha(AI_ROOT / "configs/openlm.weights.v1.json"),
               "entry_script_sha256": sha(Path(__file__)),
               "weights_sha256": weights, "packages": {k: version(k) for k in ["torch", "transformers", "peft", "bitsandbytes"]},
               "device": torch.cuda.get_device_name(0),
               "code": {name: sha(AI_ROOT / "src/evolv_openlm" / name) for name in ["training.py", "lora.py", "runtime.py", "sft_dataset.py"]}}
    result = fit(model, train_data, validation_data, collator, settings, args.output, binding,
                 device="cuda", resume=args.resume, original_metrics=original)
    if result["status"] == "complete":
        if sha(data_root / "manifest.json") != binding["data_manifest_sha256"] or any(sha(snapshot / n) != value for n, value in weights.items()):
            raise ValueError("Pesos ou dados foram alterados durante o run.")
        from evolv_openlm.training_report import render
        render(args.output)
        files = {name: sha(args.output / name) for name in ["binding.json", "recipe.json", "checkpoint_index.json", "history.json", "history.csv", "original_metrics.json", "results.json"]}
        atomic_json(args.output / "manifest.json", {"binding": binding, "outputs": files,
                                                   "test_evaluated": False})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_LORA_CONFIG)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=AI_ROOT / "artifacts/openlm_training/1.0.0")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--download-workers", type=int, default=8)
    args = parser.parse_args()
    job = AI_ROOT / "artifacts/openlm_jobs/1.0.0"
    from filelock import FileLock
    job.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(job / ".job.lock"), timeout=1)
    lock.acquire()
    try:
        if args.download:
            from evolv_openlm.parallel_download import download
            from filelock import Timeout
            config = load_settings()
            atomic_json(job / "status.json", {"status": "downloading", "training_started": False})
            # A transfer already running in another terminal can finish first.
            # If it exits early, download() resumes its verified-sized chunks.
            transfer_lock = FileLock(str(args.cache_dir / "evolv-transfer.lock"), timeout=0)
            deadline = time.monotonic() + 6 * 60 * 60
            while True:
                try:
                    transfer_lock.acquire()
                    transfer_lock.release()
                    break
                except Timeout:
                    if time.monotonic() > deadline:
                        raise TimeoutError("A transferência anterior não terminou em seis horas.")
                    source = AI_ROOT / "artifacts/openlm_download/1.0.0/progress.json"
                    state = read_json(source) if source.exists() else {"status": "downloading"}
                    atomic_json(job / "status.json", {**state, "status": "downloading",
                        "waiting_for_existing_transfer": True, "training_started": False})
                    time.sleep(5)
            result = download(config["model_id"], config["revision"], args.cache_dir,
                workers=args.download_workers, progress=lambda x: atomic_json(job / "status.json", {**x, "training_started": False}))
            result.pop("snapshot")
            atomic_json(job / "download_manifest.json", result)
        atomic_json(job / "status.json", {"status": "preparing_training", "training_started": False})
        result = train(args)
        atomic_json(job / "status.json", {"status": result["status"], "training_started": True,
            "selected_epoch": result.get("selected_epoch"), "optimizer_steps": result.get("optimizer_steps"),
            "validation_nll": result.get("final_validation", {}).get("nll"), "test_evaluated": False})
        print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
    except Exception as exc:
        atomic_json(job / "status.json", {"status": "failed", "error_type": type(exc).__name__,
                                          "message": str(exc), "test_evaluated": False})
        raise
    finally:
        lock.release()


if __name__ == "__main__":
    main()

"""Verify architecture and forward/backward on TRAIN data; no optimizer steps."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))


def smoke_test(config, cpu_batch, device, seed):
    import torch
    from evolv_tinylm.model import TinyLM

    torch.manual_seed(seed)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    model = TinyLM(config).to(device)
    batch = {key: value.to(device) for key, value in cpu_batch.items()}
    model.eval()
    # Causality: change only the future, compare earlier logits, with dropout off.
    length = min(32, int(batch["attention_mask"][0].sum()))
    prefix_input = batch["input_ids"][:1, :length]
    prefix_mask = torch.ones_like(prefix_input, dtype=torch.bool)
    cut = max(1, length // 2)
    changed = prefix_input.clone()
    changed[:, cut:] = (changed[:, cut:] + 17) % config.vocab_size
    with torch.no_grad():
        reference = model(prefix_input, prefix_mask)["logits"]
        altered = model(changed, prefix_mask)["logits"]
        causal_delta = float((reference[:, :cut] - altered[:, :cut]).abs().max())
        future_delta = float((reference[:, cut:] - altered[:, cut:]).abs().max())
        unpadded = model(prefix_input, prefix_mask)["logits"]
        padded_input = torch.zeros((1, config.context_length), dtype=torch.long, device=device)
        padded_mask = torch.zeros_like(padded_input, dtype=torch.bool)
        padded_input[:, :length] = prefix_input
        padded_mask[:, :length] = True
        padded = model(padded_input, padded_mask)["logits"][:, :length]
        padding_delta = float((unpadded - padded).abs().max())
    if causal_delta > 2e-5 or future_delta <= 1e-5 or padding_delta > 2e-5:
        raise AssertionError("Causalidade ou invariancia ao padding falhou.")
    model.train()
    output = model(**batch)
    if not bool(torch.isfinite(output["loss"])):
        raise AssertionError("Loss nao finita.")
    output["loss"].backward()
    gradients = [parameter.grad for parameter in model.parameters() if parameter.requires_grad]
    if not all(grad is not None and bool(torch.isfinite(grad).all()) for grad in gradients):
        raise AssertionError("Gradiente ausente ou nao finito.")
    grad_norm = float(torch.stack([grad.float().square().sum() for grad in gradients]).sum().sqrt())
    if grad_norm <= 0:
        raise AssertionError("Gradientes nulos.")
    result = {
        "device": device, "input_shape": list(batch["input_ids"].shape),
        "logits_shape": list(output["logits"].shape),
        "initial_random_weight_loss": float(output["loss"].detach()),
        "valid_target_tokens": int(output["valid_tokens"]),
        "gradients_finite": True, "gradient_norm": grad_norm,
        "causal_prefix_max_difference": causal_delta,
        "changed_future_max_difference": future_delta,
        "padding_prefix_max_difference": padding_delta,
        "optimizer_steps": 0, "weights_saved": False,
        "parameter_summary": model.parameter_summary(),
    }
    if device == "cuda":
        result["gpu"] = torch.cuda.get_device_name()
        result["peak_allocated_mib"] = round(torch.cuda.max_memory_allocated() / 2**20, 2)
    return result


def main():
    import torch
    from torch.utils.data import DataLoader
    from evolv_tinylm import MODEL_VERSION
    from evolv_tinylm.data import load_prepared_data
    from evolv_tinylm.dataset import NextTokenDataset
    from evolv_tinylm.model import TinyLMConfig
    from evolv_tinylm.tokenizer import sha256
    from evolv_tinylm.tokenizer_training import write_json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=AI_ROOT / "configs/tinylm.v1.json")
    parser.add_argument("--data", type=Path, default=AI_ROOT / "artifacts/tinylm_data/1.0.0")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "all"), default="auto")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cpu-threads", type=int, default=4)
    parser.add_argument("--output", type=Path, help="Optional new report directory; never overwrites.")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        raise FileExistsError("A pasta de relatorio ja existe.")
    if args.batch_size < 1 or args.cpu_threads < 1:
        raise ValueError("Lote e quantidade de threads devem ser positivos.")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA indisponivel; use --device cpu.")
    torch.set_num_threads(args.cpu_threads)
    data_manifest_hash = sha256(args.data / "manifest.json")
    config_hash = sha256(args.config)
    metadata = load_prepared_data(args.data)
    config = TinyLMConfig.load(args.config)
    config.validate_data_config(metadata["config"])
    dataset = NextTokenDataset(args.data, "train")
    batch = next(iter(DataLoader(dataset, batch_size=args.batch_size, shuffle=False)))
    dataset.close()
    if args.device == "all":
        devices = ["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"]
    elif args.device == "auto":
        devices = ["cuda" if torch.cuda.is_available() else "cpu"]
    else:
        devices = [args.device]
    report = {
        "model_version": MODEL_VERSION, "status": "architecture_verified_untrained",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "architecture": config.to_dict(), "config_sha256": config_hash,
        "prepared_data_manifest_sha256": data_manifest_hash,
        "tokenizer_sha256": metadata["manifest"]["tokenizer_sha256"],
        "seed": args.seed, "data_partition_used": "train",
        "runtime": {"python": platform.python_version(), "torch": torch.__version__,
                    "cpu_threads": torch.get_num_threads()},
        "interpretation": "Random initialization checks only; loss is not trained-model quality.",
        "checks": [smoke_test(config, batch, device, args.seed) for device in devices],
    }
    if sha256(args.data / "manifest.json") != data_manifest_hash or sha256(args.config) != config_hash:
        raise ValueError("Entradas alteradas durante a verificacao.")
    if args.output is not None:
        args.output.mkdir(parents=True)
        write_json(args.output / "architecture.json", config.to_dict())
        write_json(args.output / "smoke_report.json", report)
        source_files = [AI_ROOT / "src/evolv_tinylm/model.py", Path(__file__).resolve()]
        write_json(args.output / "manifest.json", {
            "version": MODEL_VERSION, "status": "architecture_verified_untrained",
            "files": {name: {"sha256": sha256(args.output / name),
                             "bytes": (args.output / name).stat().st_size}
                      for name in ("architecture.json", "smoke_report.json")},
            "source_sha256": {str(path.relative_to(AI_ROOT)).replace("\\", "/"): sha256(path)
                              for path in source_files},
        })
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

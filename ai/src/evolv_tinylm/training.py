"""Token-weighted training, heldout validation and epoch-boundary checkpoints."""
from __future__ import annotations

from contextlib import nullcontext
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import random
import time

import numpy as np
import torch
from torch.utils.data import DataLoader

from . import TRAINING_VERSION
from .data import load_prepared_data
from .dataset import NextTokenDataset, _seed_worker
from .model import TinyLM, TinyLMConfig
from .tokenizer import sha256


@dataclass(frozen=True)
class TrainingConfig:
    epochs: int = 8
    batch_size: int = 16
    learning_rate: float = 3e-4
    min_lr_ratio: float = 0.1
    weight_decay: float = 0.1
    beta1: float = 0.9
    beta2: float = 0.95
    eps: float = 1e-8
    warmup_fraction: float = 0.05
    grad_clip_norm: float = 1.0
    patience: int = 3
    min_delta: float = 0.005
    seed: int = 42
    num_workers: int = 0
    precision: str = "auto"
    cpu_threads: int = 4
    log_every: int = 100

    def __post_init__(self):
        for key in ("epochs", "batch_size", "patience", "cpu_threads", "log_every"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 1:
                raise ValueError(f"{key} deve ser um inteiro positivo.")
        for key in ("seed", "num_workers"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 0:
                raise ValueError(f"{key} deve ser um inteiro nao negativo.")
        if self.seed >= 2**32:
            raise ValueError("seed deve caber em 32 bits.")
        for key in ("learning_rate", "min_lr_ratio", "weight_decay", "beta1", "beta2",
                    "eps", "warmup_fraction", "grad_clip_norm", "min_delta"):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{key} deve ser um numero finito.")
        if (self.learning_rate <= 0 or self.eps <= 0 or self.grad_clip_norm <= 0
                or not 0 < self.min_lr_ratio <= 1 or self.weight_decay < 0 or self.min_delta < 0
                or not 0 <= self.warmup_fraction < 1
                or not 0 <= self.beta1 < 1 or not 0 <= self.beta2 < 1):
            raise ValueError("Hiperparametros de treinamento fora dos limites.")
        if self.precision not in ("auto", "float32", "bfloat16", "float16"):
            raise ValueError("Precisao nao suportada.")

    @classmethod
    def load(cls, path: str | Path) -> "TrainingConfig":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


def atomic_json(path: Path, value: dict | list) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_checkpoint(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        torch.save(value, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def build_optimizer(model: TinyLM, config: TrainingConfig, device: torch.device):
    # parameters() deduplicates the tied embedding/output weight.
    decay, no_decay = [], []
    for parameter in model.parameters():
        if parameter.requires_grad:
            (decay if parameter.ndim >= 2 else no_decay).append(parameter)
    return torch.optim.AdamW(
        [{"params": decay, "weight_decay": config.weight_decay},
         {"params": no_decay, "weight_decay": 0.0}],
        lr=config.learning_rate, betas=(config.beta1, config.beta2), eps=config.eps,
        foreach=(device.type == "cuda"),
    )


def lr_factor(step: int, total_steps: int, warmup_steps: int, minimum: float) -> float:
    if step < warmup_steps:
        return (step + 1) / warmup_steps
    progress = min(1.0, max(0.0, (step - warmup_steps) / max(1, total_steps - warmup_steps - 1)))
    return minimum + (1 - minimum) * 0.5 * (1 + math.cos(math.pi * progress))


def resolve_precision(requested: str, device: torch.device) -> str:
    if device.type == "cpu":
        if requested not in ("auto", "float32"):
            raise ValueError("Este treinador usa float32 na CPU; selecione auto ou float32.")
        return "float32"
    if requested == "auto":
        return "bfloat16" if torch.cuda.is_bf16_supported() else "float16"
    if requested == "bfloat16" and not torch.cuda.is_bf16_supported():
        raise ValueError("A GPU nao suporta bfloat16.")
    return requested


def autocast_context(device: torch.device, precision: str):
    if precision == "float32":
        return nullcontext()
    dtype = torch.bfloat16 if precision == "bfloat16" else torch.float16
    return torch.autocast(device_type=device.type, dtype=dtype)


def evaluate_loss(model, loader, device: torch.device, precision: str) -> dict:
    was_training = model.training
    model.eval()
    loss_sum, tokens, sequences = 0.0, 0, 0
    try:
        with torch.no_grad():
            for batch in loader:
                batch = {key: value.to(device, non_blocking=True) for key, value in batch.items()}
                with autocast_context(device, precision):
                    output = model(**batch)
                loss_sum += float(output["loss_sum"])
                tokens += int(output["valid_tokens"])
                sequences += batch["input_ids"].shape[0]
    finally:
        model.train(was_training)
    if not tokens or not math.isfinite(loss_sum):
        raise FloatingPointError("Avaliacao vazia ou loss nao finita.")
    return {"loss": loss_sum / tokens, "loss_sum": loss_sum,
            "valid_tokens": tokens, "sequences": sequences}


def capture_rng(generators: dict) -> dict:
    numpy_state = np.random.get_state()
    return {
        "python": random.getstate(), "torch": torch.get_rng_state(),
        "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
        "numpy": [numpy_state[0], numpy_state[1].tolist(), *numpy_state[2:]],
        "generators": {key: generator.get_state() for key, generator in generators.items()},
    }


def restore_rng(state: dict, generators: dict) -> None:
    random.setstate(state["python"])
    torch.set_rng_state(state["torch"])
    if state["cuda"]:
        torch.cuda.set_rng_state_all(state["cuda"])
    name, keys, position, has_gaussian, cached = state["numpy"]
    np.random.set_state((name, np.asarray(keys, dtype=np.uint32), position, has_gaussian, cached))
    for key, generator in generators.items():
        generator.set_state(state["generators"][key])


def read_checkpoint(run_dir: str | Path, which: str = "best") -> dict:
    if which not in ("best", "last"):
        raise ValueError("Escolha best ou last.")
    root = Path(run_dir).resolve()
    index = json.loads((root / "checkpoint_index.json").read_text(encoding="utf-8"))
    record = index[which]
    path = (root / record["file"]).resolve()
    if (not path.is_relative_to(root / "private") or path.stat().st_size != record["bytes"]
            or sha256(path) != record["sha256"]):
        raise ValueError("Checkpoint fora da pasta ou com integridade invalida.")
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint["epoch"] != record["epoch"] or checkpoint["binding"] != index["binding"]:
        raise ValueError("Checkpoint incompativel com seu indice.")
    return checkpoint


def load_trained_model(run_dir: str | Path, *, which: str = "best", device: str = "cpu"):
    checkpoint = read_checkpoint(run_dir, which)
    model = TinyLM(TinyLMConfig(**checkpoint["model_config"]))
    model.load_state_dict(checkpoint["model"])
    return model.to(device).eval(), {"epoch": checkpoint["epoch"],
                                    "validation_loss": checkpoint["history"][-1]["validation_loss"],
                                    "binding": checkpoint["binding"]}


def _write_history(root: Path, history: list[dict]) -> None:
    atomic_json(root / "history.json", history)
    temporary = root / "history.csv.tmp"
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    os.replace(temporary, root / "history.csv")


def _save_epoch(root: Path, model, optimizer, scheduler, scaler, generators,
                binding, config, state: dict, index: dict) -> dict:
    epoch = state["epoch"]
    path = root / "private" / f"epoch_{epoch:04d}.pt"
    checkpoint = {
        **state, "binding": binding, "model_config": model.config.to_dict(),
        "training_config": asdict(config), "model": model.state_dict(),
        "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
        "scaler": scaler.state_dict(), "rng": capture_rng(generators),
    }
    atomic_checkpoint(path, checkpoint)
    record = {"file": f"private/{path.name}", "epoch": epoch,
              "sha256": sha256(path), "bytes": path.stat().st_size,
              "validation_loss": state["history"][-1]["validation_loss"]}
    index = {**index, "last": record, "epochs": index.get("epochs", []) + [record]}
    if state["best_epoch"] == epoch:
        index["best"] = record
    # Pointer changes only after the uniquely named checkpoint is fully written.
    atomic_json(root / "checkpoint_index.json", index)
    _write_history(root, state["history"])
    return index


def train(data_dir: str | Path, model_config: TinyLMConfig, config: TrainingConfig,
          output: str | Path, *, device: str = "auto", resume: bool = False,
          stop_after_epoch: int | None = None) -> dict:
    root, data_dir = Path(output), Path(data_dir)
    if not resume and root.exists():
        raise FileExistsError("Pasta existente: use --resume ou uma nova pasta de treinamento.")
    if resume and not (root / "checkpoint_index.json").is_file():
        raise ValueError("Nao ha checkpoint completo para retomar.")
    if stop_after_epoch is not None and (type(stop_after_epoch) is not int or stop_after_epoch < 1):
        raise ValueError("stop_after_epoch deve ser positivo.")
    selected = "cuda" if device == "auto" and torch.cuda.is_available() else device
    selected = "cpu" if selected == "auto" else selected
    device_obj = torch.device(selected)
    if device_obj.type not in ("cpu", "cuda"):
        raise ValueError("Use CPU ou CUDA.")
    if device_obj.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA indisponivel.")
    precision = resolve_precision(config.precision, device_obj)
    metadata = load_prepared_data(data_dir)
    model_config.validate_data_config(metadata["config"])
    torch.set_num_threads(config.cpu_threads)
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)
    torch.backends.cudnn.benchmark = False
    binding = {
        "prepared_manifest_sha256": sha256(data_dir / "manifest.json"),
        "tokenizer_sha256": metadata["manifest"]["tokenizer_sha256"],
        "model_config": model_config.to_dict(), "training_config": asdict(config),
        "device": str(device_obj), "precision": precision,
        "runtime": {"python": platform.python_version(), "torch": str(torch.__version__),
                    "numpy": str(np.__version__)},
        "sources": {name: sha256(Path(__file__).parent / name)
                    for name in ("training.py", "model.py", "dataset.py", "data.py", "tokenizer.py")},
    }
    generators = {split: torch.Generator().manual_seed(config.seed + number)
                  for number, split in enumerate(("train", "validation"))}
    loaders = {
        split: DataLoader(NextTokenDataset(data_dir, split), batch_size=config.batch_size,
                          shuffle=(split == "train"), drop_last=False, generator=generators[split],
                          num_workers=config.num_workers, worker_init_fn=_seed_worker,
                          pin_memory=(device_obj.type == "cuda"))
        for split in ("train", "validation")
    }
    model = TinyLM(model_config).to(device_obj)
    optimizer = build_optimizer(model, config, device_obj)
    total_steps = config.epochs * len(loaders["train"])
    warmup_steps = int(total_steps * config.warmup_fraction)
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda step: lr_factor(step, total_steps, warmup_steps, config.min_lr_ratio),
    )
    scaler = torch.amp.GradScaler("cuda", enabled=(precision == "float16"))
    if resume:
        state = read_checkpoint(root, "last")
        if state["binding"] != binding:
            raise ValueError("Retomada exige os mesmos dados, codigo, configuracao e runtime.")
        if state["epoch"] >= config.epochs or state["bad_epochs"] >= config.patience:
            raise ValueError("Este treinamento ja terminou.")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scheduler.load_state_dict(state["scheduler"])
        scaler.load_state_dict(state["scaler"])
        restore_rng(state["rng"], generators)
        index = json.loads((root / "checkpoint_index.json").read_text(encoding="utf-8"))
        state = {key: state[key] for key in ("epoch", "global_step", "history", "best_epoch",
                                            "best_validation_loss", "stopping_best", "bad_epochs",
                                            "tokens_seen", "skipped_updates")}
        _write_history(root, state["history"])
    else:
        root.mkdir(parents=True)
        (root / "private").mkdir()
        atomic_json(root / "model_config.json", model_config.to_dict())
        atomic_json(root / "training_config.json", asdict(config))
        atomic_json(root / "binding.json", binding)
        initial = evaluate_loss(model, loaders["validation"], device_obj, precision)
        row = {"epoch": 0, "optimizer_steps": 0, "train_loss_online": None,
               "validation_loss": initial["loss"], "learning_rate": optimizer.param_groups[0]["lr"],
               "train_target_tokens": 0, "validation_target_tokens": initial["valid_tokens"],
               "mean_gradient_norm_before_clip": None, "skipped_updates": 0}
        state = {"epoch": 0, "global_step": 0, "history": [row], "best_epoch": 0,
                 "best_validation_loss": initial["loss"], "stopping_best": initial["loss"],
                 "bad_epochs": 0, "tokens_seen": 0, "skipped_updates": 0}
        index = _save_epoch(root, model, optimizer, scheduler, scaler, generators, binding,
                            config, state, {"binding": binding})
        print(json.dumps({"event": "initial_validation", **initial, "precision": precision}), flush=True)
    run_start = time.monotonic()
    status = "running"
    atomic_json(root / "progress.json", {"status": status, "epoch": state["epoch"],
                                         "global_step": state["global_step"]})
    try:
        for epoch in range(state["epoch"] + 1, config.epochs + 1):
            model.train()
            train_sum, token_count, grad_sum, skipped = 0.0, 0, 0.0, 0
            epoch_start = time.monotonic()
            for batch_number, batch in enumerate(loaders["train"], start=1):
                batch = {key: value.to(device_obj, non_blocking=True) for key, value in batch.items()}
                optimizer.zero_grad(set_to_none=True)
                with autocast_context(device_obj, precision):
                    output_batch = model(**batch)
                if not bool(torch.isfinite(output_batch["loss"])) or int(output_batch["valid_tokens"]) < 1:
                    raise FloatingPointError("Loss nao finita ou lote sem alvos.")
                scaler.scale(output_batch["loss"]).backward()
                scaler.unscale_(optimizer)
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip_norm)
                if not scaler.is_enabled() and not bool(torch.isfinite(norm)):
                    raise FloatingPointError("Gradiente nao finito.")
                old_scale = scaler.get_scale()
                scaler.step(optimizer)
                scaler.update()
                update_skipped = scaler.get_scale() < old_scale
                if not update_skipped:
                    scheduler.step()
                    state["global_step"] += 1
                else:
                    skipped += 1
                if bool(torch.isfinite(norm)):
                    grad_sum += float(norm)
                train_sum += float(output_batch["loss_sum"].detach())
                valid_tokens = int(output_batch["valid_tokens"])
                token_count += valid_tokens
                state["tokens_seen"] += valid_tokens
                if batch_number % config.log_every == 0 or batch_number == len(loaders["train"]):
                    progress = {"status": "running", "epoch": epoch, "batch": batch_number,
                                "batches_per_epoch": len(loaders["train"]),
                                "global_step": state["global_step"], "train_loss_online": train_sum / token_count,
                                "learning_rate": optimizer.param_groups[0]["lr"],
                                "valid_tokens_per_second": round(token_count / max(1e-6, time.monotonic() - epoch_start))}
                    atomic_json(root / "progress.json", progress)
                    print(json.dumps(progress), flush=True)
            validation = evaluate_loss(model, loaders["validation"], device_obj, precision)
            expected = metadata["report"]["partitions"]
            if token_count != expected["train"]["target_tokens"] or validation["valid_tokens"] != expected["validation"]["target_tokens"]:
                raise AssertionError("A epoca nao cobriu todos os alvos de treino/validacao.")
            if validation["loss"] < state["best_validation_loss"]:
                state["best_validation_loss"], state["best_epoch"] = validation["loss"], epoch
            if validation["loss"] < state["stopping_best"] - config.min_delta:
                state["stopping_best"], state["bad_epochs"] = validation["loss"], 0
            else:
                state["bad_epochs"] += 1
            state["skipped_updates"] += skipped
            state["epoch"] = epoch
            state["history"].append({
                "epoch": epoch, "optimizer_steps": state["global_step"],
                "train_loss_online": train_sum / token_count, "validation_loss": validation["loss"],
                "learning_rate": optimizer.param_groups[0]["lr"], "train_target_tokens": token_count,
                "validation_target_tokens": validation["valid_tokens"],
                "mean_gradient_norm_before_clip": grad_sum / len(loaders["train"]), "skipped_updates": skipped,
            })
            index = _save_epoch(root, model, optimizer, scheduler, scaler, generators, binding, config, state, index)
            print(json.dumps({"event": "epoch_completed", **state["history"][-1],
                              "best_epoch": state["best_epoch"], "bad_epochs": state["bad_epochs"]}), flush=True)
            if state["bad_epochs"] >= config.patience:
                status = "early_stopped"
                break
            if stop_after_epoch is not None and epoch >= stop_after_epoch and epoch < config.epochs:
                status = "stopped_at_epoch_boundary"
                break
        else:
            status = "completed"
        verified_loss = None
        if status in ("completed", "early_stopped"):
            best = read_checkpoint(root, "best")
            model.load_state_dict(best["model"])
            verified_loss = evaluate_loss(model, loaders["validation"], device_obj, precision)["loss"]
            if not math.isclose(verified_loss, state["best_validation_loss"], rel_tol=1e-5, abs_tol=1e-5):
                raise AssertionError("Loss do checkpoint recarregado nao corresponde ao selecionado.")
        if (sha256(data_dir / "manifest.json") != binding["prepared_manifest_sha256"]
                or load_prepared_data(data_dir) != metadata):
            raise ValueError("Dados preparados alterados durante o treinamento.")
        results = {
            "training_version": TRAINING_VERSION, "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completed_epochs": state["epoch"], "planned_epochs": config.epochs,
            "optimizer_steps": state["global_step"], "tokens_seen": state["tokens_seen"],
            "initial_validation_loss": state["history"][0]["validation_loss"],
            "best_validation_loss": state["best_validation_loss"], "best_epoch": state["best_epoch"],
            "reloaded_best_validation_loss": verified_loss,
            "last_train_loss_online": state["history"][-1]["train_loss_online"],
            "skipped_optimizer_updates": state["skipped_updates"],
            "elapsed_seconds_this_invocation": round(time.monotonic() - run_start, 2),
            "precision": precision, "device": str(device_obj),
            "gpu": torch.cuda.get_device_name(device_obj) if device_obj.type == "cuda" else None,
            "parameter_summary": model.parameter_summary(), "best_checkpoint": index["best"],
            "last_checkpoint": index["last"], "reserved_test_evaluated": False,
            "inputs_preserved": True, "binding": binding,
            "interpretation": "Online train loss uses dropout/changing weights; validation uses eval/fixed weights.",
        }
        atomic_json(root / "results.json", results)
        atomic_json(root / "progress.json", {"status": status, "epoch": state["epoch"],
                                             "best_epoch": state["best_epoch"],
                                             "best_validation_loss": state["best_validation_loss"]})
        return results
    except BaseException as error:
        atomic_json(root / "progress.json", {
            "status": "interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
            "error_type": type(error).__name__,
            "resume_from_completed_epoch": index["last"]["epoch"],
        })
        raise
    finally:
        for loader in loaders.values():
            loader.dataset.close()

"""Token-weighted QLoRA training, validation and epoch-boundary recovery."""
from contextlib import nullcontext
import csv
import gc
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import time
import uuid

from .lora import make_optimizer, training_plan, trainability_report
from .sft_data import read_json, sha


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def atomic_torch(path, state):
    import torch
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as stream:
        torch.save(state, stream)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def amp(device):
    import torch
    return torch.autocast("cuda", dtype=torch.bfloat16) if str(device).startswith("cuda") else nullcontext()


def causal_nll(logits, labels):
    """HF labels align with inputs; shift exactly once here, not in the dataset."""
    import torch.nn.functional as F
    targets = labels[:, 1:].contiguous()
    count = int((targets != -100).sum().item())
    if count <= 0:
        raise ValueError("Lote sem tokens-alvo.")
    valid = targets != -100
    scores = logits[:, :-1, :][valid].float()
    nll = F.cross_entropy(scores, targets[valid], reduction="sum")
    return nll, count


def forward_nll(model, batch):
    # Keep the full attention context, but avoid the 151936-way vocabulary
    # projection for prompt positions whose targets are all masked anyway.
    valid = (batch["labels"][:, 1:] != -100).nonzero(as_tuple=False)
    if valid.numel() == 0:
        raise ValueError("Lote sem alvos.")
    first_prediction = int(valid[:, 1].min().item())
    keep = batch["input_ids"].shape[1] - first_prediction
    logits = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"],
                   use_cache=False, logits_to_keep=keep).logits
    return causal_nll(logits, batch["labels"][:, -keep:])


def evaluate_nll(model, loader, device):
    import torch
    previous = model.training
    model.eval()
    total, tokens, examples = 0.0, 0, 0
    try:
        with torch.inference_mode():
            for cpu in loader:
                batch = {key: value.to(device, non_blocking=True) for key, value in cpu.items()}
                with amp(device):
                    loss_sum, count = forward_nll(model, batch)
                value = loss_sum.double().item()
                if not math.isfinite(value):
                    raise FloatingPointError("NLL de avaliação não finita.")
                total += value
                tokens += count
                examples += batch["input_ids"].shape[0]
    finally:
        model.train(previous)
    if tokens == 0:
        raise ValueError("Avaliação vazia.")
    nll = total / tokens
    return {"nll": nll, "perplexity": math.exp(nll) if nll < 709 else None,
            "target_tokens": tokens, "examples": examples}


def rng_state(train_generator, validation_generator):
    import torch
    return {"python": random.getstate(), "torch": torch.get_rng_state(),
            "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
            "train_generator": train_generator.get_state(),
            "validation_generator": validation_generator.get_state()}


def restore_rng(state, train_generator, validation_generator):
    import torch
    random.setstate(state["python"])
    torch.set_rng_state(state["torch"])
    if state["cuda"]:
        torch.cuda.set_rng_state_all(state["cuda"])
    train_generator.set_state(state["train_generator"])
    validation_generator.set_state(state["validation_generator"])


def checkpoint_path(run, relative):
    root = (Path(run) / "private/checkpoints").resolve()
    path = (Path(run) / relative).resolve()
    if path.parent != root or not re.fullmatch(r"epoch_\d{4}", path.name):
        raise ValueError("Caminho de checkpoint fora do diretório esperado.")
    return path


def save_checkpoint(run, model, state):
    run = Path(run)
    root = run / "private/checkpoints"
    root.mkdir(parents=True, exist_ok=True)
    epoch = state["epoch"]
    final = root / f"epoch_{epoch:04d}"
    if final.exists():
        # A completed directory not referenced by the atomic index can survive
        # a crash. Preserve it, rather than silently overwriting its weights.
        final.rename(root / (final.name + ".orphan-" + uuid.uuid4().hex[:8]))
    stage = root / (".staging-" + uuid.uuid4().hex)
    stage.mkdir()
    model.save_pretrained(stage, safe_serialization=True, save_embedding_layers=False)
    atomic_torch(stage / "trainer_state.pt", state)
    files = {p.name: sha(p) for p in stage.iterdir() if p.is_file()}
    stage.rename(final)
    return {"epoch": epoch, "validation_nll": state["history"][-1]["validation_nll"],
            "path": final.relative_to(run).as_posix(), "files": files}


def prune_checkpoints(run, index):
    root = (Path(run) / "private/checkpoints").resolve()
    retained = {checkpoint_path(run, index[key]["path"]) for key in ("best", "last")}
    for path in root.iterdir():
        resolved = path.resolve()
        if path.is_dir() and re.fullmatch(r"epoch_\d{4}", path.name) and resolved not in retained:
            if resolved.parent != root or not resolved.is_relative_to(root):
                raise ValueError("Diretório de limpeza fora do run.")
            shutil.rmtree(resolved)


def read_checkpoint(run, which="last"):
    import torch
    if which not in ("best", "last"):
        raise ValueError("Use best ou last.")
    item = read_json(Path(run) / "checkpoint_index.json")[which]
    path = checkpoint_path(run, item["path"])
    for name, expected in item["files"].items():
        if Path(name).name != name or sha(path / name) != expected:
            raise ValueError("Checkpoint alterado ou corrompido.")
    state = torch.load(path / "trainer_state.pt", map_location="cpu", weights_only=True)
    if state["epoch"] != item["epoch"]:
        raise ValueError("Época divergente no checkpoint.")
    return path, state


def restore_adapter(model, path):
    from safetensors.torch import load_file
    from peft import get_peft_model_state_dict, set_peft_model_state_dict
    values = load_file(str(Path(path) / "adapter_model.safetensors"), device="cpu")
    expected = get_peft_model_state_dict(model)
    if set(values) != set(expected) or any(values[k].shape != expected[k].shape for k in values):
        raise ValueError("Pesos do adaptador incompatíveis com o modelo.")
    set_peft_model_state_dict(model, values)


def write_history(run, history):
    atomic_json(Path(run) / "history.json", history)
    path = Path(run) / "history.csv"
    temp = path.with_suffix(".csv.tmp")
    with temp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    temp.replace(path)


def fit(model, train, validation, collator, settings, run, binding, device="cuda",
        resume=False, stop_after_epoch=None, original_metrics=None):
    import torch
    from torch.utils.data import DataLoader
    from filelock import FileLock
    run = Path(run)
    if run.exists() and not resume:
        raise FileExistsError("Run existente. Use outra pasta ou --resume.")
    if resume and not run.exists():
        raise FileNotFoundError("Não há run para retomar.")
    run.mkdir(parents=True, exist_ok=True)
    with FileLock(str(run / ".run.lock"), timeout=1):
        return _fit_locked(model, train, validation, collator, settings, run, binding,
                           device, resume, stop_after_epoch, original_metrics)


def _fit_locked(model, train, validation, collator, settings, run, binding,
                device, resume, stop_after_epoch, original_metrics):
    import torch
    from torch.utils.data import DataLoader
    config = settings["training"]
    plan = training_plan(len(train), settings)
    trainability = trainability_report(model)
    train_generator = torch.Generator().manual_seed(config["data_seed"])
    validation_generator = torch.Generator().manual_seed(config["data_seed"] + 1)
    cuda = str(device).startswith("cuda")
    if cuda:
        torch.backends.cuda.matmul.allow_tf32 = config["tf32"]
    loaders = {"train": DataLoader(train, batch_size=config["per_device_train_batch_size"], shuffle=True,
                  generator=train_generator, collate_fn=collator, num_workers=0, pin_memory=cuda),
               "validation": DataLoader(validation, batch_size=config["per_device_eval_batch_size"], shuffle=False,
                  generator=validation_generator, collate_fn=collator, num_workers=0, pin_memory=cuda)}
    optimizer = make_optimizer(model, settings)
    total, warmup = plan["planned_optimizer_steps_max"], plan["warmup_steps"]

    def lr_factor(step):
        if step < warmup:
            return step / max(1, warmup)
        return max(0.0, (total - step) / max(1, total - warmup))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_factor)
    global_step, epoch, bad_epochs, best_epoch = 0, 0, 0, 0
    history, index = [], None
    base_binding = fingerprint(binding)
    if resume:
        if read_json(run / "binding.json") != binding:
            raise ValueError("Fontes, código ou ambiente mudaram desde o run.")
        if (run / "results.json").exists() and read_json(run / "results.json")["status"] == "complete":
            raise ValueError("Run já completo; não continuar treinando a mesma versão.")
        if original_metrics is None and (run / "original_metrics.json").exists():
            original_metrics = read_json(run / "original_metrics.json")
        if (run / "checkpoint_index.json").exists():
            path, state = read_checkpoint(run, "last")
            if state["binding_sha256"] != base_binding:
                raise ValueError("Checkpoint não pertence à configuração atual.")
            restore_adapter(model, path)
            optimizer.load_state_dict(state["optimizer"])
            scheduler.load_state_dict(state["scheduler"])
            epoch, global_step = state["epoch"], state["global_step"]
            history, bad_epochs, best_epoch = state["history"], state["bad_epochs"], state["best_epoch"]
            original_metrics = state["original_metrics"]
            restore_rng(state["rng"], train_generator, validation_generator)
            index = read_json(run / "checkpoint_index.json")
    else:
        atomic_json(run / "binding.json", binding)
        atomic_json(run / "recipe.json", settings)
        atomic_json(run / "original_metrics.json", original_metrics)

    def state_for_checkpoint():
        return {"epoch": epoch, "global_step": global_step, "history": history,
                "bad_epochs": bad_epochs, "best_epoch": best_epoch, "binding_sha256": base_binding,
                "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
                "rng": rng_state(train_generator, validation_generator), "original_metrics": original_metrics}

    if not history:
        initial_val = evaluate_nll(model, loaders["validation"], device)
        eval_train_loader = DataLoader(train, batch_size=1, shuffle=False, collate_fn=collator,
            generator=torch.Generator().manual_seed(2026), num_workers=0)
        initial_train = evaluate_nll(model, eval_train_loader, device)
        history.append({"epoch": 0, "global_step": 0, "train_nll": initial_train["nll"],
                        "validation_nll": initial_val["nll"], "validation_perplexity": initial_val["perplexity"],
                        "train_target_tokens": initial_train["target_tokens"], "validation_target_tokens": initial_val["target_tokens"],
                        "lr_end": scheduler.get_last_lr()[0], "seconds": 0.0,
                        "train_loss_mode": "eval_fixed_initial_adapter"})
        item = save_checkpoint(run, model, state_for_checkpoint())
        index = {"best": item, "last": item}
        atomic_json(run / "checkpoint_index.json", index)
        write_history(run, history)
    best_nll = index["best"]["validation_nll"]
    expected_train_tokens = sum(sum(x != -100 for x in train[i]["labels"][1:]) for i in range(len(train)))
    started = time.perf_counter()
    memory = {"peak_allocated_mib": 0.0, "peak_reserved_mib": 0.0}
    if cuda:
        torch.cuda.reset_peak_memory_stats()
    while epoch < config["num_train_epochs"] and bad_epochs < settings["early_stopping"]["patience"]:
        epoch += 1
        epoch_start = time.perf_counter()
        model.train()
        optimizer.zero_grad(set_to_none=True)
        train_sum, train_tokens, examples, updates = 0.0, 0, 0, 0
        iterator = iter(loaders["train"])
        while True:
            group = list(itertools.islice(iterator, config["gradient_accumulation_steps"]))
            if not group:
                break
            group_tokens = sum(int((batch["labels"][:, 1:] != -100).sum().item()) for batch in group)
            if group_tokens <= 0:
                raise ValueError("Acumulação sem alvos.")
            for cpu in group:
                batch = {key: value.to(device, non_blocking=True) for key, value in cpu.items()}
                with amp(device):
                    loss_sum, count = forward_nll(model, batch)
                    loss = loss_sum / group_tokens
                if not torch.isfinite(loss).item():
                    raise FloatingPointError("Loss de treino não finita.")
                value = loss_sum.detach().double().item()
                loss.backward()
                train_sum += value
                train_tokens += count
                examples += batch["input_ids"].shape[0]
                del loss_sum, loss, batch
            norm = torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], config["max_grad_norm"])
            if not torch.isfinite(norm).item():
                raise FloatingPointError("Gradientes não finitos; pesos não atualizados neste passo.")
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)
            global_step += 1
            updates += 1
            if cuda:
                memory = {"peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20,
                          "peak_reserved_mib": torch.cuda.max_memory_reserved() / 2**20}
            atomic_json(run / "progress.json", {"status": "training", "epoch": epoch,
                "global_step": global_step, "examples_this_epoch": examples,
                "target_tokens_this_epoch": train_tokens, "train_nll_online": train_sum / train_tokens,
                "resume_granularity": "last_complete_epoch", **memory})
            if updates % config["logging_steps"] == 0 or examples == len(train):
                print(f"Época {epoch}: {examples}/{len(train)}; update {global_step}/{total}; NLL treino {train_sum/train_tokens:.4f}", flush=True)
        if train_tokens != expected_train_tokens or examples != len(train) or updates != plan["optimizer_steps_per_epoch"]:
            raise RuntimeError("Cobertura de treino ou updates diferente do plano.")
        val = evaluate_nll(model, loaders["validation"], device)
        if val["target_tokens"] != history[0]["validation_target_tokens"]:
            raise RuntimeError("Quantidade de alvos de validação mudou.")
        improved = val["nll"] < best_nll
        if improved:
            best_nll, best_epoch, bad_epochs = val["nll"], epoch, 0
        else:
            bad_epochs += 1
        history.append({"epoch": epoch, "global_step": global_step, "train_nll": train_sum / train_tokens,
                        "validation_nll": val["nll"], "validation_perplexity": val["perplexity"],
                        "train_target_tokens": train_tokens, "validation_target_tokens": val["target_tokens"],
                        "lr_end": scheduler.get_last_lr()[0], "seconds": time.perf_counter() - epoch_start,
                        "train_loss_mode": "online_dropout_and_changing_weights"})
        item = save_checkpoint(run, model, state_for_checkpoint())
        index["last"] = item
        if improved:
            index["best"] = item
        atomic_json(run / "checkpoint_index.json", index)
        write_history(run, history)
        prune_checkpoints(run, index)
        print(f"Validação época {epoch}: NLL {val['nll']:.4f}; melhor época {best_epoch}", flush=True)
        if stop_after_epoch is not None and epoch >= stop_after_epoch and epoch < config["num_train_epochs"]:
            atomic_json(run / "progress.json", {"status": "interrupted_for_resume", "epoch": epoch, "global_step": global_step})
            return {"status": "interrupted_for_resume", "epoch": epoch, "global_step": global_step}
    best_path, _ = read_checkpoint(run, "best")
    restore_adapter(model, best_path)
    final_val = evaluate_nll(model, loaders["validation"], device)
    if abs(final_val["nll"] - best_nll) > 1e-5:
        raise RuntimeError("Loss do adaptador recarregado divergiu do checkpoint escolhido.")
    final_train = evaluate_nll(model, DataLoader(train, batch_size=1, shuffle=False,
        generator=torch.Generator().manual_seed(2026), collate_fn=collator, num_workers=0), device)
    result = {"status": "complete", "model_id": settings["model_id"], "model_revision": settings["model_revision"],
              "initial_adapter_validation_nll": history[0]["validation_nll"],
              "initial_adapter_train_nll": history[0]["train_nll"], "original_model_metrics": original_metrics,
              "selected_epoch": best_epoch, "epochs_completed": epoch, "optimizer_steps": global_step,
              "early_stopped": epoch < config["num_train_epochs"], "plan": plan,
              "final_validation": final_val, "final_train_eval": final_train, "trainability": trainability,
              "validation_improved_over_initial_adapter": best_nll < history[0]["validation_nll"],
              "validation_improved_over_original": best_nll < original_metrics["validation"]["nll"] if original_metrics else None,
              "test_evaluated": False, "elapsed_seconds_this_invocation": time.perf_counter() - started,
              "memory": memory, "best_adapter": index["best"]["path"], "last_checkpoint": index["last"]["path"],
              "resume_granularity": "last_complete_epoch", "model_promoted_to_app": False}
    atomic_json(run / "results.json", result)
    atomic_json(run / "progress.json", {"status": "complete", "epoch": epoch, "global_step": global_step,
                                        "best_epoch": best_epoch, "validation_nll": best_nll})
    return result

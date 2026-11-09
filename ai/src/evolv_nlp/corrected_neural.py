"""GPU adaptation on corrected labels, without opening any reserved partition."""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import random

import numpy as np
from scipy.special import softmax

from evolv_nlp.corrected_release import load_partition
from evolv_nlp.dataset import file_sha256
from evolv_nlp.neural_review import make_model, predict_logits
from evolv_nlp.real_data import write_json
from evolv_nlp.review_training import (intent_metrics, risk_metrics, risk_matrix,
    compact, choose_thresholds, confidence_policy)

VERSION = "1.8.1"
MAX_LENGTH = 384
PROFILES = (("encoder12", 1e-5, 12), ("encoder4", 3e-5, 4))
EPOCHS = 6
BATCH_SIZE = 16


def tokenize(tokenizer, texts):
    import torch

    ids, masks, truncated = [], [], 0
    for text in texts:
        tokens = tokenizer.encode(text, add_special_tokens=True, truncation=False, verbose=False)
        if len(tokens) > MAX_LENGTH:
            truncated += 1
            tokens = tokens[:MAX_LENGTH // 2] + tokens[-MAX_LENGTH // 2:]
        ids.append(tokens + [tokenizer.pad_token_id] * (MAX_LENGTH - len(tokens)))
        masks.append([1] * len(tokens) + [0] * (MAX_LENGTH - len(tokens)))
    return torch.tensor(ids, dtype=torch.long), torch.tensor(masks, dtype=torch.long), truncated


def configure_layers(model, count):
    for parameter in model.backbone.parameters():
        parameter.requires_grad = False
    for layer in model.backbone.encoder.layer[-count:]:
        for parameter in layer.parameters():
            parameter.requires_grad = True


def checked_weights(ai_root):
    prior = json.loads((ai_root / "artifacts/baseline/1.7.0/manifest.json").read_text("utf-8"))
    weights = ai_root / prior["base_directory"]
    if not weights.resolve().is_relative_to((ai_root / "artifacts/encoders").resolve()):
        raise ValueError("Invalid base weights path")
    if file_sha256(weights / "model.safetensors") != prior["base_encoder"]["training_weight_sha256"]:
        raise ValueError("Base weights changed")
    for name in ("config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"):
        if file_sha256(weights / name) != prior["base_encoder"]["files"][name]:
            raise ValueError("Base tokenizer changed")
    return weights, prior["base_encoder"]


def train(ai_root):
    import torch
    from safetensors.torch import save_file
    from transformers import AutoTokenizer

    output = ai_root / f"artifacts/baseline/{VERSION}"
    if (output / "candidate_selection.json").exists():
        return json.loads((output / "candidate_selection.json").read_text("utf-8"))
    if (output / "selection_frozen.json").exists():
        raise ValueError("Neural experiment already frozen")
    if not torch.cuda.is_available():
        raise RuntimeError("No CUDA GPU; no neural training has been claimed")
    configuration = {"profiles": PROFILES, "epochs_max": EPOCHS, "batch_size": BATCH_SIZE,
        "max_tokens": MAX_LENGTH, "head_learning_rate": 3e-4, "weight_decay": 0.02,
        "uncertain_training_weight": 0.5, "dropout": 0.2, "test_used": False,
        "early_stopping": "after epoch 3, patience 2 on mean validation F1; task checkpoints separately selected"}
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "registered_experiment.json", configuration)
    private = output / "private"
    private.mkdir(exist_ok=True)
    weights, base_metadata = checked_weights(ai_root)
    tokenizer = AutoTokenizer.from_pretrained(weights, local_files_only=True, trust_remote_code=False)
    taxonomy = json.loads((ai_root / "data/releases/1.8.0/taxonomy.json").read_text("utf-8"))
    classes = sorted(r["id"] for r in taxonomy["intents"])
    risk_classes = sorted(r["id"] for r in taxonomy["risks"] if r["id"] != "none")
    rows, val = load_partition(ai_root, "train"), load_partition(ai_root, "validation")
    encoded, val_encoded = tokenize(tokenizer, [r["input"] for r in rows]), tokenize(tokenizer, [r["input"] for r in val])
    device = torch.device("cuda")
    torch.set_num_threads(2)
    y = torch.tensor([classes.index(r["label"]) for r in rows], device=device)
    ry = torch.tensor(risk_matrix(rows, risk_classes), dtype=torch.float32, device=device)
    counts = torch.bincount(y, minlength=len(classes)).float()
    class_weights = (len(rows) / (len(classes) * counts)).pow(0.25)
    class_weights /= class_weights.mean()
    positive = ry.sum(0)
    positive_weights = ((len(rows) - positive) / positive).sqrt().clamp(max=10)
    ce = torch.nn.CrossEntropyLoss(weight=class_weights, label_smoothing=0.04, reduction="none")
    bce = torch.nn.BCEWithLogitsLoss(pos_weight=positive_weights, reduction="none")
    reliability = torch.tensor([0.5 if r.get("ai_review", {}).get("uncertain") else 1.0 for r in rows], device=device)
    trials, winners = [], {}
    for profile, learning_rate, layer_count in PROFILES:
        random.seed(42)
        np.random.seed(42)
        torch.manual_seed(42)
        torch.cuda.manual_seed_all(42)
        model = make_model(weights, len(classes), len(risk_classes))
        configure_layers(model, layer_count)
        model.to(device)
        body = [p for name, p in model.named_parameters() if p.requires_grad and name.startswith("backbone.")]
        heads = [p for name, p in model.named_parameters() if p.requires_grad and not name.startswith("backbone.")]
        optimizer = torch.optim.AdamW([{"params": body, "lr": learning_rate}, {"params": heads, "lr": 3e-4}], weight_decay=0.02)
        total_steps = EPOCHS * math.ceil(len(rows) / BATCH_SIZE)
        warmup = max(1, int(total_steps * 0.1))
        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda step:
            min((step + 1) / warmup, max(0, (total_steps - step) / max(1, total_steps - warmup))))
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32
        best_mean, stale = -1.0, 0
        print(f"Neural profile={profile}, lr={learning_rate}, GPU={torch.cuda.get_device_name(0)}", flush=True)
        for epoch in range(EPOCHS):
            model.train()
            model.backbone.embeddings.eval()
            for layer in model.backbone.encoder.layer[:-layer_count]:
                layer.eval()
            order = np.random.default_rng(42 + epoch).permutation(len(rows))
            loss_total = 0.0
            for step, start in enumerate(range(0, len(rows), BATCH_SIZE)):
                batch = order[start:start + BATCH_SIZE]
                ids, mask = (value[batch].to(device) for value in encoded[:2])
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast("cuda", dtype=dtype, enabled=dtype != torch.float32):
                    intent_logits, risk_logits = model(ids, mask)
                    per_row = ce(intent_logits.float(), y[batch]) + 0.7 * bce(risk_logits.float(), ry[batch]).mean(1)
                    loss = (per_row * reliability[batch]).sum() / reliability[batch].sum()
                if not torch.isfinite(loss):
                    raise ValueError("Nonfinite neural loss")
                loss.backward()
                torch.nn.utils.clip_grad_norm_([*body, *heads], 1.0)
                optimizer.step()
                scheduler.step()
                loss_total += float(loss.detach())
                if step % 150 == 0:
                    print(f"{profile} epoch={epoch+1} batch={step+1}/{math.ceil(len(rows)/BATCH_SIZE)} loss={float(loss.detach()):.4f}", flush=True)
            logits, risk_scores = predict_logits(model, val_encoded, device, batch_size=24)
            intent_scores = softmax(logits, axis=1)
            predicted = np.asarray(classes)[intent_scores.argmax(1)]
            thresholds = choose_thresholds(risk_matrix(val, risk_classes), risk_scores)
            result = {"intent": intent_metrics([r["label"] for r in val], predicted, classes),
                      "risk": risk_metrics(risk_matrix(val, risk_classes), risk_scores >= thresholds, risk_classes)}
            trial = {"profile": profile, "learning_rate": learning_rate, "encoder_layers": layer_count, "epoch": epoch + 1,
                     "mean_loss": loss_total / (step + 1), "validation": {task: compact(report) for task, report in result.items()}}
            trials.append(trial)
            for task, report in result.items():
                score = report["macro_f1_supported"]
                if task not in winners or score > winners[task]["score"]:
                    state = {name: p.detach().cpu().contiguous() for name, p in model.named_parameters() if p.requires_grad}
                    path = private / f"{task}_adapter.safetensors"
                    save_file(state, str(path))
                    policy = None
                    if task == "intent":
                        ordered = np.sort(intent_scores, axis=1)
                        policy = confidence_policy([r["label"] for r in val], predicted, ordered[:, -1] - ordered[:, -2])
                        policy["validation_label_support"] = dict(Counter(r["label"] for r in val))
                        policy["minimum_label_validation_support"] = 5
                    winners[task] = {"score": score, "trial": trial, "file": path.relative_to(output).as_posix(),
                        "sha256": file_sha256(path), "thresholds": thresholds.tolist() if task == "risk" else None,
                        "confidence_policy": policy}
            mean = sum(report["macro_f1_supported"] for report in result.values()) / 2
            stale = 0 if mean > best_mean + 1e-4 else stale + 1
            best_mean = max(best_mean, mean)
            print(f"{profile} epoch={epoch+1}: intent F1={result['intent']['macro_f1_supported']:.4f}; risk F1={result['risk']['macro_f1_supported']:.4f}", flush=True)
            write_json(output / "search_progress.json", {"test_opened": False, "trials": trials, "winners": winners})
            if epoch >= 2 and stale >= 2:
                print("Early stopping on validation only", flush=True)
                break
        del model, optimizer
        torch.cuda.empty_cache()
    selection = {"model_version": VERSION, "dataset_version": "1.8.0", "configuration": configuration,
        "base_directory": weights.relative_to(ai_root).as_posix(), "base_encoder": base_metadata,
        "intent_classes": classes, "risk_classes": risk_classes, "winners": winners, "trials": trials,
        "train_truncated": encoded[2], "validation_truncated": val_encoded[2], "test_opened": False,
        "dataset_manifest_sha256": file_sha256(ai_root / "data/releases/1.8.0/manifest.json"),
        "raw_text_sent_to_api": False, "production_approved": False}
    write_json(output / "candidate_selection.json", selection)
    return selection


def load_model(ai_root, selection, task, device):
    from safetensors.torch import load_file

    weights, _ = checked_weights(ai_root)
    metadata = selection["winners"][task]
    root = (ai_root / f"artifacts/baseline/{VERSION}").resolve()
    path = (root / metadata["file"]).resolve()
    if not path.is_relative_to(root) or file_sha256(path) != metadata["sha256"]:
        raise ValueError("Neural adapter checksum/path mismatch")
    model = make_model(weights, len(selection["intent_classes"]), len(selection["risk_classes"]))
    configure_layers(model, metadata["trial"]["encoder_layers"])
    state = load_file(str(path), device="cpu")
    expected = {name for name, p in model.named_parameters() if p.requires_grad}
    if set(state) != expected:
        raise ValueError("Unexpected trainable adapter keys")
    model.load_state_dict(state, strict=False)
    return model.to(device).eval()

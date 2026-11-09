"""Local partial encoder fine-tuning, separate from the educational TinyLM."""
from __future__ import annotations

import json
import math
import random
import shutil
from importlib.metadata import version
from pathlib import Path

import numpy as np

from evolv_nlp.context_data import frozen_fingerprints
from evolv_nlp.dataset import file_sha256
from evolv_nlp.real_data import write_json, write_jsonl
from evolv_nlp.review_release import load_partition, model_text
from evolv_nlp.review_training import (intent_metrics, risk_metrics, risk_matrix,
    choose_thresholds, confidence_policy, compact)
from evolv_nlp.privacy import review_text

VERSION = "1.7.0"
MAX_LENGTH = 256
PROFILES = (2e-5, 5e-5)
EPOCHS = 4


def register_experiment(ai_root):
    configuration = {"learning_rates": list(PROFILES), "epochs": EPOCHS, "unfrozen_encoder_layers": 4,
        "max_length": MAX_LENGTH, "long_text": "first_half_and_last_half_tokens",
        "batch_size": 16, "dropout": 0.2, "weight_decay": 0.01,
        "intent_loss": "sqrt_class_weighted_cross_entropy_label_smoothing_0.03",
        "risk_loss": "BCEWithLogits_sqrt_positive_weight_cap_15", "risk_loss_weight": 0.7,
        "selection": "best_validation_macro_f1_separately_for_each_task", "test_used_for_selection": False}
    path = ai_root / f"artifacts/baseline/{VERSION}/registered_experiment.json"
    if path.exists():
        if json.loads(path.read_text("utf-8")) != configuration:
            raise ValueError("Registered experiment changed; use a new version")
    else:
        write_json(path, configuration)
    return configuration


def prepare_weights(ai_root):
    from huggingface_hub import hf_hub_download

    original = ai_root / "artifacts/encoders/multilingual-minilm"
    metadata = json.loads((original / "encoder_manifest.json").read_text("utf-8"))
    target = ai_root / "artifacts/encoders/multilingual-minilm-trainable"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"):
        if file_sha256(original / name) != metadata["files"][name]:
            raise ValueError("Original encoder changed")
        shutil.copy2(original / name, target / name)
    if metadata["license"] != "apache-2.0":
        raise ValueError("Review encoder license before use")
    hf_hub_download(metadata["model_id"], filename="model.safetensors", revision=metadata["revision"], local_dir=target)
    return target, {**metadata, "training_weight_sha256": file_sha256(target / "model.safetensors")}


def make_model(weights, intent_count, risk_count):
    import torch
    from transformers import AutoModel

    class CoachEncoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = AutoModel.from_pretrained(weights, local_files_only=True,
                                                      trust_remote_code=False, use_safetensors=True)
            for parameter in self.backbone.parameters():
                parameter.requires_grad = False
            for layer in self.backbone.encoder.layer[-4:]:
                for parameter in layer.parameters():
                    parameter.requires_grad = True
            hidden = self.backbone.config.hidden_size
            self.dropout = torch.nn.Dropout(0.2)
            self.intent_head = torch.nn.Linear(hidden, intent_count)
            self.risk_head = torch.nn.Linear(hidden, risk_count)

        def forward(self, ids, mask):
            hidden = self.backbone(input_ids=ids, attention_mask=mask).last_hidden_state
            expanded = mask.unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * expanded).sum(1) / expanded.sum(1).clamp(min=1)
            pooled = self.dropout(pooled)
            return self.intent_head(pooled), self.risk_head(pooled)

    return CoachEncoder()


def tokenize_inputs(tokenizer, texts):
    import torch

    ids, masks, truncated = [], [], 0
    for text in texts:
        row = tokenizer.encode(text, add_special_tokens=True, truncation=False, verbose=False)
        if len(row) > MAX_LENGTH:
            truncated += 1
            middle = MAX_LENGTH // 2
            # Keep the original leading/trailing special tokens as well as both text ends.
            row = row[:middle] + row[-(MAX_LENGTH - middle):]
        masks.append([1] * len(row) + [0] * (MAX_LENGTH - len(row)))
        ids.append(row + [tokenizer.pad_token_id] * (MAX_LENGTH - len(row)))
    return torch.tensor(ids, dtype=torch.long), torch.tensor(masks, dtype=torch.long), truncated


def predict_logits(model, encoded, device, batch_size=32):
    import torch

    model.eval()
    intents, risks = [], []
    dtype = torch.bfloat16 if device.type == "cuda" and torch.cuda.is_bf16_supported() else torch.float32
    with torch.inference_mode():
        for start in range(0, len(encoded[0]), batch_size):
            ids, mask = (value[start:start + batch_size].to(device) for value in encoded[:2])
            with torch.autocast(device_type=device.type, dtype=dtype, enabled=dtype != torch.float32):
                intent, risk = model(ids, mask)
            intents.append(intent.float().cpu().numpy())
            risks.append(risk.float().sigmoid().cpu().numpy())
    return np.concatenate(intents), np.concatenate(risks)


def train(ai_root):
    import torch
    from safetensors.torch import save_file, load_file
    from transformers import AutoTokenizer

    output = ai_root / f"artifacts/baseline/{VERSION}"
    if (output / "manifest.json").exists() or (output / "selection_frozen.json").exists():
        raise ValueError("Neural selection already frozen; do not rerun on observed test")
    output.mkdir(parents=True, exist_ok=True)
    configuration = register_experiment(ai_root)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU unavailable; neural experiment was not trained")
    device = torch.device("cuda")
    torch.set_num_threads(2)
    print(f"Fine-tuning locally on {torch.cuda.get_device_name(0)}", flush=True)
    protected = frozen_fingerprints(ai_root)
    weights, base_metadata = prepare_weights(ai_root)
    tokenizer = AutoTokenizer.from_pretrained(weights, local_files_only=True, trust_remote_code=False)
    taxonomy = json.loads((ai_root / "data/releases/1.7.0/taxonomy.json").read_text("utf-8"))
    intent_classes = sorted(item["id"] for item in taxonomy["intents"])
    risk_classes = sorted(item["id"] for item in taxonomy["risks"] if item["id"] != "none")
    rows, validation = load_partition(ai_root, "train"), load_partition(ai_root, "validation")
    encoded = tokenize_inputs(tokenizer, [r["input"] for r in rows])
    validation_encoded = tokenize_inputs(tokenizer, [r["input"] for r in validation])
    y = torch.tensor([intent_classes.index(r["label"]) for r in rows], device=device)
    risk_y = torch.tensor(risk_matrix(rows, risk_classes), dtype=torch.float32, device=device)
    counts = torch.bincount(y, minlength=len(intent_classes)).float()
    class_weights = (len(rows) / (len(intent_classes) * counts)).sqrt()
    class_weights /= class_weights.mean()
    positive = risk_y.sum(0)
    positive_weights = ((len(rows) - positive) / positive).sqrt().clamp(max=15)
    ce = torch.nn.CrossEntropyLoss(weight=class_weights, label_smoothing=0.03)
    bce = torch.nn.BCEWithLogitsLoss(pos_weight=positive_weights)
    winners, trials = {}, []
    private = output / "private"
    private.mkdir(exist_ok=True)
    for learning_rate in PROFILES:
        random.seed(42)
        np.random.seed(42)
        torch.manual_seed(42)
        torch.cuda.manual_seed_all(42)
        model = make_model(weights, len(intent_classes), len(risk_classes)).to(device)
        backbone = [p for name, p in model.named_parameters() if p.requires_grad and name.startswith("backbone.")]
        heads = [p for name, p in model.named_parameters() if p.requires_grad and not name.startswith("backbone.")]
        optimizer = torch.optim.AdamW([{"params": backbone, "lr": learning_rate},
                                       {"params": heads, "lr": 5e-4}], weight_decay=0.01)
        total_steps = EPOCHS * math.ceil(len(rows) / 16)
        warmup = max(1, int(total_steps * 0.1))
        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda step:
            min((step + 1) / warmup, max(0, (total_steps - step) / max(1, total_steps - warmup))))
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32
        for epoch in range(EPOCHS):
            model.train()
            model.backbone.embeddings.eval()
            for layer in model.backbone.encoder.layer[:-4]:
                layer.eval()
            order = np.random.default_rng(42 + epoch).permutation(len(rows))
            loss_sum = 0.0
            for step, start in enumerate(range(0, len(rows), 16)):
                selection = order[start:start + 16]
                ids, mask = (value[selection].to(device) for value in encoded[:2])
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast("cuda", dtype=dtype, enabled=dtype != torch.float32):
                    intent_logits, risk_logits = model(ids, mask)
                    loss = ce(intent_logits.float(), y[selection]) + 0.7 * bce(risk_logits.float(), risk_y[selection])
                if not torch.isfinite(loss):
                    raise ValueError("Nonfinite neural loss")
                loss.backward()
                torch.nn.utils.clip_grad_norm_([*backbone, *heads], 1.0)
                optimizer.step()
                scheduler.step()
                loss_sum += float(loss.detach())
                if step % 100 == 0:
                    print(f"lr={learning_rate} epoch={epoch+1} batch={step+1}/{math.ceil(len(rows)/16)} loss={float(loss.detach()):.4f}", flush=True)
            logits, scores = predict_logits(model, validation_encoded, device)
            predicted = np.asarray(intent_classes)[logits.argmax(1)]
            limits = choose_thresholds(risk_matrix(validation, risk_classes), scores)
            intent_result = intent_metrics([r["label"] for r in validation], predicted, intent_classes)
            risk_result = risk_metrics(risk_matrix(validation, risk_classes), scores >= limits, risk_classes)
            trial = {"learning_rate": learning_rate, "epoch": epoch + 1, "mean_loss": loss_sum / (step + 1),
                     "intent_validation": compact(intent_result), "risk_validation": compact(risk_result)}
            trials.append(trial)
            for task, result in (("intent", intent_result), ("risk", risk_result)):
                if task not in winners or result["macro_f1_supported"] > winners[task]["score"]:
                    state = {name: parameter.detach().cpu().contiguous() for name, parameter in model.named_parameters() if parameter.requires_grad}
                    path = private / f"{task}_adapter.safetensors"
                    save_file(state, str(path))
                    margins = np.sort(logits, axis=1)[:, -1] - np.sort(logits, axis=1)[:, -2]
                    winners[task] = {"score": result["macro_f1_supported"], "trial": trial,
                        "file": path.relative_to(output).as_posix(), "sha256": file_sha256(path),
                        "thresholds": limits.tolist() if task == "risk" else None,
                        "confidence_policy": confidence_policy([r["label"] for r in validation], predicted, margins) if task == "intent" else None}
            print(f"Validation: intent F1={intent_result['macro_f1_supported']:.4f}; risk F1={risk_result['macro_f1_supported']:.4f}", flush=True)
            write_json(output / "search_progress.json", {"trials": trials, "test_opened": False})
        del model, optimizer
        torch.cuda.empty_cache()
    write_json(output / "selection_frozen.json", {"winners": winners, "test_opened": False})
    manifest = {"model_version": VERSION, "dataset_version": "1.7.0", "configuration": configuration,
        "dataset_manifest_sha256": file_sha256(ai_root / "data/releases/1.7.0/manifest.json"),
        "taxonomy_sha256": file_sha256(ai_root / "data/releases/1.7.0/taxonomy.json"),
        "winners": winners, "intent_classes": intent_classes, "risk_classes": risk_classes,
        "base_encoder": base_metadata, "base_directory": weights.relative_to(ai_root).as_posix(),
        "dependencies": {name: version(name) for name in ("torch", "transformers", "safetensors", "numpy")},
        "status": "private_research_not_automatically_promoted", "trials": trials,
        "train_truncated": encoded[2], "validation_truncated": validation_encoded[2],
        "raw_text_sent_to_api": False, "protected_fingerprints": protected}
    # The frozen selection is the only input to final evaluation; no test-driven retraining.
    evaluations, predictions = evaluate_frozen(ai_root, manifest, tokenizer, device, output)
    if frozen_fingerprints(ai_root) != protected:
        raise ValueError("Historical frozen files changed")
    write_json(output / "evaluation.json", evaluations)
    write_jsonl(private / "predictions_all_12179.jsonl", predictions)
    if len(predictions) != 12179:
        raise ValueError("Not all messages evaluated")
    manifest["all_imported_records_processed"] = len(predictions)
    manifest["source_sha256"] = file_sha256(Path(__file__))
    write_json(output / "manifest.json", manifest)
    return {part: {task: compact(value) for task, value in result.items() if task in {"intent", "risk"}}
            for part, result in evaluations.items()}


def load_adapter(ai_root, manifest, task, device):
    from safetensors.torch import load_file

    weights = (ai_root / manifest["base_directory"]).resolve()
    if not weights.is_relative_to((ai_root / "artifacts/encoders").resolve()):
        raise ValueError("Encoder path outside managed directory")
    if file_sha256(weights / "model.safetensors") != manifest["base_encoder"]["training_weight_sha256"]:
        raise ValueError("Base training weights changed")
    for name in ("config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"):
        if file_sha256(weights / name) != manifest["base_encoder"]["files"][name]:
            raise ValueError("Trainable encoder configuration changed")
    root = (ai_root / f"artifacts/baseline/{VERSION}").resolve()
    metadata = manifest["winners"][task]
    path = (root / metadata["file"]).resolve()
    if not path.is_relative_to(root) or file_sha256(path) != metadata["sha256"]:
        raise ValueError("Adapter path/hash mismatch")
    model = make_model(weights, len(manifest["intent_classes"]), len(manifest["risk_classes"]))
    state = load_file(str(path), device="cpu")
    expected = {name for name, parameter in model.named_parameters() if parameter.requires_grad}
    if set(state) != expected:
        raise ValueError("Unexpected trainable adapter keys")
    model.load_state_dict(state, strict=False)
    return model.to(device).eval()


def evaluate_frozen(ai_root, manifest, tokenizer, device, output):
    classes, risks = manifest["intent_classes"], manifest["risk_classes"]
    models = {task: load_adapter(ai_root, manifest, task, device) for task in ("intent", "risk")}
    evaluations, predictions = {}, []
    for partition in ("train", "validation", "test", "external_human_language", "quarantine"):
        rows = load_partition(ai_root, partition)
        encoded = tokenize_inputs(tokenizer, [r["input"] for r in rows])
        logits, _ = predict_logits(models["intent"], encoded, device)
        _, scores = predict_logits(models["risk"], encoded, device)
        labels = np.asarray(classes)[logits.argmax(1)]
        signals = scores >= np.asarray(manifest["winners"]["risk"]["thresholds"])
        intent_valid = np.asarray([r["label"] in classes for r in rows])
        risk_valid = np.asarray([bool(r["risks"]) and set(r["risks"]) <= set(risks) | {"none"} for r in rows])
        evaluations[partition] = {"intent": intent_metrics(np.asarray([r["label"] for r in rows])[intent_valid].tolist(), labels[intent_valid], classes),
            "risk": risk_metrics(risk_matrix(rows, risks)[risk_valid], signals[risk_valid], risks),
            "all_processed": len(rows), "truncated_inputs": encoded[2],
            "reference": "AI_reviewed_not_human_gold", "clean_headline": partition not in {"train", "quarantine"}}
        for row, label, signal in zip(rows, labels, signals):
            predictions.append({"id": row["id"], "partition": partition, "predicted_intent": str(label),
                "predicted_risks": [name for name, active in zip(risks, signal) if active] or ["none"]})
        print(f"Neural {partition}: intent accuracy={evaluations[partition]['intent']['accuracy']:.4f}; F1={evaluations[partition]['intent']['macro_f1_supported']:.4f}; risk F1={evaluations[partition]['risk']['macro_f1_supported']:.4f}", flush=True)
    return evaluations, predictions

from __future__ import annotations

import json
import platform
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack

from evolv_nlp.baseline import load_trusted_model
from evolv_nlp.context_data import frozen_fingerprints
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.real_data import normalized_key, reserved_texts, write_json
from evolv_nlp.research_data import RELEASE
from evolv_nlp.research_models import TwoStageClassifier
from evolv_nlp.semantic_encoder import LocalSemanticEncoder, prepare_encoder
from evolv_nlp.training_v12 import FILES, TASKS, metrics, predictions
from evolv_nlp.training_v13 import parent_labels, taxonomy
from evolv_nlp.tuning_v14 import MODES, estimator, features, select_trial, validate_partition_isolation

VERSION = "1.5.0"
PROFILES = ("svm_025", "svm_1", "svm_4", "lr_05", "lr_2", "lr_8")
SEMANTIC_WEIGHTS = (None, 0.0, 0.5, 1.0, 2.0)


def augment_actions(ai_root, train, definitions):
    source = ai_root / "data/source/planner_actions_augmentation.v1.json"
    payload = json.loads(source.read_text("utf-8"))
    reserved = reserved_texts(ai_root)
    seen = {normalized_key(r["text"]) for r in train} | reserved
    added = []
    for label, texts in payload["intents"].items():
        if label not in definitions:
            raise ValueError("Unknown augmentation label")
        for i, text in enumerate(texts):
            key = normalized_key(text)
            if key in seen:
                continue
            seen.add(key)
            added.append({"id": f"planner-extra-{label}-{i}", "text": text, "label": label,
                          "family": f"planner-extra-{label}-{i}", "provenance": "project_authored_synthetic"})
    return train + added, {"rows_added": len(added), "source_sha256": file_sha256(source),
                           "train_only": True, "not_human_gold": True}


def representation(embedded, lexical, weight):
    return embedded if weight is None else hstack([lexical, csr_matrix(weight * embedded)], format="csr")


def tune_semantic(ai_root: Path) -> dict:
    output = ai_root / f"artifacts/baseline/{VERSION}"
    if (output / "manifest.json").exists():
        raise ValueError("Finalized experiment; do not overwrite")
    output.mkdir(parents=True, exist_ok=True)
    protected = frozen_fingerprints(ai_root)
    encoder_dir = ai_root / "artifacts/encoders/multilingual-minilm"
    encoder_manifest = prepare_encoder(encoder_dir)
    encoder = LocalSemanticEncoder(encoder_dir)
    definitions = taxonomy(ai_root)
    results, artifacts = {}, {}
    for task, filename in TASKS.items():
        types = definitions["intents" if task == "intent_classification" else "risks"]
        parent_map = {key: parent_labels([key], types)[0] for key in types}
        train = read_jsonl(ai_root / f"data/releases/1.5.0/splits/train/{filename}")
        augmentation = {"rows_added": 0}
        if task == "intent_classification":
            train, augmentation = augment_actions(ai_root, train, types)
        validation = read_jsonl(ai_root / f"data/releases/1.5.0/splits/validation/{filename}")
        legacy = read_jsonl(ai_root / f"data/releases/1.3.0/splits/validation/{filename}")
        extra = [r for r in validation if r["id"].startswith("v15-")]
        weak = read_jsonl(ai_root / f"data/releases/{RELEASE}/private/weak_train/{filename}")
        validate_partition_isolation(train + weak, validation)
        train_emb = encoder.encode([r["text"] for r in train + weak])
        old_emb = encoder.encode([r["text"] for r in legacy])
        new_emb = encoder.encode([r["text"] for r in extra])
        trials, best, best_meta, best_vectorizer, best_weight = [], None, None, None, None
        best_score = -1.0
        for mode, weak_weight in MODES.items():
            pool = train + weak if weak_weight else train
            y = np.asarray([r["label"] for r in pool])
            sample_weights = np.asarray([1.0] * len(train) + ([weak_weight] * len(weak) if weak_weight else []))
            embedded = train_emb[:len(pool)]
            vectorizer = features("mixed")
            lexical = vectorizer.fit_transform([r["text"] for r in pool])
            old_lexical = vectorizer.transform([r["text"] for r in legacy])
            new_lexical = vectorizer.transform([r["text"] for r in extra])
            for weight in SEMANTIC_WEIGHTS:
                X = representation(embedded, lexical, weight)
                Xold = representation(old_emb, old_lexical, weight)
                Xnew = representation(new_emb, new_lexical, weight)
                architectures = [(p, estimator(p)) for p in PROFILES]
                architectures += [(f"two_stage_{p}", TwoStageClassifier(estimator(p), parent_map)) for p in ("svm_1", "lr_2")]
                for name, model in architectures:
                    model.fit(X, y, sample_weight=sample_weights)
                    old = metrics([r["label"] for r in legacy], parent_labels(model.predict(Xold).tolist(), types))
                    new = metrics([r["label"] for r in extra], model.predict(Xnew).tolist())
                    score = round(.65 * old["macro_f1"] + .35 * new["macro_f1"], 6)
                    row = {"id": f"{mode}-semantic_{weight}-{name}", "order": len(trials), "selection_score": score,
                        "mode": mode, "architecture": name, "semantic_weight": weight, "weak_sample_weight": weak_weight,
                        "legacy_validation": {k: old[k] for k in ("accuracy", "macro_f1")},
                        "new_native_validation": {k: new[k] for k in ("accuracy", "macro_f1")}}
                    trials.append(row)
                    if score > best_score:
                        best, best_meta, best_vectorizer, best_weight, best_score = model, row, vectorizer, weight, score
                    print(f"{task} semantic trial {len(trials)}: {score:.4f} (best {best_score:.4f})", flush=True)
                    write_json(output / "search_progress.json", {"task": task, "trials": trials, "test_opened": False})
        if select_trial(trials) != best_meta:
            raise ValueError("Winner mismatch")
        path = output / "private" / FILES[task]
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"classifier": best, "lexical_features": best_vectorizer, "semantic_weight": best_weight,
                     "encoder_relative_path": "artifacts/encoders/multilingual-minilm", "encoder": encoder_manifest,
                     "inference_contract": "native predict"}, path, compress=3)
        artifacts[task] = {"file": str(path.relative_to(output)), "sha256": file_sha256(path)}
        comparisons = {}
        for split, rows in {
            "historical_test": read_jsonl(ai_root / f"data/releases/1.3.0/splits/test/{filename}"),
            "new_authored_test": read_jsonl(ai_root / f"data/releases/1.5.0/splits/test/{filename}")}.items():
            texts, labels = [r["text"] for r in rows], [r["label"] for r in rows]
            X = representation(encoder.encode(texts), best_vectorizer.transform(texts), best_weight)
            predicted = best.predict(X).tolist()
            comparison = {"new_1_5_native": metrics(labels, predicted),
                "new_1_5_parent": metrics(parent_labels(labels, types), parent_labels(predicted, types))}
            for old_version in ("1.1.0", "1.3.0"):
                root = ai_root / f"artifacts/baseline/{old_version}"
                meta = json.loads((root / "manifest.json").read_text("utf-8"))["model_artifacts"][task]
                previous = load_trusted_model(root / meta["file"], meta["sha256"])
                comparison[f"previous_{old_version}_parent"] = metrics(parent_labels(labels, types),
                    parent_labels(predictions(previous, texts), types))
            comparisons[split] = comparison
        results[task] = {"winner": best_meta, "trial_count": len(trials), "trials": trials,
            "owned_train": len(train), "weak_train": len(weak), "classes": len(best.classes_),
            "planner_augmentation": augmentation,
            "comparisons": comparisons, "test_used_for_selection": False}
    if protected != frozen_fingerprints(ai_root):
        raise ValueError("Historical frozen inputs changed")
    write_json(output / "metrics.json", {"version": VERSION, "tasks": results,
        "encoder_frozen": True, "lm_trained_from_scratch": False,
        "limitations": ["Weak labels are correlated, not independently human reviewed.",
            "Rights and privacy not certified; private experiment only.",
            "Historical/authored holdouts were already observed in prior phases.",
            "Community replies were not answer targets, labels, or classifier features."]})
    manifest = {"version": VERSION, "dataset_version": RELEASE, "status": "private_semantic_research",
        "model_artifacts": artifacts, "default_changed": False, "automatic_acceptance_enabled": False,
        "encoder": encoder_manifest, "selection": "65% legacy validation, 35% new native validation macro F1",
        "metrics_sha256": file_sha256(output / "metrics.json"),
        "source_files": {f"src/evolv_nlp/{name}.py": file_sha256(ai_root / f"src/evolv_nlp/{name}.py")
                         for name in ("semantic_encoder", "tuning_semantic")},
        "augmentation_sha256": file_sha256(ai_root / "data/source/planner_actions_augmentation.v1.json"),
        "dependencies": {"python": platform.python_version(), **{name: version(name) for name in
            ("numpy", "scipy", "scikit-learn", "joblib", "onnxruntime", "tokenizers", "huggingface_hub")}}}
    write_json(output / "manifest.json", manifest)
    return manifest

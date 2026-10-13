from __future__ import annotations

import json
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline

from evolv_nlp.baseline import artifact_sha256
from evolv_nlp.baseline_v11 import MODEL_PROFILES, RANDOM_SEED, build_classifier, feature_names
from evolv_nlp.dataset import TextPartition, file_sha256, load_partition


DATASET_VERSION = "1.3.0"
BASELINE_VERSION = "1.1.0"
TASKS = ("intent_classification", "risk_classification")
MODEL_FILES = {
    "intent_classification": "intent_classifier.joblib",
    "risk_classification": "risk_classifier.joblib",
}


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def metrics(model: Pipeline, partition: TextPartition) -> dict[str, Any]:
    predicted = model.predict(partition.texts)
    return {
        "rows": len(partition),
        "accuracy": round(float(accuracy_score(partition.labels, predicted)), 6),
        "macro_precision": round(
            float(precision_score(partition.labels, predicted, average="macro", zero_division=0)), 6
        ),
        "macro_recall": round(
            float(recall_score(partition.labels, predicted, average="macro", zero_division=0)), 6
        ),
        "macro_f1": round(
            float(f1_score(partition.labels, predicted, average="macro", zero_division=0)), 6
        ),
    }


def class_features(model: Pipeline, limit: int = 12) -> dict[str, list[str]]:
    names = np.asarray(feature_names(model), dtype=object)
    classifier = model.named_steps["classifier"]
    result: dict[str, list[str]] = {}
    for index, label in enumerate(classifier.classes_):
        ranked = np.argsort(classifier.coef_[index])[::-1][:limit]
        result[str(label)] = [str(value) for value in names[ranked]]
    return result


def train_task(data_root: Path, output_root: Path, task: str) -> tuple[Pipeline, dict[str, Any]]:
    train = load_partition(data_root, "train", task, expected_version=DATASET_VERSION)
    validation = load_partition(data_root, "validation", task, expected_version=DATASET_VERSION)
    candidates: dict[str, dict[str, Any]] = {}
    fitted: dict[str, Pipeline] = {}
    for profile in MODEL_PROFILES:
        model = build_classifier(profile)
        model.fit(train.texts, train.labels)
        fitted[profile] = model
        candidates[profile] = metrics(model, validation)

    selected = max(
        MODEL_PROFILES,
        key=lambda profile: (
            candidates[profile]["macro_f1"],
            candidates[profile]["accuracy"],
            -MODEL_PROFILES.index(profile),
        ),
    )
    model = fitted[selected]
    model_path = output_root / MODEL_FILES[task]
    joblib.dump(model, model_path, compress=3)
    report = {
        "task": task,
        "classes": len(model.classes_),
        "train_rows": len(train),
        "validation_rows": len(validation),
        "selection_policy": "Highest validation macro F1, then accuracy; test remains closed.",
        "candidates": candidates,
        "selected_profile": selected,
        "selected_validation": metrics(model, validation),
        "feature_count": len(feature_names(model)),
        "test_evaluated": False,
    }
    return model, report


def train_all(data_root: Path, output_root: Path) -> dict[str, Any]:
    manifest_path = output_root / "manifest.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous.get("test_accessed"):
            raise ValueError(
                "Baseline 1.1.0 ja avaliado; use uma nova versao para outro experimento"
            )
    output_root.mkdir(parents=True, exist_ok=True)
    reports: dict[str, Any] = {}
    features: dict[str, Any] = {}
    model_artifacts: dict[str, Any] = {}
    for task in TASKS:
        model, report = train_task(data_root, output_root, task)
        reports[task] = report
        features[task] = class_features(model)
        model_path = output_root / MODEL_FILES[task]
        model_artifacts[task] = {
            "file": model_path.name,
            "bytes": model_path.stat().st_size,
            "sha256": artifact_sha256(model_path),
        }

    metrics_path = output_root / "metrics.json"
    write_json(
        metrics_path,
        {
            "baseline_version": BASELINE_VERSION,
            "dataset_version": DATASET_VERSION,
            "tasks": reports,
        },
    )
    features_path = output_root / "top_features.json"
    write_json(
        features_path,
        {
            "baseline_version": BASELINE_VERSION,
            "warning": "Learned correlations, not causal explanations.",
            "tasks": features,
        },
    )

    source_files: dict[str, Any] = {}
    for split in ("train", "validation"):
        for task in TASKS:
            partition = load_partition(data_root, split, task, expected_version=DATASET_VERSION)
            relative = partition.path.relative_to(data_root).as_posix()
            source_files[relative] = {"rows": len(partition), "sha256": file_sha256(partition.path)}

    manifest = {
        "artifact_version": BASELINE_VERSION,
        "dataset_version": DATASET_VERSION,
        "release_date": "2026-10-08",
        "status": "trained_test_closed",
        "random_seed": RANDOM_SEED,
        "algorithm": (
            "TF-IDF word/character n-grams with balanced multinomial logistic "
            "regression or a linear-kernel support vector classifier."
        ),
        "selection": (
            f"{len(MODEL_PROFILES)} declared candidates selected only on validation "
            "macro F1, with accuracy as the tie-breaker."
        ),
        "test_accessed": False,
        "dependencies": {
            "python": platform.python_version(),
            "joblib": version("joblib"),
            "numpy": version("numpy"),
            "scikit-learn": version("scikit-learn"),
            "scipy": version("scipy"),
        },
        "source_files": source_files,
        "model_artifacts": model_artifacts,
        "reports": {
            "metrics": {"file": metrics_path.name, "sha256": file_sha256(metrics_path)},
            "top_features": {"file": features_path.name, "sha256": file_sha256(features_path)},
        },
    }
    write_json(output_root / "manifest.json", manifest)
    return manifest

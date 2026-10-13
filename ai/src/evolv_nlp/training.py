from __future__ import annotations

import json
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    make_scorer,
)
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline

from evolv_nlp import BASELINE_VERSION, DATASET_VERSION
from evolv_nlp.baseline import (
    FEATURE_PROFILES,
    RANDOM_SEED,
    artifact_sha256,
    build_classifier,
)
from evolv_nlp.dataset import TextPartition, file_sha256, load_partition


TASKS = ("intent_classification", "risk_classification")
MODEL_FILES = {
    "intent_classification": "intent_classifier.joblib",
    "risk_classification": "risk_classifier.joblib",
}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def evaluate(model: Pipeline, partition: TextPartition) -> dict[str, Any]:
    predictions = model.predict(partition.texts)
    return {
        "rows": len(partition),
        "accuracy": round(float(accuracy_score(partition.labels, predictions)), 6),
        "macro_precision": round(
            float(
                precision_score(
                    partition.labels,
                    predictions,
                    average="macro",
                    zero_division=0,
                )
            ),
            6,
        ),
        "macro_recall": round(
            float(
                recall_score(
                    partition.labels,
                    predictions,
                    average="macro",
                    zero_division=0,
                )
            ),
            6,
        ),
        "macro_f1": round(
            float(
                f1_score(
                    partition.labels,
                    predictions,
                    average="macro",
                    zero_division=0,
                )
            ),
            6,
        ),
    }


def cross_validation_metrics(
    train: TextPartition, feature_profile: str
) -> dict[str, Any]:
    folds = 3
    splitter = StratifiedKFold(
        n_splits=folds,
        shuffle=True,
        random_state=RANDOM_SEED,
    )
    scoring = {
        "accuracy": "accuracy",
        "macro_f1": make_scorer(f1_score, average="macro", zero_division=0),
    }
    scores = cross_validate(
        build_classifier(feature_profile),
        train.texts,
        train.labels,
        cv=splitter,
        scoring=scoring,
        n_jobs=1,
        return_train_score=False,
    )
    return {
        "folds": folds,
        "accuracy_mean": round(float(np.mean(scores["test_accuracy"])), 6),
        "accuracy_std": round(float(np.std(scores["test_accuracy"])), 6),
        "macro_f1_mean": round(float(np.mean(scores["test_macro_f1"])), 6),
        "macro_f1_std": round(float(np.std(scores["test_macro_f1"])), 6),
    }


def top_features(model: Pipeline, limit: int = 10) -> dict[str, list[str]]:
    vectorizer = model.named_steps["features"]
    classifier = model.named_steps["classifier"]
    names = vectorizer.get_feature_names_out()
    result: dict[str, list[str]] = {}
    for class_index, label in enumerate(classifier.classes_):
        ranked = np.argsort(classifier.coef_[class_index])[::-1][:limit]
        result[str(label)] = [str(names[index]) for index in ranked]
    return result


def train_task(
    data_root: Path,
    output_root: Path,
    task: str,
) -> tuple[Pipeline, dict[str, Any], dict[str, list[str]]]:
    train = load_partition(data_root, "train", task)
    validation = load_partition(data_root, "validation", task)
    candidates: dict[str, dict[str, Any]] = {}
    fitted_candidates: dict[str, Pipeline] = {}
    for profile in FEATURE_PROFILES:
        candidate = build_classifier(profile)
        candidate.fit(train.texts, train.labels)
        fitted_candidates[profile] = candidate
        candidates[profile] = evaluate(candidate, validation)

    selected_profile = max(
        FEATURE_PROFILES,
        key=lambda profile: (
            candidates[profile]["macro_f1"],
            candidates[profile]["accuracy"],
            profile,
        ),
    )
    model = fitted_candidates[selected_profile]

    model_path = output_root / MODEL_FILES[task]
    joblib.dump(model, model_path, compress=3)
    metrics = {
        "task": task,
        "classes": len(model.classes_),
        "train_rows": len(train),
        "train_class_counts": {
            label: train.labels.count(label) for label in sorted(set(train.labels))
        },
        "selection": {
            "criterion": "Highest validation macro F1, then accuracy.",
            "candidates": candidates,
            "selected_feature_profile": selected_profile,
        },
        "cross_validation_on_train": cross_validation_metrics(
            train, selected_profile
        ),
        "validation": evaluate(model, validation),
        "test_evaluated": False,
        "feature_count": len(
            model.named_steps["features"].get_feature_names_out()
        ),
    }
    return model, metrics, top_features(model)


def train_all(data_root: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    task_metrics: dict[str, Any] = {}
    feature_report: dict[str, Any] = {}
    model_artifacts: dict[str, Any] = {}

    for task in TASKS:
        _, metrics, features = train_task(data_root, output_root, task)
        task_metrics[task] = metrics
        feature_report[task] = features
        model_path = output_root / MODEL_FILES[task]
        model_artifacts[task] = {
            "file": MODEL_FILES[task],
            "bytes": model_path.stat().st_size,
            "sha256": artifact_sha256(model_path),
        }

    metrics = {
        "baseline_version": BASELINE_VERSION,
        "dataset_version": DATASET_VERSION,
        "selection_policy": "Compare two declared TF-IDF profiles on validation; select by macro F1 and never inspect test.",
        "tasks": task_metrics,
    }
    write_json(output_root / "metrics.json", metrics)
    write_json(
        output_root / "top_features.json",
        {
            "baseline_version": BASELINE_VERSION,
            "warning": "Associations learned from a small seed dataset; not causal explanations.",
            "tasks": feature_report,
        },
    )

    source_files: dict[str, Any] = {}
    for split in ("train", "validation"):
        for task in TASKS:
            partition = load_partition(data_root, split, task)
            relative = partition.path.relative_to(data_root.parent).as_posix()
            source_files[relative] = {
                "rows": len(partition),
                "sha256": file_sha256(partition.path),
            }

    ai_root = Path(__file__).resolve().parents[2]
    code_paths = (
        ai_root / "requirements.txt",
        ai_root / "scripts" / "train_baseline.py",
        ai_root / "src" / "evolv_nlp" / "__init__.py",
        ai_root / "src" / "evolv_nlp" / "baseline.py",
        ai_root / "src" / "evolv_nlp" / "dataset.py",
        ai_root / "src" / "evolv_nlp" / "training.py",
    )
    code_files = {
        path.relative_to(ai_root.parent).as_posix(): {
            "sha256": file_sha256(path)
        }
        for path in code_paths
    }

    manifest = {
        "artifact_version": BASELINE_VERSION,
        "dataset_version": DATASET_VERSION,
        "release_date": "2026-10-07",
        "random_seed": RANDOM_SEED,
        "algorithm": {
            "vectorizer": "Selected per task between word TF-IDF and word+character TF-IDF.",
            "classifier": "LogisticRegression(multiclass, L2)",
        },
        "data_usage": {
            "train": "Fit vectorizer and classifier; three-fold stratified cross-validation.",
            "validation": "One fixed post-training measurement; no tuning.",
            "test": "Not loaded or evaluated in phase 7.02.1.",
            "challenge": "Not loaded or evaluated in phase 7.02.1.",
        },
        "dependencies": {
            "python": platform.python_version(),
            "joblib": version("joblib"),
            "numpy": version("numpy"),
            "scikit-learn": version("scikit-learn"),
            "scipy": version("scipy"),
        },
        "security": {
            "format": "joblib/pickle-based",
            "load_policy": "Load only repository-generated files whose SHA-256 matches this manifest.",
        },
        "source_files": dict(sorted(source_files.items())),
        "code_files": dict(sorted(code_files.items())),
        "model_artifacts": model_artifacts,
        "reports": {
            "metrics": "metrics.json",
            "top_features": "top_features.json",
        },
    }
    write_json(output_root / "manifest.json", manifest)
    return manifest

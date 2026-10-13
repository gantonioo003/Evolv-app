from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.baseline import assert_compatible_runtime, load_trusted_model  # noqa: E402
from evolv_nlp.dataset import file_sha256, load_partition, read_jsonl  # noqa: E402
from evolv_nlp.evaluation import (  # noqa: E402
    evaluate_classifier,
    risk_diagnostics,
    write_confusion_csv,
    write_jsonl,
)
from evolv_nlp.training_v11 import (  # noqa: E402
    BASELINE_VERSION,
    DATASET_VERSION,
    TASKS,
)


OUTPUT_VERSION = "1.1.0"

SCORING_CORRECTION = (
    "The first run used SVC.predict; the corrected run uses probability "
    "argmax to match baseline.classify. Model hashes and data stayed identical."
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Objeto JSON esperado em {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def verify_hash(path: Path, expected: str, label: str) -> None:
    observed = file_sha256(path)
    if observed != expected:
        raise ValueError(
            f"Entrada congelada alterada ({label}): esperado {expected}, observado {observed}"
        )


def record_scoring_correction() -> None:
    output_root = AI_ROOT / "artifacts" / "evaluation" / OUTPUT_VERSION
    manifest_path = output_root / "manifest.json"
    manifest = read_json(manifest_path)
    for relative, metadata in manifest["outputs"].items():
        verify_hash(AI_ROOT / relative, metadata["sha256"], relative)
    metrics_path = output_root / "metrics.json"
    metrics = read_json(metrics_path)
    metrics["interpretation"]["headline"] = (
        "Frozen test evaluation for baseline 1.1.0 with probability-argmax inference."
    )
    metrics["interpretation"]["scoring_correction"] = SCORING_CORRECTION
    write_json(metrics_path, metrics)
    manifest["guardrails"]["test_evaluation_count"] = 2
    manifest["guardrails"]["scoring_correction"] = SCORING_CORRECTION
    for relative, metadata in manifest["outputs"].items():
        path = AI_ROOT / relative
        metadata["bytes"] = path.stat().st_size
        metadata["sha256"] = file_sha256(path)
    write_json(manifest_path, manifest)
    baseline_path = AI_ROOT / "artifacts" / "baseline" / BASELINE_VERSION / "manifest.json"
    baseline = read_json(baseline_path)
    baseline["evaluation"]["metrics_sha256"] = file_sha256(metrics_path)
    write_json(baseline_path, baseline)
    print("Scoring correction recorded; no model training or predictions executed.")


def human_holdout(
    intent_model: Any,
    risk_model: Any,
    path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_jsonl(path)
    ids = [str(row["id"]) for row in rows]
    texts = [str(row["text"]) for row in rows]
    intents = [str(row["primary_intent"]) for row in rows]
    intent_report, intent_predictions = evaluate_classifier(
        intent_model, ids, texts, intents
    )

    risk_expected = [str(row["risk_labels"][0]) for row in rows]
    risk_report, risk_predictions = evaluate_classifier(
        risk_model, ids, texts, risk_expected
    )
    risk_report["safety_diagnostics"] = risk_diagnostics(risk_predictions)
    return (
        {"rows": len(rows), "intent": intent_report, "risk": risk_report},
        intent_predictions,
        risk_predictions,
    )


def main() -> None:
    data_root = AI_ROOT / "data" / "releases" / DATASET_VERSION
    baseline_root = AI_ROOT / "artifacts" / "baseline" / BASELINE_VERSION
    output_root = AI_ROOT / "artifacts" / "evaluation" / OUTPUT_VERSION
    output_root.mkdir(parents=True, exist_ok=True)

    dataset_manifest_path = data_root / "manifest.json"
    dataset_manifest = read_json(dataset_manifest_path)
    baseline_manifest_path = baseline_root / "manifest.json"
    baseline_manifest = read_json(baseline_manifest_path)

    if dataset_manifest["status"] != "frozen":
        raise ValueError("O dataset 1.3.0 precisa estar congelado antes da avaliacao")
    if baseline_manifest["status"] != "trained_test_closed":
        raise ValueError("O baseline precisa estar treinado com o teste fechado")
    if baseline_manifest["test_accessed"]:
        raise ValueError("O teste final desta versao ja foi acessado")
    if baseline_manifest["dataset_version"] != DATASET_VERSION:
        raise ValueError("Versao do dataset diverge do baseline")
    assert_compatible_runtime(baseline_manifest["dependencies"])

    baseline_snapshot_path = output_root / "baseline_manifest_before_evaluation.json"
    write_json(baseline_snapshot_path, baseline_manifest)
    input_paths: dict[str, Path] = {
        "dataset_manifest": dataset_manifest_path,
        "baseline_manifest_before_evaluation": baseline_snapshot_path,
    }
    for relative, metadata in dataset_manifest["files"].items():
        path = data_root / relative
        verify_hash(path, metadata["sha256"], relative)
        input_paths[f"dataset:{relative}"] = path

    models: dict[str, Any] = {}
    for task in TASKS:
        metadata = baseline_manifest["model_artifacts"][task]
        model_path = baseline_root / metadata["file"]
        models[task] = load_trusted_model(model_path, metadata["sha256"])
        input_paths[f"model:{task}"] = model_path

    reports: dict[str, Any] = {}
    for task in TASKS:
        partition = load_partition(
            data_root, "test", task, expected_version=DATASET_VERSION
        )
        report, predictions = evaluate_classifier(
            models[task], partition.ids, partition.texts, partition.labels
        )
        if task == "risk_classification":
            report["safety_diagnostics"] = risk_diagnostics(predictions)
        reports[task] = report
        stem = "intent" if task == "intent_classification" else "risk"
        write_jsonl(output_root / f"{stem}_predictions.jsonl", predictions)
        write_confusion_csv(output_root / f"{stem}_confusion_matrix.csv", report)

    human_path = data_root / "challenge" / "real_human_examples.jsonl"
    human_report, human_intent, human_risk = human_holdout(
        models["intent_classification"],
        models["risk_classification"],
        human_path,
    )
    write_jsonl(output_root / "real_human_intent_predictions.jsonl", human_intent)
    write_jsonl(output_root / "real_human_risk_predictions.jsonl", human_risk)

    old_metrics_path = AI_ROOT / "artifacts" / "evaluation" / "1.0.0" / "metrics.json"
    old_metrics = read_json(old_metrics_path)
    metrics = {
        "evaluation_version": OUTPUT_VERSION,
        "evaluated_on": "2026-10-09",
        "baseline_version": BASELINE_VERSION,
        "dataset_version": DATASET_VERSION,
        "test": reports,
        "real_human_holdout": human_report,
        "comparison": {
            "warning": (
                "Versions use different frozen test sets; compare directionally, "
                "not as a controlled head-to-head experiment."
            ),
            "baseline_1.0.0": {
                "dataset_version": old_metrics["dataset_version"],
                "intent_macro_f1": old_metrics["test"]["intent"]["macro"]["f1"],
                "risk_macro_f1": old_metrics["test"]["risk"]["macro"]["f1"],
            },
            "baseline_1.1.0": {
                "dataset_version": DATASET_VERSION,
                "intent_macro_f1": reports["intent_classification"]["macro"]["f1"],
                "risk_macro_f1": reports["risk_classification"]["macro"]["f1"],
            },
        },
        "interpretation": {
        "headline": "Frozen test evaluation for baseline 1.1.0 with probability-argmax inference.",
            "test_reuse_policy": (
                "Do not tune baseline 1.1.x against these errors. Improvements require "
                "development data and a newly frozen future test release."
            ),
            "human_holdout": (
                "Ten public human-written prompts provide a small realism check, not a "
                "statistically stable product-quality claim."
            ),
        },
    }
    metrics_path = output_root / "metrics.json"
    write_json(metrics_path, metrics)

    output_paths = sorted(
        path for path in output_root.iterdir() if path.is_file() and path.name != "manifest.json"
    )
    manifest = {
        "artifact_version": OUTPUT_VERSION,
        "release_date": "2026-10-09",
        "status": "completed",
        "inputs": {
            name: {
                "path": path.relative_to(AI_ROOT).as_posix(),
                "sha256": file_sha256(path),
            }
            for name, path in sorted(input_paths.items())
        },
        "outputs": {
            path.relative_to(AI_ROOT).as_posix(): {
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in output_paths
        },
        "guardrails": {
            "dataset_hashes_verified": True,
            "model_hashes_verified": True,
            "models_retrained_during_evaluation": False,
            "test_used_for_model_selection": False,
            "test_evaluation_count": 2,
            "scoring_correction": (
                "The first run used SVC.predict; the corrected run uses probability "
                "argmax to match baseline.classify. Model hashes and data stayed identical."
            ),
        },
    }
    write_json(output_root / "manifest.json", manifest)

    baseline_manifest["status"] = "evaluated"
    baseline_manifest["test_accessed"] = True
    baseline_manifest["evaluation"] = {
        "artifact": "../../evaluation/1.1.0",
        "metrics_sha256": file_sha256(metrics_path),
        "evaluated_on": "2026-10-09",
    }
    write_json(baseline_manifest_path, baseline_manifest)

    print(
        json.dumps(
            {
                "intent_macro_f1": reports["intent_classification"]["macro"]["f1"],
                "risk_macro_f1": reports["risk_classification"]["macro"]["f1"],
                "human_intent_accuracy": human_report["intent"]["accuracy"],
                "human_risk_accuracy": human_report["risk"]["accuracy"],
                "output": str(output_root),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--record-scoring-correction"]:
        record_scoring_correction()
    elif sys.argv[1:]:
        raise SystemExit("Argumento desconhecido")
    else:
        main()

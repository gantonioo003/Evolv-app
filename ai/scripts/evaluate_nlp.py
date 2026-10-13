from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp import (  # noqa: E402
    BASELINE_VERSION,
    DATASET_VERSION,
    ENTITY_EXTRACTOR_VERSION,
    EVALUATION_VERSION,
)
from evolv_nlp.baseline import (  # noqa: E402
    assert_compatible_runtime,
    load_trusted_model,
)
from evolv_nlp.dataset import file_sha256, load_partition  # noqa: E402
from evolv_nlp.evaluation import (  # noqa: E402
    evaluate_challenge,
    evaluate_classifier,
    evaluate_entities,
    read_jsonl,
    render_error_report,
    risk_diagnostics,
    write_confusion_csv,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa a avaliacao congelada da fase 7.02.3."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=AI_ROOT / "artifacts" / "evaluation" / EVALUATION_VERSION,
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
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
            f"{label} deixou de ser congelado: esperado {expected}, observado {observed}"
        )


def relative(path: Path) -> str:
    return path.relative_to(AI_ROOT).as_posix()


def main() -> None:
    args = parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    protocol_path = AI_ROOT / "data" / "evaluation" / "protocol.v1.json"
    protocol = load_json(protocol_path)
    split_manifest_path = AI_ROOT / "data" / "splits" / "manifest.json"
    split_manifest = load_json(split_manifest_path)
    baseline_root = AI_ROOT / "artifacts" / "baseline" / BASELINE_VERSION
    baseline_manifest_path = baseline_root / "manifest.json"
    baseline_manifest = load_json(baseline_manifest_path)

    if protocol["status"] != "frozen":
        raise ValueError("O protocolo de avaliacao precisa estar congelado")
    if split_manifest["status"] != "frozen":
        raise ValueError("As divisoes de dados precisam estar congeladas")
    if baseline_manifest["dataset_version"] != DATASET_VERSION:
        raise ValueError("Versao do dataset diverge do modelo baseline")
    assert_compatible_runtime(baseline_manifest["dependencies"])

    input_paths: dict[str, Path] = {}
    for split_file in (
        "test/intent_examples.jsonl",
        "test/risk_examples.jsonl",
        "challenge/ambiguity_examples.jsonl",
    ):
        path = AI_ROOT / "data" / "splits" / split_file
        expected_hash = split_manifest["files"][split_file]["sha256"]
        verify_hash(path, expected_hash, split_file)
        protocol_hash = protocol["frozen_inputs"][split_file]["sha256"]
        verify_hash(path, protocol_hash, f"protocolo:{split_file}")
        input_paths[split_file] = path

    entity_holdout_path = (
        AI_ROOT / "data" / "evaluation" / "entity_holdout.v1.jsonl"
    )
    verify_hash(
        entity_holdout_path,
        protocol["frozen_inputs"]["entity_holdout.v1.jsonl"]["sha256"],
        "entity_holdout.v1.jsonl",
    )
    input_paths["entity_holdout.v1.jsonl"] = entity_holdout_path

    catalog_path = AI_ROOT / "data" / "catalogs" / "entity_catalogs.v1.json"
    input_paths["entity_catalogs.v1.json"] = catalog_path
    input_paths["protocol.v1.json"] = protocol_path

    models: dict[str, Any] = {}
    for task, model_info in baseline_manifest["model_artifacts"].items():
        model_path = baseline_root / model_info["file"]
        models[task] = load_trusted_model(model_path, model_info["sha256"])
        input_paths[f"model:{task}"] = model_path

    intent_test = load_partition(AI_ROOT / "data", "test", "intent_classification")
    risk_test = load_partition(AI_ROOT / "data", "test", "risk_classification")
    intent_report, intent_predictions = evaluate_classifier(
        models["intent_classification"],
        intent_test.ids,
        intent_test.texts,
        intent_test.labels,
    )
    risk_report, risk_predictions = evaluate_classifier(
        models["risk_classification"],
        risk_test.ids,
        risk_test.texts,
        risk_test.labels,
    )
    risk_report["safety_diagnostics"] = risk_diagnostics(risk_predictions)

    challenge_rows = read_jsonl(
        AI_ROOT / "data" / "splits" / "challenge" / "ambiguity_examples.jsonl"
    )
    challenge_report, challenge_predictions = evaluate_challenge(
        models["intent_classification"],
        models["risk_classification"],
        challenge_rows,
    )
    entity_report, entity_predictions = evaluate_entities(
        entity_holdout_path, catalog_path
    )

    metrics = {
        "evaluation_version": EVALUATION_VERSION,
        "evaluated_on": "2026-10-08",
        "baseline_version": BASELINE_VERSION,
        "dataset_version": DATASET_VERSION,
        "entity_extractor_version": ENTITY_EXTRACTOR_VERSION,
        "test": {"intent": intent_report, "risk": risk_report},
        "entities": entity_report,
        "challenge": challenge_report,
        "interpretation": {
            "headline": "First frozen test evaluation; not a production claim.",
            "test_reuse_policy": (
                "Do not tune version 1.x against these results. Future tuning "
                "requires new development data and a newly frozen test version."
            ),
        },
    }
    metrics_path = output / "metrics.json"
    write_json(metrics_path, metrics)
    write_confusion_csv(output / "intent_confusion_matrix.csv", intent_report)
    write_confusion_csv(output / "risk_confusion_matrix.csv", risk_report)
    write_jsonl(output / "intent_predictions.jsonl", intent_predictions)
    write_jsonl(output / "risk_predictions.jsonl", risk_predictions)
    write_jsonl(output / "entity_predictions.jsonl", entity_predictions)
    write_jsonl(output / "challenge_predictions.jsonl", challenge_predictions)
    report_path = output / "error_analysis.md"
    report_path.write_text(
        render_error_report(metrics), encoding="utf-8", newline="\n"
    )

    code_paths = (
        AI_ROOT / "src" / "evolv_nlp" / "evaluation.py",
        AI_ROOT / "scripts" / "evaluate_nlp.py",
    )
    output_paths = tuple(
        path
        for path in output.iterdir()
        if path.is_file() and path.name != "manifest.json"
    )
    manifest = {
        "artifact_version": EVALUATION_VERSION,
        "release_date": "2026-10-08",
        "status": "completed",
        "protocol": {
            "path": relative(protocol_path),
            "sha256": file_sha256(protocol_path),
        },
        "inputs": {
            name: {"path": relative(path), "sha256": file_sha256(path)}
            for name, path in sorted(input_paths.items())
        },
        "code": {
            relative(path): {"sha256": file_sha256(path)} for path in code_paths
        },
        "outputs": {
            relative(path): {
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in sorted(output_paths)
        },
        "guardrails": {
            "test_files_modified": False,
            "models_retrained": False,
            "entity_extractor_modified_after_holdout": False,
            "planner_writes": False,
            "probabilities_calibrated": False,
        },
    }
    write_json(output / "manifest.json", manifest)

    print(
        json.dumps(
            {
                "intent_macro_f1": intent_report["macro"]["f1"],
                "risk_macro_f1": risk_report["macro"]["f1"],
                "entity_macro_f1": entity_report["macro"]["f1"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

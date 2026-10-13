from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp import ENTITY_EXTRACTOR_VERSION  # noqa: E402
from evolv_nlp.entities import (  # noqa: E402
    entity_signature,
    extract_entities,
    load_entity_catalog,
    score_entity_predictions,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Avalia o extrator hibrido em exemplos congelados."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=AI_ROOT / "data" / "entities" / "evaluation.v1.jsonl",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=AI_ROOT / "data" / "catalogs" / "entity_catalogs.v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=AI_ROOT / "artifacts" / "entities" / "1.0.0" / "metrics.json",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"JSON invalido em {path}:{line_number}") from error
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(dataset: Path, catalog_path: Path) -> dict[str, Any]:
    rows = read_jsonl(dataset)
    catalog = load_entity_catalog(catalog_path)
    total_expected: Counter[tuple[str, str]] = Counter()
    total_predicted: Counter[tuple[str, str]] = Counter()
    exact_messages = 0
    per_type_expected: Counter[str] = Counter()
    per_type_predicted: Counter[str] = Counter()
    per_type_tp: Counter[str] = Counter()
    errors: list[dict[str, Any]] = []

    for row in rows:
        expected = row["expected"]
        result = extract_entities(
            row["text"], catalog, date.fromisoformat(row["reference_date"])
        )
        score = score_entity_predictions(expected, result.entities)
        expected_counter = Counter(entity_signature(item) for item in expected)
        predicted_counter = Counter(entity_signature(item) for item in result.entities)
        total_expected.update(expected_counter)
        total_predicted.update(predicted_counter)
        exact_messages += int(score["exact"])
        for entity_type, _ in expected_counter.elements():
            per_type_expected[entity_type] += 1
        for entity_type, _ in predicted_counter.elements():
            per_type_predicted[entity_type] += 1
        for entity_type, _ in (expected_counter & predicted_counter).elements():
            per_type_tp[entity_type] += 1
        if not score["exact"]:
            errors.append(
                {
                    "id": row["id"],
                    "text": row["text"],
                    "missing": [
                        {"entity_type": entity_type, "value": json.loads(value)}
                        for entity_type, value in (expected_counter - predicted_counter).elements()
                    ],
                    "unexpected": [
                        {"entity_type": entity_type, "value": json.loads(value)}
                        for entity_type, value in (predicted_counter - expected_counter).elements()
                    ],
                }
            )

    true_positive = sum((total_expected & total_predicted).values())
    predicted_count = sum(total_predicted.values())
    expected_count = sum(total_expected.values())
    precision = true_positive / predicted_count if predicted_count else 0.0
    recall = true_positive / expected_count if expected_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    entity_types = sorted(set(per_type_expected) | set(per_type_predicted))
    per_type: dict[str, Any] = {}
    for entity_type in entity_types:
        tp = per_type_tp[entity_type]
        predicted = per_type_predicted[entity_type]
        expected = per_type_expected[entity_type]
        type_precision = tp / predicted if predicted else 0.0
        type_recall = tp / expected if expected else 0.0
        type_f1 = (
            2 * type_precision * type_recall / (type_precision + type_recall)
            if type_precision + type_recall
            else 0.0
        )
        per_type[entity_type] = {
            "support": expected,
            "precision": round(type_precision, 6),
            "recall": round(type_recall, 6),
            "f1": round(type_f1, 6),
        }

    return {
        "extractor_version": ENTITY_EXTRACTOR_VERSION,
        "catalog_version": catalog.version,
        "dataset": {
            "file": dataset.name,
            "sha256": sha256(dataset),
            "messages": len(rows),
            "expected_entities": expected_count,
        },
        "catalog": {"file": catalog_path.name, "sha256": sha256(catalog_path)},
        "micro": {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        },
        "exact_message_accuracy": round(exact_messages / len(rows), 6),
        "per_type": per_type,
        "error_count": len(errors),
        "errors": errors,
    }


if __name__ == "__main__":
    args = parse_args()
    metrics = evaluate(args.dataset, args.catalog)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    code_path = AI_ROOT / "src" / "evolv_nlp" / "entities.py"
    manifest = {
        "artifact_version": ENTITY_EXTRACTOR_VERSION,
        "release_date": "2026-10-07",
        "method": {
            "catalog": "Versioned exact phrase catalogs with aliases",
            "rules": "Deterministic regular expressions for dates and quantities",
            "context": "Lexical context rules for roles, preferences and limitations",
        },
        "evaluation_scope": (
            "Development regression set created for phase 7.02.2. The scores "
            "prevent regressions but are not an unbiased production estimate."
        ),
        "files": {
            "catalog": {
                "path": args.catalog.relative_to(AI_ROOT).as_posix(),
                "sha256": sha256(args.catalog),
            },
            "evaluation": {
                "path": args.dataset.relative_to(AI_ROOT).as_posix(),
                "sha256": sha256(args.dataset),
            },
            "code": {
                "path": code_path.relative_to(AI_ROOT).as_posix(),
                "sha256": sha256(code_path),
            },
            "metrics": {
                "path": args.output.relative_to(AI_ROOT).as_posix(),
                "sha256": sha256(args.output),
            },
        },
        "safety": {
            "planner_writes": False,
            "medical_inference": False,
            "requires_downstream_validation": True,
        },
    }
    manifest_path = args.output.parent / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

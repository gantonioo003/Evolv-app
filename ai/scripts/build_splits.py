from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from audit_splits import audit_generated_dataset


AI_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = AI_ROOT / "data"
SPLITS_ROOT = DATA_ROOT / "splits"
SPLIT_NAMES = ("train", "validation", "test")
DATASET_VERSION = "1.2.0"
BUILDER_VERSION = "1.0.0"
POLICY_PATH = SPLITS_ROOT / "split_policy.v1.json"
ASSIGNMENTS_PATH = SPLITS_ROOT / "assignments.v1.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def stable_rank(label: str, text: str) -> str:
    value = f"{label}\0{text}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def split_examples(
    examples: list[dict[str, Any]], label: str
) -> dict[str, list[dict[str, Any]]]:
    if len(examples) < 6:
        raise ValueError(f"{label} precisa de pelo menos 6 exemplos")

    ordered = sorted(examples, key=lambda item: stable_rank(label, item["text"]))
    validation_count = max(1, int(len(ordered) * 0.15))
    test_count = max(1, int(len(ordered) * 0.15))
    train_count = len(ordered) - validation_count - test_count

    if train_count < 4:
        raise ValueError(f"{label} precisa deixar ao menos 4 exemplos em treino")

    return {
        "train": ordered[:train_count],
        "validation": ordered[train_count : train_count + validation_count],
        "test": ordered[train_count + validation_count :],
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    path.write_text(content, encoding="utf-8", newline="\n")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_assignment_registry(
    intent_rows: dict[str, list[dict[str, Any]]],
    risk_rows: dict[str, list[dict[str, Any]]],
    challenge_rows: list[dict[str, Any]],
    frozen_at: str,
) -> dict[str, Any]:
    assignments: dict[str, dict[str, str]] = {}
    for split in SPLIT_NAMES:
        for row in intent_rows[split] + risk_rows[split]:
            assignments[row["id"]] = {
                "split": split,
                "task": row["task"],
                "label": row["label"],
            }
    for row in challenge_rows:
        assignments[row["id"]] = {
            "split": "challenge",
            "task": row["task"],
            "label": row["primary_intent"],
        }

    registry = {
        "version": "1.0.0",
        "dataset_version": DATASET_VERSION,
        "status": "frozen",
        "frozen_at": frozen_at,
        "assignments": dict(sorted(assignments.items())),
    }
    if ASSIGNMENTS_PATH.exists():
        current = load_json(ASSIGNMENTS_PATH)
        if current != registry:
            raise ValueError(
                "A divisao congelada mudou. Crie uma nova versao do dataset e "
                "revise o registro de assignments antes de continuar."
            )
    else:
        write_json(ASSIGNMENTS_PATH, registry)
    return registry


def build_intent_rows() -> dict[str, list[dict[str, Any]]]:
    taxonomy = load_json(DATA_ROOT / "taxonomy" / "intents.v1.json")
    source = load_json(DATA_ROOT / "source" / "intent_examples.v1.json")
    real_patterns = load_json(
        DATA_ROOT / "source" / "real_pattern_examples.v1.json"
    )
    definitions = {item["id"]: item for item in taxonomy["intents"]}
    rows_by_split: dict[str, list[dict[str, Any]]] = {
        name: [] for name in SPLIT_NAMES
    }

    for label, synthetic_texts in source["examples_by_intent"].items():
        definition = definitions[label]
        examples = [
            {
                "text": text,
                "style": "curated_mixed",
                "difficulty": "standard",
                "source_id": None,
                "source_type": "synthetic_curated",
            }
            for text in synthetic_texts
        ]
        examples.extend(
            {
                **item,
                "source_type": "real_pattern_rewrite",
            }
            for item in real_patterns["intent_examples_by_label"][label]
        )
        for split, items in split_examples(examples, label).items():
            for item in items:
                text = item["text"]
                digest = stable_rank(label, text)[:12]
                rows_by_split[split].append(
                    {
                        "id": f"intent_{label}_{digest}",
                        "task": "intent_classification",
                        "text": text,
                        "label": label,
                        "category": definition["category"],
                        "route": definition["route"],
                        "implementation_status": definition["implementation_status"],
                        "planner_action": definition["planner_action"],
                        "language": source["language"],
                        "source_type": item["source_type"],
                        "source_id": item["source_id"],
                        "style": item["style"],
                        "difficulty": item["difficulty"],
                        "dataset_version": DATASET_VERSION,
                    }
                )

    for rows in rows_by_split.values():
        rows.sort(key=lambda row: (row["label"], row["id"]))
    return rows_by_split


def build_risk_rows() -> dict[str, list[dict[str, Any]]]:
    taxonomy = load_json(DATA_ROOT / "taxonomy" / "risks.v1.json")
    source = load_json(DATA_ROOT / "source" / "risk_examples.v1.json")
    real_patterns = load_json(
        DATA_ROOT / "source" / "real_pattern_examples.v1.json"
    )
    definitions = {item["id"]: item for item in taxonomy["risks"]}
    rows_by_split: dict[str, list[dict[str, Any]]] = {
        name: [] for name in SPLIT_NAMES
    }

    for label, synthetic_texts in source["examples_by_risk"].items():
        definition = definitions[label]
        examples = [
            {
                "text": text,
                "style": "curated_mixed",
                "difficulty": "standard",
                "source_id": None,
                "source_type": "synthetic_curated",
            }
            for text in synthetic_texts
        ]
        examples.extend(
            {
                **item,
                "source_type": "real_pattern_rewrite",
            }
            for item in real_patterns["risk_examples_by_label"][label]
        )
        for split, items in split_examples(examples, label).items():
            for item in items:
                text = item["text"]
                digest = stable_rank(label, text)[:12]
                rows_by_split[split].append(
                    {
                        "id": f"risk_{label}_{digest}",
                        "task": "risk_classification",
                        "text": text,
                        "label": label,
                        "severity": definition["severity"],
                        "route": definition["route"],
                        "language": source["language"],
                        "source_type": item["source_type"],
                        "source_id": item["source_id"],
                        "style": item["style"],
                        "difficulty": item["difficulty"],
                        "dataset_version": DATASET_VERSION,
                    }
                )

    for rows in rows_by_split.values():
        rows.sort(key=lambda row: (row["label"], row["id"]))
    return rows_by_split


def build_challenge_rows() -> list[dict[str, Any]]:
    source = load_json(DATA_ROOT / "source" / "ambiguity_examples.v1.json")
    rows = [
        {
            **item,
            "task": "challenge_evaluation",
            "language": source["language"],
            "source_type": "synthetic_adversarial_curated",
            "dataset_version": DATASET_VERSION,
        }
        for item in source["examples"]
    ]
    return sorted(rows, key=lambda row: row["id"])


def build() -> dict[str, Any]:
    policy = load_json(POLICY_PATH)
    if policy.get("dataset_version") != DATASET_VERSION:
        raise ValueError("A politica de split nao corresponde a versao do dataset")
    if policy.get("status") != "frozen":
        raise ValueError("A politica de split precisa estar congelada")

    intent_rows = build_intent_rows()
    risk_rows = build_risk_rows()
    challenge_rows = build_challenge_rows()
    manifest_files: dict[str, Any] = {}

    for split in SPLIT_NAMES:
        intent_path = SPLITS_ROOT / split / "intent_examples.jsonl"
        risk_path = SPLITS_ROOT / split / "risk_examples.jsonl"
        write_jsonl(intent_path, intent_rows[split])
        write_jsonl(risk_path, risk_rows[split])

        manifest_files[f"{split}/intent_examples.jsonl"] = {
            "rows": len(intent_rows[split]),
            "labels": dict(Counter(row["label"] for row in intent_rows[split])),
            "sha256": file_sha256(intent_path),
        }
        manifest_files[f"{split}/risk_examples.jsonl"] = {
            "rows": len(risk_rows[split]),
            "labels": dict(Counter(row["label"] for row in risk_rows[split])),
            "sha256": file_sha256(risk_path),
        }

    challenge_path = SPLITS_ROOT / "challenge" / "ambiguity_examples.jsonl"
    write_jsonl(challenge_path, challenge_rows)
    manifest_files["challenge/ambiguity_examples.jsonl"] = {
        "rows": len(challenge_rows),
        "ambiguity_types": dict(
            Counter(row["ambiguity_type"] for row in challenge_rows)
        ),
        "expected_behaviors": dict(
            Counter(row["expected_behavior"] for row in challenge_rows)
        ),
        "sha256": file_sha256(challenge_path),
    }

    registry = build_assignment_registry(
        intent_rows,
        risk_rows,
        challenge_rows,
        policy["frozen_at"],
    )
    audit = audit_generated_dataset(write_report=True)
    if audit["status"] != "passed":
        raise ValueError(
            "A auditoria de splits encontrou "
            f"{audit['summary']['blocking_findings']} problema(s). "
            "Consulte ai/data/splits/quality_report.json."
        )

    input_paths = (
        "source/intent_examples.v1.json",
        "source/risk_examples.v1.json",
        "source/real_pattern_examples.v1.json",
        "source/ambiguity_examples.v1.json",
        "taxonomy/intents.v1.json",
        "taxonomy/risks.v1.json",
        "schema/dataset-row.schema.json",
        "splits/split_policy.v1.json",
    )
    input_fingerprints = {
        relative: file_sha256(DATA_ROOT / relative) for relative in input_paths
    }

    split_counts = {
        split: len(intent_rows[split]) + len(risk_rows[split])
        for split in SPLIT_NAMES
    }
    split_counts["challenge"] = len(challenge_rows)

    manifest = {
        "manifest_version": "1.0.0",
        "dataset_version": DATASET_VERSION,
        "status": "frozen",
        "frozen_at": policy["frozen_at"],
        "language": "pt-BR",
        "builder_version": BUILDER_VERSION,
        "split_method": policy["assignment"]["algorithm"],
        "split_policy": "ai/data/splits/split_policy.v1.json",
        "assignment_registry": {
            "path": "ai/data/splits/assignments.v1.json",
            "version": registry["version"],
            "rows": len(registry["assignments"]),
            "sha256": file_sha256(ASSIGNMENTS_PATH),
        },
        "input_fingerprints": input_fingerprints,
        "summary": {
            "rows": sum(split_counts.values()),
            "split_counts": split_counts,
            "task_counts": {
                "intent_classification": sum(map(len, intent_rows.values())),
                "risk_classification": sum(map(len, risk_rows.values())),
                "challenge_evaluation": len(challenge_rows),
            },
        },
        "quality_report": {
            "path": "ai/data/splits/quality_report.json",
            "status": audit["status"],
            "blocking_findings": audit["summary"]["blocking_findings"],
            "sha256": file_sha256(SPLITS_ROOT / "quality_report.json"),
        },
        "files": manifest_files,
    }
    manifest_path = SPLITS_ROOT / "manifest.json"
    write_json(manifest_path, manifest)
    return manifest


if __name__ == "__main__":
    result = build()
    total = sum(item["rows"] for item in result["files"].values())
    print(f"Splits gerados com sucesso: {total} linhas em {len(result['files'])} arquivos.")

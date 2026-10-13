from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = AI_ROOT / "data"
SPLITS_ROOT = DATA_ROOT / "splits"
POLICY_PATH = SPLITS_ROOT / "split_policy.v1.json"
REPORT_PATH = SPLITS_ROOT / "quality_report.json"
REGULAR_SPLITS = ("train", "validation", "test")
ROW_FILES = (
    ("train", "intent_examples.jsonl"),
    ("train", "risk_examples.jsonl"),
    ("validation", "intent_examples.jsonl"),
    ("validation", "risk_examples.jsonl"),
    ("test", "intent_examples.jsonl"),
    ("test", "risk_examples.jsonl"),
    ("challenge", "ambiguity_examples.jsonl"),
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def token_jaccard(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def sequence_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


def read_generated_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split, file_name in ROW_FILES:
        path = SPLITS_ROOT / split / file_name
        for row in load_jsonl(path):
            rows.append(
                {
                    "split": split,
                    "file": f"{split}/{file_name}",
                    "row": row,
                }
            )
    return rows


def pair_summary(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_row = left["row"]
    right_row = right["row"]
    return {
        "left_id": left_row["id"],
        "left_split": left["split"],
        "left_task": left_row["task"],
        "left_label": left_row.get("label", left_row.get("primary_intent")),
        "right_id": right_row["id"],
        "right_split": right["split"],
        "right_task": right_row["task"],
        "right_label": right_row.get("label", right_row.get("primary_intent")),
    }


def audit_rows(
    rows: list[dict[str, Any]], policy: dict[str, Any], dataset_version: str
) -> dict[str, Any]:
    findings: dict[str, list[dict[str, Any]]] = {
        "duplicate_ids": [],
        "exact_normalized_duplicates": [],
        "near_duplicates_across_splits": [],
        "version_mismatches": [],
        "allocation_mismatches": [],
        "challenge_policy_violations": [],
    }

    rows_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows_by_text: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        row = item["row"]
        rows_by_id[row.get("id", "")].append(item)
        rows_by_text[normalize_text(row.get("text", ""))].append(item)
        if row.get("dataset_version") != dataset_version:
            findings["version_mismatches"].append(
                {
                    "id": row.get("id"),
                    "split": item["split"],
                    "observed": row.get("dataset_version"),
                    "expected": dataset_version,
                }
            )

    for row_id, items in sorted(rows_by_id.items()):
        if len(items) > 1 or not row_id:
            findings["duplicate_ids"].append(
                {
                    "id": row_id,
                    "occurrences": [
                        {"split": item["split"], "file": item["file"]}
                        for item in items
                    ],
                }
            )

    for normalized, items in sorted(rows_by_text.items()):
        if len(items) > 1 or not normalized:
            findings["exact_normalized_duplicates"].append(
                {
                    "normalized_text": normalized,
                    "occurrences": [
                        {
                            "id": item["row"].get("id"),
                            "split": item["split"],
                            "task": item["row"].get("task"),
                            "label": item["row"].get(
                                "label", item["row"].get("primary_intent")
                            ),
                        }
                        for item in items
                    ],
                }
            )

    near_policy = policy["duplicate_detection"]["near_duplicates"]
    minimum_tokens = near_policy["minimum_tokens_per_text"]
    jaccard_threshold = near_policy["token_jaccard_threshold"]
    sequence_threshold = near_policy["sequence_ratio_threshold"]

    prepared = [
        {
            **item,
            "normalized": normalize_text(item["row"].get("text", "")),
        }
        for item in rows
    ]
    for left, right in combinations(prepared, 2):
        if left["split"] == right["split"]:
            continue
        left_task = left["row"].get("task")
        right_task = right["row"].get("task")
        involves_challenge = "challenge" in {left["split"], right["split"]}
        if left_task != right_task and not involves_challenge:
            continue
        if left["normalized"] == right["normalized"]:
            continue
        if min(len(left["normalized"].split()), len(right["normalized"].split())) < minimum_tokens:
            continue

        jaccard = token_jaccard(left["normalized"], right["normalized"])
        sequence = sequence_ratio(left["normalized"], right["normalized"])
        is_blocking = (
            jaccard >= jaccard_threshold and sequence >= sequence_threshold
        ) or max(jaccard, sequence) >= 0.96
        if is_blocking:
            findings["near_duplicates_across_splits"].append(
                {
                    **pair_summary(left, right),
                    "token_jaccard": round(jaccard, 4),
                    "sequence_ratio": round(sequence, 4),
                }
            )

    expected_allocation = policy["allocation_per_label"]
    for task in ("intent_classification", "risk_classification"):
        task_rows = [item for item in rows if item["row"].get("task") == task]
        labels = {item["row"].get("label") for item in task_rows}
        for label in sorted(labels):
            observed = Counter(
                item["split"]
                for item in task_rows
                if item["row"].get("label") == label
            )
            for split in REGULAR_SPLITS:
                expected = expected_allocation[split]
                if observed[split] != expected:
                    findings["allocation_mismatches"].append(
                        {
                            "task": task,
                            "label": label,
                            "split": split,
                            "observed": observed[split],
                            "expected": expected,
                        }
                    )

    for item in rows:
        is_challenge_task = item["row"].get("task") == "challenge_evaluation"
        if is_challenge_task != (item["split"] == "challenge"):
            findings["challenge_policy_violations"].append(
                {
                    "id": item["row"].get("id"),
                    "split": item["split"],
                    "task": item["row"].get("task"),
                }
            )

    blocking_count = sum(len(items) for items in findings.values())
    split_counts = Counter(item["split"] for item in rows)
    task_counts = Counter(item["row"].get("task") for item in rows)
    source_type_counts = Counter(item["row"].get("source_type") for item in rows)
    return {
        "audit_version": "1.0.0",
        "dataset_version": dataset_version,
        "audited_at": policy["frozen_at"],
        "status": "passed" if blocking_count == 0 else "failed",
        "thresholds": near_policy,
        "summary": {
            "rows": len(rows),
            "unique_ids": len(rows_by_id),
            "unique_normalized_texts": len(rows_by_text),
            "blocking_findings": blocking_count,
            "split_counts": dict(sorted(split_counts.items())),
            "task_counts": dict(sorted(task_counts.items())),
            "source_type_counts": dict(sorted(source_type_counts.items())),
        },
        "findings": findings,
    }


def audit_generated_dataset(write_report: bool = True) -> dict[str, Any]:
    policy = load_json(POLICY_PATH)
    rows = read_generated_rows()
    report = audit_rows(rows, policy, policy["dataset_version"])
    report["files"] = {
        f"{split}/{file_name}": {
            "rows": sum(
                1
                for item in rows
                if item["split"] == split and item["file"] == f"{split}/{file_name}"
            ),
            "sha256": file_sha256(SPLITS_ROOT / split / file_name),
        }
        for split, file_name in ROW_FILES
    }
    if write_report:
        REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


if __name__ == "__main__":
    result = audit_generated_dataset(write_report=True)
    print(
        "Auditoria dos splits: "
        f"{result['status']} ({result['summary']['blocking_findings']} achados)"
    )
    if result["status"] != "passed":
        sys.exit(1)

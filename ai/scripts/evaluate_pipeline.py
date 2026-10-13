from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp import PIPELINE_VERSION  # noqa: E402
from evolv_nlp.baseline import classify  # noqa: E402
from evolv_nlp.dataset import file_sha256, load_partition  # noqa: E402
from evolv_nlp.pipeline import (  # noqa: E402
    confidence_payload,
    load_json,
    load_pipeline,
)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def evaluate_intent_gate(pipeline: Any) -> dict[str, Any]:
    partition = load_partition(AI_ROOT / "data", "validation", "intent_classification")
    accepted = 0
    correct_accepted = 0
    rows: list[dict[str, Any]] = []
    settings = pipeline.policy["intent"]
    for row_id, text, expected in zip(
        partition.ids, partition.texts, partition.labels
    ):
        result = classify(pipeline.intent_model, text, top_k=int(settings["top_k"]))
        gate = confidence_payload(
            result,
            float(settings["minimum_confidence"]),
            float(settings["minimum_margin"]),
        )
        accepted += int(gate["accepted"])
        correct_accepted += int(gate["accepted"] and result.label == expected)
        rows.append(
            {
                "id": row_id,
                "expected": expected,
                "predicted": result.label,
                "confidence": gate["confidence"],
                "margin": gate["margin"],
                "accepted": gate["accepted"],
                "correct": result.label == expected,
            }
        )
    return {
        "split": "validation",
        "rows": len(partition),
        "accepted": accepted,
        "abstained": len(partition) - accepted,
        "coverage": round(accepted / len(partition), 6),
        "selective_accuracy": round(correct_accepted / accepted, 6)
        if accepted
        else None,
        "correct_accepted": correct_accepted,
        "rows_detail": rows,
    }


def evaluate_risk_gate(pipeline: Any) -> dict[str, Any]:
    partition = load_partition(AI_ROOT / "data", "validation", "risk_classification")
    accepted = 0
    correct_accepted = 0
    escalated = 0
    false_escalations = 0
    rows: list[dict[str, Any]] = []
    settings = pipeline.policy["risk"]
    for row_id, text, expected in zip(
        partition.ids, partition.texts, partition.labels
    ):
        result = classify(pipeline.risk_model, text, top_k=int(settings["top_k"]))
        if result.label == "none":
            minimum_confidence = float(settings["safe_minimum_confidence"])
            minimum_margin = float(settings["safe_minimum_margin"])
            decision = "safe" if expected == "none" else "false_safe"
        else:
            minimum_confidence = float(settings["escalate_minimum_confidence"])
            minimum_margin = float(settings["escalate_minimum_margin"])
            decision = "escalate"
        gate = confidence_payload(
            result, minimum_confidence, minimum_margin
        )
        accepted += int(gate["accepted"])
        correct_accepted += int(gate["accepted"] and result.label == expected)
        escalated += int(gate["accepted"] and result.label != "none")
        false_escalations += int(
            gate["accepted"] and result.label != "none" and expected == "none"
        )
        rows.append(
            {
                "id": row_id,
                "expected": expected,
                "predicted": result.label,
                "decision": decision if gate["accepted"] else "abstain",
                "confidence": gate["confidence"],
                "margin": gate["margin"],
                "accepted": gate["accepted"],
                "correct": result.label == expected,
            }
        )
    return {
        "split": "validation",
        "rows": len(partition),
        "accepted": accepted,
        "abstained": len(partition) - accepted,
        "coverage": round(accepted / len(partition), 6),
        "selective_accuracy": round(correct_accepted / accepted, 6)
        if accepted
        else None,
        "correct_accepted": correct_accepted,
        "escalated": escalated,
        "false_escalations": false_escalations,
        "rows_detail": rows,
    }


def main() -> None:
    output = AI_ROOT / "artifacts" / "pipeline" / PIPELINE_VERSION
    output.mkdir(parents=True, exist_ok=True)
    pipeline = load_pipeline(AI_ROOT)
    policy_path = AI_ROOT / "data" / "pipeline" / "confidence_policy.v1.json"
    policy = load_json(policy_path)

    metrics = {
        "pipeline_version": PIPELINE_VERSION,
        "evaluated_on": "2026-10-08",
        "selection_data": "validation only",
        "test_used_for_threshold_selection": False,
        "challenge_used_for_threshold_selection": False,
        "intent_gate": evaluate_intent_gate(pipeline),
        "risk_gate": evaluate_risk_gate(pipeline),
        "interpretation": {
            "intent": (
                "The baseline cannot reach the conservative gate on validation; "
                "the pipeline abstains instead of pretending confidence."
            ),
            "risk": (
                "Accepted risk labels are safety overrides; low-confidence risk "
                "candidates request clarification."
            ),
        },
    }
    metrics_path = output / "confidence_metrics.json"
    write_json(metrics_path, metrics)

    sample_texts = [
        "amanha troca o supino por flexao e faz 4x10 com 30 kg",
        "meu peito apertou e fiquei sem ar correndo agora",
        "por que aumentar carga ajuda na hipertrofia?",
        "nao gosto de peixe no jantar",
        "pode trocar?",
    ]
    samples = [
        {
            "sample_id": f"pipeline-sample-{index:03d}",
            "text": text,
            "analysis": pipeline.analyze(text, date(2026, 10, 8)),
        }
        for index, text in enumerate(sample_texts, start=1)
    ]
    samples_path = output / "sample_outputs.jsonl"
    write_jsonl(samples_path, samples)

    code_paths = (
        AI_ROOT / "src" / "evolv_nlp" / "pipeline.py",
        AI_ROOT / "src" / "evolv_nlp" / "topics.py",
        AI_ROOT / "scripts" / "analyze_message.py",
        AI_ROOT / "scripts" / "evaluate_pipeline.py",
    )
    input_paths = (
        policy_path,
        AI_ROOT / "data" / "pipeline" / "topic_rules.v1.json",
        AI_ROOT / "data" / "taxonomy" / "intents.v1.json",
        AI_ROOT / "data" / "taxonomy" / "risks.v1.json",
        AI_ROOT / "data" / "taxonomy" / "topics.v1.json",
        AI_ROOT / "data" / "catalogs" / "entity_catalogs.v1.json",
        AI_ROOT / "data" / "splits" / "validation" / "intent_examples.jsonl",
        AI_ROOT / "data" / "splits" / "validation" / "risk_examples.jsonl",
    )
    outputs = (metrics_path, samples_path)
    manifest = {
        "artifact_version": PIPELINE_VERSION,
        "release_date": "2026-10-08",
        "status": "completed_conservative",
        "inputs": {
            path.relative_to(AI_ROOT).as_posix(): {"sha256": file_sha256(path)}
            for path in input_paths
        },
        "code": {
            path.relative_to(AI_ROOT).as_posix(): {"sha256": file_sha256(path)}
            for path in code_paths
        },
        "outputs": {
            path.relative_to(AI_ROOT).as_posix(): {
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in outputs
        },
        "guardrails": {
            "test_used_for_threshold_selection": False,
            "challenge_used_for_threshold_selection": False,
            "direct_planner_writes": False,
            "confirmation_required": True,
            "probabilities_calibrated": False,
            "production_ready": False,
        },
    }
    write_json(output / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "intent_gate": {
                    key: metrics["intent_gate"][key]
                    for key in ("accepted", "abstained", "coverage")
                },
                "risk_gate": {
                    key: metrics["risk_gate"][key]
                    for key in (
                        "accepted",
                        "abstained",
                        "coverage",
                        "selective_accuracy",
                    )
                },
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

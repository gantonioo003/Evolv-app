"""Private, provisional research data. This does not change training_permission."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from evolv_nlp.baseline import load_trusted_model
from evolv_nlp.context_data import PRIVATE_DIR, close_duplicate_pairs, frozen_fingerprints
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.privacy import review_text
from evolv_nlp.real_data import normalized_key, write_json, write_jsonl
from evolv_nlp.risk_rules_v13 import detect_risks
from evolv_nlp.training_v12 import TASKS, weak_intent
from evolv_nlp.training_v13 import parent_labels, taxonomy

RELEASE = "1.6.0"


def group_key(row: dict) -> str:
    return row.get("thread_id") or row.get("group_id") or row["id"]


def blocked_groups(rows: list[dict]) -> set[str]:
    partitions = defaultdict(set)
    banned = set()
    for row in rows:
        partitions[group_key(row)].add(row["source_split"])
        if row.get("quarantine_reasons"):
            banned.add(group_key(row))
    return banned | {key for key, splits in partitions.items() if len(splits) != 1}


def private_eligibility(row: dict) -> list[str]:
    reasons = list(row.get("quarantine_reasons", []))
    reasons.extend(row.get("privacy_flags", []))
    if row.get("media_context"):
        reasons.append("external_media_context")
    if not 15 <= len(row["text"]) <= 6000:
        reasons.append("length_outside_research_scope")
    if row.get("source") not in {"reddit/" + name for name in (
        "r/maromba", "r/corrida", "r/gymgurls", "r/mejulguemaromba", "r/conversas",
        "r/perguntereddit", "r/bicicletasbrasil", "r/perguntas", "r/musculacaonatural", "r/brasilvegan"
    )}:
        reasons.append("source_outside_selected_local_research_scope")
    return sorted(set(reasons))


def reply_text(reply) -> str:
    if isinstance(reply, str):
        return reply
    if isinstance(reply, dict):
        return next((reply[key] for key in ("texto_original", "corpo_original", "texto", "body", "text")
                     if isinstance(reply.get(key), str)), "")
    return ""


def prepare_research(source: Path, ai_root: Path) -> dict:
    output = ai_root / f"data/releases/{RELEASE}"
    if (output / "manifest.json").exists():
        raise ValueError("Release finalized; do not overwrite")
    raw = read_jsonl(source / "mensagens.jsonl")
    queue = read_jsonl(ai_root / PRIVATE_DIR / "review_queue.jsonl")
    if len(raw) != 10000 or {r["id_mensagem"] for r in raw} != {r["id"] for r in queue}:
        raise ValueError("Original collection and audit differ")
    by_id = {r["id_mensagem"]: r for r in raw}
    enriched = [{**r, "thread_id": by_id[r["id"]]["thread_id"]} for r in queue]
    banned = blocked_groups(enriched)
    # Keep original thread splits, and quarantine related threads across duplicate groups.
    for left, right in close_duplicate_pairs(raw):
        if by_id[left]["split"] != by_id[right]["split"]:
            banned.update((by_id[left]["thread_id"], by_id[right]["thread_id"]))
    partitions = {s: [] for s in ("train", "validation", "test", "quarantine")}
    exclusions = Counter()
    for row in enriched:
        original = by_id[row["id"]]
        split = "quarantine" if group_key(row) in banned else row["source_split"]
        if split not in partitions:
            raise ValueError("Unknown source split")
        replies = []
        for i, answer in enumerate(original.get("respostas", [])):
            review = review_text(reply_text(answer))
            replies.append({"id": f"{row['id']}-reply-{i}", "text": review.minimized_text,
                            "privacy_flags": list(review.flags), "review_status": "community_unverified",
                            "approved_response_target": False, "lm_training_allowed": False})
        reasons = private_eligibility(row)
        if split == "quarantine":
            reasons.append("quarantined_thread")
        exclusions.update(reasons)
        partitions[split].append({**row, "thread_id": original["thread_id"], "replies": replies,
            "private_research_eligible": not reasons, "research_exclusions": sorted(set(reasons)),
            "rights_status": "unverified", "production_training_allowed": False,
            "lm_training_allowed": False, "owner_request": "2026-10-10 local private NLP experiments"})
    for split, rows in partitions.items():
        write_jsonl(output / f"private/conversations/{split}.jsonl", rows)
    write_json(output / "frozen_fingerprints.json", frozen_fingerprints(ai_root))
    manifest = {"version": RELEASE, "records": 10000,
        "partitions": {s: {"questions": len(rows), "community_replies": sum(len(r["replies"]) for r in rows),
                            "eligible_private_questions": sum(r["private_research_eligible"] for r in rows)}
                       for s, rows in partitions.items()},
        "excluded_signals": dict(exclusions), "source_sha256": file_sha256(source / "mensagens.jsonl"),
        "protocol": "Keep source thread splits; quarantine contaminated threads; no old holdout reassignment",
        "rights_status": "unverified_not_authorized_by_rightsholders",
        "local_owner_request_is_not_legal_clearance": True,
        "restrictions": ["private_local_research_only", "no_weights_or_text_publication", "no_commercial_activation",
                         "no_forum_answers_as_gold", "privacy_minimization_is_not_verified_anonymization"],
        "source_policy_references": ["https://support.reddithelp.com/hc/en-us/articles/26410290525844-Public-Content-Policy",
            "https://huggingface.co/datasets/yikeee/reddit-subreddits25"],
        "existing_training_permission_gate_changed": False}
    write_json(output / "manifest.json", manifest)
    return manifest


def weak_training_rows(ai_root: Path, task: str) -> tuple[list[dict], dict]:
    definitions = taxonomy(ai_root)["intents" if task == "intent_classification" else "risks"]
    root = ai_root / "artifacts/baseline/1.1.0"
    manifest = json.loads((root / "manifest.json").read_text("utf-8"))
    meta = manifest["model_artifacts"][task]
    teacher = load_trusted_model(root / meta["file"], meta["sha256"])
    rows = [r for r in read_jsonl(ai_root / f"data/releases/{RELEASE}/private/conversations/train.jsonl")
            if r["private_research_eligible"]]
    probabilities = teacher.predict_proba([r["text"] for r in rows]) if rows else np.empty((0, 0))
    cap, reasons, result = Counter(), Counter(), []
    for row, probabilities_row in zip(rows, probabilities):
        order = np.argsort(probabilities_row)
        top = str(teacher.classes_[order[-1]])
        margin = probabilities_row[order[-1]] - probabilities_row[order[-2]]
        if task == "intent_classification":
            rule_label = weak_intent(row["text"])
            candidate = row.get("intent_candidate")
            options = [v for v in (rule_label, candidate) if v in definitions]
            agreeing = [v for v in options if parent_labels([v], definitions)[0] == top]
            label = agreeing[0] if agreeing else None
            limit = 200
        else:
            detected = list(detect_risks(row["text"]).risks)
            candidate = row.get("risk_candidates", [])
            label = detected[0] if len(detected) == 1 else None
            # Absence of a rule is not proof of safety; this is low-weight weak supervision only.
            if not detected and candidate == ["none"] and top == "none":
                label = "none"
            if label not in definitions or parent_labels([label], definitions)[0] != top:
                label = None
            limit = 80 if label == "none" else 160
        if label is None or margin < 0.02:
            reasons["teacher_and_candidates_disagree_or_low_margin"] += 1
            continue
        if cap[label] >= limit:
            reasons["class_cap"] += 1
            continue
        cap[label] += 1
        result.append({"id": row["id"], "text": row["text"], "label": label,
                       "family": row["thread_id"], "provenance": "external_weak_not_gold",
                       "review_status": "machine_consensus_not_human_reviewed", "rights_status": "unverified",
                       "production_training_allowed": False, "response_used_as_feature": False})
    summary = {"eligible_train_questions": len(rows), "weak_train_questions": len(result),
               "labels": dict(cap), "not_selected": dict(reasons),
               "teacher": "historical_1.1_parent_classifier", "not_independent_labels": True,
               "responses_used": False, "heldout_questions_used": False}
    write_jsonl(ai_root / f"data/releases/{RELEASE}/private/weak_train/{TASKS[task]}", result)
    return result, summary

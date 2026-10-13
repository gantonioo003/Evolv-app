from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.privacy import review_text, training_permission
from evolv_nlp.real_data import normalized_key, reserved_texts, validate_external, write_json, write_jsonl

DATASET_VERSION = "1.5.0"
PRIVATE_DIR = "data/external_private/ptbr-context-1.0.0"


def frozen_fingerprints(ai_root: Path) -> dict[str, str]:
    roots = [ai_root / "data/evaluation", ai_root / "data/releases/1.3.0/splits/test",
             ai_root / "data/releases/1.3.0/challenge", ai_root / "data/splits",
             ai_root / "data/lm_corpus/1.1.0", ai_root / "artifacts/baseline/1.1.0",
             ai_root / "artifacts/baseline/1.2.0"]
    return {str(p.relative_to(ai_root)): file_sha256(p) for root in roots for p in root.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts}


def close_duplicate_pairs(rows: list[dict]) -> set[tuple[str, str]]:
    # Bounded candidate search, not an exhaustive semantic leakage detector.
    signatures, buckets = {}, defaultdict(list)
    for row in rows:
        words = normalized_key(row["texto_original"]).split()
        grams = {" ".join(words[i:i + 4]) for i in range(len(words) - 3)}
        signatures[row["id_mensagem"]] = grams
        hashes = sorted(hashlib.sha256(g.encode()).hexdigest()[:12] for g in grams)[:8]
        for value in hashes:
            buckets[value].append(row["id_mensagem"])
    candidates = set()
    for ids in buckets.values():
        if len(ids) > 30:
            continue
        for i, left in enumerate(ids):
            candidates.update(tuple(sorted((left, right))) for right in ids[i + 1:])
    result = set()
    for left, right in candidates:
        a, b = signatures[left], signatures[right]
        if a | b and len(a & b) / len(a | b) >= 0.8:
            result.add((left, right))
    return result


def audit_import(source: Path, ai_root: Path, expected_rows: int = 10000) -> dict:
    manifest_path = ai_root / f"data/releases/{DATASET_VERSION}/external_manifest.json"
    if manifest_path.exists():
        raise ValueError("Importacao finalizada; use nova versao para outra coleta")
    rows, candidates = validate_external(source, expected_rows)
    index = {r["id_mensagem"]: r for r in rows}
    historical = reserved_texts(ai_root)
    old_file = ai_root / "data/external_private/ptbr-10000-1.0.0/mensagens.jsonl"
    old_index = {r["id_mensagem"]: r for r in read_jsonl(old_file)} if old_file.exists() else {}
    overlap_ids = set(index) & set(old_index)
    groups = defaultdict(list)
    for row in rows:
        for value in ("thread:" + row["thread_id"], "group:" + row["split_group_id"],
                      "text:" + normalized_key(row["texto_original"])):
            groups[value].append(row["id_mensagem"])
    quarantined = defaultdict(set)
    for ids in groups.values():
        if len({index[i]["split"] for i in ids}) > 1:
            for i in ids:
                quarantined[i].add("cross_split_group_or_exact_duplicate")
    pairs = close_duplicate_pairs(rows)
    for left, right in pairs:
        if index[left]["split"] != index[right]["split"]:
            quarantined[left].add("cross_split_near_duplicate")
            quarantined[right].add("cross_split_near_duplicate")
    queue, identifiers, flags, answer_identifiers = [], Counter(), Counter(), Counter()
    for row in rows:
        message_id = row["id_mensagem"]
        if normalized_key(row["texto_original"]) in historical:
            quarantined[message_id].add("historical_frozen_overlap")
        if message_id in old_index:
            quarantined[message_id].add("previous_collection_overlap")
        review = review_text(row["texto_original"])
        identifiers.update(review.identifier_counts)
        flags.update(review.flags)
        for answer in row.get("respostas", []):
            answer_text = next((answer[k] for k in ("texto_original", "corpo_original", "texto", "body", "text")
                                if isinstance(answer.get(k), str)), "") if isinstance(answer, dict) else str(answer)
            answer_identifiers.update(review_text(answer_text).identifier_counts)
        item = {
            "id": message_id, "text": review.minimized_text, "group_id": row["split_group_id"],
            "source_split": row["split"], "source": row["fonte"],
            "source_url": row["source_url"], "text_sha256": row["texto_original_sha256"],
            "privacy_flags": list(review.flags), "privacy_review_status": "pending",
            "rights_status": "unverified", "review_status": "machine_candidate",
            "authorization": {"status": "pending", "purposes": []},
            "intent_candidate": candidates[message_id].get("intenção_principal_sugerida"),
            "risk_candidates": candidates[message_id].get("riscos_sugeridos", []),
            "quarantine_reasons": sorted(quarantined[message_id]),
            "body_complete_claim": row["metadados"].get("body_is_complete", False),
            "media_context": row["metadados"].get("media_reference_present", False),
        }
        item["training_permission"] = training_permission(item)
        item["lm_training_allowed"] = False
        queue.append(item)
    private = ai_root / PRIVATE_DIR
    write_jsonl(private / "review_queue.jsonl", queue)
    # Retain the candidate library locally, not as approved scientific answers.
    library = json.loads((source / "biblioteca_cientifica.json").read_text("utf-8"))
    write_json(private / "knowledge_candidates.json", library)
    summary = {
        "dataset_version": DATASET_VERSION, "records": len(rows),
        "complete_body_claims": sum(r["metadados"].get("body_is_complete", False) for r in rows),
        "counts_by_source": dict(Counter(r["fonte"] for r in rows)),
        "counts_by_topic": dict(Counter(r.get("tema_amostragem") for r in rows)),
        "counts_by_split": dict(Counter(r["split"] for r in rows)),
        "rows_with_answers": sum(bool(r.get("respostas")) for r in rows),
        "answers": sum(len(r.get("respostas", [])) for r in rows),
        "question_identifier_matches": dict(identifiers), "answer_identifier_matches": dict(answer_identifiers),
        "privacy_flags": dict(flags), "quarantined_rows": sum(bool(q["quarantine_reasons"]) for q in queue),
        "quarantine_reasons": dict(Counter(v for q in queue for v in q["quarantine_reasons"])),
        "near_duplicate_pairs": len(pairs), "previous_collection_overlap_ids": len(overlap_ids),
        "near_duplicate_method": "bottom-8 hashed word 4-grams, buckets <=30, Jaccard >=0.8; not exhaustive",
        "source_hashes": {p.name: file_sha256(p) for p in source.glob("*.json*")},
        "source_labels": "machine_candidates_not_gold", "external_training_rows_approved": 0,
        "external_answers_used_as_targets": False, "external_texts_added_to_lm_corpus": False,
        "library_entries_pending_review": len(library["entries"]),
        "public_status": "aggregate_manifest_only_no_external_texts",
        "privacy_status": "redaction_is_not_verified_anonymization; rights_and_lawful_basis_review_pending",
    }
    write_json(manifest_path, summary)
    return summary

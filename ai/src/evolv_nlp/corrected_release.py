"""Apply AI-reviewed development disagreements without modifying reserved data."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import shutil
import unicodedata

from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.real_data import write_json, write_jsonl
from evolv_nlp.review_release import validate_isolation

VERSION = "1.8.0"
PARENT_VERSION = "1.7.0"
RESERVED = ("test", "external_human_language", "quarantine")


def canonical(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value or ""))).strip()


def read_reviews(path):
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        iterator = iter(workbook["Revisao"].values)
        header = next((r for r in iterator if r and r[0] == "Nº"), None)
        if header is None:
            raise ValueError("Reviewed workbook header not found")
        rows = []
        for row in iterator:
            if not row or not isinstance(row[0], (int, float)):
                continue
            if len(row) < 6 or not all(isinstance(v, str) and v.strip() for v in row[1:6]):
                raise ValueError(f"Incomplete review row: {row[0]}")
            rows.append({"number": int(row[0]), "message": row[1], "intent": row[2].strip(),
                         "risks": list(dict.fromkeys(v.strip() for v in re.split(r"[;\n]", row[3]) if v.strip())),
                         "explanation": row[4], "status": row[5],
                         "uncertain": "duvida" in unicodedata.normalize("NFKD", row[5]).encode("ascii", "ignore").decode().lower()})
        if len({r["number"] for r in rows}) != len(rows):
            raise ValueError("Duplicate review numbers")
        return rows
    finally:
        workbook.close()


def match_reviews(reviews, disagreements):
    """Match complete text/context only, never model predictions or fuzzy similarity."""
    normalized = [(r, canonical(r["text"]), canonical(r.get("context"))) for r in disagreements]
    exact = defaultdict(list)
    for record, text, _ in normalized:
        exact[text].append(record)
    result, used = [], set()
    for review in reviews:
        text = canonical(review["message"])
        candidates = exact.get(text, [])
        if len(candidates) != 1:
            candidates = [r for r, message, context in normalized
                          if len(message) >= 8 and message in text and (not context or context in text)]
            if len(candidates) > 1:
                size = max(len(canonical(r["text"])) + len(canonical(r.get("context"))) for r in candidates)
                candidates = [r for r in candidates if len(canonical(r["text"])) + len(canonical(r.get("context"))) == size]
        if len(candidates) != 1 or candidates[0]["id"] in used:
            raise ValueError(f"Missing, duplicate or ambiguous correspondence at review {review['number']}")
        if candidates[0]["partition"] not in {"train", "validation"}:
            raise ValueError("Review attempted to change a reserved partition")
        used.add(candidates[0]["id"])
        result.append((review, candidates[0]["id"]))
    return result


def load_partition(ai_root, partition):
    return read_jsonl(ai_root / f"data/releases/{VERSION}/private/{partition}.jsonl")


def import_corrections(source: Path, ai_root: Path):
    output = ai_root / f"data/releases/{VERSION}"
    if (output / "manifest.json").exists():
        existing = json.loads((output / "manifest.json").read_text("utf-8"))
        if existing["review_workbook_sha256"] != file_sha256(source):
            raise ValueError("Finalized corrected release has a different source")
        for name, digest in existing["files"].items():
            if file_sha256(output / name) != digest:
                raise ValueError("Corrected release changed after finalization")
        return existing
    parent = ai_root / f"data/releases/{PARENT_VERSION}"
    taxonomy = json.loads((parent / "taxonomy.json").read_text("utf-8"))
    intents = {r["id"] for r in taxonomy["intents"]}
    risks = {r["id"] for r in taxonomy["risks"]}
    rows = read_jsonl(parent / "private/records.jsonl")
    index = {r["id"]: r for r in rows}
    old = read_jsonl(ai_root / "artifacts/baseline/1.6.0/private/errors.jsonl")
    development = [r for r in old if r["partition"] in {"train", "validation"}]
    reviews = read_reviews(source)
    if len(reviews) != len(development) or len(reviews) != 2180:
        raise ValueError("Unexpected review coverage")
    changes, counts = [], Counter()
    source_digest = file_sha256(source)
    for review, rid in match_reviews(reviews, development):
        if review["intent"] not in intents or not review["risks"] or not set(review["risks"]) <= risks:
            raise ValueError(f"Unknown or empty labels at {review['number']}")
        if "none" in review["risks"] and len(review["risks"]) != 1:
            raise ValueError("none must remain exclusive")
        record = index[rid]
        before = {"intent": record["label"], "risks": record["risks"], "status": record["review_status"]}
        intent_changed = record["label"] != review["intent"]
        risk_changed = set(record["risks"]) != set(review["risks"])
        record["label"] = review["intent"]
        record["risks"] = review["risks"]
        record["secondary_intents"] = [x for x in record["secondary_intents"] if x != record["label"]]
        record["review_status"] = "revisado_ia_provisorio" if review["uncertain"] else "revisado_ia"
        record["human_gold"] = False
        record["ai_review"] = {"source_sha256": source_digest, "row_number": review["number"],
                               "uncertain": review["uncertain"], "before": before,
                               "explanation_not_a_model_feature": True}
        counts["intent_changes"] += intent_changed
        counts["risk_changes"] += risk_changed
        counts["any_label_change"] += intent_changed or risk_changed
        counts["uncertain_ai_reference"] += review["uncertain"]
        changes.append({"id": rid, "partition": record["partition"], "number": review["number"],
                        "before": before, "after": {"intent": record["label"], "risks": record["risks"]},
                        "uncertain": review["uncertain"], "explanation": review["explanation"]})
    validate_isolation(rows)
    if len(rows) != 12179:
        raise ValueError("Input records were lost")
    private = output / "private"
    private.mkdir(parents=True, exist_ok=True)
    write_jsonl(private / "records.jsonl", rows)
    write_jsonl(private / "annotation_changes.jsonl", changes)
    for part in ("train", "validation"):
        write_jsonl(private / f"{part}.jsonl", [r for r in rows if r["partition"] == part])
    for part in RESERVED:
        shutil.copyfile(parent / f"private/{part}.jsonl", private / f"{part}.jsonl")
    shutil.copyfile(parent / "taxonomy.json", output / "taxonomy.json")
    frozen = {part: file_sha256(parent / f"private/{part}.jsonl") for part in RESERVED}
    assert all(file_sha256(private / f"{part}.jsonl") == digest for part, digest in frozen.items())
    coverage = {part: {"records": sum(r["partition"] == part for r in rows),
                      "intents": dict(Counter(r["label"] for r in rows if r["partition"] == part)),
                      "uncertain_ai_reference": sum(r["partition"] == part and r.get("ai_review", {}).get("uncertain", False) for r in rows)}
                for part in sorted({r["partition"] for r in rows})}
    manifest = {"dataset_version": VERSION, "parent_version": PARENT_VERSION, "total_imported": len(rows),
        "parent_manifest_sha256": file_sha256(parent / "manifest.json"),
        "review_workbook_sha256": source_digest, "reviewed_records": len(reviews),
        "changes": dict(counts), "coverage": coverage, "reserved_byte_identical": frozen,
        "taxonomy_counts": {"intents": len(intents), "risks": len(risks)},
        "review_authority": "AI_reviewed_experimental_reference_not_human_gold",
        "validation_bias": "review_selected_prior_model_disagreements_and_exposed_predictions; not independent gold",
        "features": "unchanged original input only; explanations/status/predictions are never input features",
        "privacy": {"raw_text_sent_to_api": False, "anonymization_verified": False,
                    "public_redistribution_allowed": False, "automatic_lm_training": False},
        "files": {p.relative_to(output).as_posix(): file_sha256(p) for p in private.glob("*.jsonl")}}
    write_json(output / "manifest.json", manifest)
    return manifest

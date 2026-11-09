"""Deterministic, source-preserving preparation. No model or web access."""
from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import unicodedata


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def spans(text: str, limit: int) -> list[tuple[int, int]]:
    """Non-overlapping word-bounded slices; prefer sentence boundaries.

    Offsets refer to the original Python Unicode string, not UTF-8 bytes.
    Inter-slice whitespace is preserved in the offsets, so concatenation is exact.
    """
    if limit < 1:
        raise ValueError("max_words must be positive")
    words = list(re.finditer(r"\S+", text))
    if not words:
        raise ValueError("empty content")
    result, first, start = [], 0, 0
    while first < len(words):
        last = min(first + limit, len(words))
        if last < len(words):
            candidates = [i + 1 for i in range(first, last)
                          if re.search(r"[.!?][\"')]*$", words[i].group())]
            if candidates:
                last = candidates[-1]
        end = words[last].start() if last < len(words) else len(text)
        result.append((start, end))
        start, first = end, last
    return result


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def prepare(ai_root: Path, output: Path, config: dict, as_of: date) -> dict:
    if output.exists():
        raise FileExistsError(f"Release already exists: {output}. Use a new version.")
    if config["version"] not in {"1.0.0", "1.1.0"}:
        raise ValueError("unsupported preparation schema")
    if config["version"] == "1.1.0" and any(k not in config for k in (
            "knowledge_input", "sources_input", "topics_input", "risks_input", "supplements_input", "evidence_input")):
        raise ValueError("Explicit knowledge roles/evidence required")
    inputs = {rel: ai_root / rel for rel in config["inputs"]}
    if any(not p.resolve().is_relative_to(ai_root.resolve()) for p in inputs.values()):
        raise ValueError("input outside AI directory")
    snapshots = {rel: digest(path) for rel, path in inputs.items()}
    kb_rel = config.get("knowledge_input", "data/knowledge/knowledge_chunks.v1.json")
    sources_rel = config.get("sources_input", "data/metadata/sources.v1.json")
    topics_rel = config.get("topics_input", "data/taxonomy/topics.v1.json")
    risks_rel = config.get("risks_input", "data/taxonomy/risks.v1.json")
    supplements_rel = config.get("supplements_input", "data/knowledge/coach-boundaries.v1.json")
    kb = read(inputs[kb_rel])
    sources = read(inputs[sources_rel])["sources"]
    evidence = {}
    if config.get("evidence_input"):
        ledger = read(inputs[config["evidence_input"]])["entries"]
        evidence = {e["id"]: e for e in ledger}
        if len(evidence) != len(ledger):
            raise ValueError("duplicate evidence id")
        for entry in ledger:
            for name, expected in entry.get("local_sha256", {}).items():
                p = (ai_root.parent / name).resolve()
                if not p.is_relative_to(ai_root.parent.resolve()) or digest(p) != expected:
                    raise ValueError("internal evidence contract changed")
                snapshots["../" + name] = expected
    source_map = {s["id"]: s for s in sources}
    if len(source_map) != len(sources):
        raise ValueError("duplicate source id")
    for source in sources:
        date.fromisoformat(source["review_due_at"])
        if not source.get("url") and not source.get("path"):
            raise ValueError(f"missing citation locator: {source['id']}")
        if source.get("path"):
            path = (ai_root.parent / source["path"]).resolve()
            if not path.is_relative_to(ai_root.parent.resolve()):
                raise ValueError("internal source outside repository")
            snapshots["../" + source["path"]] = digest(path)
    topics = {x["id"] for x in read(inputs[topics_rel])["topics"]}
    risks = {x["id"] for x in read(inputs[risks_rel])["risks"]}
    documents, chunks, quarantine, seen_ids, seen_text = [], [], [], set(), {}
    for doc in kb["chunks"]:
        doc_id = doc["id"]
        if doc_id in seen_ids:
            raise ValueError(f"duplicate document id: {doc_id}")
        seen_ids.add(doc_id)
        for key in ("text", "title", "domain", "allowed_use", "not_for", "response_mode",
                    "confidence", "evidence_level", "version", "reviewed_at"):
            if not isinstance(doc.get(key), str) or not doc[key].strip():
                raise ValueError(f"missing {key}: {doc_id}")
        date.fromisoformat(doc["reviewed_at"])
        due = date.fromisoformat(doc["review_due_at"])
        if doc["domain"] not in {"training", "nutrition", "recovery", "safety"}:
            raise ValueError(f"unknown domain: {doc_id}")
        if not doc["topic_ids"] or set(doc["topic_ids"]) - topics:
            raise ValueError(f"unknown/missing topics: {doc_id}")
        if set(doc["risk_tags"]) - risks:
            raise ValueError(f"unknown risks: {doc_id}")
        if not doc["source_ids"] or set(doc["source_ids"]) - source_map.keys():
            raise ValueError(f"unknown/missing sources: {doc_id}")
        if evidence and (not doc.get("evidence_ids") or set(doc["evidence_ids"]) - evidence.keys()):
            raise ValueError(f"unknown/missing evidence: {doc_id}")
        key = normalized(doc["text"])
        if key in seen_text:
            raise ValueError(f"duplicate content: {doc_id}, {seen_text[key]}")
        seen_text[key] = doc_id
        refs = [source_map[s] for s in doc["source_ids"]]
        reasons = []
        if due <= as_of:
            reasons.append("document_review_due")
        if date.fromisoformat(doc["reviewed_at"]) > as_of:
            reasons.append("future_document_review")
        for source in refs:
            if source["status"] != "approved":
                reasons.append("source_not_approved:" + source["id"])
            if date.fromisoformat(source["review_due_at"]) <= as_of:
                reasons.append("source_review_due:" + source["id"])
            if date.fromisoformat(source["last_verified_at"]) > as_of:
                reasons.append("future_source_review:" + source["id"])
        effective_due = min([doc["review_due_at"]] + [s["review_due_at"] for s in refs])
        documents.append({**doc, "eligible_as_of_build": not reasons,
                          "effective_review_due_at": effective_due})
        if reasons:
            quarantine.append({"document_id": doc_id, "reasons": reasons,
                               "input": kb_rel})
            continue
        # Keep each already-curated short fact intact; no arbitrary padding/overlap.
        for n, (start, end) in enumerate(spans(doc["text"], config["max_words"]), 1):
            text = doc["text"][start:end]
            context = {k: doc[k] for k in ("title", "domain", "topic_ids", "risk_tags",
                       "response_mode", "allowed_use", "not_for", "confidence", "evidence_level")}
            for key in ("evidence_ids", "evidence_notes", "content_kind"):
                if key in doc:
                    context[key] = doc[key]
            chunks.append({"id": f"kb:{doc_id}:v{doc['version']}:{n:03d}",
                           "document_id": doc_id, "ordinal": n,
                           "language": kb["language"], **context,
                           "text": text, "char_start": start, "char_end": end,
                           "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                           "embedding_text": doc["title"] + "\n" + text.strip(),
                           "source_ids": doc["source_ids"], "citations": refs,
                           "reviewed_at": doc["reviewed_at"],
                           "effective_review_due_at": effective_due,
                           "source_version": doc["version"],
                           "generation_context": {**context, "text": text,
                                                  "source_ids": doc["source_ids"],
                                                  "citations": refs,
                                                  "effective_review_due_at": effective_due}})
    supplements = read(inputs[supplements_rel])["chunks"]
    for doc in supplements:
        quarantine.append({"document_id": "boundary:" + doc["id"],
                           "input": supplements_rel,
                           "reasons": ["missing_registered_sources_topics_review_dates"],
                           "record": doc})
    # Recheck all bytes before publishing, including internal source documents.
    for rel, expected in snapshots.items():
        if digest(ai_root / rel) != expected:
            raise ValueError(f"input changed during preparation: {rel}")
    report = {"phase": config.get("phase", "7.05.1"), "version": config["version"],
              "as_of": as_of.isoformat(), "documents": len(documents),
              "eligible_documents": sum(d["eligible_as_of_build"] for d in documents),
              "retrieval_chunks": len(chunks), "registered_sources": len(sources),
              "quarantined_records": len(quarantine),
              "domains": dict(sorted(Counter(c["domain"] for c in chunks).items())),
              "covered_topics": sorted({t for c in chunks for t in c["topic_ids"]}),
              "uncovered_topics": sorted(topics - {t for c in chunks for t in c["topic_ids"]}),
              "covered_risk_tags": sorted({r for c in chunks for r in c["risk_tags"]}),
              "max_chunk_words": max((len(c["text"].split()) for c in chunks), default=0),
              "validation": "passed", "source_web_reverification_performed": bool(evidence),
              "semantic_index_built": False, "app_integrated": False}
    if evidence:
        report["source_review_scope"] = dict(Counter(e["status"] for e in evidence.values()))
        report["source_review_limitation"] = "Selected scopes only; inherited/unverified entries remain explicit. Not clinical validation."
    output.mkdir(parents=True, exist_ok=False)
    write(output / "documents.json", documents)
    write(output / "sources.json", sources)
    (output / "chunks.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks), encoding="utf-8")
    write(output / "quarantine.json", quarantine)
    write(output / "report.json", report)
    write(output / "config.json", config)
    code_paths = [Path(__file__), ai_root / "scripts/prepare_rag_base.py"]
    write(output / "manifest.json", {"version": config["version"], "as_of": as_of.isoformat(),
          "inputs": snapshots, "code": {str(p.relative_to(ai_root)): digest(p) for p in code_paths},
          "outputs": {p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return report

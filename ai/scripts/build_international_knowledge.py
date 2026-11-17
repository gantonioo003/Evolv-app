"""Build an appended RAG release from reviewed guidance and the previous index."""

import argparse
from datetime import date
import hashlib
from pathlib import Path
import sys

import numpy as np

AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI / "src"))
from evolv_rag.preparation import digest, read, write
from evolv_rag.retrieval_runtime import EXPANSION_RELEASES, load_search


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", choices=tuple(EXPANSION_RELEASES), default="1.2.0")
    release = parser.parse_args().release
    source_path = AI / "data/knowledge" / EXPANSION_RELEASES[release]
    expansion = read(source_path)
    parent_version = ("1.1.1", *EXPANSION_RELEASES)[list(EXPANSION_RELEASES).index(release)]
    parent = AI / "artifacts/rag" / parent_version
    target = AI / "artifacts/rag" / release
    if target.exists():
        raise FileExistsError(target)
    reviewed, due = expansion["verified_at"], expansion["review_due_at"]
    if expansion["version"] != "1.0.0" or date.fromisoformat(reviewed) >= date.fromisoformat(due):
        raise ValueError("Invalid international knowledge metadata")
    base = load_search(AI, parent_version)
    encoder = base.encoder
    ids = {row["document_id"] for row in base.rows}
    topics = {topic for row in base.rows for topic in row["topic_ids"]}
    rows = []
    for passage in expansion["passages"]:
        source = expansion["sources"][passage["source"]]
        key = passage["id"]
        text = passage["text"].strip()
        domain = passage["domain"]
        if (key in ids or not text or not source["url"].startswith("https://")
                or domain not in {"training", "nutrition", "recovery", "safety"}
                or not set(passage["topics"]).issubset(topics) or not passage["section"]):
            raise ValueError(f"Invalid international passage {key}")
        ids.add(key)
        evidence_id = f"evidence:{passage['source']}:{key}"
        citation = {
            **source, "id": passage["source"], "status": "approved",
            "last_verified_at": reviewed, "review_due_at": due,
            "verification": {"id": evidence_id, "section": passage["section"],
                             "method": "selected_public_guidance",
                             "reuse_policy": "reference_and_paraphrase_only"},
        }
        allowed = "Educação geral para adultos ou a população explicitamente indicada no trecho."
        not_for = "Diagnóstico, dose pessoal, reabilitação ou prescrição clínica."
        notes = f"Síntese em português da seção {passage['section']}."
        rows.append({
            "id": f"kb:{key}:v1.0.0:001", "document_id": key, "ordinal": 1,
            "language": "pt-BR", "title": passage["title"], "domain": domain,
            "topic_ids": passage["topics"], "risk_tags": [], "response_mode": "educate",
            "allowed_use": allowed, "not_for": not_for, "confidence": "high",
            "evidence_ids": [evidence_id], "evidence_notes": notes,
            "content_kind": "scientific_or_safety_synthesis",
            "text": text, "char_start": 0, "char_end": len(text),
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "embedding_text": "\n".join((passage["title"], text, passage["terms"])),
            "source_ids": [passage["source"]], "citations": [citation],
            "reviewed_at": reviewed, "effective_review_due_at": due,
            "generation_context": {
                "text": text, "allowed_use": allowed, "not_for": not_for,
                "evidence_notes": notes, "citations": [citation],
            },
        })
    vectors = np.concatenate((base.vectors, encoder.encode([row["embedding_text"] for row in rows])))
    target.mkdir(parents=True)
    np.save(target / "vectors.npy", vectors, allow_pickle=False)
    write(target / "chunks.json", base.rows + rows)
    write(target / "manifest.json", {
        "version": release, "parent_manifest_sha256": digest(parent / "manifest.json"),
        "source_sha256": digest(source_path), "encoder": encoder.manifest,
        "rows": len(vectors), "additional_passages": len(rows), "dimension": 384,
        "outputs": {name: digest(target / name) for name in ("vectors.npy", "chunks.json")},
    })
    print(f"Built {len(rows)} new passages. Total: {len(vectors)}.")


if __name__ == "__main__":
    main()

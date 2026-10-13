from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.real_data import normalized_key, reserved_texts, write_json, write_jsonl


def extend_corpus(ai_root: Path) -> dict:
    previous = ai_root / "data/lm_corpus/1.0.0"
    output = ai_root / "data/lm_corpus/1.1.0"
    if (output / "manifest.json").exists():
        raise ValueError("Corpus ja versionado: crie uma nova versao, nao sobrescreva.")
    base_manifest = json.loads((previous / "manifest.json").read_text("utf-8"))
    for filename, metadata in base_manifest.get("files", {}).items():
        if (previous / filename).is_file() and metadata.get("sha256") != file_sha256(previous / filename):
            raise ValueError(f"Corpus historico alterado: {filename}")
    train = read_jsonl(previous / "train.jsonl")
    validation = read_jsonl(previous / "validation.jsonl")
    test = read_jsonl(previous / "test.jsonl")
    blocked_groups = {r["group_id"] for r in validation + test}
    blocked_texts = {normalized_key(r["text"]) for r in validation + test} | reserved_texts(ai_root)
    seen = {normalized_key(r["text"]) for r in train}
    additions = []
    authored = json.loads((ai_root / "data/source/expansion_ptbr.v1.json").read_text("utf-8"))
    # Only authored TRAIN families, never external questions or new development titles.
    for task in ("intents", "risks"):
        for label, partitions in authored[task].items():
            for index, text in enumerate(partitions["train"]):
                additions.append({"doc_id": f"evolv-v14:{task}:{label}:{index}",
                                  "group_id": f"evolv-v14:{task}:{label}:train:{index}",
                                  "source": "evolv_v14_authored_train", "split": "train",
                                  "text": text, "license": "Project-owned", "attribution_url": "repository-local",
                                  "human_generated": False, "conversational": False,
                                  "content_kind": "synthetic_question_not_human_or_reviewed_answer"})
    knowledge = json.loads((ai_root / "data/knowledge/knowledge_chunks.v1.json").read_text("utf-8"))
    train_knowledge_ids = {r["group_id"] for r in train if r["source"] == "evolv_knowledge"}
    for chunk in knowledge["chunks"]:
        group_id = f"evolv-knowledge:{chunk['id']}"
        if group_id not in train_knowledge_ids or group_id in blocked_groups:
            continue
        additions.append({"doc_id": f"{group_id}:qa", "group_id": group_id,
                          "source": "evolv_knowledge_qa", "split": "train",
                          "text": f"Usuario: Me explica: {chunk['title']}.\nAssistente: {chunk['text']}\nLimite: {chunk['not_for']}",
                          "license": "Project-owned", "attribution_url": "repository-local",
                          "knowledge_source_ids": chunk["source_ids"], "human_generated": False,
                          "conversational": True, "content_kind": "synthetic_qa_from_existing_reviewed_knowledge",
                          "knowledge_reviewed_at": chunk["reviewed_at"]})
    accepted = []
    for row in additions:
        key = normalized_key(row["text"])
        if row["group_id"] in blocked_groups or key in blocked_texts or key in seen:
            continue
        seen.add(key)
        accepted.append(row)
    output.mkdir(parents=True, exist_ok=True)
    for split in ("validation", "test"):
        for extension in ("jsonl", "txt"):
            shutil.copy2(previous / f"{split}.{extension}", output / f"{split}.{extension}")
    combined = train + accepted
    write_jsonl(output / "train.jsonl", combined)
    (output / "train.txt").write_text("\n\n".join(r["text"] for r in combined) + "\n", "utf-8", newline="\n")
    manifest = {
        "version": "1.1.0", "base_version": "1.0.0", "language": "pt-BR",
        "status": "prepared_not_trained", "train_rows": len(combined), "added_rows": len(accepted),
        "validation_rows": len(validation), "test_rows": len(test),
        "added_sources": dict(Counter(r["source"] for r in accepted)),
        "whitespace_units": sum(len(r["text"].split()) for r in combined + validation + test),
        "actual_token_count": None,
        "policy": {
            "validation_and_test_preserved_byte_for_byte": True,
            "web_questions_excluded": "All 10000 have unverified training/redistribution rights and are candidates, not reviewed knowledge.",
            "community_answers_excluded": True,
            "synthetic_rows_not_reported_as_human": True,
            "no_lm_training_or_tokenizer_training_started": True,
            "corpus_size_is_not_response_quality": True,
        },
        "files": {path.name: {"sha256": file_sha256(path), "bytes": path.stat().st_size}
                  for path in output.iterdir() if path.is_file()},
        "inputs": {"old_manifest": file_sha256(previous / "manifest.json"),
                   "authored_train": file_sha256(ai_root / "data/source/expansion_ptbr.v1.json"),
                   "knowledge": file_sha256(ai_root / "data/knowledge/knowledge_chunks.v1.json")},
    }
    write_json(output / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(extend_corpus(AI_ROOT), ensure_ascii=False, indent=2))

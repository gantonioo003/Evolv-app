import json
import sys
from collections import Counter
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.privacy import review_text
from evolv_nlp.real_data import normalized_key, reserved_texts, write_json, write_jsonl


def extend(ai_root):
    previous = ai_root / "data/lm_corpus/1.1.0"
    output = ai_root / "data/lm_corpus/1.2.0"
    if (output / "manifest.json").exists():
        raise ValueError("Corpus finalizado; use nova versao")
    manifest = json.loads((previous / "manifest.json").read_text("utf-8"))
    for filename, meta in manifest["files"].items():
        if file_sha256(previous / filename) != meta["sha256"]:
            raise ValueError("Corpus anterior alterado")
    validation, test = read_jsonl(previous / "validation.jsonl"), read_jsonl(previous / "test.jsonl")
    reserved = reserved_texts(ai_root) | {normalized_key(r["text"]) for r in validation + test}
    blocked_groups = {r["group_id"] for r in validation + test}
    source = json.loads((ai_root / "data/source/context_expansion.v1.json").read_text("utf-8"))
    for collection in ("intents", "risks"):
        for samples in source[collection].values():
            reserved.update(normalized_key(t) for split in ("validation", "test") for t in samples[split])
    train, excluded = [], []
    for row in read_jsonl(previous / "train.jsonl"):
        review = review_text(row["text"])
        # Keep historical held-out bytes, but do not repeat detected identifiers in a new train release.
        if review.identifier_counts or (row.get("source", "").lower().startswith("oasst") and review.flags):
            excluded.append({"doc_id": row["doc_id"], "reasons": list(review.flags)})
        else:
            train.append(row)
    seen = {normalized_key(r["text"]) for r in train}
    additions = []
    for collection in ("intents", "risks"):
        for label, samples in source[collection].items():
            for index, text in enumerate(samples["train"]):
                additions.append({"doc_id": f"context-{collection}-{label}-{index}",
                    "group_id": f"evolv-context:{collection}:{label}:train:{index}", "text": text,
                    "source": "evolv_context_authored", "split": "train", "license": "Project-owned",
                    "attribution_url": "repository-local", "human_generated": False,
                    "conversational": False, "content_kind": "synthetic_question"})
    boundaries = json.loads((ai_root / "data/knowledge/coach-boundaries.v1.json").read_text("utf-8"))
    for chunk in boundaries["chunks"]:
        additions.append({"doc_id": f"boundary-{chunk['id']}", "group_id": f"evolv-boundary:{chunk['id']}",
            "text": f"Usuario: {chunk['question']}\nAssistente: {chunk['answer']}",
            "source": "evolv_coach_boundary_qa", "split": "train", "license": "Project-owned",
            "attribution_url": "repository-local", "source_urls": chunk["source_urls"],
            "human_generated": False, "conversational": True, "content_kind": "synthetic_product_boundary_qa"})
    accepted = []
    for row in additions:
        key = normalized_key(row["text"])
        if key not in seen and key not in reserved and row["group_id"] not in blocked_groups:
            accepted.append(row)
            seen.add(key)
    train.extend(accepted)
    output.mkdir(parents=True, exist_ok=True)
    # Copy bytes only for held-out files; do not transform evaluation data.
    import shutil
    for filename in ("validation.jsonl", "validation.txt", "test.jsonl", "test.txt"):
        shutil.copyfile(previous / filename, output / filename)
    write_jsonl(output / "train.jsonl", train)
    (output / "train.txt").write_text("\n\n".join(r["text"] for r in train) + "\n", encoding="utf-8", newline="\n")
    write_json(output / "excluded_documents.json", {"documents": excluded, "not_a_complete_privacy_audit": True})
    report = {"version": "1.2.0", "base_version": "1.1.0", "rows": len(train)+len(validation)+len(test),
              "added_rows": len(accepted), "excluded_previous_train_rows": len(excluded),
              "added_sources": dict(Counter(r["source"] for r in accepted)),
              "external_dataset_questions_added": 0, "forum_answers_added": 0,
              "heldout_bytes_preserved": True, "model_or_tokenizer_trained": False,
              "actual_token_count": None,
              "files": {p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size} for p in output.glob("*.*")}}
    write_json(output / "manifest.json", report)
    return report


if __name__ == "__main__":
    print(json.dumps(extend(AI_ROOT), indent=2))

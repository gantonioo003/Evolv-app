from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests


AI_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = AI_ROOT / ".cache" / "datasets"
OUTPUT_ROOT = AI_ROOT / "data" / "lm_corpus" / "1.0.0"
OASST_PARQUET_API = (
    "https://datasets-server.huggingface.co/parquet?dataset=OpenAssistant%2Foasst1"
)
WIKIPEDIA_ROWS_API = "https://datasets-server.huggingface.co/rows"
WIKIPEDIA_DATASET = "wikimedia/wikipedia"
WIKIPEDIA_CONFIG = "20231101.pt"
WIKIPEDIA_OFFSETS = tuple(range(0, 1_000_000, 25_000))
MAX_TEXT_CHARS = 6_000


SOURCES = {
    "oasst1_ptbr_human": {
        "name": "OpenAssistant Conversations (OASST1)",
        "url": "https://huggingface.co/datasets/OpenAssistant/oasst1",
        "license": "Apache-2.0",
        "accepted": True,
        "purpose": "Human-written Brazilian Portuguese prompts and dialogue turns.",
        "selection": "pt-BR, review_result=true, deleted=false, synthetic=false.",
    },
    "wikipedia_pt": {
        "name": "Wikipedia em português 2023-11-01",
        "url": "https://huggingface.co/datasets/wikimedia/wikipedia",
        "license": "CC-BY-SA-3.0",
        "dataset_card_licenses": ["CC-BY-SA-3.0", "GFDL"],
        "accepted": True,
        "purpose": "Broad Portuguese prose for tokenizer and causal-language modeling.",
        "selection": "Deterministic article sample at declared offsets; article attribution retained.",
    },
    "evolv_knowledge": {
        "name": "Evolv reviewed knowledge base",
        "url": "repository-local",
        "license": "Project-owned",
        "accepted": True,
        "purpose": "Reviewed domain prose about training, nutrition, recovery and safety.",
        "selection": "All knowledge chunks in version 1.1.0.",
    },
    "evolv_nlu_train": {
        "name": "Evolv NLU dataset 1.3.0 training partition",
        "url": "repository-local",
        "license": "Project-owned and attributed derivatives",
        "accepted": True,
        "purpose": "Short informal language and app-specific requests.",
        "selection": "Training split only; validation, test and human holdout excluded.",
    },
}


BLOCKED_SOURCES = [
    {
        "name": "AKCIT/MedPT",
        "url": "https://huggingface.co/datasets/AKCIT/MedPT",
        "reason": "Excellent real Brazilian health questions, but no explicit dataset license was displayed during this audit. Do not ingest until permission is clear.",
    },
    {
        "name": "clips/mqa and pt-BR derivatives",
        "url": "https://huggingface.co/datasets/clips/mqa",
        "reason": "The packaging is CC0, while the authors explicitly state that they do not own the extracted web text.",
    },
    {
        "name": "Reddit posts",
        "url": "https://redditinc.com/policies/data-api-terms",
        "reason": "No scraping or model-training ingestion without the required rights and permission.",
    },
    {
        "name": "TucanoBR/GigaVerbo",
        "url": "https://huggingface.co/datasets/TucanoBR/GigaVerbo",
        "reason": "Massive mixed-source corpus; individual-source licensing and local hardware budget need a separate audit.",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the licensed TinyLM corpus version 1.0.0.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use only files already available in ai/.cache/datasets.",
    )
    return parser.parse_args()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=240)
    response.raise_for_status()
    path.write_bytes(response.content)


def ensure_oasst_cache(offline: bool) -> list[Path]:
    files = sorted(CACHE_ROOT.glob("oasst1_*.parquet"))
    if files:
        return files
    if offline:
        raise FileNotFoundError("OASST1 cache is absent and --offline was requested")
    index = requests.get(OASST_PARQUET_API, timeout=60)
    index.raise_for_status()
    for item in index.json()["parquet_files"]:
        path = CACHE_ROOT / f"oasst1_{item['split']}.parquet"
        download(item["url"], path)
    return sorted(CACHE_ROOT.glob("oasst1_*.parquet"))


def label_score(labels: Any, name: str) -> float:
    if not isinstance(labels, dict):
        return 0.0
    names = list(labels.get("name", []))
    values = list(labels.get("value", []))
    try:
        return float(values[names.index(name)])
    except (ValueError, IndexError, TypeError):
        return 0.0


def clean_text(value: str) -> str:
    value = html.unescape(unicodedata.normalize("NFC", value))
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL_REMOVIDO]", value)
    value = re.sub(r"https?://\S+", "[URL_REMOVIDA]", value)
    value = re.sub(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?\d{4,5}[-\s]?\d{4}(?!\d)", "[TELEFONE_REMOVIDO]", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalized_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def split_for(group_id: str) -> str:
    bucket = int(hashlib.sha256(group_id.encode()).hexdigest()[:8], 16) % 100
    if bucket == 0:
        return "validation"
    if bucket == 1:
        return "test"
    return "train"


def chunks(text: str, max_chars: int = MAX_TEXT_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    paragraphs = [item.strip() for item in text.split("\n") if item.strip()]
    result: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        else:
            sentences = [paragraph]
        for sentence in sentences:
            if len(current) + len(sentence) + 2 <= max_chars:
                current = f"{current}\n\n{sentence}".strip()
            else:
                if current:
                    result.append(current)
                current = sentence[:max_chars]
    if current:
        result.append(current)
    return result


def oasst_documents(offline: bool) -> list[dict[str, Any]]:
    frame = pd.concat([pd.read_parquet(path) for path in ensure_oasst_cache(offline)], ignore_index=True)
    holdout_path = AI_ROOT / "data" / "releases" / "1.3.0" / "challenge" / "real_human_examples.jsonl"
    reserved_ids = {
        json.loads(line)["source_id"].removeprefix("oasst1:")
        for line in holdout_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    reserved_trees = set(
        frame.loc[frame["message_id"].isin(reserved_ids), "message_tree_id"].astype(str)
    )
    selected = frame[
        (frame["lang"] == "pt-BR")
        & (frame["review_result"] == True)  # noqa: E712
        & (frame["deleted"] == False)  # noqa: E712
        & (frame["synthetic"] == False)  # noqa: E712
    ]
    documents: list[dict[str, Any]] = []
    for row in selected.itertuples(index=False):
        if str(row.message_tree_id) in reserved_trees:
            continue
        if label_score(row.labels, "pii") > 0.2 or label_score(row.labels, "toxicity") > 0.5:
            continue
        text = clean_text(str(row.text))
        if len(text) < 3 or len(text) > 12_000:
            continue
        documents.append(
            {
                "doc_id": f"oasst1:{row.message_id}",
                "group_id": f"oasst1-tree:{row.message_tree_id}",
                "text": text,
                "source": "oasst1_ptbr_human",
                "license": "Apache-2.0",
                "human_generated": True,
                "conversational": True,
                "role": str(row.role),
                "attribution_url": "https://huggingface.co/datasets/OpenAssistant/oasst1",
            }
        )
    return documents


def wikipedia_cache_path(offset: int) -> Path:
    return CACHE_ROOT / f"wikipedia_pt_{offset:07d}.json"


def ensure_wikipedia_cache(offset: int, offline: bool) -> dict[str, Any]:
    path = wikipedia_cache_path(offset)
    if not path.exists():
        if offline:
            raise FileNotFoundError(f"Wikipedia cache missing: {path}")
        error: Exception | None = None
        for attempt in range(1, 6):
            try:
                response = requests.get(
                    WIKIPEDIA_ROWS_API,
                    params={
                        "dataset": WIKIPEDIA_DATASET,
                        "config": WIKIPEDIA_CONFIG,
                        "split": "train",
                        "offset": offset,
                        "length": 100,
                    },
                    timeout=120,
                )
                response.raise_for_status()
                write_json(path, response.json())
                error = None
                break
            except requests.RequestException as caught:
                error = caught
                if attempt < 5:
                    time.sleep(attempt * 2)
        if error is not None:
            raise error
    return json.loads(path.read_text(encoding="utf-8"))


def wikipedia_documents(offline: bool) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for offset in WIKIPEDIA_OFFSETS:
        payload = ensure_wikipedia_cache(offset, offline)
        for item in payload.get("rows", []):
            row = item["row"]
            article_id = str(row.get("id") or item["row_idx"])
            title = clean_text(str(row.get("title") or ""))
            text = clean_text(str(row.get("text") or ""))
            if len(text) < 200:
                continue
            header = f"{title}\n\n" if title else ""
            for index, part in enumerate(chunks(text)):
                documents.append(
                    {
                        "doc_id": f"wikipedia:{article_id}:{index}",
                        "group_id": f"wikipedia-article:{article_id}",
                        "text": f"{header}{part}".strip(),
                        "source": "wikipedia_pt",
                        "license": "CC-BY-SA-3.0",
                        "human_generated": True,
                        "conversational": False,
                        "title": title,
                        "attribution_url": row.get("url") or "https://pt.wikipedia.org/",
                    }
                )
    return documents


def evolv_documents() -> list[dict[str, Any]]:
    knowledge = json.loads(
        (AI_ROOT / "data" / "knowledge" / "knowledge_chunks.v1.json").read_text(encoding="utf-8")
    )["chunks"]
    documents = [
        {
            "doc_id": f"evolv-knowledge:{item['id']}",
            "group_id": f"evolv-knowledge:{item['id']}",
            "text": clean_text(f"{item['title']}\n\n{item['text']}"),
            "source": "evolv_knowledge",
            "license": "Project-owned",
            "human_generated": False,
            "conversational": False,
            "domain": item["domain"],
            "attribution_url": "repository-local",
        }
        for item in knowledge
    ]
    nlu_root = AI_ROOT / "data" / "releases" / "1.3.0" / "splits" / "train"
    for path in sorted(nlu_root.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            documents.append(
                {
                    "doc_id": f"evolv-nlu:{row['id']}",
                    "group_id": f"evolv-nlu:{row.get('group_id', row['id'])}",
                    "text": clean_text(row["text"]),
                    "source": "evolv_nlu_train",
                    "license": "Project-owned and attributed derivatives",
                    "human_generated": row["source_type"] in {"human_real_public"},
                    "conversational": True,
                    "task": row["task"],
                    "label": row["label"],
                    "attribution_url": "repository-local",
                }
            )
    return documents


def deduplicate(documents: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    observed: set[str] = set()
    result: list[dict[str, Any]] = []
    removed = 0
    for document in documents:
        key = normalized_key(document["text"])
        if len(key) < 3 or key in observed:
            removed += 1
            continue
        observed.add(key)
        result.append(document)
    return result, removed


def build(offline: bool = False) -> dict[str, Any]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    candidates = oasst_documents(offline) + wikipedia_documents(offline) + evolv_documents()
    release_root = AI_ROOT / "data" / "releases" / "1.3.0"
    reserved_paths = [
        *sorted((release_root / "splits" / "validation").glob("*.jsonl")),
        *sorted((release_root / "splits" / "test").glob("*.jsonl")),
        *sorted((release_root / "challenge").glob("*.jsonl")),
    ]
    reserved_texts = {
        normalized_key(json.loads(line)["text"])
        for path in reserved_paths
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    filtered = [item for item in candidates if normalized_key(item["text"]) not in reserved_texts]
    documents, duplicates = deduplicate(filtered)
    partitions: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    for document in documents:
        split = split_for(document["group_id"])
        partitions[split].append({**document, "split": split})
    for split in partitions:
        partitions[split].sort(key=lambda item: item["doc_id"])
        write_jsonl(OUTPUT_ROOT / f"{split}.jsonl", partitions[split])
        (OUTPUT_ROOT / f"{split}.txt").write_text(
            "\n\n".join(item["text"] for item in partitions[split]) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    group_splits: dict[str, set[str]] = {}
    for split, rows in partitions.items():
        for row in rows:
            group_splits.setdefault(row["group_id"], set()).add(split)
    leakage = sorted(group for group, splits in group_splits.items() if len(splits) > 1)
    source_counts = Counter(item["source"] for item in documents)
    source_words = Counter()
    for item in documents:
        source_words[item["source"]] += len(item["text"].split())
    split_counts = {split: len(rows) for split, rows in partitions.items()}
    split_words = {
        split: sum(len(item["text"].split()) for item in rows) for split, rows in partitions.items()
    }
    total_words = sum(split_words.values())
    quality = {
        "status": "passed" if not leakage and len(partitions["validation"]) > 0 and len(partitions["test"]) > 0 else "failed",
        "exact_duplicates_removed": duplicates,
        "reserved_nlu_texts_excluded": len(candidates) - len(filtered),
        "nlu_human_holdout_conversations_excluded": True,
        "group_leakage": leakage,
        "documents": len(documents),
        "split_documents": split_counts,
        "split_whitespace_tokens": split_words,
        "whitespace_tokens": total_words,
        "estimated_subword_tokens": round(total_words * 1.35),
        "source_documents": dict(sorted(source_counts.items())),
        "source_whitespace_tokens": dict(sorted(source_words.items())),
        "pii_controls": ["OASST PII label filter", "email redaction", "URL redaction", "phone redaction"],
        "limitations": [
            "This is an educational TinyLM corpus, not production-scale pretraining data.",
            "Wikipedia is broad prose; OASST1 supplies the conversational component.",
            "Automated filtering reduces but cannot guarantee removal of every quality or privacy issue.",
            "Medical answers from unlicensed or weakly sourced datasets were intentionally excluded.",
        ],
    }
    write_json(OUTPUT_ROOT / "quality_report.json", quality)
    write_json(
        OUTPUT_ROOT / "sources.json",
        {
            "corpus_version": "1.0.0",
            "accepted_sources": SOURCES,
            "blocked_sources": BLOCKED_SOURCES,
        },
    )

    files: dict[str, Any] = {}
    for path in sorted(OUTPUT_ROOT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "manifest_version": "1.0.0",
        "corpus_version": "1.0.0",
        "created_at": "2026-10-09",
        "language": "pt-BR",
        "status": quality["status"],
        "split_policy": "SHA-256 of source document/conversation group: 98% train, 1% validation, 1% test.",
        "document_grouping": "All chunks from one Wikipedia article or OASST conversation tree stay in one split.",
        "summary": quality,
        "files": files,
    }
    write_json(OUTPUT_ROOT / "manifest.json", manifest)
    if quality["status"] != "passed":
        raise ValueError(f"Corpus audit failed: {quality}")
    return manifest


if __name__ == "__main__":
    arguments = parse_args()
    print(json.dumps(build(arguments.offline), ensure_ascii=False, indent=2))

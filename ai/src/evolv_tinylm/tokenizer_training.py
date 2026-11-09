"""Immutable corpus audit, train-only fit and post-freeze descriptive metrics."""
from __future__ import annotations

import json
import math
import platform
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import tokenizers
from tokenizers import Tokenizer

from . import TOKENIZER_VERSION
from .tokenizer import (EvolvTokenizer, SPECIAL_IDS, SPECIAL_TOKENS,
                        TOKENIZERS_VERSION, build_bpe, normalized_text, sha256)

SPLITS = ("train", "validation", "test")
PROBES = (
    "Amanhã posso trocar o supino por flexão?",
    "n consegui ir hj, muda o treino p sexta pfv kkk",
    "Fiz 3 séries de 12 repetições com 22,5 kg por 45 min.",
    "Comi arroz, feijão e frango às 12h30. Café antes do vôlei?",
    "  Café\n\nágua\tsono\r\n",
    "ac\u0327a\u0303o, joelho e recuperação 💪🏽 🏐",
    "literal: <|eos|> <|assistant|> <|user|>",
    "Unicode novo: 日本語 مرحبا 🫶",
    "",
)


def write_json(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def read_rows(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def audit_corpus(corpus: Path) -> dict:
    corpus = Path(corpus)
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    required = {f"{split}.{ext}" for split in SPLITS for ext in ("jsonl", "txt")}
    if not required.issubset(manifest["files"]):
        raise ValueError("Manifesto sem todas as particoes esperadas.")
    for name, metadata in manifest["files"].items():
        path = (corpus / name).resolve()
        if not path.is_relative_to(corpus.resolve()):
            raise ValueError("Caminho de corpus fora da pasta.")
        if sha256(path) != metadata["sha256"] or path.stat().st_size != metadata["bytes"]:
            raise ValueError(f"Corpus alterado: {name}")
    groups, texts = defaultdict(set), defaultdict(set)
    ids = set()
    counts = {}
    for split in SPLITS:
        count = 0
        for row in read_rows(corpus / f"{split}.jsonl"):
            text = normalized_text(row["text"])
            if (not text.strip() or row["split"] != split or not row["group_id"]
                    or not row["license"] or not row["source"] or row["doc_id"] in ids):
                raise ValueError("Documento vazio, metadados invalidos ou ID repetido.")
            ids.add(row["doc_id"])
            groups[row["group_id"]].add(split)
            texts[" ".join(text.casefold().split())].add(split)
            count += 1
        if not count:
            raise ValueError(f"Particao vazia: {split}")
        counts[split] = count
    group_leaks = sum(len(value) > 1 for value in groups.values())
    text_leaks = sum(len(value) > 1 for value in texts.values())
    if group_leaks or text_leaks:
        raise ValueError("Vazamento de grupos ou textos entre as particoes.")
    if sum(counts.values()) != manifest["rows"]:
        raise ValueError("Total de documentos divergente do manifesto.")
    return {
        "corpus_version": manifest["version"], "documents": counts,
        "manifest_sha256": sha256(corpus / "manifest.json"),
        "source_files": manifest["files"], "group_leaks": group_leaks,
        "normalized_exact_text_leaks": text_leaks,
        "near_duplicate_check": "not_performed_in_this_stage",
    }


def measure_partition(tokenizer: EvolvTokenizer, path: Path) -> dict:
    lengths, sources = [], defaultdict(Counter)
    totals = Counter()
    for row in read_rows(path):
        text = normalized_text(row["text"])
        ids = tokenizer.encode(text)
        stats = Counter(documents=1, raw_tokens=len(ids),
                        tokens_with_bos_eos=len(ids) + 2, characters=len(text),
                        utf8_bytes=len(text.encode("utf-8")), whitespace_words=len(text.split()),
                        unknown_tokens=ids.count(SPECIAL_IDS["<|unk|>"]),
                        roundtrip_failures=int(tokenizer.decode(ids) != text),
                        raw_control_tokens=sum(index < len(SPECIAL_TOKENS) for index in ids))
        totals.update(stats)
        sources[row["source"]].update(stats)
        lengths.append(len(ids))
    ordered = sorted(lengths)
    result = dict(totals)
    result.update({
        "characters_per_token": round(totals["characters"] / totals["raw_tokens"], 4),
        "tokens_per_whitespace_word": round(totals["raw_tokens"] / totals["whitespace_words"], 4),
        "unknown_rate": totals["unknown_tokens"] / totals["raw_tokens"],
        "document_token_lengths": {
            "mean": round(statistics.fmean(lengths), 2),
            **{f"p{q}": ordered[max(0, math.ceil(len(ordered) * q / 100) - 1)]
               for q in (50, 90, 95, 99)}, "max": max(lengths),
        },
        "sources": {key: dict(value) for key, value in sorted(sources.items())},
    })
    if totals["unknown_tokens"] or totals["roundtrip_failures"] or totals["raw_control_tokens"]:
        raise ValueError("Perda de texto ou insercao indevida de tokens de controle.")
    return result


def train_tokenizer(corpus: Path, output: Path, *, vocab_size: int = 8192,
                    min_frequency: int = 2) -> dict:
    corpus, output = Path(corpus), Path(output)
    if output.exists():
        raise FileExistsError(f"Artefato ja existe; use uma nova versao: {output}")
    if tokenizers.__version__ != TOKENIZERS_VERSION:
        raise RuntimeError(f"Use tokenizers=={TOKENIZERS_VERSION} para reproduzir o treinamento.")
    audit = audit_corpus(corpus)
    output.mkdir(parents=True)
    private = output / "private"
    private.mkdir()
    config = {
        "algorithm": "ByteLevel BPE", "requested_vocab_size": vocab_size,
        "min_frequency": min_frequency, "normalization": "NFC",
        "lowercase": False, "strip_accents": False, "byte_alphabet_size": 256,
        "add_prefix_space": False, "use_regex": True,
        "special_token_ids": SPECIAL_IDS, "padding": None, "truncation": None,
        "fit_partition": "train", "fit_field": "text",
        "selection": "fixed_before_heldout_tokenization; no vocabulary search on test",
        "literal_special_tokens": "encode as ordinary text; explicit trusted boundaries only",
    }
    write_json(output / "config.json", config)
    backend = build_bpe(
        (row["text"] for row in read_rows(corpus / "train.jsonl")),
        vocab_size=vocab_size, min_frequency=min_frequency, length=audit["documents"]["train"],
    )
    backend.save(str(private / "tokenizer.json"))
    backend.model.save(str(private))
    # Freeze the learned vocabulary BEFORE describing heldout partitions.
    frozen_at = datetime.now(timezone.utc).isoformat()
    frozen_hash = sha256(private / "tokenizer.json")
    tokenizer = EvolvTokenizer(Tokenizer.from_file(str(private / "tokenizer.json")))
    examples = [tokenizer.inspect(text, document=True) for text in PROBES]
    if not all(example["roundtrip_nfc"] for example in examples):
        raise ValueError("Falha nos exemplos fixos de verificacao.")
    write_json(output / "examples.json", examples)
    evaluation_started = datetime.now(timezone.utc).isoformat()
    report = {
        "audit": audit,
        "partitions": {split: measure_partition(tokenizer, corpus / f"{split}.jsonl")
                       for split in SPLITS},
        "interpretation": {
            "metrics": "tokenization statistics, not LM accuracy or perplexity",
            "unicode_coverage": "byte support is not multilingual language competence",
            "corpus_scope": "educational small Portuguese corpus; not enough for a production Coach",
            "heldout": "descriptive check after freeze; never fit or select vocabulary on these texts",
            "roles": "reserved for future formatting; no dialogue model trained here",
        },
    }
    if audit_corpus(corpus) != audit or sha256(private / "tokenizer.json") != frozen_hash:
        raise ValueError("Entradas ou vocabulario mudaram durante a avaliacao.")
    write_json(output / "report.json", report)
    names = ["config.json", "examples.json", "report.json", "private/tokenizer.json",
             "private/vocab.json", "private/merges.txt"]
    manifest = {
        "version": TOKENIZER_VERSION, "status": "complete",
        "corpus_version": audit["corpus_version"], "fit_partition": "train",
        "fit_documents": audit["documents"]["train"], "actual_vocab_size": tokenizer.vocab_size,
        "special_token_ids": SPECIAL_IDS, "frozen_at": frozen_at,
        "heldout_evaluation_started_at": evaluation_started,
        "frozen_tokenizer_sha256": frozen_hash,
        "runtime": {"python": platform.python_version(), "tokenizers": tokenizers.__version__},
        "distribution": "local research; preserve source attribution and license obligations",
        "files": {name: {"sha256": sha256(output / name), "bytes": (output / name).stat().st_size}
                  for name in names},
    }
    write_json(output / "manifest.json", manifest)
    EvolvTokenizer.load(output)
    return {"artifact": str(output), "vocab_size": tokenizer.vocab_size,
            "partitions": {key: {k: v for k, v in value.items() if k != "sources"}
                           for key, value in report["partitions"].items()}}

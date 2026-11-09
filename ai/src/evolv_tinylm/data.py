"""Prepare immutable token arrays without fitting a tokenizer or requiring torch."""
from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tokenizers

from . import PREPARED_DATA_VERSION
from .tokenizer import EvolvTokenizer, SPECIAL_IDS, normalized_text, sha256
from .tokenizer_training import SPLITS, audit_corpus, read_rows, write_json

IGNORE_INDEX = -100


def array_paths(root: Path, split: str) -> tuple[Path, Path]:
    if split not in SPLITS:
        raise ValueError(f"Particao invalida: {split}")
    return (root / "private" / f"{split}.tokens.npy",
            root / "private" / f"{split}.offsets.npy")


def partition_stats(offsets: np.ndarray, context_length: int) -> dict:
    lengths = np.diff(offsets)
    pairs = lengths - 1  # Every token except BOS is a next-token target.
    windows_per_doc = (pairs + context_length - 1) // context_length
    windows = int(windows_per_doc.sum())
    targets = int(pairs.sum())
    capacity = windows * context_length
    return {
        "documents": len(lengths), "stored_tokens": int(lengths.sum()),
        "target_tokens": targets, "sequences": windows,
        "padded_positions": capacity - targets,
        "target_utilization": round(targets / capacity, 6),
        "documents_split_into_multiple_sequences": int((windows_per_doc > 1).sum()),
        "max_document_tokens": int(lengths.max()),
        "dropped_tokens": 0, "cross_document_sequences": 0,
        "prediction_of_next_document_bos": False,
    }


def _check_arrays(root: Path, split: str, config: dict) -> dict:
    tokens_path, offsets_path = array_paths(root, split)
    tokens = np.load(tokens_path, mmap_mode="r", allow_pickle=False)
    offsets = np.load(offsets_path, allow_pickle=False)
    if (tokens.ndim != 1 or tokens.dtype.str != config["storage_dtype"]
            or offsets.ndim != 1 or offsets.dtype.str != "<i8" or len(offsets) < 2
            or offsets[0] != 0 or offsets[-1] != len(tokens)
            or np.any(np.diff(offsets) < 2)):
        raise ValueError(f"Arrays ou limites de documento invalidos: {split}")
    if (np.any(tokens >= config["vocab_size"])
            or np.any(tokens[offsets[:-1]] != SPECIAL_IDS["<|bos|>"])
            or np.any(tokens[offsets[1:] - 1] != SPECIAL_IDS["<|eos|>"])
            or np.count_nonzero(tokens == SPECIAL_IDS["<|bos|>"]) != len(offsets) - 1
            or np.count_nonzero(tokens == SPECIAL_IDS["<|eos|>"]) != len(offsets) - 1
            or np.any((tokens < 7) & (tokens != 1) & (tokens != 2))):
        raise ValueError(f"IDs ou tokens especiais invalidos: {split}")
    return partition_stats(offsets, config["context_length"])


def load_prepared_data(root: str | Path) -> dict:
    """Validate files, IDs, document boundaries, counts and X/y policy."""
    root = Path(root).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "complete" or manifest.get("version") != PREPARED_DATA_VERSION:
        raise ValueError("Versao de dados incompleta ou nao suportada.")
    required = {"config.json", "report.json"}
    required.update(f"private/{split}.{kind}.npy" for split in SPLITS
                    for kind in ("tokens", "offsets"))
    if set(manifest["files"]) != required:
        raise ValueError("Arquivos obrigatorios divergentes do manifesto.")
    for name, metadata in manifest["files"].items():
        path = (root / name).resolve()
        if (not path.is_relative_to(root) or path.stat().st_size != metadata["bytes"]
                or sha256(path) != metadata["sha256"]):
            raise ValueError(f"Dados preparados alterados: {name}")
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if (type(config["context_length"]) is not int or config["context_length"] < 1
            or config["storage_dtype"] not in ("<u2", "<u4")
            or config["special_token_ids"] != SPECIAL_IDS
            or config["ignore_index"] != IGNORE_INDEX
            or config["window_policy"] != "within_document_nonoverlapping_targets"
            or config["stride"] != config["context_length"]
            or config["target_shift"] != 1):
        raise ValueError("Politica de sequencias invalida.")
    report = json.loads((root / "report.json").read_text(encoding="utf-8"))
    for split in SPLITS:
        if _check_arrays(root, split, config) != report["partitions"][split]:
            raise ValueError(f"Contagens de sequencias divergentes: {split}")
    return {"manifest": manifest, "config": config, "report": report}


def prepare_data(corpus: str | Path, tokenizer_dir: str | Path, output: str | Path,
                 *, context_length: int = 256) -> dict:
    """Encode all partitions using the frozen BPE; keep each document separate."""
    if type(context_length) is not int or context_length < 1:
        raise ValueError("O contexto deve ser um inteiro positivo.")
    corpus, tokenizer_dir, output = Path(corpus), Path(tokenizer_dir), Path(output)
    if output.exists():
        raise FileExistsError(f"Pasta ja existe; os dados prontos nao serao sobrescritos: {output}")
    audit = audit_corpus(corpus)
    tokenizer = EvolvTokenizer.load(tokenizer_dir)
    tokenizer_manifest_hash = sha256(tokenizer_dir / "manifest.json")
    tokenizer_report = json.loads((tokenizer_dir / "report.json").read_text(encoding="utf-8"))
    tokenizer_manifest = json.loads((tokenizer_dir / "manifest.json").read_text(encoding="utf-8"))
    if audit != tokenizer_report["audit"]:
        raise ValueError("Corpus diferente daquele associado ao tokenizador congelado.")
    config = {
        "context_length": context_length, "stride": context_length, "target_shift": 1,
        "window_policy": "within_document_nonoverlapping_targets",
        "vocab_size": tokenizer.vocab_size,
        "storage_dtype": "<u2" if tokenizer.vocab_size <= 65536 else "<u4",
        "offsets_dtype": "<i8", "tensor_dtype": "torch.int64",
        "special_token_ids": SPECIAL_IDS, "ignore_index": IGNORE_INDEX,
        "right_padding": True, "attention_mask_true_means": "real_input_token",
        "drop_tail": False, "refit_tokenizer": False,
    }
    output.mkdir(parents=True)
    (output / "private").mkdir()
    write_json(output / "config.json", config)
    partitions = {}
    for split in SPLITS:
        expected = tokenizer_report["partitions"][split]
        tokens_path, offsets_path = array_paths(output, split)
        tokens = np.lib.format.open_memmap(
            tokens_path, mode="w+", dtype=config["storage_dtype"],
            shape=(expected["tokens_with_bos_eos"],),
        )
        offsets = [0]
        raw_count = 0
        for row in read_rows(corpus / f"{split}.jsonl"):
            raw = tokenizer.encode(row["text"])
            if any(index < 7 for index in raw) or tokenizer.decode(raw) != normalized_text(row["text"]):
                raise ValueError(f"Codificacao de texto divergente: {split}")
            ids = [SPECIAL_IDS["<|bos|>"]] + raw + [SPECIAL_IDS["<|eos|>"]]
            stop = offsets[-1] + len(ids)
            if stop > len(tokens):
                raise ValueError("Quantidade de tokens excede a versao congelada.")
            tokens[offsets[-1]:stop] = ids
            offsets.append(stop)
            raw_count += len(raw)
        tokens.flush()
        del tokens  # Release the writable Windows mapping before reopening read-only.
        if (offsets[-1] != expected["tokens_with_bos_eos"]
                or raw_count != expected["raw_tokens"]
                or len(offsets) - 1 != expected["documents"]):
            raise ValueError(f"Contagens diferentes da tokenizacao anterior: {split}")
        np.save(offsets_path, np.asarray(offsets, dtype="<i8"), allow_pickle=False)
        partitions[split] = _check_arrays(output, split, config)
    # Preparation must not rewrite either input artifact.
    if (audit_corpus(corpus) != audit
            or sha256(tokenizer_dir / "manifest.json") != tokenizer_manifest_hash):
        raise ValueError("Corpus ou manifesto do tokenizador alterado durante a preparacao.")
    EvolvTokenizer.load(tokenizer_dir)
    report = {
        "partitions": partitions,
        "source_audit": audit,
        "coverage": "all documents and adjacent within-document pairs; no dropped tails",
        "labels": "tokens shifted by one position; padded labels use ignore_index=-100",
        "context_limit": "long documents are split; context does not carry between windows",
        "attention": "padding mask provided; future decoder must also apply causal masking",
        "training_status": "data prepared only; no neural model trained",
    }
    write_json(output / "report.json", report)
    names = ["config.json", "report.json"]
    names += [f"private/{split}.{kind}.npy" for split in SPLITS for kind in ("tokens", "offsets")]
    manifest = {
        "version": PREPARED_DATA_VERSION, "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_version": audit["corpus_version"], "corpus_manifest_sha256": audit["manifest_sha256"],
        "tokenizer_version": tokenizer_manifest["version"],
        "tokenizer_manifest_sha256": tokenizer_manifest_hash,
        "tokenizer_sha256": tokenizer_manifest["files"]["private/tokenizer.json"]["sha256"],
        "runtime": {"python": platform.python_version(), "numpy": np.__version__,
                    "tokenizers": tokenizers.__version__},
        "distribution": "local research; same corpus privacy, attribution and license obligations",
        "files": {name: {"sha256": sha256(output / name), "bytes": (output / name).stat().st_size}
                  for name in names},
    }
    write_json(output / "manifest.json", manifest)
    load_prepared_data(output)
    return {"artifact": str(output), "context_length": context_length,
            "vocab_size": tokenizer.vocab_size, "partitions": partitions}

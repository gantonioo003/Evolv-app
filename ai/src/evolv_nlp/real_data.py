from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evolv_nlp.dataset import file_sha256, read_jsonl


IMPORT_VERSION = "1.0.0"
DATASET_VERSION = "1.4.0"
SPLITS = {"train", "validation", "test"}
SOURCE_FILES = (
    "mensagens.jsonl", "classificacao_revisar.jsonl", "entidades_revisar.jsonl",
    "candidatos_novas_entidades.jsonl", "split_manifest.jsonl",
)
PRIVATE_PATTERN = re.compile(
    r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|"
    r"\b(?:whatsapp|telefone|celular|zap)\s*[:=]?\s*\+?\d[\d ()-]{7,}", re.I,
)


def normalized_key(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def taxonomy_labels(ai_root: Path) -> dict[str, set[str]]:
    extension = json.loads((ai_root / "data/taxonomy/expansion.v1.1.json").read_text("utf-8"))
    labels: dict[str, set[str]] = {}
    for collection in ("intents", "risks", "entities"):
        base = json.loads((ai_root / f"data/taxonomy/{collection}.v1.json").read_text("utf-8"))
        labels[collection] = {r["id"] for r in base[collection]} | {
            r["id"] for r in extension[collection]
        }
    return labels


def reserved_texts(ai_root: Path) -> set[str]:
    # These texts are only used for exclusion, never to tune labels or rules.
    paths = list((ai_root / "data/releases/1.3.0/splits/validation").glob("*.jsonl"))
    paths += list((ai_root / "data/releases/1.3.0/splits/test").glob("*.jsonl"))
    paths += list((ai_root / "data/releases/1.3.0/challenge").glob("*.jsonl"))
    paths += list((ai_root / "data/evaluation").rglob("*.jsonl"))
    return {normalized_key(r["text"]) for path in paths for r in read_jsonl(path) if r.get("text")}


def duplicate_groups(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        groups[f"group:{row['split_group_id']}"].add(row["id_mensagem"])
        groups[f"text:{normalized_key(row['texto_original'])}"].add(row["id_mensagem"])
        groups[f"thread:{row['thread_id']}"].add(row["id_mensagem"])
    return groups


def near_duplicate_pairs(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    inverted: dict[tuple[str, ...], list[int]] = defaultdict(list)
    tokens, shingles = [], []
    for index, row in enumerate(rows):
        words = normalized_key(row["texto_original"]).split()
        tokens.append(words)
        grams = {tuple(words[i:i + 3]) for i in range(len(words) - 2)} if len(words) >= 8 else set()
        shingles.append(grams)
        for gram in grams:
            inverted[gram].append(index)
    candidates: set[tuple[int, int]] = set()
    for indices in inverted.values():
        if len(indices) > 40:
            continue
        for position, left in enumerate(indices):
            for right in indices[position + 1:]:
                if rows[left]["split"] != rows[right]["split"]:
                    candidates.add(tuple(sorted((left, right))))
    pairs = set()
    for left, right in candidates:
        intersection = shingles[left] & shingles[right]
        union = shingles[left] | shingles[right]
        if union and len(intersection) / len(union) >= 0.85:
            pairs.add((rows[left]["id_mensagem"], rows[right]["id_mensagem"]))
    return pairs


def validate_external(source: Path, expected_rows: int = 10_000) -> tuple[list[dict], dict[str, dict]]:
    rows = read_jsonl(source / "mensagens.jsonl")
    annotations = read_jsonl(source / "classificacao_revisar.jsonl")
    if len(rows) != expected_rows:
        raise ValueError(f"Esperados {expected_rows} registros; recebidos {len(rows)}")
    index = {r["id_mensagem"]: r for r in rows}
    labels = {r["id_mensagem"]: r for r in annotations}
    if len(index) != len(rows) or len(labels) != len(annotations) or set(index) != set(labels):
        raise ValueError("IDs duplicados ou classificacoes nao correspondem as mensagens")
    checksums = source / "checksums_sha256.csv"
    if checksums.exists():
        with checksums.open(encoding="utf-8-sig", newline="") as stream:
            checks = list(csv.DictReader(stream))
        for item in checks:
            filename = item.get("arquivo", item.get("file", item.get("path", "")))
            expected = item.get("sha256", item.get("SHA256"))
            if filename in SOURCE_FILES and expected and file_sha256(source / filename) != expected:
                raise ValueError(f"Checksum incorreto: {filename}")
    for row in rows:
        text = row.get("texto_original")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Mensagem vazia")
        if row.get("idioma") not in ("pt", "pt-BR", "pt-br") or row.get("split") not in SPLITS:
            raise ValueError(f"Idioma/split invalido: {row['id_mensagem']}")
        expected = row.get("texto_original_sha256")
        if expected and hashlib.sha256(text.encode()).hexdigest() != expected:
            raise ValueError(f"Texto alterado: {row['id_mensagem']}")
        if labels[row["id_mensagem"]]["texto_original"] != text:
            raise ValueError(f"Texto da anotacao diferente: {row['id_mensagem']}")
    for filename in ("entidades_revisar.jsonl", "candidatos_novas_entidades.jsonl"):
        for span in read_jsonl(source / filename):
            message = index.get(span["id_mensagem"])
            start, end = span.get("start"), span.get("end")
            if message is None or not isinstance(start, int) or not isinstance(end, int):
                raise ValueError(f"Span invalido em {filename}")
            if not 0 <= start < end <= len(message["texto_original"]):
                raise ValueError(f"Offset fora do texto em {filename}")
            captured = span.get("trecho_original", span.get("text", span.get("texto_entidade", span.get("texto"))))
            if captured is not None and message["texto_original"][start:end] != captured:
                raise ValueError(f"Span nao corresponde ao texto em {filename}")
    split_path = source / "split_manifest.jsonl"
    if split_path.exists():
        split_rows = read_jsonl(split_path)
        split_index = {r["id_mensagem"]: r for r in split_rows}
        if len(split_index) != len(split_rows) or set(split_index) != set(index):
            raise ValueError("Manifesto de split nao corresponde as mensagens")
        for message_id, row in index.items():
            if any(split_index[message_id].get(key) != row.get(key)
                   for key in ("split", "split_group_id", "thread_id", "source_url")):
                raise ValueError(f"Grupo/split divergente: {message_id}")
    return rows, labels


def import_external(source: Path, ai_root: Path, expected_rows: int = 10_000) -> dict:
    rows, annotations = validate_external(source, expected_rows)
    private = ai_root / "data/external_private/ptbr-10000-1.0.0"
    manifest_path = ai_root / "data/releases/1.4.0/external_manifest.json"
    source_hashes = {name: file_sha256(source / name) for name in SOURCE_FILES}
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text("utf-8"))
        if previous["source_hashes"] != source_hashes:
            raise ValueError("Importacao ja versionada: crie nova versao para outra coleta")
    private.mkdir(parents=True, exist_ok=True)
    for name in SOURCE_FILES:
        target = private / name
        if not target.exists():
            shutil.copy2(source / name, target)
        elif file_sha256(target) != source_hashes[name]:
            raise ValueError(f"Copia local alterada: {name}")
    index = {r["id_mensagem"]: r for r in rows}
    reserved = reserved_texts(ai_root)
    quarantined: dict[str, set[str]] = defaultdict(set)
    for ids in duplicate_groups(rows).values():
        if len({index[i]["split"] for i in ids}) > 1:
            for message_id in ids:
                quarantined[message_id].add("cross_split_duplicate_or_thread")
    near_pairs = near_duplicate_pairs(rows)
    for pair in near_pairs:
        for message_id in pair:
            quarantined[message_id].add("cross_split_near_duplicate")
    for row in rows:
        if normalized_key(row["texto_original"]) in reserved:
            quarantined[row["id_mensagem"]].add("historical_holdout_overlap")
        if PRIVATE_PATTERN.search(row["texto_original"]):
            quarantined[row["id_mensagem"]].add("possible_personal_identifier")
    queue: list[dict[str, Any]] = []
    for row in rows:
        candidate = annotations[row["id_mensagem"]]
        flags = set(quarantined[row["id_mensagem"]])
        if row["metadados"].get("text_completeness") in ("title_only", "excerpt_only"):
            flags.add("missing_body_context")
        queue.append({
            "id": row["id_mensagem"], "text": row["texto_original"],
            "language": "pt-BR", "source": row["fonte"], "source_url": row["source_url"],
            "source_split": row["split"], "group_id": row["split_group_id"],
            "intent_candidate": candidate.get("intenção_principal_sugerida"),
            "risk_candidates": candidate.get("riscos_sugeridos", []),
            "intent_reviewed": None, "risks_reviewed": None,
            "review_status": "pending", "training_allowed": False,
            "corpus_allowed": False, "rights_status": "unverified",
            "flags": sorted(flags),
            "text_sha256": hashlib.sha256(row["texto_original"].encode()).hexdigest(),
        })
    write_jsonl(private / "review_queue.jsonl", queue)
    summary = {
        "import_version": IMPORT_VERSION, "dataset_version": DATASET_VERSION,
        "rows": len(rows), "language": "pt-BR", "source_hashes": source_hashes,
        "counts_by_source": dict(Counter(r["fonte"] for r in rows)),
        "counts_by_split": dict(Counter(r["split"] for r in rows)),
        "completeness": dict(Counter(r["metadados"].get("text_completeness") for r in rows)),
        "intent_candidates": dict(Counter(r.get("intenção_principal_sugerida") or "unknown" for r in annotations.values())),
        "risk_candidates": dict(Counter(v for r in annotations.values() for v in r.get("riscos_sugeridos", []))),
        "quarantined_rows": sum(bool(quarantined[r["id_mensagem"]]) for r in rows),
        "quarantine_reasons": dict(Counter(v for reasons in quarantined.values() for v in reasons)),
        "near_duplicate_pairs": len(near_pairs),
        "near_duplicate_method": "word trigram Jaccard >=0.85 for texts of >=8 words; frequent shingles skipped, not exhaustive semantic deduplication",
        "raw_text_location": "data/external_private/ptbr-10000-1.0.0 (ignored by Git)",
        "annotation_status": "machine_candidates_not_gold",
        "rights_status": "unverified_do_not_publish_or_add_to_lm_corpus",
        "test_status": "reserved_not_used_for_training_or_model_selection",
        "community_answers_used_as_knowledge": False,
        "existing_versions_overwritten": False,
    }
    write_json(manifest_path, summary)
    return summary


def load_reviews(path: Path, raw_rows: list[dict], labels: dict[str, set[str]]) -> list[dict]:
    reviews = json.loads(path.read_text("utf-8"))["reviews"]
    index = {r["id_mensagem"]: r for r in raw_rows}
    seen: set[str] = set()
    for review in reviews:
        if review["id"] in seen or review["id"] not in index:
            raise ValueError("Revisao duplicada ou de ID desconhecido")
        seen.add(review["id"])
        row = index[review["id"]]
        if row["split"] != "train":
            raise ValueError("Revisoes de desenvolvimento devem vir apenas do TRAIN externo")
        if review.get("intent") and review["intent"] not in labels["intents"]:
            raise ValueError("Intencao revisada desconhecida")
        if not set(review.get("risks", [])).issubset(labels["risks"]):
            raise ValueError("Risco revisado desconhecido")
        if "none" in review.get("risks", []) and len(review["risks"]) != 1:
            raise ValueError("none nao pode coexistir com sinal de risco")
    return reviews

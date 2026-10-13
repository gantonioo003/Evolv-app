from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evolv_nlp import DATASET_VERSION


REGULAR_SPLITS = ("train", "validation", "test")
TASK_FILES = {
    "intent_classification": "intent_examples.jsonl",
    "risk_classification": "risk_examples.jsonl",
}


@dataclass(frozen=True)
class TextPartition:
    split: str
    task: str
    path: Path
    ids: tuple[str, ...]
    texts: tuple[str, ...]
    labels: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.ids)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"JSON invalido em {path}:{line_number}: {error}"
                ) from error
    return rows


def load_partition(
    data_root: Path,
    split: str,
    task: str,
    expected_version: str = DATASET_VERSION,
) -> TextPartition:
    if split not in REGULAR_SPLITS:
        raise ValueError(f"Split regular desconhecido: {split}")
    if task not in TASK_FILES:
        raise ValueError(f"Tarefa de baseline desconhecida: {task}")

    path = data_root / "splits" / split / TASK_FILES[task]
    if not path.exists():
        raise FileNotFoundError(f"Dataset ausente: {path}")
    rows = read_jsonl(path)
    if not rows:
        raise ValueError(f"Dataset vazio: {path}")

    ids: list[str] = []
    texts: list[str] = []
    labels: list[str] = []
    for row in rows:
        row_id = row.get("id")
        text = row.get("text")
        label = row.get("label")
        if row.get("task") != task:
            raise ValueError(f"Tarefa incorreta em {row_id}: {row.get('task')}")
        if row.get("dataset_version") != expected_version:
            raise ValueError(
                f"Versao incorreta em {row_id}: {row.get('dataset_version')}"
            )
        if not all(isinstance(value, str) and value.strip() for value in (row_id, text, label)):
            raise ValueError(f"Registro incompleto em {path}: {row_id}")
        ids.append(row_id)
        texts.append(text)
        labels.append(label)

    if len(ids) != len(set(ids)):
        raise ValueError(f"IDs duplicados em {path}")
    return TextPartition(
        split=split,
        task=task,
        path=path,
        ids=tuple(ids),
        texts=tuple(texts),
        labels=tuple(labels),
    )

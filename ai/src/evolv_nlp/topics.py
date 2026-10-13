from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from evolv_nlp.entities import normalize_text


@dataclass(frozen=True)
class TopicDefinition:
    topic_id: str
    domain: str
    description: str
    aliases: tuple[str, ...]


def load_topics(path: Path) -> tuple[str, dict[str, TopicDefinition]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = payload.get("version")
    rows = payload.get("topics")
    if not isinstance(version, str) or not isinstance(rows, list):
        raise ValueError(f"Taxonomia de topicos invalida: {path}")

    topics: dict[str, TopicDefinition] = {}
    for row in rows:
        topic_id = row.get("id")
        domain = row.get("domain")
        description = row.get("description")
        aliases = row.get("aliases")
        if not (
            isinstance(topic_id, str)
            and isinstance(domain, str)
            and isinstance(description, str)
            and isinstance(aliases, list)
            and all(isinstance(alias, str) and alias.strip() for alias in aliases)
        ):
            raise ValueError(f"Topico invalido em {path}: {row}")
        if topic_id in topics:
            raise ValueError(f"Topico duplicado em {path}: {topic_id}")
        topics[topic_id] = TopicDefinition(
            topic_id=topic_id,
            domain=domain,
            description=description,
            aliases=tuple(aliases),
        )
    return version, topics


def load_topic_rules(path: Path, valid_topic_ids: set[str]) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for group in ("intent_defaults", "entity_defaults"):
        mapping = payload.get(group)
        if not isinstance(mapping, dict):
            raise ValueError(f"Grupo ausente em {path}: {group}")
        for key, values in mapping.items():
            if not isinstance(key, str) or not isinstance(values, list):
                raise ValueError(f"Regra de topico invalida em {group}: {key}")
            unknown = set(values) - valid_topic_ids
            if unknown:
                raise ValueError(f"Topicos desconhecidos em {group}.{key}: {unknown}")
    return payload


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = re.escape(normalize_text(phrase)).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){pattern}(?!\w)", text) is not None


def match_topics(
    text: str,
    topics: dict[str, TopicDefinition],
    rules: dict[str, Any],
    intent_label: str,
    entity_types: Iterable[str],
) -> list[dict[str, Any]]:
    normalized = normalize_text(text)
    sources: dict[str, set[str]] = {}

    for topic_id, topic in topics.items():
        if any(_contains_phrase(normalized, alias) for alias in topic.aliases):
            sources.setdefault(topic_id, set()).add("lexical")

    for topic_id in rules["intent_defaults"].get(intent_label, []):
        sources.setdefault(topic_id, set()).add("intent_hint")
    for entity_type in set(entity_types):
        for topic_id in rules["entity_defaults"].get(entity_type, []):
            sources.setdefault(topic_id, set()).add("entity_hint")

    return [
        {
            "id": topic_id,
            "domain": topics[topic_id].domain,
            "sources": sorted(topic_sources),
        }
        for topic_id, topic_sources in sorted(sources.items())
    ]

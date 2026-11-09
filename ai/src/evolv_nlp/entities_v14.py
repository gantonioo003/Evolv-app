"""Explicit-span enrichment for the reviewed 60-intent dataset (not learned NER)."""
from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date

from evolv_nlp.entities import CatalogEntry, EntityCatalog, ExtractedEntity, WEEKDAYS
from evolv_nlp import entities_v13 as previous
from evolv_nlp.entities_v12 import _normalize, _span, _assertion_attributes
from evolv_nlp.activity_type import activity_mentions

EXTRACTOR_VERSION = "1.3.1"
RULES = {
    "action_scope": r"\b(?:so hoje|apenas hoje|esta semana|essa semana|de agora em diante|so amanha)\b",
    "change_direction": r"\b(?:aumentar|aumenta|reduzir|reduz|diminuir|diminui|manter|mantem)\b",
    "context_reference": r"\b(?:esse mesmo|essa mesma|o de hoje|aquele exercicio|essa refeicao)\b",
    "pending_action": r"\b(?:essa proposta|a proposta pendente|essa mudanca|pode aplicar)\b",
    "previous_action": r"\b(?:a ultima troca|ultima alteracao|o que voce mudou|mudanca anterior)\b",
    "negation": r"\b(?:nao|nunca|sem)\b",
    "certainty": r"\b(?:talvez|acho que|tenho certeza|nao sei se)\b",
    "request_priority": r"\b(?:principalmente|o mais importante|minha prioridade)\b",
    "plan_scope": r"\b(?:treino de hoje|dieta da semana|treino da semana|plano alimentar)\b",
    "meal_context": r"\b(?:dia de treino|dia de descanso|no trabalho|apos o treino|antes do treino)\b",
    "budget": r"(?:r\$\s*\d+(?:[.,]\d{2})?|\b(?:ate|no maximo)\s+\d+(?:[.,]\d{2})?\s+reais\b)",
    "work_schedule": r"\b(?:trabalho (?:a noite|de manha|a tarde)|plantao de \d+ horas|escala 12x36)\b",
    "weekday": r"\b(?:segunda|terca|quarta|quinta|sexta)(?:[ -]feira)?\b|\b(?:sabado|domingo)\b",
    "storage_duration": r"\b(?:guardar|armazenar|conservar|na geladeira)(?:\s+\w+){0,3}\s+(?:\d+|dois|tres|quatro)\s+dias\b",
    "goal_timeframe": r"\b(?:emagrecer|ganhar massa|atingir (?:a )?meta)(?:\s+\w+){0,3}\s+em\s+\d+\s+(?:semanas|meses)\b",
    "competition_date": r"\b(?:campeonato|competicao|prova)\s+(?:em|dia|no dia)\s+(?:\d{1,2}(?:/\d{1,2}(?:/\d{2,4})?)?|janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b",
    "time_period": r"\b(?:ultim[ao]s?\s+(?:\d+|duas|tres|quatro)\s+(?:dias|semanas|meses)|por\s+\d+\s+(?:dias|semanas|meses))\b",
}


def load_catalog(ai_root):
    catalog = previous.load_catalog(ai_root)
    data = json.loads((ai_root / "data/catalogs/entity_catalogs.extension.v1.3.json").read_text("utf-8"))
    entries = list(catalog.entries)
    for kind, values in data["catalogs"].items():
        for value in values:
            entries.append(CatalogEntry(kind, value["canonical"], tuple(value["aliases"])))
    return EntityCatalog(EXTRACTOR_VERSION, catalog.language, tuple(entries))


def supported_entity_types(catalog):
    return previous.supported_entity_types(catalog) | frozenset(RULES) | {"activity_type"}


def extract_entities(text, catalog, reference_date: date):
    result = previous.extract_entities(text, catalog, reference_date)
    normalized, mapping = _normalize(text)
    entities = list(result.entities) + activity_mentions(text)
    for kind, expression in RULES.items():
        for match in re.finditer(expression, normalized):
            start, end = _span(text, mapping, *match.span())
            attrs = {**_assertion_attributes(normalized, match.start()), "explicit_mention_only": True}
            value = match.group()
            if kind == "weekday":
                value = WEEKDAYS[value.replace("-", " ").replace(" feira", "")]
            if kind in {"pending_action", "previous_action", "context_reference", "competition_date"}:
                attrs["requires_context"] = True
            entities.append(ExtractedEntity(kind, text[start:end], value, start, end, "review_rule", attrs))
    # Apply assertion scope also to catalog mentions: a condition mentioned under negation
    # or about another person is not silently asserted as the current user's condition.
    scoped = []
    for entity in entities:
        if entity.entity_type in {"intensity", "range_of_motion"}:
            prefix = _normalize(text[max(0, entity.start - 45):entity.start])[0]
            mention = _normalize(entity.text)[0]
            anchor = r"(?:cardio|treino|corrida|pedalada|intensidade)" if entity.entity_type == "intensity" else r"amplitude"
            if not (re.search(rf"\b{anchor}\s+(?:muito\s+)?$", prefix) or re.search(rf"\b{anchor}\b", mention)):
                continue
        attributes = {**entity.attributes}
        if entity.entity_type in {"medical_condition", "medication", "supplement", "hunger_level", "stress_level"}:
            position = next((i for i, original in enumerate(mapping) if original >= entity.start), 0)
            attributes.update(_assertion_attributes(normalized, position))
            attributes["not_a_diagnosis"] = True
        scoped.append(replace(entity, attributes=attributes))
    unique = {(e.entity_type, e.start, e.end, json.dumps(e.value, sort_keys=True)): e for e in scoped}
    return replace(result, extractor_version=EXTRACTOR_VERSION,
                   entities=tuple(sorted(unique.values(), key=lambda e: (e.start, e.end, e.entity_type))))

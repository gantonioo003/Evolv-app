from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from evolv_nlp import ENTITY_CATALOG_VERSION, ENTITY_EXTRACTOR_VERSION


NUMBER_WORDS = {
    "zero": 0,
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
    "onze": 11,
    "doze": 12,
    "treze": 13,
    "quatorze": 14,
    "catorze": 14,
    "quinze": 15,
    "dezesseis": 16,
    "dezessete": 17,
    "dezoito": 18,
    "dezenove": 19,
    "vinte": 20,
    "trinta": 30,
    "quarenta": 40,
    "cinquenta": 50,
    "sessenta": 60,
    "setenta": 70,
    "oitenta": 80,
    "noventa": 90,
    "cem": 100,
}
NUMBER_ATOM = "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))
NUMBER_PATTERN = rf"(?:\d+(?:[.,]\d+)?|(?:{NUMBER_ATOM})(?:\s+e\s+(?:{NUMBER_ATOM}))?)"

WEEKDAYS = {
    "segunda": 0,
    "segunda feira": 0,
    "terca": 1,
    "terca feira": 1,
    "quarta": 2,
    "quarta feira": 2,
    "quinta": 3,
    "quinta feira": 3,
    "sexta": 4,
    "sexta feira": 4,
    "sabado": 5,
    "domingo": 6,
}
MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


@dataclass(frozen=True)
class CatalogEntry:
    entity_type: str
    canonical: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class EntityCatalog:
    version: str
    language: str
    entries: tuple[CatalogEntry, ...]


@dataclass(frozen=True)
class ExtractedEntity:
    entity_type: str
    text: str
    value: Any
    start: int
    end: int
    source: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    reference_date: str
    extractor_version: str
    catalog_version: str
    entities: tuple[ExtractedEntity, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "reference_date": self.reference_date,
            "extractor_version": self.extractor_version,
            "catalog_version": self.catalog_version,
            "entities": [entity.to_dict() for entity in self.entities],
        }


def normalize_text(text: str) -> str:
    normalized, _ = _normalize_with_mapping(text)
    return normalized


def load_entity_catalog(path: Path) -> EntityCatalog:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != ENTITY_CATALOG_VERSION:
        raise ValueError(f"Versao inesperada do catalogo: {payload.get('version')}")
    catalogs = payload.get("catalogs")
    if not isinstance(catalogs, dict) or not catalogs:
        raise ValueError("Catalogo de entidades vazio ou invalido")

    entries: list[CatalogEntry] = []
    aliases_by_type: dict[str, set[str]] = {}
    for entity_type, raw_entries in catalogs.items():
        if not isinstance(raw_entries, list) or not raw_entries:
            raise ValueError(f"Catalogo vazio para {entity_type}")
        seen = aliases_by_type.setdefault(entity_type, set())
        for raw in raw_entries:
            canonical = raw.get("canonical")
            aliases = raw.get("aliases", [])
            if not isinstance(canonical, str) or not canonical.strip():
                raise ValueError(f"Entrada sem canonical em {entity_type}")
            if not isinstance(aliases, list) or not all(
                isinstance(alias, str) and alias.strip() for alias in aliases
            ):
                raise ValueError(f"Aliases invalidos para {canonical}")
            terms = (canonical, *aliases)
            for term in terms:
                normalized = normalize_text(term).strip()
                if normalized in seen:
                    raise ValueError(
                        f"Alias duplicado em {entity_type}: {normalized}"
                    )
                seen.add(normalized)
            entries.append(
                CatalogEntry(
                    entity_type=entity_type,
                    canonical=canonical,
                    aliases=tuple(aliases),
                )
            )
    return EntityCatalog(
        version=payload["version"],
        language=payload.get("language", "pt-BR"),
        entries=tuple(entries),
    )


def extract_entities(
    text: str,
    catalog: EntityCatalog,
    reference_date: date,
) -> ExtractionResult:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("O texto para extracao nao pode estar vazio")
    if len(text) > 10_000:
        raise ValueError("O texto para extracao excede 10.000 caracteres")

    normalized, mapping = _normalize_with_mapping(text)
    catalog_entities = _extract_catalog_entities(text, normalized, mapping, catalog)
    entities = [
        *catalog_entities,
        *_extract_dates(text, normalized, mapping, reference_date),
        *_extract_training_numbers(text, normalized, mapping),
        *_extract_amounts(text, normalized, mapping),
        *_extract_preferences_and_limitations(
            text, normalized, mapping, catalog_entities
        ),
    ]
    entities = _assign_replacement_roles(normalized, entities)
    entities = _deduplicate_entities(entities)
    return ExtractionResult(
        text=text,
        reference_date=reference_date.isoformat(),
        extractor_version=ENTITY_EXTRACTOR_VERSION,
        catalog_version=catalog.version,
        entities=tuple(entities),
    )


def _normalize_with_mapping(text: str) -> tuple[str, list[int]]:
    output: list[str] = []
    mapping: list[int] = []
    for index, character in enumerate(text):
        decomposed = unicodedata.normalize("NFKD", character)
        produced = False
        for candidate in decomposed:
            if unicodedata.combining(candidate):
                continue
            output.append(candidate.lower() if candidate.isalnum() else " ")
            mapping.append(index)
            produced = True
        if not produced:
            output.append(" ")
            mapping.append(index)
    return "".join(output), mapping


def _original_span(
    mapping: list[int], normalized_start: int, normalized_end: int
) -> tuple[int, int]:
    return mapping[normalized_start], mapping[normalized_end - 1] + 1


def _term_pattern(term: str) -> re.Pattern[str]:
    normalized = normalize_text(term).strip()
    parts = [re.escape(part) for part in normalized.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)")


def _extract_catalog_entities(
    text: str,
    normalized: str,
    mapping: list[int],
    catalog: EntityCatalog,
) -> list[ExtractedEntity]:
    candidates: list[ExtractedEntity] = []
    for entry in catalog.entries:
        for term in (entry.canonical, *entry.aliases):
            for match in _term_pattern(term).finditer(normalized):
                start, end = _original_span(mapping, match.start(), match.end())
                candidates.append(
                    ExtractedEntity(
                        entity_type=entry.entity_type,
                        text=text[start:end],
                        value=entry.canonical,
                        start=start,
                        end=end,
                        source="catalog",
                        attributes={"matched_alias": term},
                    )
                )

    selected: list[ExtractedEntity] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (-(item.end - item.start), item.start, item.entity_type),
    ):
        if any(
            candidate.start < current.end and current.start < candidate.end
            for current in selected
        ):
            continue
        selected.append(candidate)
    return sorted(selected, key=lambda item: (item.start, item.end, item.entity_type))


def _extract_dates(
    text: str,
    normalized: str,
    mapping: list[int],
    reference: date,
) -> list[ExtractedEntity]:
    candidates: list[ExtractedEntity] = []

    relative = {
        "depois de amanha": reference + timedelta(days=2),
        "amanha": reference + timedelta(days=1),
        "hoje": reference,
        "ontem": reference - timedelta(days=1),
    }
    for phrase, resolved in relative.items():
        for match in _term_pattern(phrase).finditer(normalized):
            if any(
                match.start() < item.attributes["normalized_end"]
                and item.attributes["normalized_start"] < match.end()
                for item in candidates
            ):
                continue
            candidates.append(
                _date_entity(text, mapping, match, resolved, "relative_date")
            )

    numeric_pattern = re.compile(
        r"(?<!\d)(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?!\d)"
    )
    for match in numeric_pattern.finditer(text):
        day, month = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else reference.year
        if year < 100:
            year += 2000
        resolved = _safe_date(year, month, day)
        if resolved:
            candidates.append(
                ExtractedEntity(
                    entity_type="target_date",
                    text=text[match.start() : match.end()],
                    value=resolved.isoformat(),
                    start=match.start(),
                    end=match.end(),
                    source="date_rule",
                    attributes={
                        "kind": "absolute_date",
                        "normalized_start": match.start(),
                        "normalized_end": match.end(),
                    },
                )
            )

    iso_pattern = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
    for match in iso_pattern.finditer(text):
        resolved = _safe_date(
            int(match.group(1)), int(match.group(2)), int(match.group(3))
        )
        if resolved:
            candidates.append(
                ExtractedEntity(
                    entity_type="target_date",
                    text=text[match.start() : match.end()],
                    value=resolved.isoformat(),
                    start=match.start(),
                    end=match.end(),
                    source="date_rule",
                    attributes={
                        "kind": "iso_date",
                        "normalized_start": match.start(),
                        "normalized_end": match.end(),
                    },
                )
            )

    month_names = "|".join(MONTHS)
    written_pattern = re.compile(
        rf"(?<!\w)(\d{{1,2}})\s+de\s+({month_names})(?:\s+de\s+(\d{{4}}))?(?!\w)"
    )
    for match in written_pattern.finditer(normalized):
        resolved = _safe_date(
            int(match.group(3)) if match.group(3) else reference.year,
            MONTHS[match.group(2)],
            int(match.group(1)),
        )
        if resolved:
            candidates.append(
                _date_entity(text, mapping, match, resolved, "absolute_date")
            )

    for phrase, weekday in sorted(WEEKDAYS.items(), key=lambda item: -len(item[0])):
        for match in _term_pattern(phrase).finditer(normalized):
            if any(
                match.start() < item.attributes["normalized_end"]
                and item.attributes["normalized_start"] < match.end()
                for item in candidates
            ):
                continue
            days_ahead = (weekday - reference.weekday()) % 7
            resolved = reference + timedelta(days=days_ahead)
            entity = _date_entity(text, mapping, match, resolved, "weekday")
            candidates.append(
                replace(
                    entity,
                    attributes={
                        **entity.attributes,
                        "weekday": weekday,
                        "resolution": "next_or_same",
                    },
                )
            )

    candidates.sort(key=lambda item: item.start)
    has_directional_connector = len(candidates) >= 2 and bool(
        re.search(
            r"\b(?:para|pra|pro|ate)\b",
            normalized[candidates[0].end : candidates[-1].start],
        )
    )
    if has_directional_connector:
        for index, entity in enumerate(candidates):
            if index == 0:
                candidates[index] = replace(entity, entity_type="source_date")
                continue
            previous = candidates[index - 1]
            between = normalize_text(text[previous.end : entity.start])
            if re.search(r"\b(?:para|pra|pro|ate)\b", between):
                resolved = date.fromisoformat(str(entity.value))
                previous_resolved = date.fromisoformat(str(previous.value))
                if (
                    entity.attributes.get("kind") == "weekday"
                    and resolved <= previous_resolved
                ):
                    resolved += timedelta(days=7)
                candidates[index] = replace(
                    entity,
                    entity_type="target_date",
                    value=resolved.isoformat(),
                )
            else:
                candidates[index] = replace(entity, entity_type="target_date")
    else:
        candidates = [
            replace(entity, entity_type="target_date") for entity in candidates
        ]

    return [
        replace(
            entity,
            attributes={
                key: value
                for key, value in entity.attributes.items()
                if key not in {"normalized_start", "normalized_end"}
            },
        )
        for entity in candidates
    ]


def _date_entity(
    text: str,
    mapping: list[int],
    match: re.Match[str],
    resolved: date,
    kind: str,
) -> ExtractedEntity:
    start, end = _original_span(mapping, match.start(), match.end())
    return ExtractedEntity(
        entity_type="target_date",
        text=text[start:end],
        value=resolved.isoformat(),
        start=start,
        end=end,
        source="date_rule",
        attributes={
            "kind": kind,
            "normalized_start": match.start(),
            "normalized_end": match.end(),
        },
    )


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _extract_training_numbers(
    text: str, normalized: str, mapping: list[int]
) -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []

    compact = re.compile(
        r"(?<!\w)(\d{1,2})\s*x\s*(\d{1,3})(?:\s+(?:a\s+)?(\d{1,3}))?(?!\w)"
    )
    for match in compact.finditer(normalized):
        start, end = _original_span(mapping, match.start(), match.end())
        entities.append(
            ExtractedEntity(
                "sets", text[start:end], int(match.group(1)), start, end,
                "numeric_rule", {"notation": "compact"},
            )
        )
        repetition_value: int | dict[str, int]
        if match.group(3):
            repetition_value = {
                "minimum": int(match.group(2)),
                "maximum": int(match.group(3)),
            }
        else:
            repetition_value = int(match.group(2))
        entities.append(
            ExtractedEntity(
                "repetitions", text[start:end], repetition_value, start, end,
                "numeric_rule", {"notation": "compact"},
            )
        )

    sets_pattern = re.compile(
        rf"(?<!\w)({NUMBER_PATTERN})\s+(?:series?|sets?)(?!\w)"
    )
    for match in sets_pattern.finditer(normalized):
        _append_numeric_entity(entities, text, mapping, match, "sets", match.group(1))

    repetitions_pattern = re.compile(
        rf"(?<!\w)({NUMBER_PATTERN})(?:\s+(?:a\s+)?({NUMBER_PATTERN}))?\s+(?:repeticoes|reps?)(?!\w)"
    )
    for match in repetitions_pattern.finditer(normalized):
        minimum = _parse_number(match.group(1))
        maximum = _parse_number(match.group(2)) if match.group(2) else None
        value: int | float | dict[str, int | float]
        value = (
            {"minimum": minimum, "maximum": maximum}
            if maximum is not None
            else minimum
        )
        _append_value_entity(entities, text, mapping, match, "repetitions", value)

    load_pattern = re.compile(
        rf"(?<!\w)({NUMBER_PATTERN})\s*(kg|quilos?|kilos?|lbs?|libras?)(?:\s+de\s+cada\s+lado)?(?!\w)"
    )
    for match in load_pattern.finditer(normalized):
        unit = "kg" if match.group(2).startswith(("kg", "quilo", "kilo")) else "lb"
        _append_value_entity(
            entities,
            text,
            mapping,
            match,
            "load",
            {"amount": _parse_number(match.group(1)), "unit": unit},
            {"per_side": "cada lado" in match.group(0)},
        )

    duration_pattern = re.compile(
        rf"(?<!\w)({NUMBER_PATTERN})\s*(horas?|h|minutos?|min|segundos?|seg)(?!\w)"
    )
    for match in duration_pattern.finditer(normalized):
        amount = _parse_number(match.group(1))
        raw_unit = match.group(2)
        if raw_unit.startswith(("hora", "h")):
            unit, seconds = "hour", float(amount) * 3600
        elif raw_unit.startswith(("min", "minuto")):
            unit, seconds = "minute", float(amount) * 60
        else:
            unit, seconds = "second", float(amount)
        context = normalized[max(0, match.start() - 28) : match.end() + 28]
        if re.search(r"\b(?:descanso|descansa|descansar|intervalo|pausa)\b", context):
            entity_type = "rest_duration"
        elif re.search(r"\b(?:dormi|sono|dormir)\b", context):
            entity_type = "sleep_duration"
        else:
            entity_type = "duration"
        _append_value_entity(
            entities,
            text,
            mapping,
            match,
            entity_type,
            {"amount": amount, "unit": unit, "seconds": int(seconds)},
        )

    weekly_pattern = re.compile(
        rf"(?<!\w)({NUMBER_PATTERN})\s+(?:vezes|dias|sessoes|treinos)\s+por\s+semana(?!\w)"
    )
    for match in weekly_pattern.finditer(normalized):
        _append_numeric_entity(
            entities, text, mapping, match, "weekly_frequency", match.group(1)
        )

    for entity_type, pattern in (
        ("rpe", re.compile(r"(?<!\w)rpe\s*(\d{1,2})(?!\w)")),
        ("rir", re.compile(r"(?<!\w)(\d{1,2})\s*rir(?!\w)")),
    ):
        for match in pattern.finditer(normalized):
            _append_value_entity(
                entities, text, mapping, match, entity_type, int(match.group(1))
            )
    return entities


def _extract_amounts(
    text: str, normalized: str, mapping: list[int]
) -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []
    amount_pattern = re.compile(
        rf"(?<!\w)({NUMBER_PATTERN})\s*(g|gramas?|ml|litros?|l|fatias?|colheres?|xicaras?|unidades?)(?!\w)"
    )
    for match in amount_pattern.finditer(normalized):
        context = normalized[match.start() : match.end() + 24]
        entity_type = (
            "macronutrient_amount"
            if re.search(r"\b(?:proteina|carboidrato|carbo|gordura)\b", context)
            else "amount"
        )
        _append_value_entity(
            entities,
            text,
            mapping,
            match,
            entity_type,
            {"amount": _parse_number(match.group(1)), "unit": match.group(2)},
        )
    return entities


def _extract_preferences_and_limitations(
    text: str,
    normalized: str,
    mapping: list[int],
    catalog_entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []
    preference_patterns = (
        ("negative", re.compile(r"\b(?:nao\s+gosto\s+de|nao\s+curto|odeio)\s+([^,.;!?]+)")),
        (
            "positive",
            re.compile(r"(?:\bprefiro|(?<!nao\s)\bgosto\s+de|\badoro)\s+([^,.;!?]+)"),
        ),
    )
    for polarity, pattern in preference_patterns:
        for match in pattern.finditer(normalized):
            group_start, group_end = match.span(1)
            group_end = _trim_at_connector(normalized, group_start, group_end)
            start, end = _original_span(mapping, match.start(), group_end)
            target = _best_catalog_target(catalog_entities, start, end)
            value = {
                "polarity": polarity,
                "target": target.value if target else text[_original_span(mapping, group_start, group_end)[0] : end].strip(),
                "target_type": target.entity_type if target else "free_text",
            }
            entities.append(
                ExtractedEntity(
                    "preference", text[start:end], value, start, end,
                    "context_rule", {},
                )
            )

    limitation_pattern = re.compile(
        r"\b(?:nao\s+consigo|nao\s+posso|tenho\s+dificuldade\s+(?:de|em)|evito)\s+([^,.;!?]+)"
    )
    for match in limitation_pattern.finditer(normalized):
        group_end = _trim_at_connector(normalized, *match.span(1))
        start, end = _original_span(mapping, match.start(), group_end)
        entities.append(
            ExtractedEntity(
                "limitation",
                text[start:end],
                text[start:end].strip(),
                start,
                end,
                "context_rule",
                {},
            )
        )

    allergy_pattern = re.compile(
        r"\b(?:alergia\s+a|alergico\s+a|alergica\s+a)\s+([^,.;!?]+)"
    )
    for match in allergy_pattern.finditer(normalized):
        group_end = _trim_at_connector(normalized, *match.span(1))
        start, end = _original_span(mapping, match.start(), group_end)
        value_start, _ = _original_span(mapping, match.start(1), group_end)
        entities.append(
            ExtractedEntity(
                "allergy",
                text[start:end],
                text[value_start:end].strip(),
                start,
                end,
                "context_rule",
                {},
            )
        )
    return entities


def _trim_at_connector(normalized: str, start: int, end: int) -> int:
    segment = normalized[start:end]
    connector = re.search(r"\s+(?:mas|porque|porem|e\s+tambem)\s+", segment)
    return start + connector.start() if connector else end


def _best_catalog_target(
    entities: list[ExtractedEntity], start: int, end: int
) -> ExtractedEntity | None:
    inside = [
        entity
        for entity in entities
        if entity.start >= start
        and entity.end <= end
        and entity.entity_type in {"exercise", "food", "modality", "meal"}
    ]
    return max(inside, key=lambda item: item.end - item.start, default=None)


def _assign_replacement_roles(
    normalized: str, entities: list[ExtractedEntity]
) -> list[ExtractedEntity]:
    output = list(entities)
    for base_type in ("exercise", "food"):
        matches = sorted(
            [
                (index, entity)
                for index, entity in enumerate(output)
                if entity.entity_type == base_type
            ],
            key=lambda item: item[1].start,
        )
        for (left_index, left), (right_index, right) in zip(matches, matches[1:]):
            between = normalized[left.end : right.start]
            if re.search(r"\b(?:por|pelo|pela)\b", between):
                output[right_index] = replace(
                    right,
                    entity_type=f"replacement_{base_type}",
                    source="context_rule",
                    attributes={**right.attributes, "relation": "replace_with"},
                )
            elif "no lugar de" in between:
                output[left_index] = replace(
                    left,
                    entity_type=f"replacement_{base_type}",
                    source="context_rule",
                    attributes={**left.attributes, "relation": "replace_with"},
                )
    return output


def _append_numeric_entity(
    entities: list[ExtractedEntity],
    text: str,
    mapping: list[int],
    match: re.Match[str],
    entity_type: str,
    number: str,
) -> None:
    _append_value_entity(
        entities, text, mapping, match, entity_type, _parse_number(number)
    )


def _append_value_entity(
    entities: list[ExtractedEntity],
    text: str,
    mapping: list[int],
    match: re.Match[str],
    entity_type: str,
    value: Any,
    attributes: dict[str, Any] | None = None,
) -> None:
    start, end = _original_span(mapping, match.start(), match.end())
    entities.append(
        ExtractedEntity(
            entity_type,
            text[start:end],
            value,
            start,
            end,
            "numeric_rule",
            attributes or {},
        )
    )


def _parse_number(value: str | None) -> int | float:
    if value is None:
        raise ValueError("Numero ausente")
    normalized = normalize_text(value).strip()
    if re.fullmatch(r"\d+(?:[.,]\d+)?", value.strip()):
        number = float(value.replace(",", "."))
        return int(number) if number.is_integer() else number
    parts = [part.strip() for part in normalized.split(" e ")]
    if not all(part in NUMBER_WORDS for part in parts):
        raise ValueError(f"Numero por extenso desconhecido: {value}")
    return sum(NUMBER_WORDS[part] for part in parts)


def _deduplicate_entities(
    entities: Iterable[ExtractedEntity],
) -> list[ExtractedEntity]:
    unique: dict[tuple[str, int, int, str], ExtractedEntity] = {}
    for entity in entities:
        value_key = json.dumps(entity.value, ensure_ascii=False, sort_keys=True)
        unique[(entity.entity_type, entity.start, entity.end, value_key)] = entity
    return sorted(
        unique.values(),
        key=lambda item: (item.start, item.end, item.entity_type),
    )


def entity_signature(entity: ExtractedEntity | dict[str, Any]) -> tuple[str, str]:
    if isinstance(entity, ExtractedEntity):
        entity_type, value = entity.entity_type, entity.value
    else:
        entity_type, value = entity["entity_type"], entity["value"]
    return entity_type, json.dumps(value, ensure_ascii=False, sort_keys=True)


def score_entity_predictions(
    expected: Iterable[dict[str, Any]],
    predicted: Iterable[ExtractedEntity],
) -> dict[str, Any]:
    expected_counter = Counter(entity_signature(item) for item in expected)
    predicted_counter = Counter(entity_signature(item) for item in predicted)
    true_positive = sum((expected_counter & predicted_counter).values())
    predicted_total = sum(predicted_counter.values())
    expected_total = sum(expected_counter.values())
    precision = true_positive / predicted_total if predicted_total else 0.0
    recall = true_positive / expected_total if expected_total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "predicted": predicted_total,
        "expected": expected_total,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "exact": expected_counter == predicted_counter,
    }

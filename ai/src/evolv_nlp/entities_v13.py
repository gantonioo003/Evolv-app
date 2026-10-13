from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date
from pathlib import Path

from evolv_nlp import entities_v12 as previous
from evolv_nlp.entities import CatalogEntry, EntityCatalog, ExtractedEntity, load_entity_catalog

EXTRACTOR_VERSION = "1.2.0"
NEW_TYPES = frozenset({"drink_volume", "elevation_gain", "cadence", "training_experience"})
ACTIVE_EXISTING = frozenset({"pain_severity", "symptom_onset", "laterality", "movement_tempo", "meal_frequency"})


def load_catalog(ai_root: Path) -> EntityCatalog:
    base = load_entity_catalog(ai_root / "data/catalogs/entity_catalogs.v1.json")
    extra = json.loads((ai_root / "data/catalogs/entity_catalogs.extension.v1.2.json").read_text("utf-8"))
    entries = {(item.entity_type, item.canonical): item for item in base.entries}
    for kind, rows in extra["catalogs"].items():
        for row in rows:
            key = kind, row["canonical"]
            old = entries.get(key)
            aliases = tuple(dict.fromkeys((*old.aliases, *row["aliases"]))) if old else tuple(row["aliases"])
            entries[key] = CatalogEntry(kind, row["canonical"], aliases)
    return EntityCatalog(EXTRACTOR_VERSION, "pt-BR", tuple(entries.values()))


def supported_entity_types(catalog: EntityCatalog) -> frozenset[str]:
    return previous.supported_entity_types(catalog) | NEW_TYPES | ACTIVE_EXISTING


def extract_entities(text: str, catalog: EntityCatalog, reference_date: date):
    result = previous.extract_entities(text, catalog, reference_date)
    normalized, mapping = previous._normalize(text)
    extra = []

    def add(kind, match, value, attributes=None):
        start, end = previous._span(text, mapping, *match.span())
        attributes = {**previous._assertion_attributes(normalized, match.start()), **(attributes or {})}
        extra.append(ExtractedEntity(kind, text[start:end], value, start, end, "context_rule", attributes))

    number = previous._DIGITS
    for m in re.finditer(rf"(?<![\w.,-])({number})\s*(ml|litros?|l)\s*(?:de\s+)?(agua|leite|suco|isotonico|cerveja)(?!\w)", normalized):
        amount = previous._number(m[1])
        ml = amount if m[2] == "ml" else amount * 1000
        add("drink_volume", m, {"amount_ml": ml, "drink": m[3]}, {"subtype": "reported_not_recommended"})
    for m in re.finditer(rf"\b(?:desnivel|ganho de elevacao)\s*(?:de|:)\s*({number})\s*m(?:etros?)?(?!\w)", normalized):
        add("elevation_gain", m, {"amount": previous._number(m[1]), "unit": "m"})
    for m in re.finditer(r"(?<!\w)(\d{2,3})\s*passos\s*/\s*min\b|(?<!\w)(\d{2,3})\s*rpm\b", normalized):
        add("cadence", m, {"amount": int(m[1] or m[2]), "unit": "steps/min" if m[1] else "rpm"})
    for m in re.finditer(rf"\b(?:treino|corro|malho|pedalo|pratico musculacao)\s*(?:ha|faz)\s*({number})\s*(anos?|meses?|semanas?)\b", normalized):
        add("training_experience", m, {"amount": previous._number(m[1]), "unit": m[2]}, {"not_session_duration": True})
    for m in re.finditer(r"\b(?:dor|desconforto)\s*(?:de|:)?\s*(10|[0-9])\s*/\s*10\b", normalized):
        add("pain_severity", m, {"amount": int(m[1]), "scale_max": 10}, {"self_report_not_diagnosis": True})
    for m in re.finditer(r"\b(?:joelho|ombro|punho|tornozelo|braco|perna)\s+(direit[oa]|esquerd[oa])\b", normalized):
        add("laterality", m, "right" if m[1].startswith("direit") else "left")
    for m in re.finditer(r"\b(?:dor|desconforto|incomodo).{0,25}?\b(?:ha|faz)\s*(\d+)\s*(dias?|semanas?|meses?)\b", normalized):
        add("symptom_onset", m, {"amount": int(m[1]), "unit": m[2]}, {"self_report_not_diagnosis": True})
    for m in re.finditer(r"\b(?:cadencia|tempo)\s*(?:de|:)?\s*([0-9])-([0-9])-([0-9])(?:-([0-9]))?(?!\d)", normalized):
        add("movement_tempo", m, {"phases_seconds": [int(value) for value in m.groups() if value is not None]})
    for m in re.finditer(r"(?<!\w)([1-9])\s*refeicoes\s*(?:por|ao)\s*dia\b", normalized):
        add("meal_frequency", m, int(m[1]))
    retained = [e for e in result.entities if not (e.entity_type in {"duration", "sleep_duration", "rest_duration"}
                and any(a.entity_type == "training_experience" and a.start <= e.start and e.end <= a.end for a in extra))]
    unique = {(e.entity_type, e.start, e.end): e for e in (*retained, *extra)}
    return replace(result, extractor_version=EXTRACTOR_VERSION,
                   entities=tuple(sorted(unique.values(), key=lambda e: (e.start, e.end, e.entity_type))))

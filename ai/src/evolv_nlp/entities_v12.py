"""Opt-in entity enrichment; the operational extractor remains unchanged."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from datetime import date
from functools import lru_cache
from typing import Any

from evolv_nlp import entities as legacy
from evolv_nlp.entities import EntityCatalog, ExtractedEntity, ExtractionResult


EXTRACTOR_VERSION = "1.1.0"
EXTRA_ENTITY_TYPES = frozenset({"distance", "pace", "speed", "heart_rate", "lab_measurement", "ambiguous_weight"})

# Each alias is enabled only when its canonical entry exists in the supplied catalog.
_ALIASES = {
    ("exercise", "leg press"): ("legpress", "leg-press"),
    ("exercise", "flexao de bracos"): ("flexao de braco", "flexoes de braco", "flexoes de bracos"),
    ("exercise", "puxada alta"): ("puxada frontal", "puxada na frente"),
    ("exercise", "supino reto com halteres"): ("supino com halter", "supino reto com halter"),
    ("exercise", "supino inclinado"): ("supino inclinado com halter",),
    ("equipment", "halteres"): ("haltere",),
    ("food", "banana"): ("bananas",),
    ("food", "peixe"): ("peixes",),
    ("food", "batata-doce cozida"): ("batatas doces",),
}
_DIGITS = r"(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"
_NUMBER = rf"(?:{_DIGITS}|(?:{legacy.NUMBER_ATOM})(?:\s+e\s+(?:{legacy.NUMBER_ATOM}))?)"
_QUANTITIES = {
    "sets", "repetitions", "load", "duration", "rest_duration", "sleep_duration",
    "weekly_frequency", "rpe", "rir", "amount", "macronutrient_amount",
}
_CONTEXT_TYPES = {"preference", "limitation", "allergy", "replacement_exercise", "replacement_food"}
_BOUNDARY = re.compile(r"[;!?\n]|(?<!\d)[.,]|[.,](?!\d)|\b(?:mas|por[e\u00e9]m)\b", re.I)
_MACRO = r"(?:proteinas?|carboidratos?|carbos?|gorduras?)"
_CLINICAL_CONTEXT = re.compile(r"\b(?:oxandrolona|anastrozol|durateston|enantato|testosterona|testo|insulina|semaglutida|medicamento)\b")


def supported_entity_types(catalog: EntityCatalog) -> frozenset[str]:
    """Types with extraction rules or supplied catalog entries, not measured recall."""
    return frozenset(entry.entity_type for entry in catalog.entries) | _QUANTITIES | _CONTEXT_TYPES | EXTRA_ENTITY_TYPES | {
        "source_date", "target_date", "energy_amount", "body_measurement", "age_group", "schedule",
    }


def extract_entities(text: str, catalog: EntityCatalog, reference_date: date) -> ExtractionResult:
    result = legacy.extract_entities(text, catalog, reference_date)
    normalized, mapping = _normalize(text)
    catalog_entities = _catalog_entities(text, normalized, mapping, catalog)
    additional = _additional_entities(text, normalized, mapping)
    quantities = _quantities(text, normalized, mapping, catalog_entities)
    quantities = [
        entity for entity in quantities
        if not any(
            other.entity_type == "schedule" and other.start <= entity.start and entity.end <= other.end
            for other in additional
        )
    ]
    retained = [
        entity for entity in result.entities
        if entity.source != "catalog"
        and entity.entity_type not in _QUANTITIES | _CONTEXT_TYPES
    ]
    entities = [
        *retained,
        *catalog_entities,
        *quantities,
        *additional,
        *_context_entities(text, normalized, mapping, catalog_entities),
    ]
    entities = _replacement_roles(text, entities)
    unique = {
        (entity.entity_type, entity.start, entity.end, legacy.entity_signature(entity)[1]): entity
        for entity in entities
    }
    return replace(
        result,
        extractor_version=EXTRACTOR_VERSION,
        entities=tuple(sorted(unique.values(), key=lambda item: (item.start, item.end, item.entity_type))),
    )


def _normalize(text: str) -> tuple[str, list[int]]:
    characters: list[str] = []
    mapping: list[int] = []
    for index, character in enumerate(text):
        for candidate in unicodedata.normalize("NFKD", character.casefold()):
            if not unicodedata.combining(candidate):
                characters.append(candidate)
                mapping.append(index)
    return "".join(characters), mapping


def _fold(text: str) -> str:
    return _normalize(text)[0]


def _span(text: str, mapping: list[int], start: int, end: int) -> tuple[int, int]:
    original_end = mapping[end - 1] + 1
    while original_end < len(text) and unicodedata.combining(text[original_end]):
        original_end += 1
    return mapping[start], original_end


@lru_cache(maxsize=512)
def _term_pattern(term: str) -> re.Pattern[str]:
    parts = re.split(r"[\W_]+", _fold(term).strip())
    return re.compile(r"(?<!\w)" + r"[\W_]+".join(map(re.escape, parts)) + r"(?!\w)")


def _clause(text: str, position: int) -> tuple[int, int]:
    start, end = 0, len(text)
    for match in _BOUNDARY.finditer(text):
        if match.end() <= position:
            start = match.end()
        elif match.start() >= position:
            end = match.start()
            break
    return start, end


def _negated(prefix: str) -> bool:
    return bool(re.search(
        r"\b(?:nao|nunca|sem)(?:\s+(?:sou|e|eh|tenho|tem|estou|era|fui|mais|"
        r"nenhuma?|qualquer|muito|de|ser|estar|quero|vou|posso|preciso)){0,4}\s*$",
        prefix,
    ))


def _assertion_attributes(normalized: str, start: int) -> dict[str, Any]:
    clause_start, _ = _clause(normalized, start)
    prefix = normalized[clause_start:start]
    attributes: dict[str, Any] = {}
    if _negated(prefix[-50:]):
        attributes["negated"] = True
    if re.search(r"\b(?:minha|meu)\s+(?:irma|irmao|mae|pai|amig[oa]|filh[oa])\b", prefix):
        attributes.update(subject="other", requires_context=True)
    if re.search(r"\b(?:se eu|caso eu|e se|hipoteticamente)\b", prefix):
        attributes.update(hypothetical=True, requires_context=True)
    return attributes


def _catalog_entities(
    text: str, normalized: str, mapping: list[int], catalog: EntityCatalog,
) -> list[ExtractedEntity]:
    candidates: list[ExtractedEntity] = []
    for entry in catalog.entries:
        terms = (entry.canonical, *entry.aliases, *_ALIASES.get((entry.entity_type, entry.canonical), ()))
        for term in dict.fromkeys(terms):
            for match in _term_pattern(term).finditer(normalized):
                start, end = _span(text, mapping, *match.span())
                attributes: dict[str, Any] = {"matched_alias": term}
                if entry.entity_type == "dietary_restriction":
                    attributes.update(_assertion_attributes(normalized, match.start()))
                candidates.append(ExtractedEntity(
                    entry.entity_type, text[start:end], entry.canonical, start, end, "catalog", attributes,
                ))
    selected: list[ExtractedEntity] = []
    for candidate in sorted(candidates, key=lambda item: (-(item.end - item.start), item.start, item.entity_type)):
        if not any(candidate.start < other.end and other.start < candidate.end for other in selected):
            selected.append(candidate)
    return sorted(selected, key=lambda item: (item.start, item.end, item.entity_type))


def _number(raw: str) -> int | float:
    if re.fullmatch(_DIGITS, raw):
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", raw):
            raw = raw.replace(".", "")
        value = float(raw.replace(",", "."))
        return int(value) if value.is_integer() else value
    return legacy._parse_number(raw)


def _mass_type(
    text: str, start: int, end: int, per_side: bool, catalog: list[ExtractedEntity],
) -> str | None:
    # Clause positions are computed in original text; folding can expand Unicode.
    clause_start, clause_end = _clause(text, start)
    before = _fold(text[clause_start:start])
    after = _fold(text[end:clause_end])
    if per_side:
        return "load"
    body_prefix = r"\b(?:peso|pesava|pesando|meu peso|peso corporal)\s*:?\s*(?:(?:cerca de|aproximadamente|uns|atualmente)\s*)?$"
    if re.search(body_prefix, before) or re.match(r"\s*(?:de\s+)?peso corporal\b", after):
        return "body_measurement"
    if re.search(r"\b(?:perdi|perder|ganhei|ganhar|emagreci|engordei|engordar)\s*$", before):
        return "body_weight_change"
    for entity in catalog:
        if entity.entity_type not in {"exercise", "food"}:
            continue
        if clause_start <= entity.end <= start:
            gap = _fold(text[entity.end:start])
            if entity.entity_type == "exercise" and re.fullmatch(
                r"\s*(?:com\s*)?(?:\d{1,2}\s*[x\u00d7]\s*\d{1,3}(?:\s*(?:-|a)\s*\d{1,3})?\s*)?(?:com\s*)?", gap,
            ):
                return "load"
        if end <= entity.start < clause_end:
            gap = _fold(text[end:entity.start])
            if re.fullmatch(r"\s*(?:no|na|de|para)\s+", gap):
                return "load" if entity.entity_type == "exercise" else "amount"
    if re.search(r"\b(?:carga|levantei|levantando|usei|usa|peguei|pego)\s*(?:de\s*)?$", before):
        return "load"
    if re.search(r"\b(?:tenho|estou com)\s*(?:aproximadamente\s*)?$", before):
        return "body_measurement"
    return None


def _duration_type(normalized: str, start: int, end: int) -> str:
    clause_start, clause_end = _clause(normalized, start)
    before = normalized[max(clause_start, start - 40):start]
    after = normalized[end:min(clause_end, end + 28)]
    if re.match(r"\s*(?:de\s+)?(?:sono|descanso|intervalo)\b", after):
        return "sleep_duration" if "sono" in after.split()[:2] else "rest_duration"
    anchors = list(re.finditer(
        r"\b(?:dormi|durmo|sono|dormir|descanso|descansa|descansar|intervalo|pausa|treino|treinei|corrida|cardio|caminhada)\b",
        before,
    ))
    if anchors:
        last = anchors[-1].group()
        if last in {"dormi", "durmo", "sono", "dormir"}:
            return "sleep_duration"
        if last in {"descanso", "descansa", "descansar", "intervalo", "pausa"}:
            return "rest_duration"
    return "duration"


def _quantities(
    text: str, normalized: str, mapping: list[int], catalog: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []

    def add(kind: str, match: re.Match[str], value: Any, attributes: dict[str, Any] | None = None) -> None:
        start, end = _span(text, mapping, *match.span())
        entities.append(ExtractedEntity(kind, text[start:end], value, start, end, "numeric_rule", attributes or {}))

    compact = r"(?<!\w)(\d{1,2})\s*[x\u00d7]\s*(\d{1,3})(?:\s*(?:-|\u2013|a)\s*(\d{1,3}))?(?!\w)"
    for match in re.finditer(compact, normalized):
        minimum, maximum = int(match[2]), int(match[3]) if match[3] else None
        if maximum is not None and maximum < minimum:
            continue
        add("sets", match, int(match[1]), {"notation": "compact"})
        add("repetitions", match, {"minimum": minimum, "maximum": maximum} if maximum is not None else minimum, {"notation": "compact"})

    for kind, pattern in (
        ("sets", rf"(?<![\w.,])({_NUMBER})\s+(?:series?|sets?)(?!\w)"),
        ("weekly_frequency", rf"(?<![\w.,])({_NUMBER})\s*(?:vezes|dias|sessoes|treinos|x)\s*(?:por|na)\s+semana(?!\w)"),
        ("rpe", rf"(?<!\w)rpe\s*({_NUMBER})(?![\w.,])"),
        ("rir", rf"(?<![\w.,])({_NUMBER})\s*rir(?!\w)"),
    ):
        for match in re.finditer(pattern, normalized):
            value = _number(match[1])
            if kind == "rpe" and not 0 <= value <= 10:
                continue
            if kind in {"sets", "weekly_frequency", "rir"} and not isinstance(value, int):
                continue
            add(kind, match, value)

    repetition_pattern = rf"(?<![\w.,])({_NUMBER})(?:\s*(?:-|\u2013|a)\s*({_NUMBER}))?\s+(?:repeticoes|reps?)(?!\w)"
    for match in re.finditer(repetition_pattern, normalized):
        minimum, maximum = _number(match[1]), _number(match[2]) if match[2] else None
        if not isinstance(minimum, int) or (maximum is not None and (not isinstance(maximum, int) or maximum < minimum)):
            continue
        add("repetitions", match, {"minimum": minimum, "maximum": maximum} if maximum is not None else minimum)

    mass_pattern = rf"(?<![\w.,-])({_NUMBER})\s*(kg|kgs|quilos?|kilos?|lbs?|libras?)(?:\s+(?:de\s+)?cada\s+lado)?(?!\w)"
    for match in re.finditer(mass_pattern, normalized):
        if re.search(r"\d\s*[-\u2013\u2014]\s*$", normalized[:match.start()]):
            continue
        start, end = _span(text, mapping, *match.span())
        per_side = "cada lado" in match[0]
        kind = _mass_type(text, start, end, per_side, catalog)
        if kind is None:
            kind = "ambiguous_weight"
        unit = "kg" if match[2].startswith(("kg", "quilo", "kilo")) else "lb"
        value: dict[str, Any] = {"amount": _number(match[1]), "unit": unit}
        if kind in {"body_measurement", "body_weight_change"}:
            value["measurement"] = "body_weight" if kind == "body_measurement" else "body_weight_change"
            kind = "body_measurement"
        attributes: dict[str, Any] = {"per_side": per_side} if kind == "load" else {}
        if kind == "ambiguous_weight":
            attributes.update(requires_context=True, candidates=["load", "body_measurement", "amount"])
        add(kind, match, value, attributes)

    amount_pattern = rf"(?<![\w.,-])({_NUMBER})\s*(g|gramas?|ml|litros?|l|fatias?|colheres?|xicaras?|unidades?)(?!\w)"
    for match in re.finditer(amount_pattern, normalized):
        clause_start, clause_end = _clause(normalized, match.start())
        before, after = normalized[clause_start:match.start()], normalized[match.end():clause_end]
        macro = re.match(rf"\s*(?:de\s+)?({_MACRO})\b", after) or re.search(rf"\b({_MACRO})\s*:?\s*$", before)
        attributes: dict[str, Any] = {}
        suffix = re.match(r"\s*/\s*(\w+)", after)
        if suffix:
            if suffix[1] != "kg":
                continue
            attributes["per_unit"] = "kg"
            macro = macro or re.match(rf"\s*(?:de\s+)?({_MACRO})\b", after[suffix.end():])
        if match[2] in {"ml", "l", "litro", "litros"}:
            if re.match(r"\s*(?:de\s+)?agua\b", after):
                attributes["subtype"] = "hydration"
            elif _CLINICAL_CONTEXT.search(before[-35:] + match[0] + after[:50]):
                attributes.update(subtype="substance_dose", clinical=True, requires_context=True)
        add("macronutrient_amount" if macro else "amount", match, {"amount": _number(match[1]), "unit": match[2]}, attributes)

    for match in re.finditer(rf"(?<![\w.,-])({_NUMBER})\s*(?:kcal|calorias?)(?!\w)", normalized):
        add("energy_amount", match, {"amount": _number(match[1]), "unit": "kcal"})

    for match in re.finditer(rf"(?<![\w.,-])({_NUMBER})\s*(horas?|h|minutos?|min|segundos?|seg)(?!\w)", normalized):
        if re.match(r"\s*/\s*(?:km|mi|mile)\b", normalized[match.end():]):
            continue
        amount, raw_unit = _number(match[1]), match[2]
        unit, factor = ("hour", 3600) if raw_unit.startswith("h") else (("minute", 60) if raw_unit.startswith("min") else ("second", 1))
        add(_duration_type(normalized, *match.span()), match, {"amount": amount, "unit": unit, "seconds": int(amount * factor)})
    return entities


def _additional_entities(text: str, normalized: str, mapping: list[int]) -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []

    def add(kind: str, match: re.Match[str], value: Any, attributes: dict[str, Any] | None = None) -> None:
        start, end = _span(text, mapping, *match.span())
        entities.append(ExtractedEntity(kind, text[start:end], value, start, end, "numeric_rule", attributes or {}))

    speed_units = {"km/h": "km/h", "kph": "km/h", "mph": "mph", "m/s": "m/s"}
    for match in re.finditer(rf"(?<![\w.,-])({_DIGITS})\s*(km/h|kph|mph|m/s)(?!\w)", normalized):
        add("speed", match, {"amount": _number(match[1]), "unit": speed_units[match[2]]})

    distance_units = {"km": "km", "m": "m", "mi": "mi"}
    for match in re.finditer(rf"(?<![\w.,-])({_DIGITS})\s*(km|quilometros?|metros?|m|milhas?|mi)(?!\w)", normalized):
        if re.match(r"\s*/\s*(?:h|hora|s|seg)\b", normalized[match.end():]):
            continue
        unit = match[2]
        unit = distance_units.get(unit, "km" if unit.startswith("quilo") else ("mi" if unit.startswith("milha") else "m"))
        if unit == "m":
            start, end = _clause(normalized, match.start())
            context = normalized[max(start, match.start() - 45):min(end, match.end() + 45)]
            if re.search(r"\b(?:altura|cintura|braco|coxa|quadril)\b", context) or not re.search(r"\b(?:corro|correr|corrida|caminhada|percurso|distancia|nado|piscina|pedalo)\b", context):
                continue
        add("distance", match, {"amount": _number(match[1]), "unit": unit})

    for match in re.finditer(r"(?<![\w:])(\d{1,2}):([0-5]\d)\s*(?:min\s*)?/\s*km(?!\w)", normalized):
        seconds = int(match[1]) * 60 + int(match[2])
        add("pace", match, {"amount": seconds / 60, "unit": "min/km", "seconds_per_km": seconds})
    for match in re.finditer(rf"(?<![\w.,:])({_DIGITS})\s*(?:min(?:utos?)?\s*/\s*km|minutos?\s+por\s+(?:km|quilometro))(?!\w)", normalized):
        amount = _number(match[1])
        add("pace", match, {"amount": amount, "unit": "min/km", "seconds_per_km": amount * 60})

    for match in re.finditer(r"(?<!\w)(\d{2,3})\s*(?:bpm|batimentos por minuto)(?!\w)", normalized):
        add("heart_rate", match, {"amount": int(match[1]), "unit": "bpm"})

    lab_units = {"ng/dl": "ng/dL", "nmol/l": "nmol/L", "mg/dl": "mg/dL", "miu/l": "mIU/L", "mmol/l": "mmol/L", "ug/dl": "ug/dL"}
    for match in re.finditer(rf"(?<![\w.,-])({_DIGITS})\s*(ng/dl|nmol/l|mg/dl|miu/l|mmol/l|ug/dl)(?!\w)", normalized):
        add("lab_measurement", match, {"amount": _number(match[1]), "unit": lab_units[match[2]]}, {"clinical": True, "requires_context": True})

    dose_units = {"mg": "mg", "mcg": "mcg", "ug": "ug", "ui": "UI", "iu": "IU"}
    for match in re.finditer(rf"(?<![\w.,-])({_DIGITS})\s*(mg|mcg|ug|ui|iu)(?!\w)", normalized):
        if re.match(r"\s*/\s*(?:dl|l)\b", normalized[match.end():]):
            continue
        attributes: dict[str, Any] = {"subtype": "substance_dose", "clinical": True, "requires_context": True}
        cadence = re.match(r"\s*(?:/\s*(?:dia|semana)|a cada \d+ horas?|de \d+ em \d+ horas?)\b", normalized[match.end():])
        if cadence:
            start, end = _span(text, mapping, match.end() + cadence.start(), match.end() + cadence.end())
            attributes["cadence_text"] = text[start:end].strip()
        add("amount", match, {"amount": _number(match[1]), "unit": dose_units[match[2]]}, attributes)

    for match in re.finditer(r"\b(?:tenho\s+(\d{1,3})\s*anos|idade\s*:\s*(\d{1,3}))(?!\w)", normalized):
        age = int(match[1] or match[2])
        if 0 <= age <= 120:
            add("age_group", match, {"amount": age, "unit": "year"}, {"subtype": "numeric_age", **_assertion_attributes(normalized, match.start())})

    for match in re.finditer(rf"\baltura\s*:?\s*({_DIGITS})\s*(cm|m)(?!\w)|(?<![\w.,])({_DIGITS})\s*(cm|m)\s*de\s*altura\b", normalized):
        amount, unit = _number(match[1] or match[3]), match[2] or match[4]
        add("body_measurement", match, {"measurement": "height", "amount": amount, "unit": unit}, {"subtype": "height"})
    for match in re.finditer(rf"(?<![\w.,])({_DIGITS})\s*cm\s*de\s*(braco|cintura|coxa|quadril)(?!\w)", normalized):
        add("body_measurement", match, {"measurement": match[2], "amount": _number(match[1]), "unit": "cm"}, {"subtype": "circumference"})

    fat_pattern = rf"\b(?:bf|gordura corporal|percentual de gordura)\s*(?:(?:de|e)\s*|:\s*)?({_DIGITS})\s*%|(?<![\w.,])({_DIGITS})\s*%\s*(?:bf|de gordura corporal)\b"
    for match in re.finditer(fat_pattern, normalized):
        add("body_measurement", match, {"measurement": "body_fat_percent", "amount": _number(match[1] or match[2]), "unit": "%"}, {"subtype": "body_fat_percent"})
    for match in re.finditer(rf"\bimc\s*:?\s*({_DIGITS})(?![\w.,])", normalized):
        add("body_measurement", match, {"measurement": "bmi", "amount": _number(match[1])}, {"subtype": "bmi"})

    for match in re.finditer(r"(?<![\w:])([01]?\d|2[0-3])(?::([0-5]\d)|h(?:([0-5]\d))?)(?![\w:])", normalized):
        start, _ = _clause(normalized, match.start())
        before, after = normalized[start:match.start()], normalized[match.end():]
        if re.match(r"\s*(?:min\s*)?/\s*km\b", after):
            continue
        cue = re.search(r"\b(?:treino|treinar|malho|refeicao|almoco|janto|jantar|cafe|acordo|trabalho|disponivel)\b", before)
        if not cue or not re.search(r"\b(?:as|pelas|das)\s*$", before):
            continue
        hour, minute = int(match[1]), int(match[2] or match[3] or 0)
        add("schedule", match, {"time": f"{hour:02}:{minute:02}"}, {"subtype": "clock_time"})
    return entities


def _context_entities(
    text: str, normalized: str, mapping: list[int], catalog: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []
    patterns = (
        ("preference", "negative", r"\b(?:nao\s+gosto\s+de|nao\s+curto|odeio)\s+([^,.;!?\n]+)"),
        ("preference", "positive", r"\b(?:prefiro|gosto\s+de|adoro)\s+(?=([^,.;!?\n]+))"),
        ("limitation", None, r"\b(?:nao\s+consigo|nao\s+posso|tenho\s+dificuldade\s+(?:de|em)|evito)\s+([^,.;!?\n]+)"),
        ("allergy", None, r"\b(?:alergia\s+a|alergic[oa]\s+a)\s+([^,.;!?\n]+)"),
    )
    for kind, polarity, pattern in patterns:
        for match in re.finditer(pattern, normalized):
            clause_start, _ = _clause(normalized, match.start())
            if polarity == "positive" and _negated(normalized[clause_start:match.start()]):
                continue
            group_start, group_end = match.span(1)
            connector = re.search(r"\s+(?:mas|porque|porem|e\s+(?:tambem|(?:nao\s+)?(?:gosto|prefiro|adoro|sou|tenho)))\b", normalized[group_start:group_end])
            if connector:
                group_end = group_start + connector.start()
            while group_end > group_start and normalized[group_end - 1].isspace():
                group_end -= 1
            if group_end <= group_start:
                continue
            start, end = _span(text, mapping, match.start(), group_end)
            value_start, _ = _span(text, mapping, group_start, group_end)
            attributes = _assertion_attributes(normalized, match.start())
            if kind == "preference":
                targets = [entity for entity in catalog if value_start <= entity.start and entity.end <= end and entity.entity_type in {"exercise", "food", "modality", "meal"}]
                target = min(targets, key=lambda item: (item.entity_type == "meal", item.start, -(item.end - item.start)), default=None)
                value: Any = {"polarity": polarity, "target": target.value if target else text[value_start:end].strip(), "target_type": target.entity_type if target else "free_text"}
            else:
                value = text[value_start:end].strip() if kind == "allergy" else text[start:end].strip()
            entities.append(ExtractedEntity(kind, text[start:end], value, start, end, "context_rule", attributes))
    return entities


def _replacement_roles(text: str, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    output = list(entities)
    for base_type in ("exercise", "food"):
        matches = sorted(((index, entity) for index, entity in enumerate(output) if entity.entity_type == base_type), key=lambda item: item[1].start)
        for (left_index, left), (right_index, right) in zip(matches, matches[1:]):
            clause_start, clause_end = _clause(text, left.start)
            if right.end > clause_end:
                continue
            prefix = _fold(text[clause_start:left.start])
            verbs = list(re.finditer(r"\b(?:troca|troque|trocar|substitui|substitua|substituir|coloca|coloque|muda|mude)\b", prefix))
            if not verbs or _negated(prefix[:verbs[-1].start()]):
                continue
            between = _fold(text[left.end:right.start])
            index, entity = (left_index, left) if "no lugar de" in between else (right_index, right)
            if "no lugar de" not in between and not re.search(r"\b(?:por|pelo|pela)\b", between):
                continue
            output[index] = replace(entity, entity_type=f"replacement_{base_type}", source="context_rule", attributes={**entity.attributes, "relation": "replace_with"})
    return output

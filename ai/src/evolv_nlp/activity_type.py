"""Shared explicit activity mentions; extraction never authorizes an action."""
import re
from .entities import ExtractedEntity
from .entities_v12 import _normalize, _span, _assertion_attributes

PATTERNS = {
    "rest": r"\b(?:descanso|descansar)\b",
    "resistance": r"\b(?:musculacao|treino resistido)\b",
    "cardio": r"\bcardio\b",
    "mixed": r"\b(?:misto|mista)\b",
}


def activity_mentions(text):
    normalized, mapping = _normalize(text)
    mentions = []
    for value, pattern in PATTERNS.items():
        for match in re.finditer(pattern, normalized):
            # Rest intervals are not a calendar activity.
            tail = normalized[match.end():match.end()+60]
            prefix = normalized[max(0,match.start()-35):match.start()]
            if value == "rest" and (re.match(r"\s+(?:de |das |entre |nas |por )?(?:\d+\s*)?(?:series|repeticoes|segundos|minutos)\b", tail)
                                    or re.search(r"\b(?:intervalo|tempo)\s+de\s*$", prefix)):
                continue
            attrs = {**_assertion_attributes(normalized,match.start()), "explicit_mention_only":True}
            if re.search(r"\b(?:nao|nunca|sem)(?:\s+(?:quero|vou|irei|fazer|praticar|realizar|mais|posso|preciso|de)){0,6}\s*$",
                         normalized[max(0,match.start()-65):match.start()]):
                attrs["negated"] = True
            if re.search(r"\btalvez\b", normalized[:match.start()]):
                attrs.update(hypothetical=True,requires_context=True)
            start,end = _span(text,mapping,*match.span())
            mentions.append(ExtractedEntity("activity_type",text[start:end],value,start,end,"activity_type_rule",attrs))
    return mentions


def usable_activity_values(text):
    return {e.value for e in activity_mentions(text) if not any(e.attributes.get(k) for k in
            ("negated","requires_context","hypothetical","third_party"))}

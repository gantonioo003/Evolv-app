"""Data minimization is not proof of anonymization or a lawful basis."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from evolv_nlp.entities import normalize_text

POLICY_VERSION = "1.0.0"
PATTERNS = {
    "email": r"(?<!\w)[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}",
    "cpf": r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)",
    "phone": r"(?<!\d)(?:\+?55\s*)?\(?[1-9]\d\)?[ .-]?9?\d{4}[ .-]?\d{4}(?!\d)",
    "url": r"https?://[^\s<>]+|\bwww\.[^\s<>]+",
    "handle": r"(?<!\w)@[\w.]{2,}",
    "self_identified_name": r"\b(?:me chamo|meu nome (?:e|é))\s+[A-ZÀ-Ý][\wÀ-ÿ]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ]+){0,3}",
    "address": r"\b(?:moro na|moro em|meu endereco|meu endereço)\s+[^\n;.!?]+",
}
COMPILED = {kind: re.compile(pattern, re.I if kind != "self_identified_name" else 0)
            for kind, pattern in PATTERNS.items()}
SENSITIVE = re.compile(r"\b(?:dor|dores|doi|doendo|desconforto|lesao|lesionado|diagnostico|"
                       r"exame|diabetes|gravida|gravidez|alergia|depressao|ansiedade|"
                       r"suicidio|medicamento|testosterona|semaglutida|sertralina|"
                       r"bulimia|anorexia|compulsao|vida sexual|religiao)\b")
MINOR = re.compile(r"\b(?:tenho|idade\s*:)\s*(?:[5-9]|1[0-7])\s*anos\b")


@dataclass(frozen=True)
class PrivacyReview:
    minimized_text: str
    identifier_counts: dict[str, int]
    flags: tuple[str, ...]
    anonymization_verified: bool = False

    def summary(self) -> dict[str, Any]:
        # No spans, original text or reversible identifiers in public reports.
        return {"identifier_counts": self.identifier_counts, "flags": list(self.flags),
                "anonymization_verified": False}


def review_text(text: str) -> PrivacyReview:
    if not isinstance(text, str):
        raise ValueError("Texto deve ser uma string")
    matches = sorted(((m.start(), m.end(), kind) for kind, pattern in COMPILED.items()
                      for m in pattern.finditer(text)), key=lambda row: (row[0], -row[1]))
    selected, end = [], -1
    for match in matches:
        if match[0] >= end:
            selected.append(match)
            end = match[1]
    result = text
    for start, end, kind in reversed(selected):
        result = result[:start] + f"[REDACTED_{kind.upper()}]" + result[end:]
    counts = dict(Counter(kind for _, _, kind in selected))
    folded = normalize_text(text)
    flags = []
    if counts:
        flags.append("direct_identifiers_removed")
    if SENSITIVE.search(folded):
        flags.append("possible_sensitive_personal_data")
    if MINOR.search(folded):
        flags.append("possible_minor")
    if re.search(r"\b(?:minha mae|meu pai|minha filha|meu filho|minha amiga|meu amigo)\b", folded):
        flags.append("third_party_context")
    return PrivacyReview(result, counts, tuple(flags))


def training_permission(record: dict[str, Any], purpose: str = "nlu_training") -> dict[str, Any]:
    """Fail closed; consent to use the app is not consent to train a model."""
    reasons = []
    authored = record.get("provenance") == "project_authored_synthetic"
    authorization = record.get("authorization", {})
    if not authored:
        if record.get("rights_status") != "verified":
            reasons.append("source_rights_unverified")
        if record.get("privacy_review_status") != "approved":
            reasons.append("privacy_review_pending")
        if authorization.get("status") != "approved" or purpose not in authorization.get("purposes", []):
            reasons.append("purpose_not_authorized")
        if not authorization.get("evidence_reference") or not authorization.get("lawful_basis_review_reference"):
            reasons.append("authorization_evidence_missing")
        if authorization.get("withdrawn"):
            reasons.append("authorization_withdrawn")
        if "possible_minor" in record.get("privacy_flags", []):
            reasons.append("minor_requires_separate_review")
    if record.get("review_status") not in {"human_reviewed", "assistant_reviewed_synthetic"}:
        reasons.append("labels_not_reviewed")
    return {"allowed": not reasons, "reasons": reasons, "purpose": purpose,
            "policy_version": POLICY_VERSION, "is_legal_clearance": False}

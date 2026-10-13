from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.real_data import PRIVATE_PATTERN, normalized_key, write_json, write_jsonl
from evolv_nlp.privacy import review_text


def import_questions(source: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Nao sobrescrever uma coleta existente")
    rows, seen, seen_ids = [], set(), set()
    with source.open(encoding="utf-8-sig", newline="") as stream:
        for item in csv.DictReader(stream):
            participant = item.get("participant_code", "").strip()
            text = item.get("question", "").strip()
            if not participant or not text or item.get("source_type") != "consented_interview":
                raise ValueError("Codigo pseudonimo, pergunta e origem consented_interview sao obrigatorios")
            if not participant.startswith("P") or not participant[1:].isdigit():
                raise ValueError("Use codigos pseudonimos P001, P002, sem nomes ou contatos")
            if item.get("consent_evaluation", "").casefold() not in ("yes", "sim"):
                raise ValueError("Consentimento para avaliacao nao informado; nao importar")
            if item.get("consent_training", "").casefold() not in ("yes", "sim", "no", "nao"):
                raise ValueError("Informar separadamente consentimento para treino: sim/nao")
            privacy = review_text(text)
            if PRIVATE_PATTERN.search(text) or privacy.identifier_counts:
                raise ValueError("Possivel dado pessoal: revisar antes de importar")
            key = normalized_key(text)
            if key in seen:
                continue
            seen.add(key)
            row_id = hashlib.sha256(f"{participant}:{text}".encode()).hexdigest()
            if row_id in seen_ids:
                continue
            seen_ids.add(row_id)
            rows.append({"id": f"interview-{row_id[:16]}", "participant_group": participant,
                         "text": text, "language": "pt-BR", "source": "consented_interview",
                         "consent_training": item["consent_training"].casefold() in ("yes", "sim"),
                         "consent_evaluation": True, "split": "reserved_human_holdout",
                         "intent": None, "risks": None, "review_status": "pending",
                         "training_allowed": False, "corpus_allowed": False,
                         "privacy_flags": list(privacy.flags), "privacy_review_status": "pending",
                         "anonymization_verified": False,
                         "authorization": {"status": "pending_evidence_review", "purposes": [],
                            "evidence_reference": item.get("consent_evidence_reference") or None,
                            "lawful_basis_review_reference": item.get("lawful_basis_review_reference") or None},
                         "consent_checkbox_is_not_final_clearance": True})
    if not rows:
        raise ValueError("Nenhuma pergunta consentida encontrada")
    write_jsonl(output, rows)
    summary = {"rows": len(rows), "participant_groups": len({r["participant_group"] for r in rows}),
               "training_or_corpus_started": False, "status": "reserved_for_review_and_independent_evaluation"}
    write_json(output.with_suffix(".manifest.json"), summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import consented questions as a separate reserved human holdout.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--name", required=True, help="Versioned batch identifier, e.g. interviews-001")
    args = parser.parse_args()
    if not args.name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in args.name):
        raise ValueError("Nome deve conter somente letras minusculas, numeros e hifen")
    print(import_questions(args.input, AI_ROOT / "data/external_private/interviews" / f"{args.name}.jsonl"))

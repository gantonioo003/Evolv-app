"""Import the edited workbooks; snapshot JSONL contributes provenance, not labels."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from evolv_nlp.context_data import close_duplicate_pairs, frozen_fingerprints
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.privacy import review_text
from evolv_nlp.real_data import normalized_key, reserved_texts, write_json, write_jsonl

VERSION = "1.7.0"
SOURCES = (
    ("public", "Publicos_10000_rotulados_IA.xlsx", "publicos_rotulados_IA.jsonl", 10000),
    ("survey", "Pesquisa_amigos_rotulada_IA.xlsx", "amigos_rotulados_IA.jsonl", 258),
    ("coach", "Acoes_Coach_441_rotuladas_IA.xlsx", "coach_rotulados_IA.jsonl", 441),
    ("rare_synthetic", "Quarta_Sinteticos_Classes_Raras_1480.xlsx",
     "Complemento_Sintetico_2026-10-18/sinteticos_classes_raras_1480.jsonl", 1480),
)


def labels(value):
    if value is None:
        return []
    values = value if isinstance(value, list) else re.split(r"[;\n]", str(value))
    return list(dict.fromkeys(str(v).strip() for v in values
                              if str(v).strip() and str(v).strip().lower() != "nenhuma"))


def read_workbook(path):
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = iter(workbook["Revisao"].values)
        columns = next((list(row) for row in rows if row and row[0] == "id_mensagem"), None)
        if not columns or len(columns) != len(set(columns)):
            raise ValueError("Missing or duplicate workbook headers")
        return [dict(zip(columns, row)) for row in rows if row and row[0]]
    finally:
        workbook.close()


def model_text(text, context=""):
    # Annotation notes, model candidates and expected decisions never enter features.
    return f"Contexto anterior: {context}\nMensagem atual: {text}" if context else text


def choose_partition(source, raw, meta):
    if source == "public":
        split = raw.get("split")
        if split not in {"train", "validation", "test"}:
            raise ValueError(f"Invalid original split: {split}")
        return split
    if source == "survey":
        return "external_human_language"
    if source == "rare_synthetic":
        return "train"
    # The 120 seed-derived simulations stay outside training with their 21 sources.
    if meta.get("leakage_group_id") == "coach_seed_collection_2026_10_14":
        return "external_synthetic" if meta.get("is_synthetic") else "external_human_language"
    if not meta.get("is_synthetic", False):
        return "external_human_language"
    return "train"


def input_fingerprint(text, context=""):
    return hashlib.sha256(normalized_key(model_text(text, context)).encode()).hexdigest()


def import_release(source: Path, ai_root: Path):
    output = ai_root / f"data/releases/{VERSION}"
    if (output / "manifest.json").exists():
        raise ValueError("Finalized release; create a new version instead of overwriting")
    protected = frozen_fingerprints(ai_root)
    taxonomy_path = source / "taxonomia_revisada.json"
    taxonomy = json.loads(taxonomy_path.read_text("utf-8"))
    intents = {item["id"] for item in taxonomy["intents"]}
    risks = {item["id"] for item in taxonomy["risks"]}
    if len(intents) != 60 or len(risks) != 21:
        raise ValueError("Unexpected reviewed taxonomy")
    rows, checksums, identifiers, privacy_flags = [], {}, Counter(), Counter()
    historical = reserved_texts(ai_root)
    for family, workbook_name, snapshot_name, expected in SOURCES:
        path = source / workbook_name
        workbook = read_workbook(path)
        snapshot = {r["id_mensagem"]: r for r in read_jsonl(source / snapshot_name)}
        if len(workbook) != expected or len({r["id_mensagem"] for r in workbook}) != expected:
            raise ValueError(f"Unexpected count/duplicate IDs in {workbook_name}")
        checksums[workbook_name] = file_sha256(path)
        checksums[snapshot_name] = file_sha256(source / snapshot_name)
        for raw in workbook:
            source_id = str(raw["id_mensagem"])
            meta = snapshot.get(source_id, {})
            if not meta:
                raise ValueError(f"Missing provenance: {source_id}")
            original = raw.get("texto_original")
            if not isinstance(original, str) or not original.strip():
                raise ValueError(f"Empty message: {source_id}")
            context = str(raw.get("contexto_necessário") or "")
            primary = labels(raw.get("intenção_principal"))
            secondary = labels(raw.get("intenções_secundárias"))
            signals = labels(raw.get("riscos"))
            status = str(raw.get("status_revisao") or "").lower()
            invalid = (len(primary) != 1 or primary[0] not in intents or not signals
                       or not set(signals) <= risks or not set(secondary) <= intents)
            if "none" in signals and len(signals) > 1:
                raise ValueError(f"none must be exclusive: {source_id}")
            minimized, minimized_context = review_text(original), review_text(context)
            identifiers.update(minimized.identifier_counts)
            identifiers.update(minimized_context.identifier_counts)
            privacy_flags.update(minimized.flags)
            privacy_flags.update(minimized_context.flags)
            partition = choose_partition(family, raw, meta)
            reasons = []
            if invalid or "duvida" in status or "dúvida" in status or not status.startswith("revisado"):
                reasons.append("unresolved_annotation")
            if normalized_key(original) in historical:
                reasons.append("historical_frozen_overlap")
            group = (raw.get("leakage_group_id") or meta.get("leakage_group_id")
                     or raw.get("split_group_id") or raw.get("grupo_independencia")
                     or meta.get("independence_group_id") or raw.get("grupo_cenario") or source_id)
            synthetic = family == "rare_synthetic" or bool(meta.get("is_synthetic", False))
            rows.append({
                "id": f"{family}:{source_id}", "source_id": source_id, "source_family": family,
                "text": minimized.minimized_text, "context": minimized_context.minimized_text,
                "input": model_text(minimized.minimized_text, minimized_context.minimized_text),
                "label": primary[0] if len(primary) == 1 else None,
                "secondary_intents": secondary, "risks": signals,
                "group_id": f"{family}:{group}", "source_split": raw.get("split"),
                "partition": partition, "is_synthetic": synthetic,
                "review_status": status, "human_gold": status == "revisado_humano",
                "source_text_sha256": hashlib.sha256(original.encode()).hexdigest(),
                "input_fingerprint": input_fingerprint(minimized.minimized_text, minimized_context.minimized_text),
                "privacy_flags": sorted(set(minimized.flags + minimized_context.flags)),
                "source_rights": "not_certified_by_project_owner_authorization",
                "scope": "private_research_only_not_production_or_lm_training",
                "quarantine_reasons": reasons,
            })
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate release IDs")
    # Evaluation wins conflicts: remove training/development neighbors, never move test to train.
    priority = {"train": 0, "validation": 1, "test": 2,
                "external_synthetic": 3, "external_human_language": 4}
    exact, groups = defaultdict(list), defaultdict(list)
    for row in rows:
        exact[row["input_fingerprint"]].append(row)
        groups[row["group_id"]].append(row)
    collisions = Counter()
    for kind, clusters in (("exact_input", exact), ("source_group", groups)):
        for cluster in clusters.values():
            partitions = {r["partition"] for r in cluster}
            if len(partitions) > 1:
                keep = max(partitions, key=priority.get)
                for row in cluster:
                    if row["partition"] != keep:
                        row["quarantine_reasons"].append(f"cross_partition_{kind}")
                        collisions[kind] += 1
            if kind == "exact_input" and len(cluster) > 1:
                candidates = [r for r in cluster if not r["quarantine_reasons"]]
                if len({(r["label"], tuple(sorted(r["risks"]))) for r in candidates}) > 1:
                    for row in candidates:
                        row["quarantine_reasons"].append("conflicting_duplicate_annotations")
                else:
                    for row in sorted(candidates, key=lambda r: r["id"])[1:]:
                        row["quarantine_reasons"].append("duplicate_input")
    pairs = close_duplicate_pairs([{"id_mensagem": r["id"], "texto_original": r["input"]}
                                  for r in rows if len(r["input"].split()) >= 12])
    index = {r["id"]: r for r in rows}
    for left, right in pairs:
        a, b = index[left], index[right]
        if a["partition"] != b["partition"]:
            lower = a if priority[a["partition"]] < priority[b["partition"]] else b
            lower["quarantine_reasons"].append("cross_partition_near_duplicate")
            collisions["near_duplicate"] += 1
    for row in rows:
        row["quarantine_reasons"] = sorted(set(row["quarantine_reasons"]))
        if row["quarantine_reasons"]:
            row["partition_before_quarantine"] = row["partition"]
            row["partition"] = "quarantine"
    validate_isolation(rows)
    private = output / "private"
    write_jsonl(private / "records.jsonl", rows)
    for partition in sorted({r["partition"] for r in rows}):
        write_jsonl(private / f"{partition}.jsonl", [r for r in rows if r["partition"] == partition])
    write_json(output / "taxonomy.json", taxonomy)
    coverage = {}
    for partition in sorted({r["partition"] for r in rows}):
        subset = [r for r in rows if r["partition"] == partition]
        coverage[partition] = {"records": len(subset),
            "intents": dict(Counter(r["label"] for r in subset)),
            "risks": dict(Counter(v for r in subset for v in r["risks"])),
            "synthetic": sum(r["is_synthetic"] for r in subset)}
    checksums["taxonomia_revisada.json"] = file_sha256(taxonomy_path)
    manifest = {"dataset_version": VERSION, "total_imported": len(rows),
        "taxonomy_counts": {"intents": len(intents), "risks": len(risks), "entities_declared": len(taxonomy["entities"])},
        "source_files_sha256": checksums, "source_authority": "edited_workbooks_Revisao_columns_B_to_G",
        "coverage": coverage, "collision_counts": dict(collisions),
        "quarantine_reasons": dict(Counter(v for r in rows for v in r["quarantine_reasons"])),
        "privacy": {"identifiers_minimized": dict(identifiers), "flags": dict(privacy_flags),
                    "anonymization_verified": False, "public_redistribution_allowed": False,
                    "one_drive_sync_prevented": False, "raw_text_sent_to_api": False},
        "evaluation": "AI-reviewed reference labels, not independently human-validated gold",
        "split_policy": "original_public_splits; survey_reserved; seed_and_derivatives_reserved; rare_batch_train_only",
        "near_duplicate_method": "bounded four-word shingle Jaccard >=0.8; not semantic proof",
        "responses": "not imported as verified answers or language-model corpus",
        "protected_fingerprints": protected,
        "files": {p.relative_to(output).as_posix(): file_sha256(p) for p in private.glob("*.jsonl")}}
    if frozen_fingerprints(ai_root) != protected:
        raise ValueError("Historical frozen files changed")
    write_json(output / "manifest.json", manifest)
    return manifest


def validate_isolation(rows):
    used = [r for r in rows if r["partition"] != "quarantine"]
    for field in ("id", "input_fingerprint", "group_id"):
        seen = defaultdict(set)
        for row in used:
            # Seed source and seed-derived synthetic holdouts are both evaluation, never train.
            partition = "external" if row["partition"].startswith("external_") else row["partition"]
            seen[row[field]].add(partition)
        if any(len(parts) > 1 for parts in seen.values()):
            raise ValueError(f"Cross-partition leakage: {field}")


def load_partition(ai_root, partition):
    output = ai_root / f"data/releases/{VERSION}"
    manifest = json.loads((output / "manifest.json").read_text("utf-8"))
    name = f"private/{partition}.jsonl"
    expected = manifest["files"].get(name, manifest["files"].get(name.replace("/", "\\")))
    if file_sha256(output / name) != expected:
        raise ValueError("Release partition checksum mismatch")
    return read_jsonl(output / name)

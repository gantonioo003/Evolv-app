"""Action development data v1.9; preserves every parent row and reserved file."""
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
from evolv_nlp.real_data import normalized_key
from evolv_nlp.privacy import review_text
from evolv_nlp.review_release import validate_isolation

VERSION = "1.9.0"
RESERVED = ("test", "external_human_language", "quarantine")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_rows(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def load_partition(ai_root, partition):
    """Explicit development loader for the next training phase; no test access."""
    if partition not in {"train", "validation", "validation_legacy", "train_actions_synthetic", "validation_actions_synthetic"}:
        raise ValueError("Only development partitions are allowed here")
    root = ai_root / f"data/releases/{VERSION}"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    name = f"private/{partition}.jsonl"
    if sha(root / name) != manifest["files"][name]:
        raise ValueError("Action release partition checksum mismatch")
    return read_rows(root / name)


def read_bank(path):
    spec = importlib.util.spec_from_file_location("evolv_authored_action_examples", path)
    bank = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bank)
    return bank


def authored_rows(path):
    bank = read_bank(path)
    records = []
    for family, mapping in (("action", bank.BANK), ("contrast", bank.CONTRAST)):
        for label, partitions in mapping.items():
            for partition, block in zip(("train", "validation"), partitions):
                for number, line in enumerate(filter(None, (s.strip() for s in block.splitlines())), 1):
                    parts = line.split(" || ")
                    if len(parts) not in (1, 2):
                        raise ValueError("Invalid scenario separator")
                    context, text = ("", parts[0]) if len(parts) == 1 else parts
                    if review_text(text).identifier_counts or review_text(context).identifier_counts:
                        raise ValueError("Unexpected identifiers in project-authored data")
                    rid = f"action_v1:{family}:{label}:{partition}:{number:02d}"
                    model_input = f"Contexto anterior: {context}\nMensagem atual: {text}" if context else text
                    records.append({"id": rid, "group_id": rid + ":scenario", "partition": partition,
                        "text": text, "context": context, "input": model_input,
                        "input_fingerprint": hashlib.sha256(normalized_key(model_input).encode()).hexdigest(),
                        "label": label, "secondary_intents": [], "risks": ["none"],
                        "source_family": "project_authored_actions_v1", "source_id": rid,
                        "source_split": partition, "source_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "source_rights": "project_authored_synthetic", "is_synthetic": True,
                        "human_gold": False, "review_status": "assistant_reviewed_synthetic",
                        "scope": "nlu_development_not_production_clearance_or_automatic_lm_training",
                        "privacy_flags": [], "quarantine_reasons": [],
                        "annotation": {"authoring": "individually_authored_scenarios_no_cartesian_augmentation",
                            "is_execution_authorization": False,
                            "pending_action_requires_backend_identity": label in {
                                "confirm_planner_action", "reject_planner_action", "defer_planner_action", "undo_planner_action"}}})
    return records


def cross_split_collisions(old, additions, threshold=0.92):
    """Lexical check only: never use predictions or answers to select labels."""
    all_rows = old + additions
    keys = [normalized_key(r["input"]) for r in all_rows]
    normalized_partition = lambda r: "external" if r["partition"].startswith("external_") else r["partition"]
    exact = defaultdict(list)
    for i, key in enumerate(keys):
        exact[key].append(i)
    reasons = defaultdict(list)
    start = len(old)
    for i in range(start, len(all_rows)):
        for j in exact[keys[i]]:
            if i == j:
                continue
            # New records must be novel, including relative to parent train.
            if j < start or normalized_partition(all_rows[i]) != normalized_partition(all_rows[j]) or j < i:
                reasons[all_rows[i]["id"]].append({"kind": "exact_duplicate", "other_id": all_rows[j]["id"]})
    # A single TF-IDF index is a deduplication diagnostic, never a fitted feature/model artifact.
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, max_features=60000)
    matrix = vec.fit_transform(keys)
    neighbors = NearestNeighbors(metric="cosine", algorithm="brute").fit(matrix)
    distances, indices = neighbors.radius_neighbors(matrix[start:], radius=1-threshold+1e-12, sort_results=True)
    for local, (ds, js) in enumerate(zip(distances, indices)):
        i = start + local
        if len(keys[i].split()) < 5:
            continue
        for distance, j in zip(ds, js):
            if i == j or 1 - distance < threshold:
                continue
            if j < start or normalized_partition(all_rows[i]) != normalized_partition(all_rows[j]):
                reasons[all_rows[i]["id"]].append({"kind": "near_duplicate", "similarity": round(float(1-distance), 6),
                                                  "other_id": all_rows[j]["id"]})
    return dict(reasons)


def build(ai_root: Path):
    parent = ai_root / "data/releases/1.8.0"
    output = ai_root / f"data/releases/{VERSION}"
    if output.exists():
        raise FileExistsError("Finalized release: choose a new version")
    source = ai_root / "data/action_authoring/v1/examples.py"
    files = [*parent.glob("private/*.jsonl"), parent / "manifest.json", parent / "taxonomy.json"]
    before = {p.relative_to(parent).as_posix(): sha(p) for p in files}
    manifest = json.loads((parent / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if sha(parent / name) != expected:
            raise ValueError("Parent release hash mismatch")
    old = read_rows(parent / "private/records.jsonl")
    candidates = authored_rows(source)
    intents = {r["id"] for r in json.loads((parent / "taxonomy.json").read_text(encoding="utf-8"))["intents"]}
    if any(r["label"] not in intents for r in candidates):
        raise ValueError("Unknown label")
    # Reserved records are inspected only by automated fingerprint/similarity checks,
    # not by an annotator, evaluator or a predictor. Their bytes are never changed.
    exclusions = cross_split_collisions(old, candidates)
    additions = [r for r in candidates if r["id"] not in exclusions]
    action_labels = set(read_bank(source).BANK)
    for label in action_labels:
        val = [r for r in additions if r["label"] == label and r["partition"] == "validation"]
        if len(val) < 5:
            raise ValueError(f"Insufficient novel synthetic validation: {label} ({len(val)}); revise authoring, not checks")
    combined = old + additions
    validate_isolation(combined)
    if len({r["id"] for r in combined}) != len(combined):
        raise ValueError("Duplicate record identifiers")
    for path in files:
        if sha(path) != before[path.relative_to(parent).as_posix()]:
            raise ValueError("Parent changed while preparing release")
    # All checks complete before publishing; no existing dataset/model is overwritten.
    private = output / "private"
    private.mkdir(parents=True)
    for part in RESERVED:
        shutil.copyfile(parent / f"private/{part}.jsonl", private / f"{part}.jsonl")
    shutil.copyfile(parent / "taxonomy.json", output / "taxonomy.json")
    write_rows(private / "records.jsonl", combined)
    for part in ("train", "validation"):
        write_rows(private / f"{part}.jsonl", [r for r in combined if r["partition"] == part])
    write_rows(private / "validation_legacy.jsonl", [r for r in old if r["partition"] == "validation"])
    write_rows(private / "train_actions_synthetic.jsonl", [r for r in additions if r["partition"] == "train"])
    write_rows(private / "validation_actions_synthetic.jsonl", [r for r in additions if r["partition"] == "validation"])
    coverage = {part: {"records": sum(r["partition"] == part for r in combined),
        "intents": dict(Counter(r["label"] for r in combined if r["partition"] == part))}
        for part in sorted({r["partition"] for r in combined})}
    report = {"phase": "7.07.2", "dataset_version": VERSION, "parent_version": "1.8.0",
        "parent_manifest_sha256": before["manifest.json"], "authoring_sha256": sha(source),
        "original_rows_preserved": len(old), "added_records": len(additions),
        "candidates": len(candidates), "excluded_candidates": exclusions,
        "total_imported": len(combined), "coverage": coverage,
        "added_coverage": {part: dict(Counter(r["label"] for r in additions if r["partition"] == part))
                           for part in ("train", "validation")},
        "reserved_byte_identical": {part: before[f"private/{part}.jsonl"] for part in RESERVED},
        "parent_files_sha256_unchanged": before,
        "validation_policy": {"legacy_retained": True, "synthetic_stratum_separate": True,
            "report_legacy_and_synthetic_metrics_separately": True,
            "not_independent_human_gold": True, "same_assistant_author_for_both_partitions": True,
            "synthetic_support_does_not_certify_real_world_action_accuracy": True},
        "quality": {"cross_partition_ids_fingerprints_groups_checked": True,
            "near_duplicate_threshold": 0.92, "near_duplicate_metric": "char_wb TF-IDF cosine",
            "near_neighbor_limit": None, "radius_search_all_neighbors": True, "labels_not_changed_by_similarity": True,
            "test_not_used_for_training_or_metrics": True},
        "models_retrained": False, "runtime_or_confidence_policy_changed": False,
        "privacy": {"new_samples_are_project_authored_synthetic": True,
            "automatic_lm_training": False, "parent_external_rights_not_changed": True},
        "files": {p.relative_to(output).as_posix(): sha(p) for p in private.glob("*.jsonl")}}
    for part in RESERVED:
        assert sha(private / f"{part}.jsonl") == report["reserved_byte_identical"][part]
    (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report

from __future__ import annotations

import json
import platform
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from evolv_nlp.baseline import assert_compatible_runtime, load_trusted_model
from evolv_nlp.baseline_v11 import build_classifier
from evolv_nlp.context_data import DATASET_VERSION, frozen_fingerprints
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.privacy import training_permission
from evolv_nlp.real_data import normalized_key, write_json, write_jsonl
from evolv_nlp.training_v12 import TASKS, FILES, confidence_policy, metrics, predictions

BASELINE_VERSION = "1.3.0"
PROFILES = ("word_char_c1", "word_char_c2", "word_char_c4", "wide_word_char_c2", "word_emphasis_c2", "svc_linear_c1")


def taxonomy(ai_root: Path) -> dict[str, dict[str, dict]]:
    result = {}
    for collection in ("intents", "risks", "entities"):
        payload = json.loads((ai_root / f"data/taxonomy/{collection}.v1.json").read_text("utf-8"))
        result[collection] = {r["id"]: r for r in payload[collection]}
    for name in ("expansion.v1.1.json", "expansion.v1.2.json"):
        extension = json.loads((ai_root / "data/taxonomy" / name).read_text("utf-8"))
        for collection in result:
            for row in extension[collection]:
                if row["id"] in result[collection]:
                    raise ValueError("Categoria duplicada")
                result[collection][row["id"]] = row
    return result


def parent_labels(values, definitions):
    output = []
    for label in values:
        visited = set()
        while definitions[label].get("parent"):
            if label in visited:
                raise ValueError("Ciclo nos pais da taxonomia")
            visited.add(label)
            label = definitions[label]["parent"]
        output.append(label)
    return output


def classifier(profile):
    if profile != "word_emphasis_c2":
        return build_classifier(profile)
    features = FeatureUnion([
        ("word", TfidfVectorizer(strip_accents="unicode", ngram_range=(1, 2), sublinear_tf=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", strip_accents="unicode", ngram_range=(3, 5), sublinear_tf=True)),
    ], transformer_weights={"word": 2.0, "char": 0.5})
    return Pipeline([("features", features), ("classifier", LogisticRegression(
        C=2.0, class_weight="balanced", max_iter=4000, random_state=42, tol=1e-5))])


def prepare(ai_root: Path) -> dict:
    release = ai_root / f"data/releases/{DATASET_VERSION}"
    authored_old = json.loads((ai_root / "data/source/expansion_ptbr.v1.json").read_text("utf-8"))
    authored = json.loads((ai_root / "data/source/context_expansion.v1.json").read_text("utf-8"))
    definitions = taxonomy(ai_root)
    summary = {}
    for task, filename in TASKS.items():
        collection = "intents" if task == "intent_classification" else "risks"
        partitions = {}
        for split in ("train", "validation", "test"):
            base_path = ai_root / f"data/releases/1.3.0/splits/{split}/{filename}"
            # Test is referenced later for reporting, not copied or inspected during preparation.
            partitions[split] = read_jsonl(base_path) if split != "test" else []
            pools = [("previous_authored", authored_old)] if split != "test" else []
            pools.append(("context_authored", authored))
            for origin, pool in pools:
                for label, samples in pool.get(collection, {}).items():
                    if label not in definitions[collection]:
                        raise ValueError("Rotulo desconhecido")
                    for i, text in enumerate(samples.get(split, [])):
                        partitions[split].append({"id": f"v15-{origin}-{collection}-{label}-{split}-{i}",
                            "text": text, "label": label, "task": task,
                            "family": f"v15-{origin}-{collection}-{label}-{split}-{i}",
                            "provenance": "project_authored_synthetic", "review_status": "assistant_reviewed_synthetic"})
            if split != "test" and collection == "risks":
                for i, text in enumerate(authored_old.get("risk_hard_negatives", {}).get(split, [])):
                    partitions[split].append({"id": f"v15-neg-{split}-{i}", "text": text, "label": "none", "task": task,
                        "provenance": "project_authored_synthetic", "review_status": "assistant_reviewed_synthetic"})
            unique = {}
            for row in partitions[split]:
                key = normalized_key(row["text"])
                if key in unique and unique[key]["label"] != row["label"]:
                    raise ValueError("Mesmo texto com rotulos conflitantes")
                unique[key] = row
            partitions[split] = list(unique.values())
        keys = {split: {normalized_key(r["text"]) for r in rows} for split, rows in partitions.items()}
        if any(keys[a] & keys[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))):
            raise ValueError("Vazamento entre particoes")
        if {r["label"] for r in partitions["train"]} != set(definitions[collection]):
            raise ValueError("Classe sem treino")
        # Author-provided test sentences are frozen before fitting, and never used for selection.
        for split, rows in partitions.items():
            write_jsonl(release / f"splits/{split}/{filename}", rows)
        summary[task] = {split: len(rows) for split, rows in partitions.items()}
        summary[task]["train_labels"] = dict(Counter(r["label"] for r in partitions["train"]))
    write_json(release / "training_manifest.json", {"tasks": summary, "raw_external_texts_used": False,
               "external_answers_used": False, "new_labels_review": "assistant_authored_not_human_gold"})
    return summary


def fit_all(ai_root: Path) -> dict:
    output = ai_root / f"artifacts/baseline/{BASELINE_VERSION}"
    if (output / "manifest.json").exists():
        raise ValueError("Experimento finalizado; nunca sobrescrever")
    frozen = frozen_fingerprints(ai_root)
    prepared = prepare(ai_root)
    release = ai_root / f"data/releases/{DATASET_VERSION}"
    definitions = taxonomy(ai_root)
    output.mkdir(parents=True, exist_ok=True)
    results, artifacts, policies = {}, {}, {}
    for task, filename in TASKS.items():
        collection = "intents" if task == "intent_classification" else "risks"
        train = read_jsonl(release / f"splits/train/{filename}")
        validation = read_jsonl(release / f"splits/validation/{filename}")
        legacy_validation = read_jsonl(ai_root / f"data/releases/1.3.0/splits/validation/{filename}")
        new_validation = [r for r in validation if r["id"].startswith("v15-")]
        trials, fitted = {}, {}
        for profile in PROFILES:
            model = classifier(profile)
            model.fit([r["text"] for r in train], [r["label"] for r in train])
            fitted[profile] = model
            old_score = metrics([r["label"] for r in legacy_validation],
                parent_labels(predictions(model, [r["text"] for r in legacy_validation]), definitions[collection]))
            extra_score = metrics([r["label"] for r in new_validation], predictions(model, [r["text"] for r in new_validation]))
            trials[profile] = {"historical_validation_parent_labels": old_score,
                              "new_validation": extra_score,
                              "selection_score": round(0.8 * old_score["macro_f1"] + 0.2 * extra_score["macro_f1"], 6)}
            print(f"{task}: {profile}: {trials[profile]['selection_score']}", flush=True)
        selected = max(PROFILES, key=lambda p: (trials[p]["selection_score"], -PROFILES.index(p)))
        model = fitted[selected]
        policy = confidence_policy([r["label"] for r in validation], model, [r["text"] for r in validation])
        policies[task] = policy
        path = output / FILES[task]
        joblib.dump(model, path, compress=3)
        artifacts[task] = {"file": path.name, "sha256": file_sha256(path)}
        # Selection is over. Open old test only for the final report; do not tune again.
        old_test = read_jsonl(ai_root / f"data/releases/1.3.0/splits/test/{filename}")
        new_test = read_jsonl(release / f"splits/test/{filename}")
        partitions = {"historical_validation": legacy_validation, "historical_test": old_test, "new_authored_test": new_test}
        comparison = {}
        for name, rows in partitions.items():
            texts, labels = [r["text"] for r in rows], [r["label"] for r in rows]
            comparison[name] = {"new_1_3_native_labels": metrics(labels, predictions(model, texts)),
                "new_1_3_parent_labels": metrics(parent_labels(labels, definitions[collection]), parent_labels(predictions(model, texts), definitions[collection]))}
            for old_version in ("1.1.0", "1.2.0"):
                previous_root = ai_root / "artifacts/baseline" / old_version
                previous_manifest = json.loads((previous_root / "manifest.json").read_text("utf-8"))
                assert_compatible_runtime(previous_manifest["dependencies"])
                metadata = previous_manifest["model_artifacts"][task]
                previous = load_trusted_model(previous_root / metadata["file"], metadata["sha256"])
                comparison[name][f"previous_{old_version}_parent_labels"] = metrics(
                    parent_labels(labels, definitions[collection]), parent_labels(predictions(previous, texts), definitions[collection]))
        results[task] = {"selected_profile": selected, "classes": len(model.classes_), "training_rows": len(train),
                         "validation_trials": trials, "comparison": comparison,
                         "test_used_for_selection": False}
    if frozen != frozen_fingerprints(ai_root):
        raise ValueError("Arquivo historico/congelado foi alterado")
    write_json(output / "metrics.json", {"version": BASELINE_VERSION, "tasks": results,
        "limitations": ["Historical test was already observed in prior phases; not a new independent estimate.",
                        "New test is small and assistant-authored, not real human gold.",
                        "Risk classifier is single-label; independent rules may return multiple signals.",
                        "No original external messages or comments were used for training."]})
    write_json(output / "confidence_policy.json", policies)
    write_json(release / "frozen_fingerprints.json", frozen)
    fingerprints = {str(p.relative_to(ai_root)): file_sha256(p)
        for root in (release / "splits", ai_root / "data/taxonomy", ai_root / "data/source")
        for p in root.rglob("*.json*")}
    for name in ("training_v13.py", "privacy.py", "entities_v13.py", "risk_rules_v13.py", "response_policy.py", "pipeline_v12.py"):
        fingerprints[f"src/evolv_nlp/{name}"] = file_sha256(ai_root / "src/evolv_nlp" / name)
    manifest = {"artifact_version": BASELINE_VERSION, "dataset_version": DATASET_VERSION,
        "status": "experimental_not_default", "model_artifacts": artifacts, "prepared_data": prepared,
        "source_files": fingerprints, "default_changed": False, "raw_external_training_allowed": False,
        "selection": "Six declared profiles; 80% historical validation and 20% new authored validation macro F1.",
        "reports": {"metrics": {"file": "metrics.json", "sha256": file_sha256(output / "metrics.json")},
                    "policy": {"file": "confidence_policy.json", "sha256": file_sha256(output / "confidence_policy.json")}},
        "dependencies": {"python": platform.python_version(), **{name: version(name) for name in ("numpy", "scipy", "scikit-learn", "joblib")}}}
    write_json(output / "manifest.json", manifest)
    return manifest

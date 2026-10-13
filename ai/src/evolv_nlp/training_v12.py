from __future__ import annotations

import json
import platform
import re
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score

from evolv_nlp.baseline import load_trusted_model
from evolv_nlp.baseline_v11 import build_classifier
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.real_data import DATASET_VERSION, PRIVATE_PATTERN, load_reviews, normalized_key, taxonomy_labels, write_json, write_jsonl

BASELINE_VERSION = "1.2.0"
PROFILES = ("word_char_c1", "word_char_c2", "char_only_c4", "svc_linear_c1")
TASKS = {"intent_classification": "intent_examples.jsonl", "risk_classification": "risk_examples.jsonl"}
FILES = {"intent_classification": "intent_classifier.joblib", "risk_classification": "risk_classifier.joblib"}


def weak_intent(text: str) -> str | None:
    text = normalized_key(text)
    patterns = (
        ("ask_pain_guidance", r"\b(?:dor|dores|lesao|canelite|dormencia|formigamento|machuquei)\b"),
        ("ask_training_meal_timing", r"(?:comer|alimentar|refeicao|cafe da manha|lanche).*(?:antes|apos|depois|manha|noite|treino)|(?:pre|pos) treino.*(?:comida|refeicao|comer|alimentacao)"),
        ("ask_training_program_feedback", r"(?:avalie|avaliem|avalia|avaliacao|opiniao).*(?:treino|ficha|rotina|divisao)|(?:treino|ficha|rotina).*avaliacao"),
        ("ask_sports_conditioning", r"\b(?:volei|voleibol|tenis|jiu jitsu|muay thai|futsal|futebol|basquete|natacao|ciclismo)\b.*(?:treino|musculacao|academia|forca|preparacao)|(?:treino|musculacao|academia|forca|preparacao).*\b(?:volei|tenis|jiu jitsu|muay thai|futebol|basquete|natacao|ciclismo)\b"),
        ("ask_supplements", r"\b(?:whey|creatina|bcaa|albumina|beta alanina|suplemento|suplementacao|hipercalorico)\b"),
        ("ask_weight_management", r"\b(?:bulking|cutting|recomposicao|emagrecer|emagrecimento|deficit|superavit)\b"),
        ("ask_recovery", r"\b(?:sono|dormir|insonia|recuperacao|overtraining|semana de descanso)\b"),
        ("ask_exercise_execution", r"\b(?:execucao|pegada|amplitude|tecnica)\b.*\b(?:supino|rosca|agachamento|terra|remada|barra|flexao)\b|\b(?:supino|rosca|agachamento|terra|remada|barra|flexao)\b.*\b(?:execucao|pegada|amplitude|tecnica)\b"),
        ("analyze_progress", r"\b(?:estagnacao|estagnado|nao evoluo|sem progresso|carga nao sobe)\b"),
        ("ask_cooking_guidance", r"\b(?:receita|cozinhar|cozinhando|congelar|marmita)\b"),
        ("motivation_support", r"\b(?:motivacao|disciplina|desmotivado|desanimo)\b"),
    )
    matches = [label for label, pattern in patterns if re.search(pattern, text)]
    # Multi-topic forum titles stay in the review queue instead of being forced into one class.
    return matches[0] if len(matches) == 1 else None


def metrics(expected: list[str], predicted: list[str]) -> dict[str, Any]:
    labels = sorted(set(expected) | set(predicted))
    return {
        "rows": len(expected), "accuracy": round(float(accuracy_score(expected, predicted)), 6),
        "macro_precision": round(float(precision_score(expected, predicted, average="macro", zero_division=0)), 6),
        "macro_recall": round(float(recall_score(expected, predicted, average="macro", zero_division=0)), 6),
        "macro_f1": round(float(f1_score(expected, predicted, average="macro", zero_division=0)), 6),
        "labels": labels, "confusion_matrix": confusion_matrix(expected, predicted, labels=labels).tolist(),
        "per_class": classification_report(expected, predicted, labels=labels, output_dict=True, zero_division=0),
    }


def predictions(model: Any, texts: list[str]) -> list[str]:
    # Same decision rule as the operational classify(), including historical SVC artifacts.
    probabilities = model.predict_proba(texts)
    return [str(model.classes_[i]) for i in np.argmax(probabilities, axis=1)]


def parent_maps(ai_root: Path) -> dict[str, dict[str, str]]:
    extension = json.loads((ai_root / "data/taxonomy/expansion.v1.1.json").read_text("utf-8"))
    return {task: {r["id"]: r["parent"] for r in extension[collection]}
            for task, collection in (("intent_classification", "intents"), ("risk_classification", "risks"))}


def augment_train(text: str) -> list[str]:
    return [text, f"mano {text}", f"{text} explica simples pfv", f"to com uma duvida: {text}"]


def prepare_training(ai_root: Path, use_weak_web: bool = False) -> dict[str, Any]:
    from evolv_nlp.risk_rules_v12 import detect_risks

    release = ai_root / "data/releases/1.4.0"
    external = ai_root / "data/external_private/ptbr-10000-1.0.0"
    raw = read_jsonl(external / "mensagens.jsonl")
    queue = {r["id"]: r for r in read_jsonl(external / "review_queue.jsonl")}
    label_sets = taxonomy_labels(ai_root)
    reviews = load_reviews(release / "assistant_reviews.json", raw, label_sets)
    index = {r["id_mensagem"]: r for r in raw}
    reserved_groups = {index[r["id"]]["split_group_id"] for r in reviews}
    authored = json.loads((ai_root / "data/source/expansion_ptbr.v1.json").read_text("utf-8"))
    summary: dict[str, Any] = {"weak_web_enabled": use_weak_web, "tasks": {}}
    for task, filename in TASKS.items():
        collection = "intents" if task == "intent_classification" else "risks"
        splits: dict[str, list[dict]] = {}
        for split in ("train", "validation"):
            base = read_jsonl(ai_root / f"data/releases/1.3.0/splits/{split}/{filename}")
            splits[split] = [{**r, "dataset_version": DATASET_VERSION, "sample_weight": 1.0,
                              "provenance": "legacy_project_dataset"} for r in base]
            for label, partition in authored[collection].items():
                for i, text in enumerate(partition[split]):
                    variants = augment_train(text) if split == "train" else [text]
                    for variant, value in enumerate(variants):
                        splits[split].append({"id": f"v14-{task}-{label}-{split}-{i}-{variant}",
                                              "task": task, "dataset_version": DATASET_VERSION,
                                              "text": value, "label": label, "sample_weight": 1.0,
                                              "family": f"v14-{task}-{label}-{split}-{i}",
                                              "provenance": "project_authored_synthetic"})
            if collection == "risks":
                for i, text in enumerate(authored["risk_hard_negatives"][split]):
                    splits[split].append({"id": f"v14-risk-negative-{split}-{i}", "task": task,
                                          "dataset_version": DATASET_VERSION, "text": text,
                                          "label": "none", "sample_weight": 1.0,
                                          "provenance": "project_authored_synthetic"})
            write_jsonl(release / f"splits/{split}/{filename}", splits[split])
        weak: list[dict] = []
        cap: Counter[str] = Counter()
        seen = {normalized_key(r["text"]) for part in splits.values() for r in part}
        if use_weak_web:
            for row in sorted(raw, key=lambda r: r["id_mensagem"]):
                info = queue[row["id_mensagem"]]
                if row["split"] != "train" or row["split_group_id"] in reserved_groups:
                    continue
                if any(flag != "missing_body_context" for flag in info["flags"]):
                    continue
                text = row.get("titulo_original") or row["texto_original"]
                if not 12 <= len(text) <= 500 or PRIVATE_PATTERN.search(text):
                    continue
                key = normalized_key(text)
                if key in seen:
                    continue
                if collection == "intents":
                    label = weak_intent(text)
                else:
                    hits = detect_risks(text)
                    found = list(hits.risks)
                    label = found[0] if len(found) == 1 else None
                if not label or label not in label_sets[collection] or cap[label] >= 160:
                    continue
                cap[label] += 1
                seen.add(key)
                weak.append({"id": row["id_mensagem"], "task": task, "dataset_version": DATASET_VERSION,
                             "text": text, "label": label, "sample_weight": 0.15,
                             "group_id": row["split_group_id"], "source_url": row["source_url"],
                             "provenance": "weak_web_candidate_not_gold", "rights_status": "unverified",
                             "use_restriction": "local_experiment_not_production_or_redistribution"})
        write_jsonl(release / f"local/train/{filename}", weak)
        dev = []
        for review in reviews:
            row = index[review["id"]]
            text = row.get("titulo_original")
            if not text:
                continue
            label = review.get("intent") if collection == "intents" else (
                review["risks"][0] if len(review.get("risks", [])) == 1 else None
            )
            if label:
                dev.append({"id": review["id"], "text": text, "label": label,
                            "review_status": "assistant_reviewed_provisional", "group_id": row["split_group_id"]})
        write_jsonl(release / f"local/development/{filename}", dev)
        summary["tasks"][task] = {"project_train_rows": len(splits["train"]),
                                  "weak_web_train_rows": len(weak), "weak_labels": dict(cap),
                                  "validation_rows": len(splits["validation"]), "real_development_rows": len(dev)}
    write_json(release / "training_manifest.json", summary)
    return summary


def confidence_policy(expected: list[str], model: Any, texts: list[str]) -> dict:
    values = model.predict_proba(texts)
    order = np.argsort(values, axis=1)
    best = values[np.arange(len(values)), order[:, -1]]
    margin = best - values[np.arange(len(values)), order[:, -2]]
    predicted = np.asarray([str(model.classes_[i]) for i in order[:, -1]])
    selected = {"minimum_confidence": 1.01, "minimum_margin": 1.01, "accepted": 0, "precision": None}
    for threshold in (0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95):
        for gap in (0.05, 0.1, 0.2, 0.3):
            mask = (best >= threshold) & (margin >= gap)
            count = int(mask.sum())
            correct = float(np.mean(predicted[mask] == np.asarray(expected)[mask])) if count else 0.0
            if count >= 10 and correct >= 0.9 and count > selected["accepted"]:
                selected = {"minimum_confidence": threshold, "minimum_margin": gap,
                            "accepted": count, "precision": round(correct, 6)}
    return {**selected, "rows": len(expected), "selection_split": "development_only",
            "warning": "Uncalibrated scores and small provisional sample, not a safety guarantee."}


def train_all(ai_root: Path, use_weak_web: bool = False) -> dict:
    output = ai_root / f"artifacts/baseline/{BASELINE_VERSION}"
    if (output / "manifest.json").exists():
        raise ValueError("Experimento ja versionado; nao sobrescrever. Use nova versao.")
    prepared = prepare_training(ai_root, use_weak_web)
    output.mkdir(parents=True, exist_ok=True)
    release = ai_root / "data/releases/1.4.0"
    parents = parent_maps(ai_root)
    reports, artifacts, policies = {}, {}, {}
    historical_manifest = json.loads((ai_root / "artifacts/baseline/1.1.0/manifest.json").read_text("utf-8"))
    for task, filename in TASKS.items():
        train = read_jsonl(release / f"splits/train/{filename}") + read_jsonl(release / f"local/train/{filename}")
        validation = read_jsonl(release / f"splits/validation/{filename}")
        dev = read_jsonl(release / f"local/development/{filename}")
        project_texts, project_y = [r["text"] for r in validation], [r["label"] for r in validation]
        dev_texts, dev_y = [r["text"] for r in dev], [r["label"] for r in dev]
        candidates, fitted = {}, {}
        for profile in PROFILES:
            model = build_classifier(profile)
            model.fit([r["text"] for r in train], [r["label"] for r in train],
                      classifier__sample_weight=np.asarray([r["sample_weight"] for r in train]))
            fitted[profile] = model
            project_score = metrics(project_y, predictions(model, project_texts))
            real_score = metrics(dev_y, predictions(model, dev_texts))
            candidates[profile] = {"project_validation": project_score, "real_development_provisional": real_score,
                                   "selection_score": round(0.7 * project_score["macro_f1"] + 0.3 * real_score["macro_f1"], 6)}
        selected = max(PROFILES, key=lambda name: (candidates[name]["selection_score"], -PROFILES.index(name)))
        model = fitted[selected]
        model_path = output / FILES[task]
        joblib.dump(model, model_path, compress=3)
        artifacts[task] = {"file": model_path.name, "sha256": file_sha256(model_path)}
        previous_artifact = historical_manifest["model_artifacts"][task]
        previous = load_trusted_model(ai_root / "artifacts/baseline/1.1.0" / previous_artifact["file"], previous_artifact["sha256"])
        old_project = read_jsonl(ai_root / f"data/releases/1.3.0/splits/validation/{filename}")
        old_texts, old_y = [r["text"] for r in old_project], [r["label"] for r in old_project]
        collapse = lambda values: [parents[task].get(label, label) for label in values]
        policies[task] = confidence_policy(project_y + dev_y, model, project_texts + dev_texts)
        reports[task] = {"selected_profile": selected, "classes": len(model.classes_), "train_rows": len(train),
                         "candidates": candidates,
                         "same_legacy_validation": {
                             "previous_1_1": metrics(old_y, predictions(previous, old_texts)),
                             "new_1_2_parent_collapsed": metrics(old_y, collapse(predictions(model, old_texts)))},
                         "same_real_development_parent_labels": {
                             "previous_1_1": metrics(collapse(dev_y), predictions(previous, dev_texts)),
                             "new_1_2": metrics(collapse(dev_y), collapse(predictions(model, dev_texts)))},
                         "test_accessed": False}
    write_json(output / "metrics.json", {"baseline_version": BASELINE_VERSION, "tasks": reports,
               "warning": "Development scores used for selection. Web labels weak; reviewed titles provisional. No new final test opened."})
    write_json(output / "confidence_policy.json", policies)
    fingerprints = {str(path.relative_to(ai_root)): file_sha256(path)
                    for root in (release / "splits", release / "local", ai_root / "data/taxonomy")
                    for path in root.rglob("*.json*")}
    for relative in (
        "data/releases/1.4.0/assistant_reviews.json",
        "data/releases/1.4.0/external_manifest.json",
        "data/releases/1.4.0/training_manifest.json",
        "data/source/expansion_ptbr.v1.json",
        "src/evolv_nlp/training_v12.py",
        "src/evolv_nlp/real_data.py",
        "src/evolv_nlp/risk_rules_v12.py",
        "src/evolv_nlp/entities_v12.py",
        "src/evolv_nlp/baseline_v11.py",
        "src/evolv_nlp/pipeline_v12.py",
    ):
        fingerprints[relative] = file_sha256(ai_root / relative)
    manifest = {"artifact_version": BASELINE_VERSION, "dataset_version": DATASET_VERSION,
                "status": "experimental_not_default_pipeline", "test_accessed": False,
                "activation_requires": ["human_review", "rights_clearance", "independent_holdout", "risk_multilabel_validation"],
                "model_artifacts": artifacts, "prepared_data": prepared, "source_files": fingerprints,
                "selection": "4 declared profiles; 70% project validation macro F1 and 30% provisional real development macro F1.",
                "weak_web_sample_weight": 0.15, "web_answers_used": False,
                "reports": {"metrics": {"file": "metrics.json", "sha256": file_sha256(output / "metrics.json")},
                            "policy": {"file": "confidence_policy.json", "sha256": file_sha256(output / "confidence_policy.json")}},
                "dependencies": {"python": platform.python_version(), **{name: version(name) for name in ("numpy", "scipy", "scikit-learn", "joblib")}}}
    write_json(output / "manifest.json", manifest)
    return manifest

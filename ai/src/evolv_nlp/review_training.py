"""Versioned, validation-selected intent and multilabel-risk experiments."""
from __future__ import annotations

import json
import platform
import time
import warnings
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, precision_recall_fscore_support)
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion
from sklearn.svm import LinearSVC
from threadpoolctl import threadpool_limits

from evolv_nlp.context_data import frozen_fingerprints
from evolv_nlp.dataset import file_sha256
from evolv_nlp.real_data import write_json, write_jsonl
from evolv_nlp.review_release import VERSION as DATA_VERSION, load_partition
from evolv_nlp.semantic_encoder import LocalSemanticEncoder, prepare_encoder
from evolv_nlp.risk_rules_v14 import detect_risks

VERSION = "1.6.0"


def load_hashed_payload(root, metadata):
    root = root.resolve()
    path = (root / metadata["file"]).resolve()
    if not path.is_relative_to(root) or file_sha256(path) != metadata["sha256"]:
        raise ValueError("Model path/hash mismatch before deserialization")
    payload = joblib.load(path)
    if not isinstance(payload, dict) or "classifier" not in payload:
        raise TypeError("Unexpected reviewed/semantic model payload")
    return payload


def lexical_features():
    return FeatureUnion([
        ("word", TfidfVectorizer(strip_accents="unicode", ngram_range=(1, 2),
                                sublinear_tf=True, max_features=25000, dtype=np.float32)),
        ("char", TfidfVectorizer(strip_accents="unicode", analyzer="char_wb", ngram_range=(3, 5),
                                sublinear_tf=True, max_features=25000, dtype=np.float32)),
    ])


def combine(lexical, embeddings, representation):
    if representation == "lexical":
        return lexical
    if representation == "semantic":
        return embeddings
    weight = 1.0 if representation == "hybrid1" else 2.0
    return hstack([lexical, csr_matrix(weight * embeddings)], format="csr")


def intent_metrics(truth, predicted, classes):
    supported = sorted(set(truth))
    return {"records": len(truth), "accuracy": float(accuracy_score(truth, predicted)),
        "macro_f1_supported": float(f1_score(truth, predicted, labels=supported, average="macro", zero_division=0)),
        "macro_f1_all_declared": float(f1_score(truth, predicted, labels=classes, average="macro", zero_division=0)),
        "classes_with_support": len(supported), "declared_classes": len(classes),
        "unsupported_classes": sorted(set(classes) - set(supported)),
        "per_class": classification_report(truth, predicted, labels=classes, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(truth, predicted, labels=classes).tolist(), "matrix_labels": classes}


def risk_matrix(rows, classes):
    return np.asarray([[int(label in r["risks"]) for label in classes] for r in rows], dtype=np.int8)


def risk_metrics(truth, predicted, classes):
    supported = truth.sum(axis=0) > 0
    precision, recall, f1, support = precision_recall_fscore_support(truth, predicted, average=None, zero_division=0)
    return {"records": len(truth), "exact_match_accuracy": float(accuracy_score(truth, predicted)),
        "micro_f1": float(f1_score(truth, predicted, average="micro", zero_division=0)),
        "macro_f1_supported": float(f1[supported].mean()) if supported.any() else 0.0,
        "macro_f1_all_positive_labels": float(f1.mean()),
        "positive_labels_with_support": int(supported.sum()),
        "unsupported_labels": [v for v, present in zip(classes, supported) if not present],
        "none_accuracy": float(accuracy_score(truth.sum(axis=1) == 0, predicted.sum(axis=1) == 0)),
        "per_label": {label: {"precision": float(p), "recall": float(r), "f1": float(f), "support": int(n)}
                      for label, p, r, f, n in zip(classes, precision, recall, f1, support)}}


def choose_thresholds(truth, scores):
    grid = np.arange(0.15, 0.86, 0.05)
    global_threshold = max(grid, key=lambda t: (f1_score(truth, scores >= t, average="macro", zero_division=0), t))
    thresholds = np.full(truth.shape[1], global_threshold)
    for i in range(truth.shape[1]):
        # Very rare validation labels cannot support a separate fitted threshold.
        if truth[:, i].sum() >= 5 and (1 - truth[:, i]).sum() >= 5:
            thresholds[i] = max(grid, key=lambda t: (
                f1_score(truth[:, i], scores[:, i] >= t, zero_division=0), t))
    return thresholds


def intent_scores(classifier, X):
    values = classifier.predict_proba(X) if hasattr(classifier, "predict_proba") else classifier.decision_function(X)
    ordered = np.sort(values, axis=1)
    return values, ordered[:, -1] - ordered[:, -2]


def confidence_policy(truth, predicted, margins):
    candidates = []
    correct = np.asarray(truth) == np.asarray(predicted)
    for threshold in np.unique(np.quantile(margins, np.linspace(0, 0.95, 40))):
        accept = margins >= threshold
        if accept.sum() >= 30 and correct[accept].mean() >= 0.90:
            candidates.append((int(accept.sum()), float(threshold)))
    threshold = max(candidates)[1] if candidates else None
    return {"margin_threshold": threshold, "target_validation_accuracy": 0.90,
            "minimum_validation_support": 30, "is_calibrated_probability": False,
            "production_approved": False, "validation_selected_may_be_optimistic": True}


def transform_payload(payload, texts, encoder):
    vectorizer = payload.get("lexical_features")
    lexical = vectorizer.transform(texts) if vectorizer is not None else None
    embedded = encoder.encode(texts) if payload["representation"] != "lexical" else None
    return combine(lexical, embedded, payload["representation"])


def compact(metrics):
    return {k: v for k, v in metrics.items() if k not in {"per_class", "per_label", "confusion_matrix", "matrix_labels"}}


def old_predict(payload, texts, encoder):
    if isinstance(payload, dict) and "semantic_weight" in payload:
        embedded = encoder.encode(texts)
        weight = payload["semantic_weight"]
        X = embedded if weight is None else hstack([
            payload["lexical_features"].transform(texts), csr_matrix(weight * embedded)], format="csr")
        return payload["classifier"].predict(X)
    return payload.predict(texts)


def train(ai_root: Path):
    output = ai_root / f"artifacts/baseline/{VERSION}"
    if (output / "manifest.json").exists():
        raise ValueError("Finalized model release; do not overwrite")
    output.mkdir(parents=True, exist_ok=True)
    protected = frozen_fingerprints(ai_root)
    data_path = ai_root / f"data/releases/{DATA_VERSION}"
    taxonomy = json.loads((data_path / "taxonomy.json").read_text("utf-8"))
    intent_classes = sorted(item["id"] for item in taxonomy["intents"])
    risk_classes = sorted(item["id"] for item in taxonomy["risks"] if item["id"] != "none")
    train_rows, validation = load_partition(ai_root, "train"), load_partition(ai_root, "validation")
    texts, validation_texts = [r["input"] for r in train_rows], [r["input"] for r in validation]
    train_y, validation_y = np.asarray([r["label"] for r in train_rows]), [r["label"] for r in validation]
    if set(train_y) != set(intent_classes):
        raise ValueError("Some declared intents have no training examples")
    risk_y, risk_validation = risk_matrix(train_rows, risk_classes), risk_matrix(validation, risk_classes)
    if not (risk_y.sum(axis=0) > 0).all():
        raise ValueError("Missing risk training support")
    encoder_path = ai_root / "artifacts/encoders/multilingual-minilm"
    encoder_manifest = prepare_encoder(encoder_path)
    encoder = LocalSemanticEncoder(encoder_path)
    embedded, validation_embedded = encoder.encode(texts), encoder.encode(validation_texts)
    vectorizer = lexical_features()
    lexical, validation_lexical = vectorizer.fit_transform(texts), vectorizer.transform(validation_texts)
    trials, winners = [], {}
    with threadpool_limits(limits=2):
        for representation in ("lexical", "semantic", "hybrid1", "hybrid2"):
            X = combine(lexical, embedded, representation)
            V = combine(validation_lexical, validation_embedded, representation)
            for task in ("intent", "risk"):
                profiles = [("svm", c, balanced) for c in (0.5, 2.0) for balanced in (False, True)] if task == "intent" else []
                profiles += [("lr", c, balanced) for c in ((2.0,) if task == "intent" else (0.5, 2.0))
                             for balanced in (False, True)]
                for kind, c, balanced in profiles:
                    start = time.monotonic()
                    base = (LinearSVC(C=c, class_weight="balanced" if balanced else None,
                                      dual="auto", max_iter=5000, random_state=42) if kind == "svm" else
                            LogisticRegression(C=c, class_weight="balanced" if balanced else None,
                                               max_iter=600, tol=1e-3, random_state=42))
                    classifier = base if task == "intent" else OneVsRestClassifier(base, n_jobs=1)
                    with warnings.catch_warnings(record=True) as notes:
                        warnings.simplefilter("always", ConvergenceWarning)
                        classifier.fit(X, train_y if task == "intent" else risk_y)
                    if task == "intent":
                        predicted = classifier.predict(V)
                        result = intent_metrics(validation_y, predicted, intent_classes)
                        thresholds = None
                    else:
                        scores = classifier.predict_proba(V)
                        thresholds = choose_thresholds(risk_validation, scores)
                        result = risk_metrics(risk_validation, scores >= thresholds, risk_classes)
                    score = result["macro_f1_supported"]
                    trial = {"task": task, "representation": representation, "classifier": kind,
                        "C": c, "class_weight": "balanced" if balanced else None,
                        "validation": compact(result), "seconds": round(time.monotonic() - start, 2),
                        "convergence_warnings": sum(issubclass(n.category, ConvergenceWarning) for n in notes)}
                    trials.append(trial)
                    previous = winners.get(task)
                    if previous is None or score > previous["score"]:
                        payload = {"classifier": classifier, "representation": representation,
                            "lexical_features": vectorizer if representation != "semantic" else None,
                            "classes": intent_classes if task == "intent" else risk_classes,
                            "thresholds": thresholds, "task": task,
                            "encoder_relative_path": "artifacts/encoders/multilingual-minilm",
                            "encoder": encoder_manifest, "model_version": VERSION,
                            "contract": "native_predict_intent_or_multilabel_risk"}
                        if task == "intent":
                            _, margins = intent_scores(classifier, V)
                            payload["confidence_policy"] = confidence_policy(validation_y, predicted, margins)
                        winners[task] = {"score": score, "payload": payload, "selected": trial}
                    print(f"{task} {representation} {kind} C={c} balanced={balanced}: val F1={score:.4f}", flush=True)
                    write_json(output / "search_progress.json", {"test_opened": False, "trials": trials})
    # Freeze BOTH tasks, including thresholds/confidence, before opening any test partition.
    files = {}
    for task, winner in winners.items():
        path = output / f"private/{task}_classifier.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(winner["payload"], path, compress=3)
        files[task] = {"file": path.relative_to(output).as_posix(), "sha256": file_sha256(path)}
    write_json(output / "selection_frozen.json", {"models": files, "test_opened": False,
        "selected": {task: winner["selected"] for task, winner in winners.items()}})
    evaluations, comparison, error_rows, predictions = {}, {}, [], []
    previous_root = ai_root / "artifacts/baseline/1.5.0"
    previous_manifest = json.loads((previous_root / "manifest.json").read_text("utf-8"))
    for partition in ("train", "validation", "test", "external_human_language", "quarantine"):
        rows = validation if partition == "validation" else load_partition(ai_root, partition)
        inputs = [r["input"] for r in rows]
        intent_payload, risk_payload = winners["intent"]["payload"], winners["risk"]["payload"]
        IX = transform_payload(intent_payload, inputs, encoder)
        RX = transform_payload(risk_payload, inputs, encoder)
        predicted = intent_payload["classifier"].predict(IX)
        signals = risk_payload["classifier"].predict_proba(RX) >= risk_payload["thresholds"]
        truth = [r["label"] for r in rows]
        valid_intent = np.asarray([label in intent_classes for label in truth])
        valid_risk = np.asarray([bool(r["risks"]) and set(r["risks"]) <= set(risk_classes) | {"none"} for r in rows])
        evaluations[partition] = {
            "intent": intent_metrics(np.asarray(truth)[valid_intent].tolist(), predicted[valid_intent], intent_classes),
            "risk": risk_metrics(risk_matrix(rows, risk_classes)[valid_risk], signals[valid_risk], risk_classes),
            "interpretation": {"all_rows_processed": len(rows), "unscorable_intent": int((~valid_intent).sum()),
                "unscorable_risk": int((~valid_risk).sum()),
                "independent_quality_claim": False,
                "reason": "training_fit_or_doubtful_or_colliding_reference" if partition in {"train", "quarantine"}
                          else "AI_reference_not_human_gold"}}
        if partition in {"validation", "test", "external_human_language"}:
            rule_signals = np.asarray([[int(label in detect.risks) for label in risk_classes]
                                      for detect in (detect_risks(r["text"][:10000]) for r in rows)])
            evaluations[partition]["risk_with_safety_rules"] = risk_metrics(
                risk_matrix(rows, risk_classes)[valid_risk], (signals | rule_signals)[valid_risk], risk_classes)
        _, margins = intent_scores(intent_payload["classifier"], IX)
        threshold = intent_payload["confidence_policy"]["margin_threshold"]
        accepted = margins >= threshold if threshold is not None else np.zeros(len(rows), dtype=bool)
        evaluations[partition]["selective_intent"] = {
            "coverage": float(accepted.mean()), "accepted": int(accepted.sum()),
            "accuracy_when_accepted": float(np.mean(np.asarray(truth)[accepted] == predicted[accepted])) if accepted.any() else None,
            "all_predictions_still_in_headline_metrics": True}
        for row, label, risk_pred in zip(rows, predicted, signals):
            actual_risks = set(row["risks"]) - {"none"}
            predicted_risks = {name for name, active in zip(risk_classes, risk_pred) if active}
            predictions.append({"id": row["id"], "partition": partition, "predicted_intent": str(label),
                "predicted_risks": sorted(predicted_risks) or ["none"],
                "intent_reference_defined": row["label"] in intent_classes,
                "risk_reference_defined": bool(row["risks"]) and set(row["risks"]) <= set(risk_classes) | {"none"},
                "excluded_from_clean_headline": partition == "quarantine"})
            if row["label"] != label or actual_risks != predicted_risks:
                error_rows.append({"partition": partition, "id": row["id"], "text": row["text"],
                    "context": row["context"], "expected_intent": row["label"], "predicted_intent": str(label),
                    "expected_risks": sorted(actual_risks), "predicted_risks": sorted(predicted_risks)})
        if partition == "test":
            comparison = compare_previous(previous_root, previous_manifest, rows, predicted, signals, risk_classes, encoder)
    write_jsonl(output / "private/errors.jsonl", error_rows)
    write_jsonl(output / "private/predictions_all_12179.jsonl", predictions)
    if len(predictions) != 12179 or len({p["id"] for p in predictions}) != 12179:
        raise ValueError("Not every imported message was processed exactly once")
    write_json(output / "evaluation.json", evaluations)
    write_json(output / "comparison.json", comparison)
    if frozen_fingerprints(ai_root) != protected:
        raise ValueError("Historical files changed")
    manifest = {"model_version": VERSION, "dataset_version": DATA_VERSION,
        "dataset_manifest_sha256": file_sha256(data_path / "manifest.json"),
        "status": "experimental_opt_in_not_default", "models": files,
        "runtime": {"python": platform.python_version(), **{v: version(v) for v in
            ("scikit-learn", "numpy", "scipy", "joblib", "onnxruntime", "tokenizers")}},
        "selected": {task: winner["selected"] for task, winner in winners.items()},
        "trial_count": len(trials), "trials": trials, "synthetic_sample_weight": 1.0,
        "test_policy": "both tasks frozen before test; no refit or threshold changes after results",
        "evaluation_labels": "AI_reviewed_not_independent_human_gold",
        "risk_contract": "20 independent positive labels; none derived only when no label crosses threshold",
        "entity_span_gold_available": False, "automatically_promoted_to_app": False,
        "all_imported_records_processed": len(predictions),
        "source_files": {name: file_sha256(ai_root / name) for name in
            ("src/evolv_nlp/review_release.py", "src/evolv_nlp/review_training.py", "src/evolv_nlp/semantic_encoder.py")},
        "protected_fingerprints": protected}
    write_json(output / "manifest.json", manifest)
    return {partition: {task: compact(value) for task, value in result.items()}
            for partition, result in evaluations.items()}


def compare_previous(root, manifest, rows, new_intents, new_risks, risk_classes, encoder):
    output = {"same_new_test_inputs": True, "not_comparable_to_old_small_test_headline": True,
              "prior_model_may_have_seen_old_versions_of_public_rows": True}
    for task, old_key in (("intent", "intent_classification"), ("risk", "risk_classification")):
        item = manifest["model_artifacts"][old_key]
        old = load_hashed_payload(root, item)
        classes = list(old["classifier"].classes_)
        predicted = old_predict(old, [r["input"] for r in rows], encoder)
        if task == "intent":
            selection = [i for i, row in enumerate(rows) if row["label"] in classes]
            truth = [rows[i]["label"] for i in selection]
            output[task] = {"records_shared_labels": len(selection),
                "old": compact(intent_metrics(truth, predicted[selection], classes)),
                "new": compact(intent_metrics(truth, new_intents[selection], classes))}
        else:
            shared = sorted((set(classes) & set(risk_classes)) - {"none"})
            truth = risk_matrix(rows, shared)
            old_binary = np.asarray([[int(label == p) for label in shared] for p in predicted])
            new_binary = new_risks[:, [risk_classes.index(label) for label in shared]]
            output[task] = {"shared_positive_labels": len(shared),
                "old": compact(risk_metrics(truth, old_binary, shared)),
                "new": compact(risk_metrics(truth, new_binary, shared)),
                "old_contract_was_single_label": True}
    return output

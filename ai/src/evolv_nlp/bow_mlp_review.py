"""Controlled BoW/TF-IDF, stopword and MLP comparison; no test-driven selection."""
import json
import platform
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import Normalizer, StandardScaler
from threadpoolctl import threadpool_limits

from evolv_nlp.dataset import file_sha256
from evolv_nlp.real_data import write_json, write_jsonl
from evolv_nlp.review_release import load_partition
from evolv_nlp.review_training import (intent_metrics, risk_metrics, risk_matrix, compact,
    choose_thresholds, confidence_policy, intent_scores, transform_payload as previous_transform)

VERSION = "1.6.1"
# Preserve negation, timing, intent verbs and short confirmations.
STOPWORDS = sorted({"a", "as", "o", "os", "de", "da", "das", "do", "dos", "e", "em",
                    "no", "na", "nos", "nas", "um", "uma", "uns", "umas", "ao", "aos"})


class NamedIntentMLP:
    """Keep integer labels inside sklearn's early-stopping scorer, names outside."""
    def __init__(self, classifier, classes):
        self.classifier = classifier
        self.classes_ = np.asarray(classes)
        self.n_iter_ = classifier.n_iter_

    def predict(self, X):
        return self.classes_[self.classifier.predict(X).astype(int)]

    def predict_proba(self, X):
        return self.classifier.predict_proba(X)


def transform_payload(payload, texts, encoder):
    if payload["representation"] != "svd_mlp":
        return previous_transform(payload, texts, encoder)
    X = payload["lexical_features"].transform(texts)
    return payload["scaler"].transform(payload["reducer"].transform(X))


def train(ai_root):
    output = ai_root / f"artifacts/baseline/{VERSION}"
    if (output / "manifest.json").exists():
        raise ValueError("Finalized BoW/MLP experiment")
    output.mkdir(parents=True, exist_ok=True)
    taxonomy = json.loads((ai_root / "data/releases/1.7.0/taxonomy.json").read_text("utf-8"))
    intents = sorted(r["id"] for r in taxonomy["intents"])
    risks = sorted(r["id"] for r in taxonomy["risks"] if r["id"] != "none")
    rows, validation = load_partition(ai_root, "train"), load_partition(ai_root, "validation")
    texts, Vtexts = [r["input"] for r in rows], [r["input"] for r in validation]
    y, vy = np.asarray([r["label"] for r in rows]), [r["label"] for r in validation]
    ry, vry = risk_matrix(rows, risks), risk_matrix(validation, risks)
    counts = Counter(y)
    intent_weights = np.asarray([(len(rows) / (len(intents) * counts[label])) ** 0.5 for label in y])
    positive_weights = np.sqrt(len(rows) / np.maximum(ry.sum(0), 1))
    risk_weights = np.maximum(1, (ry * positive_weights).max(1)).clip(max=5)
    trials, winners = [], {}
    configuration = {"features": ["bow", "tfidf"], "stopword_variants": [False, True],
        "hidden_layers": [128, 64], "alpha": [0.01, 0.1], "svd_dimensions": 128,
        "stopwords": STOPWORDS, "preserve_negation": True, "test_for_selection": False}
    write_json(output / "registered_experiment.json", configuration)
    with threadpool_limits(limits=2):
        for representation in ("bow", "tfidf"):
            for remove_stopwords in (False, True):
                common = dict(strip_accents="unicode", ngram_range=(1, 2), max_features=30000,
                              stop_words=STOPWORDS if remove_stopwords else None, dtype=np.float32)
                lexical = (Pipeline([("counts", CountVectorizer(**common)), ("l2", Normalizer())])
                           if representation == "bow" else TfidfVectorizer(sublinear_tf=True, **common))
                X, V = lexical.fit_transform(texts), lexical.transform(Vtexts)
                reducer = TruncatedSVD(n_components=min(128, X.shape[1] - 1), random_state=42)
                reduced = reducer.fit_transform(X)
                scaler = StandardScaler()
                X, V = scaler.fit_transform(reduced), scaler.transform(reducer.transform(V))
                for task in ("intent", "risk"):
                    for alpha in (0.01, 0.1):
                        classifier = MLPClassifier(hidden_layer_sizes=(128, 64), activation="relu", solver="adam",
                            alpha=alpha, learning_rate_init=0.001, max_iter=100, batch_size=128,
                            early_stopping=True, validation_fraction=0.1, n_iter_no_change=10, random_state=42)
                        classifier.fit(X, np.asarray([intents.index(label) for label in y]) if task == "intent" else ry,
                                       sample_weight=intent_weights if task == "intent" else risk_weights)
                        if task == "intent":
                            classifier = NamedIntentMLP(classifier, intents)
                            predicted = classifier.predict(V)
                            result, limits = intent_metrics(vy, predicted, intents), None
                        else:
                            scores = classifier.predict_proba(V)
                            limits = choose_thresholds(vry, scores)
                            result = risk_metrics(vry, scores >= limits, risks)
                        trial = {"task": task, "features": representation, "remove_stopwords": remove_stopwords,
                            "alpha": alpha, "epochs": int(classifier.n_iter_), "validation": compact(result)}
                        trials.append(trial)
                        score = result["macro_f1_supported"]
                        if task not in winners or score > winners[task]["score"]:
                            payload = {"classifier": classifier, "representation": "svd_mlp", "lexical_features": lexical,
                                "reducer": reducer, "scaler": scaler, "classes": intents if task == "intent" else risks,
                                "thresholds": limits, "task": task, "model_version": VERSION}
                            if task == "intent":
                                _, margins = intent_scores(classifier, V)
                                payload["confidence_policy"] = confidence_policy(vy, predicted, margins)
                            winners[task] = {"score": score, "selected": trial, "payload": payload}
                        print(f"MLP {task} {representation} stopwords={remove_stopwords} alpha={alpha}: val F1={score:.4f}", flush=True)
                        write_json(output / "search_progress.json", {"test_opened": False, "trials": trials})
    models = {}
    for task, winner in winners.items():
        path = output / f"private/{task}_classifier.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(winner["payload"], path, compress=3)
        models[task] = {"file": path.relative_to(output).as_posix(), "sha256": file_sha256(path)}
    write_json(output / "selection_frozen.json", {"models": models, "test_opened": False})
    evaluations, predictions = {}, []
    for partition in ("train", "validation", "test", "external_human_language", "quarantine"):
        subset = load_partition(ai_root, partition)
        inputs = [r["input"] for r in subset]
        intent, risk = winners["intent"]["payload"], winners["risk"]["payload"]
        pred = intent["classifier"].predict(transform_payload(intent, inputs, None))
        signal = risk["classifier"].predict_proba(transform_payload(risk, inputs, None)) >= risk["thresholds"]
        valid_i = np.asarray([r["label"] in intents for r in subset])
        valid_r = np.asarray([bool(r["risks"]) and set(r["risks"]) <= set(risks) | {"none"} for r in subset])
        evaluations[partition] = {"intent": intent_metrics(np.asarray([r["label"] for r in subset])[valid_i].tolist(), pred[valid_i], intents),
            "risk": risk_metrics(risk_matrix(subset, risks)[valid_r], signal[valid_r], risks),
            "reference": "AI_reviewed_not_independent_human_gold"}
        for row, label, active in zip(subset, pred, signal):
            predictions.append({"id": row["id"], "partition": partition, "predicted_intent": str(label),
                "predicted_risks": [name for name, present in zip(risks, active) if present] or ["none"]})
    write_json(output / "evaluation.json", evaluations)
    write_jsonl(output / "private/predictions_all_12179.jsonl", predictions)
    write_json(output / "manifest.json", {"model_version": VERSION, "dataset_version": "1.7.0", "models": models,
        "runtime": {"python": platform.python_version(), **{name: version(name) for name in ("scikit-learn", "numpy", "scipy", "joblib")}},
        "dataset_manifest_sha256": file_sha256(ai_root / "data/releases/1.7.0/manifest.json"),
        "selected": {task: winner["selected"] for task, winner in winners.items()},
        "configuration": configuration, "trials": trials, "all_imported_records_processed": len(predictions),
        "note": "MLP already has a linear softmax/sigmoid head; no redundant post-hoc regression added"})
    return {part: {task: compact(result[task]) for task in ("intent", "risk")} for part, result in evaluations.items()}

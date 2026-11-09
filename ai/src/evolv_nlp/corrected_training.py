"""Corrected-label experiments. All feature fitting and clustering use train only."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import platform
import time
from importlib.metadata import version

import joblib
import numpy as np
from scipy.special import softmax
from scipy.sparse import csr_matrix, hstack
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import ComplementNB
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import normalize
from sklearn.svm import LinearSVC, SVC
from threadpoolctl import threadpool_limits

from evolv_nlp.corrected_release import VERSION as DATA_VERSION, load_partition
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.real_data import write_json, write_jsonl
from evolv_nlp.review_training import (lexical_features, choose_thresholds, compact,
    confidence_policy, intent_metrics, risk_metrics, risk_matrix, load_hashed_payload)
from evolv_nlp.semantic_encoder import LocalSemanticEncoder

VERSION = "1.8.0"


def load_corrected_payload(root, metadata):
    root = root.resolve()
    path = (root / metadata["file"]).resolve()
    if not path.is_relative_to(root) or file_sha256(path) != metadata["sha256"]:
        raise ValueError("Corrected model path/hash mismatch")
    payload = joblib.load(path)
    if not isinstance(payload, dict) or not ({"classifier", "components"} & set(payload)):
        raise TypeError("Unexpected corrected model payload")
    return payload


def clean_research_context(text):
    prefix, separator = "Contexto anterior: ", "\nMensagem atual: "
    if text.startswith(prefix) and separator in text:
        context, message = text[len(prefix):].split(separator, 1)
        if context.startswith(("A publicação pode depender de imagem/vídeo.",
                               "Há imagem no post;", "[estado_sintetico]")):
            return message
    return text


class HierarchicalIntent:
    def __init__(self, C=1.0):
        self.C = C

    @staticmethod
    def group(label):
        if label.startswith("ask_") or label in {"compare_options", "analyze_progress", "motivation_support", "explain_current_plan"}:
            return "information"
        if label in {"confirm_planner_action", "reject_planner_action", "defer_planner_action", "undo_planner_action"}:
            return "pending_dialog"
        if label in {"greeting", "clarification", "out_of_scope", "share_fitness_content", "image_context_request"}:
            return "interaction"
        return "plan_request_or_record"

    def fit(self, X, y, sample_weight=None):
        self.classes_ = np.unique(y)
        groups = np.asarray([self.group(label) for label in y])
        self.router = LogisticRegression(C=self.C, max_iter=600, tol=1e-3, random_state=42)
        self.router.fit(X, groups, sample_weight=sample_weight)
        self.locals = {}
        for group in self.router.classes_:
            mask = groups == group
            model = LogisticRegression(C=self.C, class_weight="balanced", max_iter=600, tol=1e-3, random_state=42)
            model.fit(X[mask], y[mask], sample_weight=None if sample_weight is None else sample_weight[mask])
            self.locals[group] = model
        return self

    def predict_proba(self, X):
        routed = self.router.predict_proba(X)
        output = np.zeros((X.shape[0], len(self.classes_)), dtype=np.float64)
        for j, group in enumerate(self.router.classes_):
            model = self.locals[group]
            positions = np.searchsorted(self.classes_, model.classes_)
            output[:, positions] = routed[:, j, None] * model.predict_proba(X)
        return output


class RiskLogistic:
    def __init__(self, C=0.5, balanced=True):
        self.C, self.balanced = C, balanced

    def fit(self, X, y, sample_weight=None):
        self.estimators_ = []
        for column in y.T:
            model = LogisticRegression(C=self.C, class_weight="balanced" if self.balanced else None,
                                       max_iter=700, tol=1e-3, random_state=42)
            model.fit(X, column, sample_weight=sample_weight)
            self.estimators_.append(model)
        return self

    def predict_proba(self, X):
        return np.column_stack([model.predict_proba(X)[:, 1] for model in self.estimators_])


class NamedMLP:
    def __init__(self, alpha=0.01):
        self.model = MLPClassifier(hidden_layer_sizes=(192,), alpha=alpha, learning_rate_init=0.001,
            early_stopping=True, validation_fraction=0.12, n_iter_no_change=8, max_iter=120,
            batch_size=128, random_state=42)

    def fit(self, X, y, sample_weight=None):
        self.classes_ = np.unique(y)
        self.model.fit(X, np.searchsorted(self.classes_, y), sample_weight=sample_weight)
        return self

    def predict_proba(self, X):
        return self.model.predict_proba(X)


def make_classifier(task, kind, c, balanced):
    if task == "risk":
        return RiskLogistic(c, balanced)
    if kind == "svm":
        return LinearSVC(C=c, class_weight="balanced" if balanced else None, dual="auto", max_iter=5000, random_state=42)
    if kind == "lr":
        return LogisticRegression(C=c, class_weight="balanced" if balanced else None, max_iter=700, tol=1e-3, random_state=42)
    if kind == "rbf":
        return SVC(C=c, kernel="rbf", class_weight="balanced", cache_size=512, break_ties=True, random_state=42)
    if kind == "nb":
        return ComplementNB(alpha=c)
    if kind == "mlp":
        return NamedMLP(c)
    raise ValueError(f"Unknown classifier kind: {kind}")


class ClusterFrequency:
    def __init__(self, clusterer, classes, task):
        self.clusterer, self.classes_, self.task = clusterer, np.asarray(classes), task

    def fit(self, X, y, sample_weight=None):
        assigned = self.clusterer.predict(X)
        weights = np.ones(len(X)) if sample_weight is None else sample_weight
        self.table = np.zeros((self.clusterer.n_clusters, len(self.classes_)), dtype=np.float32)
        for cluster in range(self.clusterer.n_clusters):
            indices = assigned == cluster
            if self.task == "intent":
                for j, label in enumerate(self.classes_):
                    self.table[cluster, j] = weights[indices & (y == label)].sum()
                self.table[cluster] /= max(self.table[cluster].sum(), 1)
            elif indices.any():
                self.table[cluster] = np.average(y[indices], axis=0, weights=weights[indices])
        return self

    def predict_proba(self, X):
        return self.table[self.clusterer.predict(X)]


class CorrectedFeatures:
    def fit_transform(self, texts, embeddings):
        self.lexical = lexical_features()
        lexical = self.lexical.fit_transform(texts)
        self.counts = CountVectorizer(strip_accents="unicode", ngram_range=(1, 2), min_df=2,
                                      max_features=35000, binary=True, dtype=np.float32)
        self.counts.fit(texts)
        self.svd = TruncatedSVD(n_components=128, n_iter=5, random_state=42)
        self.svd.fit(lexical)
        self.clusterers = {}
        for k in (30, 60, 120):
            clusterer = MiniBatchKMeans(n_clusters=k, n_init=3, max_iter=150, batch_size=512, random_state=42)
            clusterer.fit(embeddings)
            self.clusterers[k] = clusterer
        return self.transform(texts, embeddings, lexical)

    def transform(self, texts, embeddings, lexical=None):
        lexical = self.lexical.transform(texts) if lexical is None else lexical
        lsa = normalize(self.svd.transform(lexical)).astype(np.float32)
        views = {"lexical": lexical, "semantic": embeddings,
                 "bow": self.counts.transform(texts), "lsa_semantic": np.hstack([lsa, embeddings])}
        for weight in (1, 2):
            views[f"hybrid{weight}"] = hstack([lexical, csr_matrix(weight * embeddings)], format="csr")
        for k, clusterer in self.clusterers.items():
            similarities = np.exp(-clusterer.transform(embeddings) ** 2).astype(np.float32)
            views[f"cluster{k}"] = hstack([lexical, csr_matrix(embeddings), csr_matrix(similarities)], format="csr")
        if hasattr(self, "clean_lexical"):
            # Controlled ablation: clean lexical channels; cached semantic vectors stay unchanged.
            cleaned = [clean_research_context(text) for text in texts]
            clean_lexical = self.clean_lexical.transform(cleaned)
            tail = self.query_lexical.transform([" ".join(text.split()[-70:]) for text in cleaned])
            views["clean_lexical"] = clean_lexical
            views["clean_hybrid"] = hstack([clean_lexical, csr_matrix(embeddings)], format="csr")
            views["query_focus"] = hstack([clean_lexical, 1.5 * tail], format="csr")
            views["query_hybrid"] = hstack([clean_lexical, 1.5 * tail, csr_matrix(embeddings)], format="csr")
        return views


def probabilities(payload, views):
    if "components" in payload:
        return sum(weight * probabilities(component, views) for weight, component in
                   zip(payload["weights"], payload["components"]))
    model, X = payload["classifier"], views[payload["view"]]
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)
    return softmax(model.decision_function(X), axis=1)


def evaluate_payload(payload, views, rows, classes, tune=False):
    scores = probabilities(payload, views)
    if payload["task"] == "intent":
        predicted = np.asarray(classes)[scores.argmax(axis=1)]
        metrics = intent_metrics([r["label"] for r in rows], predicted, classes)
    else:
        truth = risk_matrix(rows, classes)
        if tune:
            payload["thresholds"] = choose_thresholds(truth, scores)
        predicted = scores >= payload["thresholds"]
        metrics = risk_metrics(truth, predicted, classes)
    return metrics, predicted, scores


def search(ai_root):
    output = ai_root / f"artifacts/baseline/{VERSION}"
    if (output / "candidate_selection.json").exists():
        return json.loads((output / "candidate_selection.json").read_text("utf-8"))
    if (output / "selection_frozen.json").exists():
        raise ValueError("Selection frozen; no test-driven rerun permitted")
    private = output / "private"
    private.mkdir(parents=True, exist_ok=True)
    taxonomy = json.loads((ai_root / f"data/releases/{DATA_VERSION}/taxonomy.json").read_text("utf-8"))
    classes = {"intent": sorted(r["id"] for r in taxonomy["intents"]),
               "risk": sorted(r["id"] for r in taxonomy["risks"] if r["id"] != "none")}
    train, val = load_partition(ai_root, "train"), load_partition(ai_root, "validation")
    texts, val_texts = [r["input"] for r in train], [r["input"] for r in val]
    train_y = {"intent": np.asarray([r["label"] for r in train]), "risk": risk_matrix(train, classes["risk"])}
    if set(train_y["intent"]) != set(classes["intent"]) or not train_y["risk"].sum(axis=0).all():
        raise ValueError("Some declared labels have no training support")
    encoder = LocalSemanticEncoder(ai_root / "artifacts/encoders/multilingual-minilm")
    print("Using cached local MiniLM embeddings; no private text is sent externally", flush=True)
    embedded, val_embedded = encoder.encode(texts), encoder.encode(val_texts)
    feature_path = private / "features.joblib"
    progress_path = output / "search_progress.json"
    progress = json.loads(progress_path.read_text("utf-8")) if progress_path.exists() else None
    if progress and progress.get("test_opened"):
        raise ValueError("Cannot resume search after opening test")
    features = joblib.load(feature_path) if progress else CorrectedFeatures()
    with threadpool_limits(limits=2):
        T = features.transform(texts, embedded) if progress else features.fit_transform(texts, embedded)
        V = features.transform(val_texts, val_embedded)
    if not progress:
        joblib.dump(features, feature_path, compress=3)
    trials, best, representatives = [], {}, {"intent": {}, "risk": {}}
    if progress:
        trials = progress["trials"]
        for task, trial in progress["best"].items():
            candidate_path = private / f"{task}_candidate.joblib"
            payload = load_corrected_payload(output, {"file": candidate_path.relative_to(output).as_posix(), "sha256": file_sha256(candidate_path)})
            best[task] = {"score": trial["validation"]["macro_f1_supported"], "trial": trial, "payload": payload}
        print(f"Resuming {len(trials)} completed validation trials; reserved test remains closed", flush=True)

    def record(payload, description, fit_seconds=0, tune=True):
        task = payload["task"]
        result, predicted, scores = evaluate_payload(payload, V, val, classes[task], tune)
        score = result["macro_f1_supported"]
        trial = {"number": len(trials) + 1, "task": task, **description,
                 "validation": compact(result), "seconds": round(fit_seconds, 2)}
        trials.append(trial)
        if task not in best or score > best[task]["score"] + 1e-12:
            best[task] = {"score": score, "trial": trial, "payload": payload}
            joblib.dump(payload, private / f"{task}_candidate.joblib", compress=3)
        view = payload.get("view")
        if view and (view not in representatives[task] or score > representatives[task][view][0]):
            representatives[task][view] = (score, payload)
        print(f"{task} {description}: val F1={score:.4f}", flush=True)
        write_json(output / "search_progress.json", {"test_opened": False, "trials": trials,
            "best": {task: value["trial"] for task, value in best.items()}})
        return result

    old_root = ai_root / "artifacts/baseline/1.6.0"
    old_manifest = json.loads((old_root / "manifest.json").read_text("utf-8"))
    with threadpool_limits(limits=2):
        if progress:
            for task in ("intent", "risk"):
                view_best = {}
                for trial in trials:
                    view = trial.get("view")
                    if trial["task"] == task and view and (view not in view_best or trial["validation"]["macro_f1_supported"] > view_best[view]["validation"]["macro_f1_supported"]):
                        view_best[view] = trial
                clustered = max((key for key in view_best if key.startswith("cluster")), key=lambda key: view_best[key]["validation"]["macro_f1_supported"])
                for view in ("lexical", "semantic", clustered):
                    trial = view_best[view]
                    if best[task]["payload"].get("view") == view:
                        payload = best[task]["payload"]
                    elif trial["kind"] == "unchanged_old_baseline":
                        old = load_hashed_payload(old_root, old_manifest["models"][task])
                        payload = {"task": task, "view": view, "classifier": old["classifier"], "thresholds": old.get("thresholds"), "trained_dataset_version": "1.7.0"}
                    else:
                        classifier = make_classifier(task, trial["kind"], trial["C_or_alpha"], trial["balanced"])
                        weights = np.asarray([trial["uncertain_training_weight"] if r.get("ai_review", {}).get("uncertain") else 1.0 for r in train])
                        classifier.fit(T[view], train_y[task], sample_weight=weights)
                        payload = {"task": task, "view": view, "classifier": classifier, "trained_dataset_version": DATA_VERSION}
                    result, _, _ = evaluate_payload(payload, V, val, classes[task], tune=trial["kind"] != "unchanged_old_baseline")
                    representatives[task][view] = (result["macro_f1_supported"], payload)
                    print(f"Restored voting component {task}/{view}", flush=True)
        for task, metadata in old_manifest["models"].items():
            if progress:
                continue
            old = load_hashed_payload(old_root, metadata)
            view = "lexical" if old["representation"] == "lexical" else old["representation"]
            payload = {"task": task, "view": view, "classifier": old["classifier"],
                       "thresholds": old.get("thresholds"), "trained_dataset_version": "1.7.0"}
            # Same unchanged training texts produce the same lexical vocabulary and cache vectors.
            assert old["lexical_features"].get_feature_names_out().tolist() == features.lexical.get_feature_names_out().tolist()
            record(payload, {"kind": "unchanged_old_baseline", "view": view}, tune=False)

        profiles = []
        for view in ("lexical", "semantic", "hybrid1", "hybrid2"):
            profiles.extend(("intent", view, "svm", c, balanced, 1.0) for c, balanced in ((0.25, True), (1.0, True), (0.5, False)))
            profiles.append(("intent", view, "lr", 1.0, True, 1.0))
            profiles.extend(("risk", view, "lr", c, balanced, 1.0) for c, balanced in ((0.5, True), (2.0, False)))
        for view in ("cluster30", "cluster60", "cluster120", "lsa_semantic"):
            profiles.extend(("intent", view, "svm", c, True, 1.0) for c in (0.25, 1.0))
            profiles.extend(("risk", view, "lr", c, True, 1.0) for c in (0.5, 2.0))
        profiles += [("intent", "lexical", "svm", 0.5, True, 0.5),
                     ("intent", "hybrid1", "svm", 0.5, True, 0.5),
                     ("risk", "hybrid1", "lr", 0.5, True, 0.5),
                     ("risk", "semantic", "lr", 2.0, True, 0.5)]
        profiles += [("intent", "semantic", "rbf", 2.0, True, 1.0),
                     ("intent", "semantic", "rbf", 8.0, True, 1.0),
                     ("intent", "lsa_semantic", "rbf", 4.0, True, 1.0),
                     ("intent", "bow", "nb", 0.3, False, 1.0),
                     ("intent", "bow", "nb", 1.0, False, 1.0),
                     ("intent", "lsa_semantic", "mlp", 0.01, False, 1.0)]
        for task, view, kind, c, balanced, uncertain_weight in profiles:
            if any(trial["task"] == task and trial.get("view") == view and trial["kind"] == kind and
                   trial.get("C_or_alpha") == c and trial.get("balanced") == balanced and
                   trial.get("uncertain_training_weight") == uncertain_weight for trial in trials):
                continue
            start = time.monotonic()
            weights = np.asarray([uncertain_weight if r.get("ai_review", {}).get("uncertain") else 1.0 for r in train])
            classifier = make_classifier(task, kind, c, balanced)
            classifier.fit(T[view], train_y[task], sample_weight=weights)
            payload = {"task": task, "view": view, "classifier": classifier, "trained_dataset_version": DATA_VERSION}
            record(payload, {"kind": kind, "view": view, "C_or_alpha": c, "balanced": balanced,
                             "uncertain_training_weight": uncertain_weight}, time.monotonic() - start)

        # A genuine unsupervised baseline, mapped to class frequencies using TRAIN labels only.
        for task in ("intent", "risk"):
            classifier = ClusterFrequency(features.clusterers[60], classes[task], task).fit(embedded, train_y[task])
            record({"task": task, "view": "semantic", "classifier": classifier, "trained_dataset_version": DATA_VERSION},
                   {"kind": "kmeans_frequency_baseline", "k": 60})

        for task in ("intent", "risk"):
            lexical = representatives[task]["lexical"][1]
            semantic = representatives[task]["semantic"][1]
            clustered = max((value for key, value in representatives[task].items() if key.startswith("cluster")), key=lambda item: item[0])[1]
            for other, name in ((semantic, "semantic"), (clustered, "clusters")):
                for weight in (0.25, 0.5, 0.75):
                    payload = {"task": task, "components": [lexical, other], "weights": [1 - weight, weight],
                               "trained_dataset_version": DATA_VERSION}
                    record(payload, {"kind": "soft_voting", "with": name, "weight": weight})

    artifacts = {}
    for task, item in best.items():
        payload = item["payload"]
        result, predicted, scores = evaluate_payload(payload, V, val, classes[task])
        if task == "intent":
            ordered = np.sort(scores, axis=1)
            policy = confidence_policy([r["label"] for r in val], predicted, ordered[:, -1] - ordered[:, -2])
            policy["validation_label_support"] = dict(Counter(r["label"] for r in val))
            policy["minimum_label_validation_support"] = 5
            payload["confidence_policy"] = policy
        payload["classes"] = classes[task]
        path = private / f"{task}_classifier.joblib"
        joblib.dump(payload, path, compress=3)
        artifacts[task] = {"file": path.relative_to(output).as_posix(), "sha256": file_sha256(path)}
    cluster_diagnostics = {}
    for k, clusterer in features.clusterers.items():
        assignments = clusterer.predict(embedded)
        cluster_diagnostics[str(k)] = [{"cluster": i, "records": int((assignments == i).sum()),
            "intent_counts": dict(Counter(train_y["intent"][assignments == i]))} for i in range(k)]
    write_json(output / "clustering.json", {"fit_partition": "train", "label_changes_from_clusters": False,
        "method": "MiniBatchKMeans on normalized frozen MiniLM embeddings", "clusters": cluster_diagnostics})
    selection = {"model_version": VERSION, "dataset_version": DATA_VERSION, "models": artifacts,
        "features": {"file": feature_path.relative_to(output).as_posix(), "sha256": file_sha256(feature_path)},
        "selected": {task: item["trial"] for task, item in best.items()}, "trials": trials,
        "intent_classes": classes["intent"], "risk_classes": classes["risk"], "test_opened": False,
        "clustering_fitted_on_train_only": True,
        "runtime": {"python": platform.python_version(), **{name: version(name) for name in ("scikit-learn", "numpy", "scipy", "joblib", "onnxruntime", "tokenizers")}},
        "dataset_manifest_sha256": file_sha256(ai_root / f"data/releases/{DATA_VERSION}/manifest.json"),
        "validation_reference_is_ai_reviewed_not_human_gold": True,
        "note": "Candidate selection only; compare neural candidates before a single final frozen-test evaluation"}
    write_json(output / "candidate_selection.json", selection)
    return selection

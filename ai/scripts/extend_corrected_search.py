"""Additional train-only preprocessing / hierarchy ablations, before test opening."""
import json
from pathlib import Path
import sys
import time

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import LinearSVC
from threadpoolctl import threadpool_limits

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.corrected_release import load_partition
from evolv_nlp.corrected_training import (clean_research_context, HierarchicalIntent, RiskLogistic,
    evaluate_payload, lexical_features, probabilities, confidence_policy, load_corrected_payload)
from evolv_nlp.dataset import file_sha256
from evolv_nlp.real_data import write_json
from evolv_nlp.review_training import compact, risk_matrix
from evolv_nlp.semantic_encoder import LocalSemanticEncoder


def run():
    root = AI_ROOT / "artifacts/baseline/1.8.0"
    if (root / "selection_frozen.json").exists() or (root / "manifest.json").exists():
        raise ValueError("Final selection already frozen")
    path = root / "candidate_selection.json"
    selection = json.loads(path.read_text("utf-8"))
    if selection.get("extra_preprocessing_completed"):
        return selection
    feature_path = root / selection["features"]["file"]
    if file_sha256(feature_path) != selection["features"]["sha256"]:
        raise ValueError("Feature checksum mismatch")
    features = joblib.load(feature_path)
    train, val = load_partition(AI_ROOT, "train"), load_partition(AI_ROOT, "validation")
    texts, vtexts = [r["input"] for r in train], [r["input"] for r in val]
    cleaned = [clean_research_context(text) for text in texts]
    features.clean_lexical = lexical_features()
    features.query_lexical = lexical_features()
    encoder = LocalSemanticEncoder(AI_ROOT / "artifacts/encoders/multilingual-minilm")
    with threadpool_limits(limits=2):
        features.clean_lexical.fit(cleaned)
        features.query_lexical.fit([" ".join(text.split()[-70:]) for text in cleaned])
        T = features.transform(texts, encoder.encode(texts))
        V = features.transform(vtexts, encoder.encode(vtexts))
    classes = {"intent": selection["intent_classes"], "risk": selection["risk_classes"]}
    y = {"intent": np.asarray([r["label"] for r in train]), "risk": risk_matrix(train, classes["risk"])}
    best = {task: {"score": selection["selected"][task]["validation"]["macro_f1_supported"],
                   "payload": load_corrected_payload(root, metadata), "trial": selection["selected"][task]}
            for task, metadata in selection["models"].items()}
    prior = {task: dict(item["payload"]) for task, item in best.items()}
    local_best = {}
    def assess(payload, description, seconds=0):
        task = payload["task"]
        result, _, _ = evaluate_payload(payload, V, val, classes[task], tune=True)
        trial = {"number": len(selection["trials"]) + 1, "task": task, **description,
                 "validation": compact(result), "seconds": round(seconds, 2)}
        selection["trials"].append(trial)
        if result["macro_f1_supported"] > best[task]["score"] + 1e-12:
            best[task] = {"score": result["macro_f1_supported"], "payload": payload, "trial": trial}
        if task not in local_best or result["macro_f1_supported"] > local_best[task][0]:
            local_best[task] = (result["macro_f1_supported"], payload)
        print(f"Extra {task} {description}: val F1={result['macro_f1_supported']:.4f}", flush=True)
        write_json(root / "extra_progress.json", {"test_opened": False, "trials": selection["trials"],
                   "best": {task: item["trial"] for task, item in best.items()}})
    profiles = []
    for view in ("clean_lexical", "clean_hybrid", "query_focus", "query_hybrid"):
        profiles.extend(("intent", view, "svm", c, 1.0) for c in (0.25, 1.0))
        profiles.append(("intent", view, "lr", 1.0, 1.0))
        profiles.extend(("risk", view, "lr", c, 1.0) for c in (0.5, 2.0))
    profiles += [("intent", "clean_lexical", "svm", 0.5, 0.5), ("risk", "clean_hybrid", "lr", 0.5, 0.5),
                 ("intent", "clean_lexical", "hierarchy", 1.0, 1.0), ("intent", "clean_hybrid", "hierarchy", 1.0, 1.0)]
    profiles += [("intent", "semantic", "knn", k, 1.0) for k in (3, 7, 15)]
    with threadpool_limits(limits=2):
        for task, view, kind, c, uncertain in profiles:
            start = time.monotonic()
            weights = np.asarray([uncertain if r.get("ai_review", {}).get("uncertain") else 1.0 for r in train])
            if task == "risk":
                classifier = RiskLogistic(c, True)
            elif kind == "svm":
                classifier = LinearSVC(C=c, class_weight="balanced", dual="auto", max_iter=5000, random_state=42)
            elif kind == "hierarchy":
                classifier = HierarchicalIntent(c)
            elif kind == "knn":
                classifier = KNeighborsClassifier(n_neighbors=int(c), weights="distance", metric="cosine", n_jobs=1)
            else:
                classifier = LogisticRegression(C=c, class_weight="balanced", max_iter=700, tol=1e-3, random_state=42)
            if kind == "knn":
                classifier.fit(T[view], y[task])
            else:
                classifier.fit(T[view], y[task], sample_weight=weights)
            assess({"task": task, "view": view, "classifier": classifier, "trained_dataset_version": "1.8.0"},
                   {"kind": kind, "view": view, "C": c, "uncertain_training_weight": uncertain}, time.monotonic() - start)
        for task in ("intent", "risk"):
            challenger = local_best[task][1]
            for weight in (0.25, 0.5, 0.75):
                assess({"task": task, "components": [prior[task], challenger], "weights": [1 - weight, weight],
                        "trained_dataset_version": "mixed_previous_and_corrected"},
                       {"kind": "soft_voting_clean_vs_previous", "weight_clean": weight})
    from collections import Counter
    for task, item in best.items():
        payload = item["payload"]
        if task == "intent":
            _, predicted, scores = evaluate_payload(payload, V, val, classes[task])
            ordered = np.sort(scores, axis=1)
            policy = confidence_policy([r["label"] for r in val], predicted, ordered[:, -1] - ordered[:, -2])
            policy["validation_label_support"] = dict(Counter(r["label"] for r in val))
            policy["minimum_label_validation_support"] = 5
            payload["confidence_policy"] = policy
        payload["classes"] = classes[task]
        model_path = root / selection["models"][task]["file"]
        joblib.dump(payload, model_path, compress=3)
        selection["models"][task]["sha256"] = file_sha256(model_path)
        selection["selected"][task] = item["trial"]
    joblib.dump(features, feature_path, compress=3)
    selection["features"]["sha256"] = file_sha256(feature_path)
    selection["extra_preprocessing_completed"] = True
    selection["metadata_context_stripped_train_records"] = sum(a != b for a, b in zip(texts, cleaned))
    write_json(path, selection)
    return selection

if __name__ == "__main__":
    print(json.dumps({"selected": run()["selected"]}, indent=2))

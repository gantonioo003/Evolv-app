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
from sklearn.decomposition import TruncatedSVD
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.naive_bayes import ComplementNB
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import FeatureUnion
from sklearn.svm import LinearSVC

from evolv_nlp.baseline import load_trusted_model
from evolv_nlp.context_data import frozen_fingerprints
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.real_data import normalized_key, write_json
from evolv_nlp.research_data import RELEASE, weak_training_rows
from evolv_nlp.research_models import ResearchTextModel, TwoStageClassifier
from evolv_nlp.training_v12 import FILES, TASKS, metrics, predictions
from evolv_nlp.training_v13 import parent_labels, taxonomy

VERSION = "1.4.0"
FEATURES = ("mixed", "wide_char", "word_heavy", "word_only")
MODES = {"owned": 0.0, "weak_010": 0.10, "weak_030": 0.30}
PROFILES = ("svm_025", "svm_1", "svm_4", "svm_16", "lr_05", "lr_2", "lr_8", "nb_01", "sgd")


def features(name):
    word = TfidfVectorizer(strip_accents="unicode", ngram_range=(1, 3) if name == "word_heavy" else (1, 2),
                          sublinear_tf=True, max_features=30000)
    if name == "word_only":
        return word
    char = TfidfVectorizer(analyzer="char_wb", strip_accents="unicode",
                          ngram_range=(2, 6) if name == "wide_char" else (3, 5),
                          sublinear_tf=True, max_features=50000)
    weights = {"word": 2.0, "char": 0.5} if name == "word_heavy" else None
    return FeatureUnion([("word", word), ("char", char)], transformer_weights=weights)


def estimator(profile):
    if profile.startswith("svm_"):
        c = {"025": 0.25, "1": 1.0, "4": 4.0, "16": 16.0}[profile[4:]]
        return LinearSVC(C=c, class_weight="balanced", dual="auto", max_iter=5000, random_state=42)
    if profile.startswith("lr_"):
        c = {"05": 0.5, "2": 2.0, "8": 8.0}[profile[3:]]
        return LogisticRegression(C=c, class_weight="balanced", max_iter=2000, tol=1e-4, random_state=42)
    if profile == "nb_01":
        return ComplementNB(alpha=0.1)
    if profile == "sgd":
        return SGDClassifier(loss="log_loss", alpha=0.0001, class_weight="balanced", max_iter=2000,
                             tol=1e-4, random_state=42)
    raise ValueError("Unknown model profile")


def select_trial(trials):
    # Native subtype coverage and legacy parent coverage both matter. Test never enters selection.
    usable = [r for r in trials if r.get("selection_score") is not None]
    return max(usable, key=lambda r: (r["selection_score"], -r["order"]))


def validate_partition_isolation(train, validation):
    if {normalized_key(r["text"]) for r in train} & {normalized_key(r["text"]) for r in validation}:
        raise ValueError("Training/validation text overlap")
    a = {r.get("family", r["id"]) for r in train}
    b = {r.get("family", r["id"]) for r in validation}
    if a & b:
        raise ValueError("Training/validation family overlap")


def tune(ai_root: Path) -> dict:
    output = ai_root / f"artifacts/baseline/{VERSION}"
    if (output / "manifest.json").exists():
        raise ValueError("Finalized experiment; do not overwrite")
    output.mkdir(parents=True, exist_ok=True)
    protected = frozen_fingerprints(ai_root)
    definitions = taxonomy(ai_root)
    policies, results, model_files = {}, {}, {}
    for task, filename in TASKS.items():
        collection = "intents" if task == "intent_classification" else "risks"
        definitions_task = definitions[collection]
        parent_map = {label: parent_labels([label], definitions_task)[0] for label in definitions_task}
        train = read_jsonl(ai_root / f"data/releases/1.5.0/splits/train/{filename}")
        validation = read_jsonl(ai_root / f"data/releases/1.5.0/splits/validation/{filename}")
        legacy_validation = read_jsonl(ai_root / f"data/releases/1.3.0/splits/validation/{filename}")
        extra_validation = [r for r in validation if r["id"].startswith("v15-")]
        weak, weak_summary = weak_training_rows(ai_root, task)
        validate_partition_isolation(train + weak, validation)
        trials, best, best_score = [], None, -1.0
        best_meta = None

        def record(model, Xlegacy, Xextra, metadata, warn_count=0):
            nonlocal best, best_score, best_meta
            legacy = metrics([r["label"] for r in legacy_validation],
                             parent_labels(model.predict(Xlegacy).tolist(), definitions_task))
            extra = metrics([r["label"] for r in extra_validation], model.predict(Xextra).tolist())
            score = round(0.65 * legacy["macro_f1"] + 0.35 * extra["macro_f1"], 6)
            item = {**metadata, "order": len(trials), "selection_score": score,
                    "legacy_validation": {k: legacy[k] for k in ("accuracy", "macro_f1")},
                    "new_native_validation": {k: extra[k] for k in ("accuracy", "macro_f1")},
                    "convergence_warnings": warn_count}
            trials.append(item)
            if score > best_score:
                best, best_score, best_meta = model, score, item
            print(f"{task} trial {len(trials)} {metadata['id']}: {score:.4f} (best {best_score:.4f})", flush=True)
            write_json(output / "search_progress.json", {"task": task, "trials": trials, "test_opened": False})

        for mode, weak_weight in MODES.items():
            pool = train + weak if weak_weight else train
            texts, y = [r["text"] for r in pool], np.asarray([r["label"] for r in pool])
            weights = np.asarray([1.0] * len(train) + ([weak_weight] * len(weak) if weak_weight else []))
            for feature in FEATURES:
                vectorizer = features(feature)
                X = vectorizer.fit_transform(texts)
                Xold = vectorizer.transform([r["text"] for r in legacy_validation])
                Xnew = vectorizer.transform([r["text"] for r in extra_validation])
                for profile in PROFILES:
                    model = estimator(profile)
                    start = time.monotonic()
                    with warnings.catch_warnings(record=True) as notes:
                        warnings.simplefilter("always", ConvergenceWarning)
                        model.fit(X, y, sample_weight=weights)
                    warn_count = sum(issubclass(n.category, ConvergenceWarning) for n in notes)
                    previous = best_score
                    record(model, Xold, Xnew, {"id": f"{mode}-{feature}-{profile}", "mode": mode,
                        "features": feature, "architecture": profile, "weak_sample_weight": weak_weight,
                        "seconds": round(time.monotonic() - start, 3)}, warn_count)
                    if best_score > previous:
                        best = ResearchTextModel(vectorizer, model)
                # Two-stage classification keeps the detailed taxonomy, not just 30/13 parent labels.
                for profile in ("svm_1", "lr_2"):
                    model = TwoStageClassifier(estimator(profile), parent_map)
                    model.fit(X, y, sample_weight=weights)
                    previous = best_score
                    record(model, Xold, Xnew, {"id": f"{mode}-{feature}-hierarchy-{profile}", "mode": mode,
                        "features": feature, "architecture": f"two_stage_{profile}", "weak_sample_weight": weak_weight})
                    if best_score > previous:
                        best = ResearchTextModel(vectorizer, model)
                if mode == "owned" and feature == "mixed":
                    reducer = TruncatedSVD(n_components=min(96, X.shape[0] - 1, X.shape[1] - 1), random_state=42)
                    reduced = reducer.fit_transform(X)
                    for hidden in ((64,), (96, 32)):
                        model = MLPClassifier(hidden_layer_sizes=hidden, alpha=0.01, max_iter=200,
                                              early_stopping=False, random_state=42, batch_size=32)
                        with warnings.catch_warnings(record=True) as notes:
                            warnings.simplefilter("always", ConvergenceWarning)
                            model.fit(reduced, y, sample_weight=weights)
                        previous = best_score
                        record(model, reducer.transform(Xold), reducer.transform(Xnew),
                               {"id": f"owned-lsa-mlp-{hidden}", "mode": mode, "features": "mixed_svd96",
                                "architecture": f"mlp_{hidden}", "weak_sample_weight": 0.0},
                               sum(issubclass(n.category, ConvergenceWarning) for n in notes))
                        if best_score > previous:
                            best = ResearchTextModel(vectorizer, model, reducer)
        # All selection is complete for this task. Freeze the winner before reading test files.
        path = output / "private" / FILES[task]
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(best, path, compress=3)
        model_files[task] = {"file": str(path.relative_to(output)), "sha256": file_sha256(path)}
        selected = select_trial(trials)
        if selected != best_meta:
            raise ValueError("Selected metadata does not match frozen winner")
        rows_by_name = {"historical_test": read_jsonl(ai_root / f"data/releases/1.3.0/splits/test/{filename}"),
                        "new_authored_test": read_jsonl(ai_root / f"data/releases/1.5.0/splits/test/{filename}")}
        comparisons = {}
        for split, rows in rows_by_name.items():
            texts, labels = [r["text"] for r in rows], [r["label"] for r in rows]
            predicted = best.predict(texts).tolist()
            comparison = {"new_1_4_native": metrics(labels, predicted),
                          "new_1_4_parent": metrics(parent_labels(labels, definitions_task), parent_labels(predicted, definitions_task))}
            for old_version in ("1.1.0", "1.2.0", "1.3.0"):
                root = ai_root / f"artifacts/baseline/{old_version}"
                old = json.loads((root / "manifest.json").read_text("utf-8"))["model_artifacts"][task]
                previous = load_trusted_model(root / old["file"], old["sha256"])
                comparison[f"previous_{old_version}_parent"] = metrics(parent_labels(labels, definitions_task),
                    parent_labels(predictions(previous, texts), definitions_task))
            comparisons[split] = comparison
        results[task] = {"winner": selected, "trial_count": len(trials), "trials": trials,
                         "owned_train": len(train), "weak_data": weak_summary,
                         "classes": len(best.classes_), "comparisons": comparisons,
                         "inference_contract": "native predict; not legacy predict_proba argmax",
                         "test_used_for_selection": False}
        policies[task] = {"automatic_acceptance_enabled": False,
                          "reason": "New native decision contract needs held-out calibration and pipeline integration"}
    if protected != frozen_fingerprints(ai_root):
        raise ValueError("Historical frozen input changed")
    write_json(output / "metrics.json", {"version": VERSION, "tasks": results,
        "limitations": ["External labels are weak and correlated with old model; not human gold.",
                        "Rights/privacy not certified; private local experiment, not commercial activation.",
                        "Historical and authored tests were observed previously; not independent fresh tests.",
                        "Risk classifiers remain single-label; separate rules are not validated multilabel learning.",
                        "Answers are partitioned with questions but never training targets or classifier features."]})
    write_json(output / "confidence_policy.json", policies)
    manifest = {"version": VERSION, "dataset_version": RELEASE, "default_changed": False,
        "status": "private_research_not_production", "rights_status": "unverified",
        "model_artifacts": model_files, "selection": "Declared trials: 65% historical validation, 35% new native validation macro F1",
        "native_prediction_contract": True, "no_test_retuning": True,
        "reports": {name: {"file": name, "sha256": file_sha256(output / name)}
                    for name in ("metrics.json", "confidence_policy.json")},
        "source_files": {f"src/evolv_nlp/{name}.py": file_sha256(ai_root / f"src/evolv_nlp/{name}.py")
                         for name in ("research_data", "research_models", "tuning_v14")},
        "dependencies": {"python": platform.python_version(), **{name: version(name)
                         for name in ("numpy", "scipy", "scikit-learn", "joblib")}}}
    write_json(output / "manifest.json", manifest)
    return manifest

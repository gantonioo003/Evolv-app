"""Bounded v1.9 recognition experiment; no reserved test access or live promotion."""
from collections import Counter
import json
from pathlib import Path
import time
import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.model_selection import StratifiedGroupKFold
from scipy.special import softmax
from threadpoolctl import threadpool_limits

from .action_release import load_partition, sha
from .corrected_training import (clean_research_context, load_corrected_payload,
                                probabilities, RiskLogistic)
from .corrected_pipeline import confidence_allowed
from .review_training import (lexical_features, intent_metrics, risk_matrix,
                              risk_metrics, compact, choose_thresholds, confidence_policy)
from .semantic_encoder import LocalSemanticEncoder
from .real_data import write_json

VERSION = "1.9.0"


class RecognitionFeatures:
    def fit(self, rows):
        self.full = lexical_features().fit([clean_research_context(r["input"]) for r in rows])
        self.message = lexical_features().fit([r["text"] for r in rows])
        # Full inputs prevent empty-vocabulary folds; context remains a separate channel.
        self.context = lexical_features().fit([r["context"] or "sem contexto" for r in rows])
        return self

    def transform(self, rows, embeddings):
        message = self.message.transform([r["text"] for r in rows])
        context = self.context.transform([r["context"] or "sem contexto" for r in rows])
        focus = hstack([message, .35 * context], format="csr")
        return {"full": self.full.transform([clean_research_context(r["input"]) for r in rows]),
                "focus": focus, "hybrid": hstack([focus, csr_matrix(embeddings)], format="csr")}


def intent_model(config):
    if config["kind"] == "svm":
        return LinearSVC(C=config["C"], class_weight="balanced", dual="auto", max_iter=5000, random_state=42)
    return LogisticRegression(C=config["C"], class_weight="balanced", max_iter=700, tol=1e-3, random_state=42)


def scores(model, X):
    return model.predict_proba(X) if hasattr(model, "predict_proba") else softmax(model.decision_function(X), axis=1)


def intent_strata(values, rows, classes, legacy_count):
    predicted = np.asarray(classes)[values.argmax(axis=1)]
    result = {}
    for name, positions in (("legacy", np.arange(legacy_count)),
                            ("actions_synthetic", np.arange(legacy_count, len(rows))),
                            ("combined", np.arange(len(rows)))):
        result[name] = compact(intent_metrics([rows[i]["label"] for i in positions], predicted[positions], classes))
    return result


def risk_strata(values, rows, classes, thresholds, legacy_count):
    truth = risk_matrix(rows, classes)
    return {name: compact(risk_metrics(truth[idx], values[idx] >= thresholds, classes))
            for name, idx in (("legacy", np.arange(legacy_count)),
                ("actions_synthetic", np.arange(legacy_count, len(rows))), ("combined", np.arange(len(rows))))}


def selective(values, rows, classes, policy, legacy_count):
    ranking = np.argsort(values, axis=1)
    labels = np.asarray(classes)[ranking[:, -1]]
    margins = values[np.arange(len(rows)), ranking[:, -1]] - values[np.arange(len(rows)), ranking[:, -2]]
    allowed = np.asarray([confidence_allowed(policy, label, float(margin)) for label, margin in zip(labels, margins)])
    correct = labels == np.asarray([r["label"] for r in rows])
    output = {}
    for name, idx in (("legacy", np.arange(legacy_count)), ("actions_synthetic", np.arange(legacy_count, len(rows))),
                      ("combined", np.arange(len(rows)))):
        mask = allowed[idx]
        output[name] = {"records": len(idx), "accepted": int(mask.sum()),
                        "coverage": float(mask.mean()),
                        "accepted_accuracy": float(correct[idx][mask].mean()) if mask.any() else None,
                        "accepted_errors": int((mask & ~correct[idx]).sum())}
    return output


def input_integrity(ai_root):
    names = ["data/releases/1.9.0/manifest.json", "data/releases/1.9.0/private/train.jsonl",
             "data/releases/1.9.0/private/validation.jsonl", "data/releases/1.9.0/private/validation_legacy.jsonl",
             "data/releases/1.9.0/private/validation_actions_synthetic.jsonl",
             "artifacts/baseline/1.8.0/manifest.json", "artifacts/baseline/1.8.0/candidate_selection.json",
             "artifacts/baseline/1.8.0/selection_frozen.json"]
    return {name: sha(ai_root / name) for name in names}


def run(ai_root):
    output = ai_root / f"artifacts/baseline/{VERSION}"
    if output.exists():
        raise FileExistsError("Use a new experiment version; no overwrites")
    private = output / "private"
    private.mkdir(parents=True)
    protected = input_integrity(ai_root)
    dataset = json.loads((ai_root / "data/releases/1.9.0/manifest.json").read_text(encoding="utf-8"))
    oldroot = ai_root / "artifacts/baseline/1.8.0"
    oldmeta = json.loads((oldroot / "candidate_selection.json").read_text(encoding="utf-8"))
    train, validation = load_partition(ai_root, "train"), load_partition(ai_root, "validation")
    legacy = len(load_partition(ai_root, "validation_legacy"))
    classes, risk_classes = oldmeta["intent_classes"], oldmeta["risk_classes"]
    y = np.asarray([r["label"] for r in train])
    assert sorted(set(y)) == classes
    configs = [{"kind": "svm", "view": view, "C": C, "new_weight": 1.0}
               for view in ("full", "focus", "hybrid") for C in (.5, 2.0)]
    configs += [{"kind": "lr", "view": view, "C": 1.0, "new_weight": 1.0} for view in ("full", "focus", "hybrid")]
    configs += [{"kind": "svm", "view": view, "C": 1.0, "new_weight": 3.0} for view in ("focus", "hybrid")]
    protocol = {"phase": "7.07.3", "version": VERSION, "dataset_version": "1.9.0",
        "intent_configs": configs, "risk_configs": [{"C": c, "balanced": b} for c in (.5, 2.) for b in (False, True)],
        "selection": "intent: legacy macro F1 loss <= .02 and accuracy loss <= .01; maximize .65 legacy F1 + .35 synthetic F1; otherwise keep baseline",
        "risk_selection": "legacy positive-label macro F1 must not decrease; rank .9 legacy macro F1 + .1 synthetic exact match",
        "confidence": "target .90 accuracy, >=30 OOF accepted, >=5 validation references per class; no four-case tuning",
        "calibration": "selected intent config, three group-disjoint train folds; refit vocabulary per fold; frozen MiniLM",
        "validation_not_independent_gold": True, "test_opened": False, "live_promotion": False,
        "input_sha256": protected}
    write_json(output / "protocol.json", protocol)
    encoder = LocalSemanticEncoder(ai_root / "artifacts/encoders/multilingual-minilm")
    encoder.cache_path = private / "embeddings.npz"  # Never overwrite the shared historical cache.
    print("Encoding train and validation locally (reserved test remains closed)", flush=True)
    embedded = encoder.encode([r["input"] for r in train])
    val_embedded = encoder.encode([r["input"] for r in validation])
    with threadpool_limits(limits=2):
        features = RecognitionFeatures().fit(train)
        T, V = features.transform(train, embedded), features.transform(validation, val_embedded)
        old_features = joblib.load(oldroot / oldmeta["features"]["file"])
        assert sha(oldroot / oldmeta["features"]["file"]) == oldmeta["features"]["sha256"]
        old_views = old_features.transform([r["input"] for r in validation], val_embedded)
        old_models = {task: load_corrected_payload(oldroot, oldmeta["models"][task]) for task in ("intent", "risk")}
        old_scores = {task: probabilities(p, old_views) for task, p in old_models.items()}
        baseline = {"intent": intent_strata(old_scores["intent"], validation, classes, legacy),
                    "risk": risk_strata(old_scores["risk"], validation, risk_classes, old_models["risk"]["thresholds"], legacy),
                    "selective": selective(old_scores["intent"], validation, classes, old_models["intent"]["confidence_policy"], legacy)}
        write_json(output / "baseline_validation.json", baseline)
        trials, intent_candidates, risk_candidates = [], [], []
        def save_trial(trial):
            trials.append(trial)
            write_json(output / "trials.json", trials)
            print(json.dumps({"task": trial["task"], "config": trial["config"],
                "legacy_f1": trial["metrics"]["legacy"]["macro_f1_supported"],
                "synthetic": trial["metrics"]["actions_synthetic"].get("macro_f1_supported",
                    trial["metrics"]["actions_synthetic"].get("exact_match_accuracy")), "seconds": trial["seconds"]}), flush=True)
        for config in configs:
            start = time.monotonic()
            weights = np.asarray([config["new_weight"] if r["source_family"] == "project_authored_actions_v1" else 1.0 for r in train])
            model = intent_model(config).fit(T[config["view"]], y, sample_weight=weights)
            assert list(model.classes_) == classes
            values = scores(model, V[config["view"]])
            metrics = intent_strata(values, validation, classes, legacy)
            reference, current = baseline["intent"]["legacy"], metrics["legacy"]
            eligible = (current["macro_f1_supported"] >= reference["macro_f1_supported"] - .02 and
                        current["accuracy"] >= reference["accuracy"] - .01)
            objective = .65 * current["macro_f1_supported"] + .35 * metrics["actions_synthetic"]["macro_f1_supported"]
            trial = {"task": "intent", "config": config, "metrics": metrics, "eligible": eligible,
                     "objective": objective, "seconds": round(time.monotonic()-start, 3)}
            save_trial(trial)
            intent_candidates.append((trial, model, values))
        eligible = [x for x in intent_candidates if x[0]["eligible"]]
        old_objective = .65 * baseline["intent"]["legacy"]["macro_f1_supported"] + .35 * baseline["intent"]["actions_synthetic"]["macro_f1_supported"]
        selected_intent = max(eligible, key=lambda x:x[0]["objective"]) if eligible else None
        if selected_intent and selected_intent[0]["objective"] <= old_objective:
            selected_intent = None
        train_risks = risk_matrix(train, risk_classes)
        val_risks = risk_matrix(validation, risk_classes)
        for config in protocol["risk_configs"]:
            start = time.monotonic()
            model = RiskLogistic(config["C"], config["balanced"]).fit(T["hybrid"], train_risks)
            values = model.predict_proba(V["hybrid"])
            thresholds = choose_thresholds(val_risks[:legacy], values[:legacy])  # Synthetic rows have no positive risk labels.
            metrics = risk_strata(values, validation, risk_classes, thresholds, legacy)
            eligible = metrics["legacy"]["macro_f1_supported"] >= baseline["risk"]["legacy"]["macro_f1_supported"]
            objective = .9 * metrics["legacy"]["macro_f1_supported"] + .1 * metrics["actions_synthetic"]["exact_match_accuracy"]
            trial = {"task": "risk", "config": config, "metrics": metrics, "eligible": eligible,
                     "objective": objective, "seconds": round(time.monotonic()-start, 3)}
            save_trial(trial)
            risk_candidates.append((trial, model, values, thresholds))
        eligible_risk = [x for x in risk_candidates if x[0]["eligible"]]
        selected_risk = max(eligible_risk, key=lambda x:x[0]["objective"]) if eligible_risk else None
        old_risk_objective = .9 * baseline["risk"]["legacy"]["macro_f1_supported"] + .1 * baseline["risk"]["actions_synthetic"]["exact_match_accuracy"]
        if selected_risk and selected_risk[0]["objective"] <= old_risk_objective:
            selected_risk = None
        if selected_intent:
            trial, model, intent_values = selected_intent
            oof = np.zeros((len(train), len(classes)))
            folds = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42)
            fold_report = []
            for number, (fitting, checking) in enumerate(folds.split(np.zeros(len(train)), y, [r["group_id"] for r in train]), 1):
                rows = [train[i] for i in fitting]
                assert not set(train[i]["group_id"] for i in fitting) & set(train[i]["group_id"] for i in checking)
                feat = RecognitionFeatures().fit(rows)
                TX = feat.transform(rows, embedded[fitting])[trial["config"]["view"]]
                VX = feat.transform([train[i] for i in checking], embedded[checking])[trial["config"]["view"]]
                weights = np.asarray([trial["config"]["new_weight"] if r["source_family"] == "project_authored_actions_v1" else 1. for r in rows])
                fitted = intent_model(trial["config"]).fit(TX, y[fitting], sample_weight=weights)
                positions = np.searchsorted(classes, fitted.classes_)
                oof[np.ix_(checking, positions)] = scores(fitted, VX)
                fold_report.append({"fold":number,"fit_records":len(fitting),"check_records":len(checking),"fit_classes":len(fitted.classes_)})
                print("Completed train-only group calibration fold " + str(number), flush=True)
            ordered = np.sort(oof, axis=1)
            policy = confidence_policy(y, np.asarray(classes)[oof.argmax(axis=1)], ordered[:,-1]-ordered[:,-2])
            policy.update(validation_label_support=dict(Counter(r["label"] for r in validation)), minimum_label_validation_support=5,
                          calibration="train_group_oof_3_folds", validation_support_includes_synthetic=True)
            intent_payload = {"task":"intent", "view":trial["config"]["view"], "classifier":model,
                              "confidence_policy":policy,"classes":classes,"feature_source":"new"}
            write_json(output / "calibration.json", {"folds":fold_report,"policy":policy,"not_independent_human_gold":True})
        else:
            intent_payload = {**old_models["intent"], "feature_source":"legacy"}
            intent_values = old_scores["intent"]
        if selected_risk:
            trial, model, risk_values, thresholds = selected_risk
            risk_payload = {"task":"risk","view":"hybrid","classifier":model,"thresholds":thresholds,
                            "classes":risk_classes,"feature_source":"new"}
        else:
            risk_payload = {**old_models["risk"], "feature_source":"legacy"}
            risk_values = old_scores["risk"]
        joblib.dump(features, private / "features.joblib", compress=3)
        if any(p["feature_source"] == "legacy" for p in (intent_payload,risk_payload)):
            joblib.dump(old_features, private / "legacy_features.joblib", compress=3)
        for name,payload in (("intent",intent_payload),("risk",risk_payload)):
            joblib.dump(payload, private / (name+".joblib"), compress=3)
        metrics = {"intent":intent_strata(intent_values,validation,classes,legacy),
            "risk":risk_strata(risk_values,validation,risk_classes,risk_payload["thresholds"],legacy),
            "selective":selective(intent_values,validation,classes,intent_payload["confidence_policy"],legacy)}
        write_json(output / "validation_metrics.json", metrics)
        write_json(output / "selection.json", {"intent":selected_intent[0] if selected_intent else {"kept_previous":True},
            "risk":selected_risk[0] if selected_risk else {"kept_previous":True},"production_approved":False,"test_opened":False})
        after = input_integrity(ai_root)
        assert protected == after
        record = {"phase":"7.07.3","version":VERSION,"dataset_version":"1.9.0","test_opened":False,
            "runtime_promoted":False,"prior_inputs_unchanged":True,"input_sha256":protected,
            "intent_classes":classes,"risk_classes":risk_classes,
            "files":{p.relative_to(output).as_posix():sha(p) for p in output.glob("*.json")},
            "private_models":{p.relative_to(output).as_posix():sha(p) for p in private.glob("*.joblib")}}
        write_json(output / "manifest.json",record)
        print(json.dumps({"done":True,"metrics":metrics,"selection":{
            "intent_new":bool(selected_intent),"risk_new":bool(selected_risk)}}),flush=True)
    return record

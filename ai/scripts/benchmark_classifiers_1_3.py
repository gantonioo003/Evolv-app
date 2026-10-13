from __future__ import annotations

import json
import sys
from pathlib import Path

from sklearn.metrics import accuracy_score, f1_score
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC, SVC


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.baseline_v11 import char_vectorizer, word_vectorizer  # noqa: E402
from evolv_nlp.dataset import load_partition  # noqa: E402
from sklearn.pipeline import FeatureUnion  # noqa: E402


def features() -> FeatureUnion:
    return FeatureUnion([("word", word_vectorizer(wide=True)), ("char", char_vectorizer(wide=True))])


def candidates() -> dict[str, Pipeline]:
    result: dict[str, Pipeline] = {}
    for value in (0.5, 1.0, 2.0, 4.0):
        result[f"linear_svc_c{value}"] = Pipeline(
            [("features", features()), ("classifier", LinearSVC(C=value, class_weight="balanced"))]
        )
    for value in (0.5, 1.0, 2.0):
        result[f"svc_probability_c{value}"] = Pipeline(
            [
                ("features", features()),
                (
                    "classifier",
                    SVC(
                        C=value,
                        kernel="linear",
                        class_weight="balanced",
                        probability=True,
                        random_state=42,
                    ),
                ),
            ]
        )
    for alpha in (0.1, 0.3, 0.7, 1.0):
        result[f"complement_nb_a{alpha}"] = Pipeline(
            [("features", features()), ("classifier", ComplementNB(alpha=alpha))]
        )
    return result


def main() -> None:
    data_root = AI_ROOT / "data" / "releases" / "1.3.0"
    report: dict[str, dict[str, dict[str, float]]] = {}
    for task in ("intent_classification", "risk_classification"):
        train = load_partition(data_root, "train", task, "1.3.0")
        validation = load_partition(data_root, "validation", task, "1.3.0")
        task_results: dict[str, dict[str, float]] = {}
        for name, model in candidates().items():
            model.fit(train.texts, train.labels)
            predicted = model.predict(validation.texts)
            task_results[name] = {
                "accuracy": round(float(accuracy_score(validation.labels, predicted)), 6),
                "macro_f1": round(
                    float(f1_score(validation.labels, predicted, average="macro", zero_division=0)), 6
                ),
            }
        report[task] = dict(
            sorted(task_results.items(), key=lambda item: item[1]["macro_f1"], reverse=True)
        )
    output = AI_ROOT / "artifacts" / "baseline" / "1.1.0" / "candidate_benchmark.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Compare frozen winners on train/validation, without refitting or opening test."""
import json
import sys
from pathlib import Path

import joblib

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.baseline import assert_compatible_runtime
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.real_data import write_json
from evolv_nlp.semantic_encoder import LocalSemanticEncoder
from evolv_nlp.training_v12 import TASKS, metrics
from evolv_nlp.training_v13 import parent_labels, taxonomy
from evolv_nlp.tuning_semantic import augment_actions, representation


def diagnose():
    output = AI_ROOT / "artifacts/experiments/research_fit_diagnostics.v1.json"
    if output.exists():
        raise ValueError("Diagnostics finalized; do not overwrite")
    definitions = taxonomy(AI_ROOT)
    results = {}
    encoder = None
    for artifact_version in ("1.4.0", "1.5.0"):
        root = AI_ROOT / f"artifacts/baseline/{artifact_version}"
        manifest = json.loads((root / "manifest.json").read_text("utf-8"))
        assert_compatible_runtime(manifest["dependencies"])
        selection = json.loads((root / "metrics.json").read_text("utf-8"))
        metrics_digest = manifest.get("metrics_sha256") or manifest["reports"]["metrics.json"]["sha256"]
        if file_sha256(root / "metrics.json") != metrics_digest:
            raise ValueError("Metrics changed")
        results[artifact_version] = {}
        for task, filename in TASKS.items():
            types = definitions["intents" if task == "intent_classification" else "risks"]
            train = read_jsonl(AI_ROOT / f"data/releases/1.5.0/splits/train/{filename}")
            if artifact_version == "1.5.0" and task == "intent_classification":
                train, _ = augment_actions(AI_ROOT, train, types)
            legacy = read_jsonl(AI_ROOT / f"data/releases/1.3.0/splits/validation/{filename}")
            validation = read_jsonl(AI_ROOT / f"data/releases/1.5.0/splits/validation/{filename}")
            extra = [r for r in validation if r["id"].startswith("v15-")]
            meta = manifest["model_artifacts"][task]
            path = (root / meta["file"]).resolve()
            if not path.is_relative_to(root.resolve()) or file_sha256(path) != meta["sha256"]:
                raise ValueError("Artifact path/hash mismatch")
            model = joblib.load(path)
            partitions = {}
            for split, rows in (("owned_train", train), ("historical_validation", legacy),
                                ("new_authored_validation", extra)):
                texts, labels = [r["text"] for r in rows], [r["label"] for r in rows]
                if artifact_version == "1.4.0":
                    predicted = model.predict(texts).tolist()
                else:
                    if model["encoder"] != manifest["encoder"]:
                        raise ValueError("Encoder mismatch")
                    if encoder is None:
                        encoder = LocalSemanticEncoder(AI_ROOT / "artifacts/encoders/multilingual-minilm")
                    X = representation(encoder.encode(texts), model["lexical_features"].transform(texts),
                                       model["semantic_weight"])
                    predicted = model["classifier"].predict(X).tolist()
                partitions[split] = {"rows": len(rows), "native": metrics(labels, predicted),
                    "parent": metrics(parent_labels(labels, types), parent_labels(predicted, types))}
            gap = partitions["owned_train"]["parent"]["macro_f1"] - \
                partitions["historical_validation"]["parent"]["macro_f1"]
            results[artifact_version][task] = {"model_sha256": meta["sha256"],
                "winner": selection["tasks"][task]["winner"], "partitions": partitions,
                "parent_macro_f1_train_validation_gap": round(gap, 6)}
    payload = {"results": results, "models_refitted": False, "test_opened": False,
        "limitations": ["Validation was already used for selection, not an independent estimate.",
            "A train/validation gap is not proof that variance alone explains errors.",
            "Training and validation have different class/subtype proportions.",
            "Weak external labels are excluded from reported owned-train metrics."]}
    write_json(output, payload)
    return {v: {task: {"train_parent_f1": item["partitions"]["owned_train"]["parent"]["macro_f1"],
                      "validation_parent_f1": item["partitions"]["historical_validation"]["parent"]["macro_f1"],
                      "gap": item["parent_macro_f1_train_validation_gap"]}
                for task, item in tasks.items()} for v, tasks in results.items()}


if __name__ == "__main__":
    print(json.dumps(diagnose(), ensure_ascii=False, indent=2))

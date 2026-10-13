import argparse
import json
import sys
from contextlib import redirect_stdout
from importlib.metadata import version
from pathlib import Path

import joblib

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.baseline import assert_compatible_runtime
from evolv_nlp.dataset import file_sha256
from evolv_nlp.research_models import ResearchTextModel
from evolv_nlp.training_v12 import TASKS


def predict(text, artifact_version):
    if artifact_version not in ("1.4.0", "1.5.0"):
        raise ValueError("Unsupported research version")
    if not isinstance(text, str) or not text.strip() or len(text) > 8000:
        raise ValueError("Text must contain 1 to 8000 characters")
    root = AI_ROOT / f"artifacts/baseline/{artifact_version}"
    manifest = json.loads((root / "manifest.json").read_text("utf-8"))
    assert_compatible_runtime(manifest["dependencies"])
    if artifact_version == "1.5.0":
        for name in ("onnxruntime", "tokenizers"):
            if version(name) != manifest["dependencies"][name]:
                raise ValueError(f"Incompatible research dependency: {name}")
    output = {"version": artifact_version, "private_research_only": True,
              "planner_action_applied": False, "probabilities_calibrated": False}
    encoder = None
    for task in TASKS:
        meta = manifest["model_artifacts"][task]
        path = (root / meta["file"]).resolve()
        if not path.is_relative_to(root.resolve()) or file_sha256(path) != meta["sha256"]:
            raise ValueError("Model path/hash mismatch")
        model = joblib.load(path)
        if artifact_version == "1.4.0":
            if not isinstance(model, ResearchTextModel):
                raise TypeError("Unexpected research model")
            output[task] = str(model.predict([text])[0])
        else:
            from evolv_nlp.semantic_encoder import LocalSemanticEncoder
            from evolv_nlp.tuning_semantic import representation
            if not isinstance(model, dict) or model.get("encoder") != manifest["encoder"]:
                raise TypeError("Unexpected semantic model")
            if encoder is None:
                encoder = LocalSemanticEncoder(AI_ROOT / "artifacts/encoders/multilingual-minilm")
            with redirect_stdout(sys.stderr):
                embedded = encoder.encode([text])
            X = representation(embedded, model["lexical_features"].transform([text]), model["semantic_weight"])
            output[task] = str(model["classifier"].predict(X)[0])
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--version", choices=("1.4.0", "1.5.0"), default="1.5.0")
    args = parser.parse_args()
    if not 1 <= len(args.text) <= 8000:
        parser.error("Text must contain 1 to 8000 characters")
    print(json.dumps(predict(args.text, args.version), ensure_ascii=False, indent=2))

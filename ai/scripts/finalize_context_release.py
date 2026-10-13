"""Finalize packaging metadata without retuning or changing model/evaluation bytes."""
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.context_data import frozen_fingerprints
from evolv_nlp.dataset import file_sha256
from evolv_nlp.real_data import write_json


if __name__ == "__main__":
    frozen_path = AI_ROOT / "data/releases/1.5.0/frozen_fingerprints.json"
    if json.loads(frozen_path.read_text("utf-8")) != frozen_fingerprints(AI_ROOT):
        raise ValueError("Historico/conjunto congelado alterado")
    path = AI_ROOT / "artifacts/baseline/1.3.0/manifest.json"
    manifest = json.loads(path.read_text("utf-8"))
    for metadata in [*manifest["model_artifacts"].values(), *manifest["reports"].values()]:
        if file_sha256(path.parent / metadata["file"]) != metadata["sha256"]:
            raise ValueError("Modelo ou relatorio alterado")
    # Moving the new pipeline to its own versioned module preserves old experiment hashes.
    manifest["source_files"]["src/evolv_nlp/pipeline_v12.py"] = file_sha256(AI_ROOT / "src/evolv_nlp/pipeline_v12.py")
    for name in ("pipeline_v13.py", "conversation.py", "response_policy.py", "risk_rules_v13.py", "entities_v13.py", "privacy.py"):
        manifest["source_files"][f"src/evolv_nlp/{name}"] = file_sha256(AI_ROOT / "src/evolv_nlp" / name)
    manifest["packaging_note"] = "Versioned current pipeline separately; fixed priority preservation. No model weights, hyperparameters or test/metric bytes changed."
    write_json(path, manifest)
    print("Modelos, relatorios e testes congelados preservados; hashes de empacotamento registrados.")

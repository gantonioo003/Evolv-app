from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.baseline import (  # noqa: E402
    assert_compatible_runtime,
    classify,
    load_trusted_model,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classifica intencao e risco com o baseline local do Evolv."
    )
    parser.add_argument("text", help="Mensagem em portugues para classificar")
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=AI_ROOT / "artifacts" / "baseline" / "1.0.0",
        help="Diretorio dos artefatos versionados",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    manifest = json.loads(
        (args.artifacts / "manifest.json").read_text(encoding="utf-8")
    )
    assert_compatible_runtime(manifest["dependencies"])
    output: dict[str, object] = {"text": args.text}
    for output_name, task in (
        ("intent", "intent_classification"),
        ("risk", "risk_classification"),
    ):
        artifact = manifest["model_artifacts"][task]
        model = load_trusted_model(
            args.artifacts / artifact["file"],
            artifact["sha256"],
        )
        output[output_name] = classify(model, args.text).to_dict()
    print(json.dumps(output, ensure_ascii=False, indent=2))

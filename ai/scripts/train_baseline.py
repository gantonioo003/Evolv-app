from __future__ import annotations

import sys
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.training import train_all  # noqa: E402


if __name__ == "__main__":
    artifact_root = AI_ROOT / "artifacts" / "baseline" / "1.0.0"
    manifest = train_all(AI_ROOT / "data", artifact_root)
    print(
        "Baseline treinado: "
        f"{len(manifest['model_artifacts'])} modelos em "
        f"{artifact_root.relative_to(AI_ROOT.parent)}"
    )

from __future__ import annotations

import json
import sys
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.training_v11 import train_all  # noqa: E402


if __name__ == "__main__":
    manifest = train_all(
        AI_ROOT / "data" / "releases" / "1.3.0",
        AI_ROOT / "artifacts" / "baseline" / "1.1.0",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

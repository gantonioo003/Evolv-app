from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.real_data import import_external


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate and import original PT-BR questions; not gold labels.")
    parser.add_argument("source", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(import_external(arguments.source, AI_ROOT), ensure_ascii=False, indent=2))

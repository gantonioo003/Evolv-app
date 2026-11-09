"""Prepare a versioned local knowledge release; does not train or build embeddings."""
import argparse
from datetime import date
import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.preparation import prepare, read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--config", type=Path, default=AI_ROOT / "configs/rag.preparation.v1.json")
    parser.add_argument("--output", type=Path, default=AI_ROOT / "data/rag/1.0.0")
    args = parser.parse_args()
    print(json.dumps(prepare(AI_ROOT, args.output, read(args.config), args.as_of), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

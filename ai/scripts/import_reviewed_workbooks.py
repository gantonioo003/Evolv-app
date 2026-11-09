import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.review_release import import_release

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    result = import_release(args.source, AI_ROOT)
    print(json.dumps({"total": result["total_imported"], "coverage": {
        key: value["records"] for key, value in result["coverage"].items()}}, indent=2))

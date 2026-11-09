import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.pipeline_v14 import ReviewedCoachPipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--context", default="")
    parser.add_argument("--version", choices=("1.6.0", "1.6.1"), default="1.6.0")
    args = parser.parse_args()
    print(json.dumps(ReviewedCoachPipeline(AI_ROOT, args.version).analyze(args.text, args.context), ensure_ascii=True, indent=2))

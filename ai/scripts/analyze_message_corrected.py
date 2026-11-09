import argparse
import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.corrected_pipeline import CorrectedCoachPipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--context", default="")
    args = parser.parse_args()
    print(json.dumps(CorrectedCoachPipeline(AI_ROOT).analyze(args.text, args.context), ensure_ascii=True, indent=2))

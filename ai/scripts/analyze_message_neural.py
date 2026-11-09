import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.neural_pipeline import NeuralCoachPipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--context", default="")
    args = parser.parse_args()
    print(json.dumps(NeuralCoachPipeline(AI_ROOT).analyze(args.text, args.context), ensure_ascii=True, indent=2))

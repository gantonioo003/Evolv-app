"""Evaluate the fixed checkpoint and decoding protocol; never update weights."""
import argparse
import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))


if __name__ == "__main__":
    from evolv_tinylm.lm_evaluation import evaluate_release

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=AI_ROOT / "artifacts/tinylm_data/1.0.0")
    parser.add_argument("--corpus", type=Path, default=AI_ROOT / "data/lm_corpus/1.2.0")
    parser.add_argument("--tokenizer", type=Path, default=AI_ROOT / "artifacts/tokenizer/1.0.0")
    parser.add_argument("--run", type=Path, default=AI_ROOT / "artifacts/tinylm_training/1.0.0")
    parser.add_argument("--protocol", type=Path, default=AI_ROOT / "configs/tinylm.evaluation.v1.json")
    parser.add_argument("--output", type=Path, default=AI_ROOT / "artifacts/tinylm_evaluation/1.0.0")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    print(json.dumps(evaluate_release(args.data, args.corpus, args.tokenizer, args.run, args.protocol,
                                      args.output, device=args.device), ensure_ascii=True, indent=2))

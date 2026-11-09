"""Phase 7.03.2: encode the frozen corpus without training a new tokenizer."""
import argparse
import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_tinylm.data import prepare_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=AI_ROOT / "data/lm_corpus/1.2.0")
    parser.add_argument("--tokenizer", type=Path, default=AI_ROOT / "artifacts/tokenizer/1.0.0")
    parser.add_argument("--output", type=Path, default=AI_ROOT / "artifacts/tinylm_data/1.0.0")
    parser.add_argument("--context-length", type=int, default=256)
    args = parser.parse_args()
    print(json.dumps(prepare_data(args.corpus, args.tokenizer, args.output,
                                  context_length=args.context_length), ensure_ascii=True, indent=2))

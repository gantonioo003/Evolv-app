"""Train phase 7.03.1; never change the corpus or an existing artifact."""
import argparse
import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_tinylm.tokenizer_training import train_tokenizer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=AI_ROOT / "data/lm_corpus/1.2.0")
    parser.add_argument("--output", type=Path, default=AI_ROOT / "artifacts/tokenizer/1.0.0")
    parser.add_argument("--vocab-size", type=int, default=8192)
    parser.add_argument("--min-frequency", type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(train_tokenizer(args.corpus, args.output, vocab_size=args.vocab_size,
                                     min_frequency=args.min_frequency), ensure_ascii=True, indent=2))

"""Inspect how the educational TinyLM tokenizer represents a message."""
import argparse
import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_tinylm.tokenizer import EvolvTokenizer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text")
    parser.add_argument("--artifact", type=Path, default=AI_ROOT / "artifacts/tokenizer/1.0.0")
    parser.add_argument("--document", action="store_true", help="Adicionar BOS e EOS ao documento completo.")
    args = parser.parse_args()
    print(json.dumps(EvolvTokenizer.load(args.artifact).inspect(args.text, document=args.document),
                     ensure_ascii=True, indent=2))

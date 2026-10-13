import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.tuning_semantic import tune_semantic
from evolv_nlp.semantic_encoder import prepare_encoder

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()
    result = prepare_encoder(AI_ROOT / "artifacts/encoders/multilingual-minilm") if args.download_only else tune_semantic(AI_ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))

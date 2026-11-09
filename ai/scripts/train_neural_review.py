import json
import argparse
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.neural_review import train, register_experiment

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--register-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(register_experiment(AI_ROOT) if args.register_only else train(AI_ROOT), indent=2))

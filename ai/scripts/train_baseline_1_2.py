from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.training_v12 import train_all

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train a versioned experimental baseline; historical final tests stay closed.")
    parser.add_argument("--experimental-web-training", action="store_true",
                        help="Local weak-label experiment only. Sources have unverified rights; no deployment, redistribution or LM ingestion.")
    arguments = parser.parse_args()
    print(json.dumps(train_all(AI_ROOT, arguments.experimental_web_training), ensure_ascii=False, indent=2))

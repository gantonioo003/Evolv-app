import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.research_data import RELEASE, prepare_research
from evolv_nlp.tuning_v14 import tune

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    if not (AI_ROOT / f"data/releases/{RELEASE}/manifest.json").exists():
        print(json.dumps(prepare_research(args.source, AI_ROOT), ensure_ascii=False, indent=2), flush=True)
    print(json.dumps(tune(AI_ROOT), ensure_ascii=False, indent=2))

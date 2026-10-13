from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.pipeline_v12 import DevelopmentCoachPipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a PT-BR message with the opt-in experimental NLP, never apply changes.")
    parser.add_argument("text")
    parser.add_argument("--reference-date", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    print(json.dumps(DevelopmentCoachPipeline(AI_ROOT).analyze(args.text, args.reference_date), ensure_ascii=False, indent=2))

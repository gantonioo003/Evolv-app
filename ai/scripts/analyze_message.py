from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.pipeline import load_pipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa a pipeline estruturada do Coach Evolv."
    )
    parser.add_argument("text", help="Mensagem em portugues para analisar.")
    parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        default=date.today(),
        help="Data ISO usada para resolver hoje e amanha.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    pipeline = load_pipeline(AI_ROOT)
    result = pipeline.analyze(arguments.text, arguments.reference_date)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))

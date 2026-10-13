from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.entities import extract_entities, load_entity_catalog  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrai entidades tipadas de uma mensagem em portugues."
    )
    parser.add_argument("text", help="Mensagem a analisar")
    parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        default=date.today(),
        help="Data ISO usada para resolver hoje, amanha e dias da semana",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=AI_ROOT / "data" / "catalogs" / "entity_catalogs.v1.json",
        help="Catalogo versionado de entidades",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    catalog = load_entity_catalog(args.catalog)
    result = extract_entities(args.text, catalog, args.reference_date)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

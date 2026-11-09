from __future__ import annotations

import json
import argparse
from collections import Counter
from datetime import date
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = AI_ROOT / "data"


def load_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resumo do conhecimento; não mede a qualidade do RAG.")
    parser.add_argument("--release", type=Path, help="Pasta da versão, por exemplo data/knowledge/1.2.0")
    args = parser.parse_args()
    sources = load_json(args.release / "sources.json" if args.release else DATA_ROOT / "metadata" / "sources.v1.json")["sources"]
    knowledge = load_json(args.release / "knowledge_chunks.json" if args.release else DATA_ROOT / "knowledge" / "knowledge_chunks.v1.json")
    chunks = knowledge["chunks"]

    domain_counts = Counter(chunk["domain"] for chunk in chunks)
    mode_counts = Counter(chunk["response_mode"] for chunk in chunks)
    risk_counts = Counter(
        risk for chunk in chunks for risk in chunk.get("risk_tags", [])
    )
    internal_count = sum("path" in source for source in sources)

    print(f"Base de conhecimento Evolv {knowledge['version']}")
    print(f"Fontes: {len(sources)} ({internal_count} internas)")
    print(f"Trechos: {len(chunks)}")
    print("Dominios:")
    for domain, count in sorted(domain_counts.items()):
        print(f"- {domain}: {count}")
    print("Modos de resposta:")
    for mode, count in sorted(mode_counts.items()):
        print(f"- {mode}: {count}")
    print(f"Riscos cobertos: {len(risk_counts)}")

    today = date.today()
    due_sources = sorted(
        source["id"]
        for source in sources
        if date.fromisoformat(source["review_due_at"]) <= today
    )
    due_chunks = sorted(
        chunk["id"]
        for chunk in chunks
        if date.fromisoformat(chunk["review_due_at"]) <= today
    )
    print(f"Fontes vencidas: {len(due_sources)}")
    print(f"Trechos vencidos: {len(due_chunks)}")


if __name__ == "__main__":
    main()

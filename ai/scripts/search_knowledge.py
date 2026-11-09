"""Build or query the local knowledge index."""
import argparse
import json
from pathlib import Path
import sys
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.search import Encoder, Search, build
from evolv_rag.retrieval import HybridSearch
from evolv_rag.retrieval_runtime import DEFAULT_VERSION, load_search
from evolv_rag.preparation import read

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query", nargs="?")
    p.add_argument("--build", action="store_true")
    p.add_argument("--index", type=Path)
    p.add_argument("--base", type=Path)
    p.add_argument("--legacy", action="store_true", help="Busca semântica e base antigas")
    p.add_argument("--previous", action="append", default=[], help="Mensagem anterior do usuário; pode repetir")
    p.add_argument("--min-score", type=float)
    args = p.parse_args()
    if args.build:
        index = args.index or AI_ROOT / "artifacts/rag" / ("1.0.0" if args.legacy else "1.1.1")
        base = args.base or AI_ROOT / "data/rag" / ("1.0.0" if args.legacy else "1.1.1")
        build(base, index, Encoder(AI_ROOT / "artifacts/encoders/multilingual-minilm"))
        print("Index built:", index)
    elif args.query:
        version = "1.0.0" if args.legacy else DEFAULT_VERSION
        search = load_search(AI_ROOT, version)
        if args.index:
            search = Search(args.index, search.encoder) if args.legacy else HybridSearch(args.index, search.encoder,
                read(AI_ROOT / "configs/retrieval.runtime.v1.json")["parameters"])
        if args.legacy:
            result = search.query(args.query, min_score=args.min_score if args.min_score is not None else .45)
        else:
            result = search.query_conversation(args.query, [{"role": "user", "content": t} for t in args.previous],
                                               min_score=args.min_score)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        p.error("Provide a query or --build")

if __name__ == "__main__":
    main()

"""Freeze a retrieval development protocol, select on validation, open reserved cases once."""
from datetime import date
from itertools import product
from pathlib import Path
import json
import sys
import time
AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI / "src"))
from evolv_rag.preparation import digest, read, write
from evolv_rag.search import Encoder, Search, build
from evolv_rag.retrieval import HybridSearch
from evolv_rag.knowledge_review import protected_hashes


class EvaluationEncoder:
    """Memory-only memo for this authored suite; not installed in the Coach runtime."""
    def __init__(self, encoder):
        self.encoder, self.manifest, self.cache = encoder, encoder.manifest, {}
    def encode(self, texts):
        import numpy as np
        for text in texts:
            if text not in self.cache:
                self.cache[text] = self.encoder.encode([text])[0]
        return np.asarray([self.cache[t] for t in texts])


def measure(search, cases, on, legacy=False):
    rows = []
    for case in cases:
        started = time.perf_counter()
        if legacy:
            prior = [m["content"] for m in case["history"] if m["role"] == "user"]
            query = "\n".join(prior[-1:] + [case["text"]]) if len(case["text"].split()) < 8 else case["text"]
            result = search.query(query, as_of=on)
        else:
            result = search.query_conversation(case["text"], case["history"], as_of=on)
        ids = [m["document_id"] for m in result["matches"]]
        ranks = [ids.index(i) + 1 for i in case["expected"] if i in ids]
        rank = min(ranks, default=None)
        rows.append({"id": case["id"], "category": case["category"], "question": case["text"],
            "history": case["history"], "expected": case["expected"], "rank": rank,
            "seconds": time.perf_counter() - started, "status": result["status"],
            "context": result.get("context"), "retrieved": [{"document_id": m["document_id"], "score": m["score"]} for m in result["matches"]]})
    def summary(items):
        positives = [r for r in items if r["expected"]]
        negatives = [r for r in items if not r["expected"]]
        return {"positive_queries": len(positives), "negative_queries": len(negatives),
            "hit_at_1": sum(r["rank"] == 1 for r in positives) / len(positives) if positives else None,
            "hit_at_3": sum(r["rank"] is not None for r in positives) / len(positives) if positives else None,
            "mrr_at_3": sum(1 / r["rank"] if r["rank"] else 0 for r in positives) / len(positives) if positives else None,
            "rejection_rate": sum(r["status"] == "no_evidence" for r in negatives) / len(negatives) if negatives else None}
    metrics = summary(rows)
    metrics["by_category"] = {k: summary([r for r in rows if r["category"] == k]) for k in sorted({r["category"] for r in rows})}
    return {"metrics": metrics, "cases": rows}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=AI / "artifacts/retrieval_evaluation/1.0.0")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Evaluation exists; choose a new version")
    args.output.mkdir(parents=True)
    on = date(2026, 11, 3)
    suite_file = AI / "data/evaluation/retrieval.v2.json"
    suite = read(suite_file)
    protected = protected_hashes(AI)
    candidates = [{"lexical_weight": w, "context_weight": c, "min_score": t}
                  for w, c, t in product([0., .25, .45], [0., .55, .80], [.30, .35, .40, .45, .50])]
    write(args.output / "protocol.json", {"as_of": on.isoformat(), "suite_sha256": digest(suite_file),
        "purpose": suite["purpose"], "candidate_grid": candidates,
        "selection": "Validation only; require >=90% rejection on validation negatives, then maximize mean category Hit@3 (single, followup, switch), break ties by MRR and higher threshold. If no eligible candidate, report failure without promotion.",
        "reserved_opened_only_after_selection": True,
        "fixed_rules": {"bm25_k1": 1.2, "bm25_b": .75, "duplicate_cosine": .94,
                        "context_unsupported_semantic": .30, "context_unsupported_lexical": .12,
                        "independent_subject_semantic": .62, "subject_document_cosine": .45},
        "protected": protected, "code_sha256": {name: digest(AI / name) for name in [
            "src/evolv_rag/retrieval.py", "scripts/evaluate_retrieval.py", "src/evolv_rag/search.py"]}})
    encoder = EvaluationEncoder(Encoder(AI / "artifacts/encoders/multilingual-minilm"))
    index = AI / "artifacts/rag/1.1.0"
    if not index.exists():
        build(AI / "data/rag/1.1.0", index, encoder)
    trials, best = [], None
    for i, config in enumerate(candidates):
        search = HybridSearch(index, encoder, config)
        evaluation = measure(search, suite["validation"], on)
        metrics = evaluation["metrics"]
        row = {"id": i, "config": config, "metrics": metrics}
        trials.append(row)
        eligible = metrics["rejection_rate"] >= .9
        score = sum(metrics["by_category"][k]["hit_at_3"] for k in ["single", "followup", "switch"]) / 3
        rank = (score, metrics["mrr_at_3"], config["min_score"], -config["lexical_weight"], -config["context_weight"])
        if eligible and (best is None or rank > best[0]):
            best = rank, row, evaluation
        if i % 9 == 0:
            print(json.dumps({"trial": i, "hit_at_3": metrics["hit_at_3"], "reject": metrics["rejection_rate"]}), flush=True)
    write(args.output / "trials.json", trials)
    if best is None:
        raise ValueError("No candidate meets declared validation rejection requirement")
    _, selection, validation = best
    write(args.output / "selection.json", selection)
    write(args.output / "selected_validation.json", validation)
    # The chosen configuration is persisted before evaluating any reserved case.
    selected = HybridSearch(index, encoder, selection["config"])
    reserved = measure(selected, suite["reserved"], on)
    write(args.output / "reserved.json", reserved)
    for name, directory in [("old_67", "1.0.0"), ("semantic_107", "1.1.0")]:
        search = Search(AI / "artifacts/rag" / directory, encoder)
        write(args.output / (name + ".json"), {"validation": measure(search, suite["validation"], on, True),
                                             "reserved": measure(search, suite["reserved"], on, True)})
    if protected != protected_hashes(AI):
        raise ValueError("Protected data, models or old index changed")
    summary = {"selected_config": selection["config"], "validation": validation["metrics"],
        "reserved": reserved["metrics"], "independent_human_test": False, "models_or_safety_thresholds_changed": False,
        "index_rows": len(selected.rows), "app_promoted": False}
    write(args.output / "summary.json", summary)
    write(args.output / "manifest.json", {"index_manifest_sha256": digest(index / "manifest.json"),
        "outputs": {p.name: digest(p) for p in sorted(args.output.iterdir()) if p.is_file()}})
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

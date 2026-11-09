"""All-message extraction plus like-for-like historical entity regression."""
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.entities import entity_signature
from evolv_nlp import entities_v13 as old, entities_v14 as new
from evolv_nlp.real_data import write_json, write_jsonl
from evolv_nlp.review_release import load_partition


def score(tp, predicted, expected):
    precision = tp / predicted if predicted else 0.0
    recall = tp / expected if expected else 0.0
    return {"true_positive": tp, "predicted": predicted, "expected": expected,
            "precision": precision, "recall": recall,
            "micro_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}


def evaluate():
    output = AI_ROOT / "artifacts/entities/1.3.0"
    if (output / "manifest.json").exists():
        raise ValueError("Entity audit finalized; do not overwrite")
    old_catalog, catalog = old.load_catalog(AI_ROOT), new.load_catalog(AI_ROOT)
    old_types = old.supported_entity_types(old_catalog)
    benchmark = read_jsonl(AI_ROOT / "data/entities/evaluation.v1.jsonl")
    regressions = {}
    for name, extractor, supplied in (("before", old.extract_entities, old_catalog), ("after", new.extract_entities, catalog)):
        totals = Counter()
        for row in benchmark:
            expected = Counter(entity_signature(e) for e in row["expected"] if e["entity_type"] in old_types)
            result = extractor(row["text"], supplied, date.fromisoformat(row["reference_date"]))
            predicted = Counter(entity_signature(e) for e in result.entities if e.entity_type in old_types)
            totals.update(tp=sum((expected & predicted).values()), predicted=sum(predicted.values()), expected=sum(expected.values()))
        regressions[name] = score(totals["tp"], totals["predicted"], totals["expected"])
    manifest = json.loads((AI_ROOT / "data/releases/1.7.0/manifest.json").read_text("utf-8"))
    extracted, counts, negations = [], Counter(), Counter()
    for partition in manifest["coverage"]:
        for row in load_partition(AI_ROOT, partition):
            result = new.extract_entities(row["text"], catalog, date(2026, 10, 18))
            for entity in result.entities:
                if row["text"][entity.start:entity.end] != entity.text:
                    raise ValueError("Entity span mismatch")
                counts[entity.entity_type] += 1
                if entity.attributes.get("negated"):
                    negations[entity.entity_type] += 1
            extracted.append({"id": row["id"], "partition": partition,
                              "entities": [e.to_dict() for e in result.entities]})
            if len(extracted) % 1000 == 0:
                print(f"Entities audited: {len(extracted)}/12179", flush=True)
    if len(extracted) != 12179:
        raise ValueError("Some imported messages were not extracted")
    private = AI_ROOT / "artifacts/baseline/1.6.0/private/entity_extractions_all_12179.jsonl"
    write_jsonl(private, extracted)
    result = {"extractor_version": new.EXTRACTOR_VERSION,
        "messages_processed": len(extracted), "declared_entity_types": 89,
        "supported_types_before": len(old_types), "supported_types_after": len(new.supported_entity_types(catalog)),
        "supported_types": sorted(new.supported_entity_types(catalog)),
        "observed_entity_mentions_not_recall": dict(counts), "negated_mentions": dict(negations),
        "historical_regression": {"messages": len(benchmark), "projection": "same_50_previously_supported_types_only",
            "already_observed_regression_not_fresh_test": True, **regressions},
        "new_type_independent_f1": None,
        "limitation": "Workbooks do not contain exhaustive entity/span gold; 80 active types is not 80 validated types",
        "private_extractions_sha256": file_sha256(private),
        "sources": {name: file_sha256(AI_ROOT / name) for name in
            ("src/evolv_nlp/entities_v14.py", "data/catalogs/entity_catalogs.extension.v1.3.json",
             "scripts/evaluate_reviewed_entities.py")}}
    write_json(output / "manifest.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in {"observed_entity_mentions_not_recall", "sources", "supported_types"}}, indent=2))


if __name__ == "__main__":
    evaluate()

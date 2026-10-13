import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.entities import entity_signature, load_entity_catalog
from evolv_nlp.entities_v12 import extract_entities as previous_extract
from evolv_nlp.entities_v13 import extract_entities, load_catalog, supported_entity_types
from evolv_nlp.real_data import write_json


def evaluate(rows, extractor, catalog):
    totals = Counter()
    per_type = {}
    errors = []
    for row in rows:
        expected = Counter(entity_signature(e) for e in row["expected"])
        predicted = Counter(entity_signature(e) for e in extractor(row["text"], catalog,
            date.fromisoformat(row.get("reference_date", "2026-10-10"))).entities if not row.get("types") or e.entity_type in row["types"])
        tp = expected & predicted
        totals.update(expected=sum(expected.values()), predicted=sum(predicted.values()), tp=sum(tp.values()), exact=int(expected == predicted))
        for kind in {k for k, _ in expected | predicted}:
            counters = per_type.setdefault(kind, Counter())
            counters.update(expected=sum(v for (k, _), v in expected.items() if k == kind),
                            predicted=sum(v for (k, _), v in predicted.items() if k == kind),
                            tp=sum(v for (k, _), v in tp.items() if k == kind))
        if expected != predicted:
            errors.append({"id": row.get("id"), "text": row["text"],
                           "missing": list((expected - predicted).elements()), "unexpected": list((predicted - expected).elements())})
    def scores(counts):
        p = counts["tp"] / counts["predicted"] if counts["predicted"] else 0
        r = counts["tp"] / counts["expected"] if counts["expected"] else 0
        return {"precision": round(p, 6), "recall": round(r, 6), "f1": round(2*p*r/(p+r), 6) if p+r else 0}
    return {"rows": len(rows), "exact": round(totals["exact"]/len(rows), 6), "micro": scores(totals),
            "counts": dict(totals), "per_type": {k: {**dict(v), **scores(v)} for k, v in per_type.items()}, "errors": errors}


if __name__ == "__main__":
    output = AI_ROOT / "artifacts/entities/1.2.0"
    if (output / "metrics.json").exists():
        raise ValueError("Relatorio finalizado; usar nova versao")
    old_catalog = load_entity_catalog(AI_ROOT / "data/catalogs/entity_catalogs.v1.json")
    catalog = load_catalog(AI_ROOT)
    legacy = read_jsonl(AI_ROOT / "data/evaluation/entity_holdout.v1.jsonl")
    # Compare only types annotated in the old holdout; separately report new feature coverage.
    allowed = {e["entity_type"] for r in legacy for e in r["expected"]}
    legacy_scoped = [{**r, "types": sorted(allowed)} for r in legacy]
    new_checks = json.loads((AI_ROOT / "data/entities/context_checks.v1.json").read_text("utf-8"))["cases"]
    report = {"version": "1.2.0", "supported_types": len(supported_entity_types(catalog)),
              "historical_annotated_types_only": {
                  "previous_1_1": evaluate(legacy_scoped, previous_extract, old_catalog),
                  "new_1_2": evaluate(legacy_scoped, extract_entities, catalog)},
              "new_development_feature_checks": {"previous_1_1": evaluate(new_checks, previous_extract, old_catalog),
                                                 "new_1_2": evaluate(new_checks, extract_entities, catalog)},
              "warning": "Old holdout already observed; new feature checks are scoped authored development tests, not independent real-world precision/recall.",
              "inputs": {str(p.relative_to(AI_ROOT)): file_sha256(p) for p in
                  [AI_ROOT / "data/evaluation/entity_holdout.v1.jsonl", AI_ROOT / "data/entities/context_checks.v1.json",
                   AI_ROOT / "src/evolv_nlp/entities_v13.py", AI_ROOT / "data/catalogs/entity_catalogs.extension.v1.2.json"]}}
    write_json(output / "metrics.json", report)
    print(json.dumps({k: v for k, v in report.items() if k in ("version", "supported_types", "warning")}, indent=2))

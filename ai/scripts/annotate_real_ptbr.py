from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.entities import load_entity_catalog
from evolv_nlp.entities_v12 import extract_entities
from evolv_nlp.real_data import write_json, write_jsonl
from evolv_nlp.risk_rules_v12 import detect_risks
from evolv_nlp.training_v12 import weak_intent


def annotate(ai_root: Path) -> dict:
    root = ai_root / "data/external_private/ptbr-10000-1.0.0"
    rows = read_jsonl(root / "mensagens.jsonl")
    catalog = load_entity_catalog(ai_root / "data/catalogs/entity_catalogs.v1.json")
    counts, intents, risks = Counter(), Counter(), Counter()
    annotations = []
    for row in rows:
        if row["split"] != "train":
            continue
        text = row["texto_original"]
        extraction = extract_entities(text, catalog, date(2026, 10, 10))
        signals = detect_risks(text)
        label = weak_intent(text)
        counts.update(e.entity_type for e in extraction.entities)
        intents.update([label or "unknown"])
        risks.update(signals.risks or ["unknown"])
        candidates = extraction.to_dict()["entities"]
        for entity in candidates:
            if entity["entity_type"] in ("source_date", "target_date") and entity["attributes"].get("kind") not in ("iso_date", "absolute_date"):
                entity["value"] = {"expression": entity["text"], "resolved_date": None}
                entity["attributes"]["original_reference_date_unknown"] = True
        annotations.append({"id": row["id_mensagem"], "source_split": "train",
                            "group_id": row["split_group_id"], "intent_candidate": label,
                            "risks": signals.to_dict(), "entities": candidates,
                            "review_status": "machine_candidates_not_gold", "training_allowed": False,
                            "relative_dates_are_symbolic_candidates": True,
                            "reference_date": "2026-10-10"})
    path = root / "expanded_train_candidates.jsonl"
    write_jsonl(path, annotations)
    report = {"rows": len(annotations), "intent_candidates": dict(intents), "risk_candidates": dict(risks),
              "entity_spans": sum(counts.values()), "entity_types_found": len(counts), "entity_counts": dict(counts),
              "external_validation_and_test_annotated": False, "none_inferred_from_no_rule": False,
              "text_is_not_gold": True, "candidates_sha256": file_sha256(path)}
    write_json(ai_root / "data/releases/1.4.0/annotation_report.json", report)
    return report


if __name__ == "__main__":
    print(json.dumps(annotate(AI_ROOT), ensure_ascii=False, indent=2))

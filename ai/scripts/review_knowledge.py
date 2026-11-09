"""Publish the reviewed knowledge snapshot, without building/promoting a semantic index."""
import argparse
from pathlib import Path
import sys
import json
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.knowledge_review import compile_review, publish_review

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=AI_ROOT / "data/knowledge/1.2.0")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    report = compile_review(AI_ROOT)["coverage.json"] if args.check_only else publish_review(AI_ROOT, args.output)
    print(json.dumps({"phase": report["phase"], "documents_before": report["before"]["documents"],
        "documents_after": report["after"]["documents"], "closed_topic_gaps": report["closed_nominal_topic_gaps"],
        "new_risk_coverage": report["newly_addressed_risk_tags"], "remaining_gaps": report["residual_scope_gaps"]}, ensure_ascii=False, indent=2))

"""Prepare v1.9 action data without training or changing the existing release."""
from pathlib import Path
import json
import sys
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.action_release import build

if __name__ == "__main__":
    report = build(AI_ROOT)
    print(json.dumps({k: report[k] for k in ("dataset_version", "original_rows_preserved", "added_records", "candidates")}, ensure_ascii=False))
    print(json.dumps({"added_coverage": report["added_coverage"], "excluded_candidates": report["excluded_candidates"]}, ensure_ascii=False))

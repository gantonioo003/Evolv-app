import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.corrected_training import search

if __name__ == "__main__":
    result = search(AI_ROOT)
    print(json.dumps({"selected": result["selected"], "trials": len(result["trials"]), "test_opened": False}, indent=2))

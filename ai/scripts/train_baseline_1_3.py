import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.training_v13 import fit_all

if __name__ == "__main__":
    print(json.dumps(fit_all(AI_ROOT), ensure_ascii=False, indent=2))

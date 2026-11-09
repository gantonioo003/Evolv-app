import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.review_training import train

if __name__ == "__main__":
    print(json.dumps(train(AI_ROOT), indent=2))

from pathlib import Path
import sys
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.recognition_experiment import run

if __name__ == "__main__":
    run(AI_ROOT)

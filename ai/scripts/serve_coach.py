"""Start internal loopback API. Set EVOLV_AI_SERVICE_KEY in the environment."""
from pathlib import Path
import sys
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

if __name__ == "__main__":
    import uvicorn
    # A single process owns GPU weights and in-memory sessions.
    uvicorn.run("evolv_api.app:create_app", factory=True, host="127.0.0.1",
                port=8010, workers=1, access_log=False)

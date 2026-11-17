"""Start internal loopback API. Set EVOLV_AI_SERVICE_KEY in the environment."""
from pathlib import Path
import os
import sys
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

def app_factory():
    from evolv_api.app import Settings, create_app

    settings = Settings.from_env()
    if not (model := os.environ.get("EVOLV_AI_GGUF_MODEL")):
        return create_app(settings)

    from evolv_openlm.gguf import GgufLM
    from evolv_rag.coach import Coach
    from evolv_rag.retrieval_runtime import load_search

    if (settings.mode, settings.interpreter, settings.variant) != ("generate", "qwen", "original"):
        raise ValueError("GGUF local requer o modo de interpretação qwen com os pesos originais.")

    def load():
        return Coach(None, load_search(AI_ROOT, settings.retrieval_version), GgufLM(model))

    return create_app(settings, loader=load)


if __name__ == "__main__":
    import uvicorn
    # Keep in-memory sessions in a single worker.
    uvicorn.run(app_factory(), host="127.0.0.1",
                port=8010, workers=1, access_log=False)

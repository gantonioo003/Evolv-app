"""Complete the pinned model cache using parallel ranges and official hashes."""
import argparse
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_openlm.runtime import DEFAULT_CACHE, load_settings
from evolv_openlm.parallel_download import download
from evolv_openlm.sft_data import write_json

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--chunk-mib", type=int, default=8)
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    a = p.parse_args()
    config = load_settings()
    out = AI_ROOT / "artifacts/openlm_download/1.0.0"
    write_json(out / "progress.json", {"status": "starting"})
    result = download(config["model_id"], config["revision"], a.cache_dir, a.workers, a.chunk_mib,
                      progress=lambda x: write_json(out / "progress.json", x))
    result.pop("snapshot")
    write_json(out / "download_manifest.json", result)
    write_json(out / "progress.json", {"status": "complete", "verified_complete": True})

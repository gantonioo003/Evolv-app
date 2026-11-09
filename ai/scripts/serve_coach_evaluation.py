"""Local evaluation launcher; instruments the unchanged real Coach runtime."""
from pathlib import Path
import argparse
import json
import sys
import threading
import time

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--backend-pid", type=int)
    args = parser.parse_args()
    import psutil
    import uvicorn
    process = psutil.Process()
    stop = threading.Event()
    started = time.monotonic()
    stats = {"sampling_seconds": 1, "samples": 0, "rss_peak_bytes": 0,
             "cuda_allocated_peak_bytes": 0, "cuda_reserved_peak_bytes": 0,
             "torch_peak_allocated_bytes": 0, "torch_peak_reserved_bytes": 0}

    def sample():
        while not stop.is_set():
            try:
                stats["samples"] += 1
                stats["rss_peak_bytes"] = max(stats["rss_peak_bytes"], process.memory_info().rss)
                stats["rss_last_bytes"] = process.memory_info().rss
                if args.backend_pid:
                    rss = psutil.Process(args.backend_pid).memory_info().rss
                    stats["backend_rss_peak_bytes"] = max(stats.get("backend_rss_peak_bytes", 0), rss)
                    stats["backend_rss_last_bytes"] = rss
                stats["elapsed_seconds"] = time.monotonic() - started
                torch = sys.modules.get("torch")
                if torch is not None and torch.cuda.is_initialized():
                    for key, value in {
                        "cuda_allocated_peak_bytes": torch.cuda.memory_allocated(),
                        "cuda_reserved_peak_bytes": torch.cuda.memory_reserved(),
                        "torch_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                        "torch_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                    }.items():
                        stats[key] = max(stats[key], value)
                    stats["gpu"] = torch.cuda.get_device_name(0)
                    stats["gpu_total_bytes"] = torch.cuda.get_device_properties(0).total_memory
                args.metrics.parent.mkdir(parents=True, exist_ok=True)
                temp = args.metrics.with_suffix(".tmp")
                temp.write_text(json.dumps(stats, indent=2), encoding="utf-8")
                temp.replace(args.metrics)
            except (OSError, RuntimeError, AttributeError, psutil.Error):
                pass
            stop.wait(1)

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        uvicorn.run("evolv_api.app:create_app", factory=True, host="127.0.0.1",
                    port=args.port, workers=1, access_log=False, log_level="warning")
    finally:
        stop.set()
        thread.join(timeout=3)


if __name__ == "__main__":
    main()

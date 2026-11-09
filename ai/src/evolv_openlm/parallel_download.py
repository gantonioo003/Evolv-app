"""Resumable ranged transfer of a fixed official snapshot; verify before use."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import math
from pathlib import Path
import shutil
import time
import urllib.request


def file_digest(path, lfs=True):
    result = hashlib.sha256() if lfs else hashlib.sha1()
    if not lfs:
        result.update(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def download(model_id, revision, cache_dir, workers=8, chunk_mib=8, progress=None):
    from huggingface_hub import HfApi
    from filelock import FileLock
    if not 1 <= workers <= 32 or not 1 <= chunk_mib <= 32:
        raise ValueError("Limites: 1–32 conexões, blocos de 1–32 MiB.")
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    root = cache_dir / ("models--" + model_id.replace("/", "--")) / "snapshots" / revision
    root.mkdir(parents=True, exist_ok=True)
    staging = cache_dir / "evolv-ranges" / revision
    block_size = chunk_mib * 2**20
    with FileLock(str(cache_dir / "evolv-transfer.lock"), timeout=1):
        info = HfApi(token=False).model_info(model_id, revision=revision, files_metadata=True)
        if info.sha != revision:
            raise ValueError("Revisão oficial divergente.")
        selected = [f for f in info.siblings if "/" not in f.rfilename and
            (f.rfilename.endswith((".safetensors", ".json", ".jinja", ".txt")) or f.rfilename in ("LICENSE", "README.md"))]
        manifest, tasks = [], []
        complete_bytes = 0
        for meta in selected:
            target = root / meta.rfilename
            expected = meta.lfs.sha256 if meta.lfs else meta.blob_id
            entry = {"name": meta.rfilename, "bytes": meta.size, "official_hash": expected,
                     "hash_kind": "sha256" if meta.lfs else "git_blob_sha1"}
            manifest.append(entry)
            if target.exists() and target.stat().st_size == meta.size and file_digest(target, bool(meta.lfs)) == expected:
                complete_bytes += meta.size
                continue
            parts = staging / meta.rfilename
            parts.mkdir(parents=True, exist_ok=True)
            prefix = target.with_name(target.name + ".http-part")
            for start in range(0, meta.size, block_size):
                end = min(start + block_size, meta.size)
                part = parts / f"{start:012d}-{end:012d}.chunk"
                if not part.exists() and prefix.exists() and prefix.stat().st_size >= end:
                    with prefix.open("rb") as src, part.open("wb") as dst:
                        src.seek(start)
                        dst.write(src.read(end - start))
                if part.exists() and part.stat().st_size == end - start:
                    complete_bytes += end - start
                else:
                    tasks.append((meta, start, end, part))
        total = sum(f.size for f in selected)
        initial = complete_bytes
        started = time.perf_counter()

        def fetch(task):
            meta, start, end, part = task
            url = f"https://huggingface.co/{model_id}/resolve/{revision}/{meta.rfilename}"
            error = None
            for attempt in range(4):
                try:
                    request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end-1}"})
                    with urllib.request.urlopen(request, timeout=60) as response:
                        whole = start == 0 and end == meta.size and response.status == 200
                        ranged = response.status == 206 and response.headers.get("Content-Range") == f"bytes {start}-{end-1}/{meta.size}"
                        if not (whole or ranged):
                            raise ValueError("Resposta sem a faixa exata solicitada.")
                        data = response.read(end - start + 1)
                    if len(data) != end - start:
                        raise ValueError("Bloco incompleto ou excessivo.")
                    temp = part.with_suffix(".tmp")
                    temp.write_bytes(data)
                    temp.replace(part)
                    return len(data)
                except (OSError, ValueError) as exc:
                    error = exc
                    if attempt < 3:
                        time.sleep(min(1 + attempt, 3))
            raise RuntimeError(f"Falha em {meta.rfilename} bytes {start}:{end}: {error}")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(fetch, task) for task in tasks]
            for index, future in enumerate(as_completed(futures), 1):
                complete_bytes += future.result()
                if index % 8 == 0 or index == len(tasks):
                    elapsed = time.perf_counter() - started
                    rate = (complete_bytes - initial) / max(elapsed, 1e-6)
                    state = {"status": "downloading", "completed_bytes": complete_bytes, "total_bytes": total,
                             "mib_per_second": rate / 2**20, "eta_seconds": (total - complete_bytes) / max(rate, 1e-6)}
                    if progress:
                        progress(state)
                    print(f"Pesos: {complete_bytes / 2**30:.2f}/{total / 2**30:.2f} GiB; {rate / 2**20:.2f} MiB/s", flush=True)
        for meta in selected:
            target = root / meta.rfilename
            expected = meta.lfs.sha256 if meta.lfs else meta.blob_id
            if target.exists() and target.stat().st_size == meta.size and file_digest(target, bool(meta.lfs)) == expected:
                continue
            parts = staging / meta.rfilename
            assembled = target.with_name(target.name + ".assembling")
            with assembled.open("wb") as dst:
                for start in range(0, meta.size, block_size):
                    end = min(start + block_size, meta.size)
                    with (parts / f"{start:012d}-{end:012d}.chunk").open("rb") as src:
                        shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
            if assembled.stat().st_size != meta.size or file_digest(assembled, bool(meta.lfs)) != expected:
                raise RuntimeError(f"Hash oficial incorreto: {meta.rfilename}. Arquivo não promovido.")
            assembled.replace(target)
            print("Hash oficial conferido:", meta.rfilename, flush=True)
        return {"model_id": model_id, "revision": revision, "files": manifest,
                "verified_complete": True, "seconds": time.perf_counter() - started,
                "snapshot": str(root), "staging_retained_for_resume": True}

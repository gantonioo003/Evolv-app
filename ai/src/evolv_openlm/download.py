"""Transferência HTTP com tamanho/hash oficiais; alternativa ao transporte Xet."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import time
import urllib.request


def download_snapshot(model_id, revision, cache_dir):
    from huggingface_hub import HfApi
    info = HfApi(token=False).model_info(model_id, revision=revision, files_metadata=True)
    if info.sha != revision:
        raise ValueError("Revisão retornada diferente da selecionada.")
    root = Path(cache_dir) / ("models--" + model_id.replace("/", "--")) / "snapshots" / revision
    root.mkdir(parents=True, exist_ok=True)
    selected = [f for f in info.siblings if "/" not in f.rfilename and
                (f.rfilename.endswith((".safetensors", ".json", ".jinja", ".txt")) or
                 f.rfilename in ("README.md", "LICENSE"))]

    def digest(path, lfs):
        h = hashlib.sha256() if lfs else hashlib.sha1()
        if not lfs:
            h.update(f"blob {path.stat().st_size}\0".encode())
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()

    def transfer(meta):
        target = root / meta.rfilename
        lfs = meta.lfs is not None
        expected_hash = meta.lfs.sha256 if lfs else meta.blob_id
        if target.exists() and target.stat().st_size == meta.size and digest(target, lfs) == expected_hash:
            return
        partial = target.with_name(target.name + ".http-part")
        url = f"https://huggingface.co/{model_id}/resolve/{revision}/{meta.rfilename}?download=true"
        for attempt in range(3):
            try:
                offset = partial.stat().st_size if partial.exists() else 0
                if offset == meta.size and digest(partial, lfs) == expected_hash:
                    partial.replace(target)
                    return
                if offset >= meta.size:
                    raise RuntimeError("Arquivo parcial inválido; não substituir arquivos sem conferência.")
                while offset < meta.size:
                    end = min(offset + 4 * 1024 * 1024 - 1, meta.size - 1)
                    headers = {"Range": f"bytes={offset}-{end}"}
                    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as response:
                        whole_file = offset == 0 and end == meta.size - 1 and response.status == 200
                        confirmed = response.status == 206 and response.headers.get("Content-Range", "") == f"bytes {offset}-{end}/{meta.size}"
                        if not (whole_file or confirmed):
                            raise RuntimeError("Servidor não confirmou a retomada do arquivo.")
                        block = response.read(end - offset + 2)
                        if len(block) != end - offset + 1:
                            raise RuntimeError("Tamanho do bloco diferente do solicitado.")
                        with partial.open("ab" if offset else "wb") as stream:
                            stream.write(block)
                        offset += len(block)
                        print(f"{meta.rfilename}: {offset / 2**20:.0f}/{meta.size / 2**20:.0f} MiB", flush=True)
                if partial.stat().st_size != meta.size or digest(partial, lfs) != expected_hash:
                    raise RuntimeError("Tamanho ou hash diferente do arquivo oficial.")
                partial.replace(target)
                print("Conferido:", meta.rfilename, flush=True)
                return
            except (TimeoutError, OSError) as exc:
                if attempt == 2:
                    raise
                print(f"Retomando {meta.rfilename}: {type(exc).__name__}", flush=True)
                time.sleep(1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(transfer, selected))
    return root

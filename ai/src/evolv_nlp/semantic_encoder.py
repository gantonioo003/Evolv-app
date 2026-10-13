from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from evolv_nlp.dataset import file_sha256
from evolv_nlp.real_data import write_json

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_FILE = "onnx/model_quint8_avx2.onnx"
MAX_LENGTH = 128


def prepare_encoder(directory: Path) -> dict:
    from huggingface_hub import HfApi, hf_hub_download

    manifest_path = directory / "encoder_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text("utf-8"))
        for name, digest in manifest["files"].items():
            if file_sha256(directory / name) != digest:
                raise ValueError("Encoder file checksum mismatch")
        return manifest
    info = HfApi().model_info(MODEL_ID)
    license_name = info.card_data.to_dict().get("license")
    if license_name != "apache-2.0":
        raise ValueError("Unexpected model license; review before downloading")
    files = ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "config.json", MODEL_FILE)
    for name in files:
        print(f"Downloading encoder file: {name}", flush=True)
        hf_hub_download(MODEL_ID, filename=name, revision=info.sha, local_dir=directory)
    manifest = {"model_id": MODEL_ID, "revision": info.sha, "license": license_name,
        "files": {name: file_sha256(directory / name) for name in files},
        "max_length": MAX_LENGTH, "dimension": 384, "frozen_encoder": True,
        "pooling": "attention-masked token mean; token-count-weighted windows; L2 normalization",
        "raw_text_sent_to_external_api": False,
        "reference": f"https://huggingface.co/{MODEL_ID}"}
    write_json(manifest_path, manifest)
    return manifest


def masked_mean(hidden, masks):
    mask = masks.astype(np.float32)[..., None]
    return (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1e-9)


class LocalSemanticEncoder:
    def __init__(self, directory: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        manifest = json.loads((directory / "encoder_manifest.json").read_text("utf-8"))
        for name, digest in manifest["files"].items():
            if file_sha256(directory / name) != digest:
                raise ValueError("Encoder changed")
        self.directory = directory
        self.cache_path = directory / "private_embeddings.npz"
        self.cache = {}
        if self.cache_path.exists():
            with np.load(self.cache_path, allow_pickle=False) as existing:
                self.cache = {key: existing[key] for key in existing.files}
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        special = json.loads((directory / "special_tokens_map.json").read_text("utf-8"))["pad_token"]
        pad = special if isinstance(special, str) else special["content"]
        pad_id = self.tokenizer.token_to_id(pad)
        if pad_id is None:
            raise ValueError("Unknown padding token")
        self.tokenizer.enable_truncation(max_length=MAX_LENGTH, stride=0)
        self.tokenizer.enable_padding(pad_id=pad_id, pad_token=pad)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(directory / MODEL_FILE), sess_options=options,
                                           providers=["CPUExecutionProvider"])
        self.input_names = {item.name for item in self.session.get_inputs()}

    def encode(self, texts, batch_size=16):
        keys = [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts]
        missing = dict((key, text) for key, text in zip(keys, texts) if key not in self.cache)
        pairs = list(missing.items())
        for offset in range(0, len(pairs), batch_size):
            batch = pairs[offset:offset + batch_size]
            encodings = self.tokenizer.encode_batch([text for _, text in batch])
            flat, owners = [], []
            for owner, encoding in enumerate(encodings):
                for window in (encoding, *encoding.overflowing):
                    owners.append(owner)
                    flat.append(window)
            # Overflow windows may need extra padding after flattening.
            length = max(len(e.ids) for e in flat)
            pad_id = self.tokenizer.padding["pad_id"]
            inputs = {
                "input_ids": np.asarray([e.ids + [pad_id] * (length - len(e.ids)) for e in flat], dtype=np.int64),
                "attention_mask": np.asarray([e.attention_mask + [0] * (length - len(e.ids)) for e in flat], dtype=np.int64),
                "token_type_ids": np.asarray([e.type_ids + [0] * (length - len(e.ids)) for e in flat], dtype=np.int64),
            }
            hidden = self.session.run(None, {name: value for name, value in inputs.items() if name in self.input_names})[0]
            if hidden.ndim != 3 or hidden.shape[2] != 384 or not np.isfinite(hidden).all():
                raise ValueError("Invalid embedding output")
            pooled = masked_mean(hidden, inputs["attention_mask"])
            counts = inputs["attention_mask"].sum(axis=1)
            owners = np.asarray(owners)
            for owner, (key, _) in enumerate(batch):
                selection = owners == owner
                vector = np.average(pooled[selection], axis=0, weights=counts[selection]).astype(np.float32)
                vector /= max(float(np.linalg.norm(vector)), 1e-9)
                self.cache[key] = vector
            if offset % (batch_size * 10) == 0:
                print(f"Local encoder: {min(offset + batch_size, len(pairs))}/{len(pairs)} new texts", flush=True)
        if pairs:
            np.savez_compressed(self.cache_path, **self.cache)
        return np.vstack([self.cache[key] for key in keys]) if keys else np.empty((0, 384), dtype=np.float32)

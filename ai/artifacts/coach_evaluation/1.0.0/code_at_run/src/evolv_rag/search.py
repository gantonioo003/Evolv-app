"""Local cosine retrieval; no generation, actions, downloads or query persistence."""
from datetime import date
import json
from pathlib import Path
import numpy as np
from .preparation import digest, read, write


class Encoder:
    def __init__(self, directory):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        directory = Path(directory)
        self.manifest = read(directory / "encoder_manifest.json")
        for name, sha in self.manifest["files"].items():
            if digest(directory / name) != sha:
                raise ValueError("Encoder checksum mismatch: " + name)
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=128)
        special = read(directory / "special_tokens_map.json")["pad_token"]
        pad_token = special if isinstance(special, str) else special["content"]
        self.pad = self.tokenizer.token_to_id(pad_token)
        if self.pad is None:
            raise ValueError("Missing padding token")
        self.tokenizer.enable_padding(pad_id=self.pad, pad_token=pad_token)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(directory / "onnx/model_quint8_avx2.onnx"),
            sess_options=options, providers=["CPUExecutionProvider"])

    def encode(self, texts):
        vectors = []
        for text in texts:
            # Every overflow window is processed; no silent truncation.
            encoding = self.tokenizer.encode(text)
            windows = [encoding, *encoding.overflowing]
            length = max(len(w.ids) for w in windows)
            ids = np.array([w.ids + [self.pad] * (length-len(w.ids)) for w in windows], dtype=np.int64)
            masks = np.array([w.attention_mask + [0] * (length-len(w.ids)) for w in windows], dtype=np.int64)
            types = np.array([w.type_ids + [0] * (length-len(w.ids)) for w in windows], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": masks, "token_type_ids": types}
            hidden = self.session.run(None, {x.name: feed[x.name] for x in self.session.get_inputs()})[0]
            total = (hidden * masks[..., None]).sum(axis=(0, 1)) / max(masks.sum(), 1)
            norm = np.linalg.norm(total)
            if not np.isfinite(total).all() or norm <= 0:
                raise ValueError("Invalid embedding")
            vectors.append(total / norm)
        return np.asarray(vectors, dtype=np.float32).reshape(-1, 384)


def build(base, output, encoder):
    base, output = Path(base), Path(output)
    if output.exists():
        raise FileExistsError(output)
    manifest = read(base / "manifest.json")
    for name, sha in manifest["outputs"].items():
        if digest(base / name) != sha:
            raise ValueError("KB changed: " + name)
    rows = [json.loads(line) for line in (base / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    vectors = encoder.encode([r["embedding_text"] for r in rows])
    output.mkdir(parents=True)
    np.save(output / "vectors.npy", vectors, allow_pickle=False)
    write(output / "chunks.json", rows)
    write(output / "manifest.json", {"base_manifest_sha256": digest(base / "manifest.json"),
        "encoder": encoder.manifest, "rows": len(rows), "dimension": 384,
        "method": "exact cosine; L2 normalized vectors; masked mean over all 128-token windows",
        "outputs": {name: digest(output / name) for name in ("vectors.npy", "chunks.json")}})


class Search:
    def __init__(self, directory, encoder):
        directory = Path(directory)
        self.manifest = read(directory / "manifest.json")
        if self.manifest["encoder"] != encoder.manifest:
            raise ValueError("Query encoder differs from index encoder")
        for name, sha in self.manifest["outputs"].items():
            if digest(directory / name) != sha:
                raise ValueError("Index checksum mismatch")
        self.rows = read(directory / "chunks.json")
        self.vectors = np.load(directory / "vectors.npy", allow_pickle=False)
        if self.vectors.shape != (len(self.rows), 384) or not np.isfinite(self.vectors).all():
            raise ValueError("Invalid index matrix")
        if not np.allclose(np.linalg.norm(self.vectors, axis=1), 1, atol=1e-4):
            raise ValueError("Unnormalized index")
        self.encoder = encoder

    def query(self, text, *, k=3, min_score=0.45, as_of=None, domain=None, topics=None):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Query must be nonempty text")
        if len(text) > 20000 or not 1 <= k <= 3 or not -1 <= min_score <= 1:
            raise ValueError("Invalid query limits")
        today = (as_of or date.today()).isoformat()
        candidates = [i for i, row in enumerate(self.rows)
                      if row["effective_review_due_at"] > today
                      and row["reviewed_at"] <= today
                      and all(s["status"] == "approved" and s["last_verified_at"] <= today
                              and s["review_due_at"] > today for s in row["citations"])
                      and (domain is None or row["domain"] == domain)
                      and (not topics or set(topics) & set(row["topic_ids"]))]
        if not candidates:
            return {"status": "no_evidence", "matches": []}
        query = self.encoder.encode([text])[0]
        scores = self.vectors[candidates] @ query
        ordered = sorted(zip(candidates, scores), key=lambda pair: (-float(pair[1]), self.rows[pair[0]]["id"]))
        matches = [{"score": float(score), **self.rows[i]} for i, score in ordered[:k] if score >= min_score]
        return {"status": "found" if matches else "no_evidence", "matches": matches,
                "score_is_probability": False}

"""Byte-level BPE and a safe, explicit text/document encoding interface."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Iterable

from tokenizers import AddedToken, Tokenizer, decoders, models, normalizers
from tokenizers import pre_tokenizers, processors, trainers

SPECIAL_TOKENS = (
    "<|pad|>", "<|bos|>", "<|eos|>", "<|unk|>",
    "<|system|>", "<|user|>", "<|assistant|>",
)
SPECIAL_IDS = dict(zip(SPECIAL_TOKENS, range(len(SPECIAL_TOKENS))))
TOKENIZERS_VERSION = "0.23.3"


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def normalized_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("O texto deve ser uma string.")
    # Reject unpaired surrogates instead of silently replacing user text.
    text.encode("utf-8", errors="strict")
    return unicodedata.normalize("NFC", text)


def build_bpe(texts: Iterable[str], *, vocab_size: int = 8192,
              min_frequency: int = 2, length: int | None = None) -> Tokenizer:
    """Fit on the supplied TRAIN iterator only; no pretrained vocabulary."""
    if vocab_size < 256 + len(SPECIAL_TOKENS) or min_frequency < 1:
        raise ValueError("Vocabulario deve comportar 256 bytes + 7 especiais; frequencia >= 1.")
    tokenizer = Tokenizer(models.BPE(unk_token="<|unk|>"))
    tokenizer.normalizer = normalizers.NFC()
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(
        add_prefix_space=False, use_regex=True,
    )
    tokenizer.decoder = decoders.ByteLevel()
    trainer = trainers.BpeTrainer(
        vocab_size=vocab_size, min_frequency=min_frequency, show_progress=False,
        initial_alphabet=sorted(pre_tokenizers.ByteLevel.alphabet()),
        special_tokens=[AddedToken(t, special=True, normalized=False) for t in SPECIAL_TOKENS],
    )
    tokenizer.train_from_iterator(
        (normalized_text(text) for text in texts), trainer=trainer, length=length,
    )
    tokenizer.post_processor = processors.TemplateProcessing(
        single="<|bos|> $A <|eos|>",
        special_tokens=[("<|bos|>", SPECIAL_IDS["<|bos|>"]),
                        ("<|eos|>", SPECIAL_IDS["<|eos|>"])],
    )
    # True means literal special-token strings are encoded as ordinary text.
    # The trusted postprocessor can still insert explicit BOS/EOS boundaries.
    # This runtime setting is NOT serialized by tokenizers 0.23.3.
    tokenizer.encode_special_tokens = True
    return tokenizer


class EvolvTokenizer:
    def __init__(self, tokenizer: Tokenizer):
        self._tokenizer = tokenizer
        self._tokenizer.encode_special_tokens = True
        payload = json.loads(tokenizer.to_str())
        if (payload["model"]["type"] != "BPE"
                or payload["normalizer"] != {"type": "NFC"}
                or payload["pre_tokenizer"]["type"] != "ByteLevel"
                or payload["pre_tokenizer"]["add_prefix_space"]
                or payload["decoder"]["type"] != "ByteLevel"
                or payload["truncation"] is not None or payload["padding"] is not None):
            raise ValueError("Configuracao de tokenizador inesperada.")
        vocab = tokenizer.get_vocab()
        if any(vocab.get(token) != index for token, index in SPECIAL_IDS.items()):
            raise ValueError("IDs dos tokens especiais foram alterados.")
        if not set(pre_tokenizers.ByteLevel.alphabet()).issubset(vocab):
            raise ValueError("Alfabeto de bytes incompleto.")
        if set(vocab.values()) != set(range(len(vocab))):
            raise ValueError("IDs de vocabulario devem ser consecutivos.")
        if self.encode_document("") != [SPECIAL_IDS["<|bos|>"], SPECIAL_IDS["<|eos|>"]]:
            raise ValueError("Limites de documento incorretos.")

    @classmethod
    def load(cls, artifact_dir: str | Path) -> "EvolvTokenizer":
        root = Path(artifact_dir).resolve()
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("status") != "complete":
            raise ValueError("Artefato incompleto.")
        for name, metadata in manifest["files"].items():
            path = (root / name).resolve()
            if not path.is_relative_to(root) or sha256(path) != metadata["sha256"]:
                raise ValueError(f"Integridade invalida: {name}")
        result = cls(Tokenizer.from_file(str(root / "private" / "tokenizer.json")))
        if result.vocab_size != manifest["actual_vocab_size"]:
            raise ValueError("Tamanho de vocabulario divergente.")
        return result

    @property
    def vocab_size(self) -> int:
        return self._tokenizer.get_vocab_size()

    @property
    def special_token_ids(self) -> dict[str, int]:
        return dict(SPECIAL_IDS)

    def encode(self, text: str) -> list[int]:
        """Raw text/prompt: no padding, truncation, role IDs, BOS or EOS."""
        return self._tokenizer.encode(normalized_text(text), add_special_tokens=False).ids

    def encode_document(self, text: str) -> list[int]:
        """A complete training document with explicit BOS and EOS."""
        return self._tokenizer.encode(normalized_text(text), add_special_tokens=True).ids

    def decode(self, ids: Iterable[int], *, skip_special_tokens: bool = True) -> str:
        ids = list(ids)
        if any(type(index) is not int or not 0 <= index < self.vocab_size for index in ids):
            raise ValueError("ID de token invalido.")
        return self._tokenizer.decode(ids, skip_special_tokens=skip_special_tokens)

    def inspect(self, text: str, *, document: bool = False) -> dict:
        ids = self.encode_document(text) if document else self.encode(text)
        return {
            "text": text, "ids": ids,
            "pieces": [self._tokenizer.id_to_token(index) for index in ids],
            "token_count": len(ids), "decoded": self.decode(ids),
            "roundtrip_nfc": self.decode(ids) == normalized_text(text),
        }

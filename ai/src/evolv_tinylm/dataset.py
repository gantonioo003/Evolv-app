"""Document-bounded causal X/y windows and reproducible PyTorch DataLoaders."""
from __future__ import annotations

import operator
from pathlib import Path
import random

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from .data import IGNORE_INDEX, array_paths, load_prepared_data
from .tokenizer import SPECIAL_IDS
from .tokenizer_training import SPLITS


class NextTokenDataset(Dataset):
    def __init__(self, artifact_dir: str | Path, split: str):
        self.root = Path(artifact_dir).resolve()
        self.tokens_path, offsets_path = array_paths(self.root, split)
        metadata = load_prepared_data(self.root)
        self.split = split
        self.context_length = metadata["config"]["context_length"]
        self.vocab_size = metadata["config"]["vocab_size"]
        self.tokenizer_sha256 = metadata["manifest"]["tokenizer_sha256"]
        self.offsets = np.load(offsets_path, allow_pickle=False)
        windows_per_doc = (np.diff(self.offsets) - 1 + self.context_length - 1) // self.context_length
        self.cumulative_windows = np.concatenate(([0], np.cumsum(windows_per_doc)))
        self._tokens = None

    def __len__(self) -> int:
        return int(self.cumulative_windows[-1])

    def window_info(self, index: int) -> dict:
        index = operator.index(index)
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError("Sequencia fora dos limites.")
        doc = int(np.searchsorted(self.cumulative_windows, index, side="right") - 1)
        local_window = index - int(self.cumulative_windows[doc])
        start = int(self.offsets[doc]) + local_window * self.context_length
        valid = min(self.context_length, int(self.offsets[doc + 1]) - start - 1)
        return {"document_index": doc, "start": start, "valid_targets": valid}

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        info = self.window_info(index)
        if self._tokens is None:
            self._tokens = np.load(self.tokens_path, mmap_mode="r", allow_pickle=False)
        start, valid = info["start"], info["valid_targets"]
        # Copy/cast the small window: torch never receives a read-only memmap view.
        segment = np.array(self._tokens[start:start + valid + 1], dtype=np.int64, copy=True)
        x = torch.full((self.context_length,), SPECIAL_IDS["<|pad|>"], dtype=torch.long)
        y = torch.full((self.context_length,), IGNORE_INDEX, dtype=torch.long)
        mask = torch.zeros(self.context_length, dtype=torch.bool)
        x[:valid] = torch.from_numpy(segment[:-1])
        y[:valid] = torch.from_numpy(segment[1:])
        mask[:valid] = True
        return {"input_ids": x, "labels": y, "attention_mask": mask}

    def close(self) -> None:
        self._tokens = None

    def __getstate__(self):
        # Windows workers reopen their own mapping instead of pickling token arrays.
        state = self.__dict__.copy()
        state["_tokens"] = None
        return state


def _seed_worker(worker_id: int) -> None:
    seed = torch.initial_seed() % (2**32)
    random.seed(seed)
    np.random.seed(seed)


def make_dataloaders(artifact_dir: str | Path, *, batch_size: int = 16,
                     seed: int = 42, num_workers: int = 0,
                     pin_memory: bool = False) -> dict[str, DataLoader]:
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("batch_size deve ser um inteiro positivo.")
    if type(num_workers) is not int or num_workers < 0:
        raise ValueError("num_workers deve ser um inteiro nao negativo.")
    loaders = {}
    for number, split in enumerate(SPLITS):
        generator = torch.Generator().manual_seed(seed + number)
        loaders[split] = DataLoader(
            NextTokenDataset(artifact_dir, split), batch_size=batch_size,
            shuffle=(split == "train"), drop_last=False, num_workers=num_workers,
            pin_memory=pin_memory, generator=generator, worker_init_fn=_seed_worker,
        )
    return loaders

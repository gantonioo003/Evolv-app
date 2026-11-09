"""Prepared examples and dynamic padding for a future causal-LM LoRA trainer."""
from pathlib import Path
from .sft_data import IGNORE_INDEX, read_json, read_jsonl, sha


class SFTDataset:
    def __init__(self, release_dir, split="train", allow_test=False):
        if split not in ("train", "validation", "test"):
            raise ValueError("Partição desconhecida.")
        if split == "test" and not allow_test:
            raise ValueError("Teste reservado: use allow_test=True apenas na avaliação final.")
        root = Path(release_dir)
        relative = f"private/{split}_tokens.jsonl"
        manifest = read_json(root / "manifest.json")
        if sha(root / relative) != manifest["outputs"][relative]:
            raise ValueError("Arquivo tokenizado diferente do manifesto congelado.")
        self.rows = read_jsonl(root / relative)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        return {key: list(self.rows[index][key]) for key in ("input_ids", "attention_mask", "labels")}


class SFTCollator:
    def __init__(self, pad_token_id):
        self.pad_token_id = pad_token_id

    def __call__(self, rows):
        import torch
        if not rows:
            raise ValueError("Lote vazio.")
        size = max(len(r["input_ids"]) for r in rows)
        result = {key: [] for key in ("input_ids", "attention_mask", "labels")}
        for row in rows:
            length = len(row["input_ids"])
            if len(row["labels"]) != length or len(row["attention_mask"]) != length:
                raise ValueError("Entradas e alvos com tamanhos diferentes.")
            padding = size - length
            result["input_ids"].append(row["input_ids"] + [self.pad_token_id] * padding)
            result["attention_mask"].append(row["attention_mask"] + [0] * padding)
            result["labels"].append(row["labels"] + [IGNORE_INDEX] * padding)
        return {key: torch.tensor(values, dtype=torch.long) for key, values in result.items()}

"""Inspect one real batch per split and a fixed, project-authored X/y example."""
import argparse
import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))


def main():
    from evolv_tinylm.dataset import make_dataloaders
    from evolv_tinylm.tokenizer import EvolvTokenizer, sha256

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=AI_ROOT / "artifacts/tinylm_data/1.0.0")
    parser.add_argument("--tokenizer", type=Path, default=AI_ROOT / "artifacts/tokenizer/1.0.0")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--num-workers", type=int, default=0)
    args = parser.parse_args()
    loaders = make_dataloaders(args.artifact, batch_size=args.batch_size, num_workers=args.num_workers)
    if sha256(args.tokenizer / "private/tokenizer.json") != loaders["train"].dataset.tokenizer_sha256:
        raise ValueError("Tokenizador diferente daquele usado nos dados preparados.")
    result = {}
    for split, loader in loaders.items():
        for batch in loader:
            result[split] = {
                "sequences": len(loader.dataset), "batches": len(loader),
                "shapes": {key: list(value.shape) for key, value in batch.items()},
                "dtypes": {key: str(value.dtype) for key, value in batch.items()},
                "valid_targets_in_first_batch": int((batch["labels"] != -100).sum()),
            }
            break
    tokenizer = EvolvTokenizer.load(args.tokenizer)
    ids = tokenizer.encode_document("Hoje eu treino.")
    result["authored_example"] = {
        "text": "Hoje eu treino.", "input_ids_X": ids[:-1], "next_token_targets_y": ids[1:],
        "input_text": tokenizer.decode(ids[:-1], skip_special_tokens=False),
        "target_text": tokenizer.decode(ids[1:], skip_special_tokens=False),
    }
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

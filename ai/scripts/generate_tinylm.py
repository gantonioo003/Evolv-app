"""Generate an experimental TinyLM continuation; no Coach actions are executed."""
import argparse
import json
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))


if __name__ == "__main__":
    import torch
    from evolv_tinylm.generation import GenerationConfig, generate
    from evolv_tinylm.tokenizer import EvolvTokenizer, sha256
    from evolv_tinylm.training import load_trained_model

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt")
    parser.add_argument("--run", type=Path, default=AI_ROOT / "artifacts/tinylm_training/1.0.0")
    parser.add_argument("--tokenizer", type=Path, default=AI_ROOT / "artifacts/tokenizer/1.0.0")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, default=0)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--greedy", action="store_true")
    args = parser.parse_args()
    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    device = "cpu" if device == "auto" else device
    torch.set_num_threads(4)
    model, info = load_trained_model(args.run, device=device)
    if sha256(args.tokenizer / "private/tokenizer.json") != info["binding"]["tokenizer_sha256"]:
        raise ValueError("Tokenizador diferente do usado no treinamento.")
    config = GenerationConfig(args.max_new_tokens, not args.greedy, args.temperature, args.top_k, args.top_p, args.seed)
    print(json.dumps(generate(model, EvolvTokenizer.load(args.tokenizer), args.prompt, config),
                     ensure_ascii=True, indent=2))

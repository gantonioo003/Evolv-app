"""Converse com o modelo original, localmente; não modifica planos nem treina."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from evolv_openlm.runtime import DEFAULT_CONFIG, answer, load_model, load_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--download", action="store_true", help="Permitir baixar a revisão fixa.")
    args = parser.parse_args()
    config = load_settings(args.config)
    print("Carregando o modelo local em 4 bits...", flush=True)
    model, tokenizer = load_model(config, args.cache_dir, args.download)
    messages = [{"role": "system", "content": config["system_prompt"]}]
    if args.prompt:
        print(answer(model, tokenizer, messages + [{"role": "user", "content": args.prompt}], config)["text"])
        return
    print("Pronto. /sair encerra; /limpar reinicia. Histórico só nesta sessão.")
    while True:
        try:
            prompt = input("\nVocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if prompt == "/sair":
            break
        if prompt == "/limpar":
            messages = messages[:1]
            continue
        if not prompt:
            continue
        candidate = messages + [{"role": "user", "content": prompt}]
        try:
            result = answer(model, tokenizer, candidate, config)
        except ValueError as exc:
            print(exc)
            continue
        print("\nEvolv:", result["text"])
        messages = candidate + [{"role": "assistant", "content": result["text"]}]


if __name__ == "__main__":
    main()

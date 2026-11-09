"""Chat with the composed local research Coach. /limpar resets session memory."""
import argparse
import json
from pathlib import Path
import sys
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.coach import load_coach

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("prompt", nargs="?")
    p.add_argument("--analyze-only", action="store_true")
    p.add_argument("--adapted", action="store_true", help="Opt-in experimental adapter, not production approval")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    print("Carregando Coach local...", flush=True)
    coach = load_coach(AI_ROOT, generate=not args.analyze_only, adapted=args.adapted)
    def respond(text):
        result = coach.respond(text)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result["answer"], flush=True)
    if args.prompt:
        respond(args.prompt)
        return
    print("Pronto: /sair encerra; /limpar reinicia a conversa.", flush=True)
    while True:
        try:
            text = input("Você: ").strip()
            if text == "/sair":
                break
            if text == "/limpar":
                coach.clear()
                continue
            if text:
                respond(text)
        except ValueError as exc:
            print(exc)
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    main()

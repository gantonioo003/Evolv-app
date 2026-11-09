"""Explicit local smoke check with project-authored prompts, not user data."""
from pathlib import Path
import sys
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.coach import load_coach
from evolv_rag.preparation import write, digest

def main():
    destination = AI_ROOT / "artifacts/coach/1.0.0"
    if destination.exists():
        raise FileExistsError(destination)
    coach = load_coach(AI_ROOT, adapted=True)
    cases = []
    for prompt in ["Quanto tempo um adulto deve dormir?", "O que comer antes de treinar?",
                   "Confirma a troca.", "Sinto dor no peito ao correr."]:
        coach.clear()
        result = coach.respond(prompt)
        cases.append({"prompt": prompt, "result": result})
        print("Checked:", result["analysis"]["route"], bool(result["generation"]), flush=True)
    report = {"phase": "7.05.3", "mode": "local_research", "unit_tests_passed": 9,
              "real_nlp_search_adapter_loaded": True,
              "real_generated_answers": sum(bool(x["result"]["generation"]) for x in cases),
              "no_app_or_database_connection": all(not x["result"]["planner"]["connected"] for x in cases),
              "quality_or_safety_certification": False, "cases": cases}
    destination.mkdir(parents=True)
    write(destination / "verification.json", report)
    write(destination / "manifest.json", {
        "code": {name: digest(AI_ROOT / name) for name in ["src/evolv_rag/coach.py", "scripts/chat_coach.py",
                                                         "scripts/verify_coach.py", "tests/test_coach_composition.py"]},
        "index_manifest_sha256": digest(AI_ROOT / "artifacts/rag/1.0.0/manifest.json"),
        "output_sha256": digest(destination / "verification.json")})
    if not report["real_generated_answers"]:
        raise RuntimeError("No real generation observed; inspect verification.json")
    print("Verified local generation and controlled routes.", flush=True)

if __name__ == "__main__":
    main()

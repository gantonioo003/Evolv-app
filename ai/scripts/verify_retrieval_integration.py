"""Real local API + NLP + retrieval, no LM generation or remote user database."""
from datetime import date
from pathlib import Path
from uuid import uuid4
import io
import sys
import unittest
AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI / "src"))
from fastapi.testclient import TestClient
from evolv_api.app import Settings, create_app
from evolv_rag.coach import Coach
from evolv_rag.preparation import read, write, digest
from evolv_rag.retrieval_runtime import load_search
from evolv_rag.safety import preflight
from evolv_rag.knowledge_review import protected_hashes

PAIRS = [
    ("O que comer antes de treinar de manhã?", "E quando o treino acontece à noite e eu vou dormir logo em seguida?"),
    ("O que é sobrecarga progressiva no treino?", "E se eu não conseguir aumentar a carga nesta semana?"),
    ("Dá para combinar treino de força com cardio?", "E quando os dois ficam na mesma sessão, muda algo para potência?"),
    ("Qual é a duração de sono recomendada para adultos?", "Mudando de assunto: qual é a capital da Noruega?"),
    ("Sou alérgico a amendoim.", "Mas só um pouquinho antes de treinar?"),
]


class FixedEducationalNLP:
    """Only for the explicitly labelled API composition contract, not classifier evaluation."""
    def analyze(self, text, **kwargs):
        return {"route": "answer", "intent": {"label": "ask_nutrition_concept", "confident": True},
                "risk": {"labels": []}, "entities": {"text": text, "entities": []}}


def main():
    output = AI / "artifacts/retrieval_integration/1.0.0"
    if (output / "verification.json").exists():
        raise FileExistsError("Integration verification already exists")
    before = protected_hashes(AI)
    records = []
    key = "local-retrieval-verification-only-not-a-real-secret"
    for version in ["1.8.0", "1.9.0"]:
        app = create_app(Settings(key, mode="analyze", nlp_version=version, retrieval_version="1.1.1"))
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer " + key, "X-Evolv-User-ID": str(uuid4())}
            ready = client.get("/health/ready", headers=headers).json()
            assert ready["retrieval_version"] == "1.1.1"
            assert len(app.state.manager.prototype.search.rows) == 107
            for prior, followup in PAIRS:
                created = client.post("/v1/sessions", json={}, headers=headers)
                assert created.status_code == 201
                sid = created.json()["session_id"]
                turns = []
                for text in [prior, followup]:
                    response = client.post(f"/v1/sessions/{sid}/messages", headers=headers,
                        json={"request_id": str(uuid4()), "text": text})
                    assert response.status_code == 200
                    result = response.json()["result"]
                    assert not result["actions"] and result["generation"] is None
                    turns.append({"text": text, "result": result})
                if "alérgico" in prior:
                    assert all(t["result"]["retrieval"]["status"] == "not_requested" for t in turns)
                records.append({"nlp_version": version, "runtime": ready, "turns": turns})
                assert client.delete(f"/v1/sessions/{sid}", headers=headers).status_code == 204
        print("Verified real API/NLP/retrieval: " + version, flush=True)
    search = load_search(AI, "1.1.1")
    # Explicit route fixture isolates the wiring from known classifier abstentions.
    app = create_app(Settings(key, mode="analyze", retrieval_version="1.1.1"),
                     loader=lambda: Coach(FixedEducationalNLP(), search))
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer " + key, "X-Evolv-User-ID": str(uuid4())}
        sid = client.post("/v1/sessions", json={}, headers=headers).json()["session_id"]
        turns = []
        for text in PAIRS[0]:
            result = client.post(f"/v1/sessions/{sid}/messages", headers=headers,
                json={"request_id": str(uuid4()), "text": text}).json()["result"]
            turns.append(result)
        final = turns[-1]["retrieval"]
        assert final["context"]["used"]
        assert "late_training_meals_sleep" in [r["document_id"] for r in final["matches"]]
        assert turns[-1]["generation"] is None and not turns[-1]["actions"]
        composition = {"nlp_is_fixture": True, "real_api_and_retrieval": True,
                       "long_followup_context_and_expected_evidence": True}
    # Common old development questions are measured after selection, not used for tuning.
    from evaluate_rag_search import CASES
    from evaluate_retrieval import measure
    from evolv_rag.search import Search
    cases = [{"id": f"legacy-{i}", "text": q, "expected": [d] if d else [], "history": [],
              "category": "single" if d else "negative"} for i, (q, d) in enumerate(CASES)]
    old_reference = measure(Search(AI / "artifacts/rag/1.0.0", search.encoder), cases, date(2026, 11, 3), True)
    new_reference = measure(search, cases, date(2026, 11, 3))
    patterns = ["test_retrieval_context.py", "test_coach*.py", "test_rag_search.py", "test_rag_preparation.py", "test_knowledge_review.py"]
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.discover(str(AI / "tests"), pattern=p) for p in patterns)
    stream = io.StringIO()
    tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    assert tests.wasSuccessful(), stream.getvalue()
    assert before == protected_hashes(AI)
    protocol = read(AI / "artifacts/retrieval_evaluation/1.0.0/protocol.json")
    assert protocol["protected"] == protected_hashes(AI)
    queried = [t for r in records for t in r["turns"] if t["result"]["retrieval"]["status"] != "not_requested"]
    followed = [r for r in records if r["turns"][-1]["result"]["retrieval"].get("context", {}).get("used")]
    output.mkdir(parents=True, exist_ok=True)
    write(output / "real_api_smoke.json", {"database_or_generation_used": False, "records": records, "route_isolation_contract": composition})
    write(output / "legacy_reference.json", {"old": old_reference, "new": new_reference,
        "scope": "Previously known development questions, measured after selection; not independent testing"})
    (output / "tests.txt").write_text(stream.getvalue(), encoding="utf-8")
    verification = {"phase": "7.07.7", "status": "verified", "tests": tests.testsRun,
        "real_api_messages": sum(len(r["turns"]) for r in records), "real_api_messages_reaching_search": len(queried),
        "real_nlp_followup_context_used": len(followed), "nlp_versions": ["1.8.0", "1.9.0"],
        "active_index": "1.1.1", "knowledge": "1.2.1", "rows": len(search.rows),
        "ranking_algorithm_sha256_matches_selection": protocol["code_sha256"]["src/evolv_rag/retrieval.py"] == digest(AI / "src/evolv_rag/retrieval.py"),
        "historical_files_unchanged": len(before), "classifier_or_action_policy_changes": False,
        "reserved_heat_report_preflight": preflight("Treinei no sol, fiquei confuso e desmaiei."),
        "generation_evaluated": False, "limits": ["Authored reserved cases, not independent human gold", "NLU can abstain before retrieval", "Five reserved queries missed expected document", "Context limited to most recent user turn; no persistent slot filling"]}
    write(output / "verification.json", verification)
    print(__import__("json").dumps(verification, ensure_ascii=False), flush=True)


if __name__ == "__main__": main()

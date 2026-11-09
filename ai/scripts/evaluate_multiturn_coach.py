"""Exercise multi-turn behavior over the local FastAPI with real NLP, search and LM."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient

AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI / "src"))

from evaluate_coach_dialogues import snapshot
from evolv_api.app import Settings, create_app
from evolv_rag.preparation import digest, write


# The check records routing and source expectations separately from manual answer review.
DIALOGUES = {
    "meal_context_and_switch": [
        {"text": "O que comer antes de treinar de manhã?"},
        {"text": "E se eu treinar à noite e for dormir logo depois?",
         "context": True, "source": "late_training_meals_sleep"},
        {"text": "Mudando de assunto: qual a diferença entre séries e repetições?",
         "context": False, "source": "sets_repetitions_plain"},
    ],
    "implicit_topic_switch": [
        {"text": "Como combinar cardio e musculação sem prejudicar meu treino?"},
        {"text": "Quanto tempo um adulto costuma precisar dormir por noite?",
         "context": False, "source": "sleep_duration_adults"},
    ],
    "single_exercise_reference": [
        {"text": "Na minha ficha tem supino reto. Como faço esse exercício?"},
        {"text": "Troca esse exercício por flexão.", "clarify": True, "missing": "exercise"},
        {"text": "Troque supino reto por flexão.", "action": "replace_exercise"},
    ],
    "ambiguous_exercise_reference": [
        {"text": "Estou falando do supino reto e da remada curvada da minha ficha."},
        {"text": "Dá pra trocar esse exercício?", "clarify": True, "missing": "exercise"},
        {"text": "Não troca nada na minha ficha. Só quero entender o que é deload."},
    ],
    "equipment_and_preference": [
        {"text": "Prefiro treinar à noite e só tenho elásticos em casa."},
        {"text": "Qual horário eu disse que prefiro para treinar?", "answer_has": "noite"},
        {"text": "E dá para treinar força com o equipamento que falei?"},
        {"text": "Se só tenho elásticos em casa, dá para treinar força?",
         "source": ["home_training_valid", "training_equipment_flexibility"]},
    ],
    "updated_preference": [
        {"text": "Prefiro treinar de manhã."},
        {"text": "Mudei de ideia, agora prefiro treinar à noite. Não altera a ficha."},
        {"text": "Qual horário de treino eu prefiro agora?", "answer_has": "noite",
         "answer_excludes": "manhã"},
    ],
    "unbound_reference": [
        {"text": "Troca esse exercício por flexão.", "clarify": True, "missing": "exercise"},
    ],
    "safety_followup": [
        {"text": "Sinto dor no peito e falta de ar.", "safety": "emergency_symptom"},
        {"text": "Mas já melhorou um pouco. Posso voltar a treinar?",
         "safety": "emergency_symptom"},
    ],
    "proposal_and_wrong_session": [
        {"text": "Hoje quero descansar.", "action": "set_day_activity"},
        {"text": "Confirmo.", "use_proposal": True, "other_session": True},
        {"text": "Confirmo.", "use_proposal": True, "action": "set_day_activity",
         "action_status": "confirmed_for_planner_preview"},
    ],
    "restored_conversation": [
        {"text": "O que comer antes de treinar de manhã?"},
        {"text": "E se eu treinar à noite e for dormir logo depois?", "restore": True,
         "context": True, "source": "late_training_meals_sleep"},
    ],
}


def observe(case, result):
    actions = result["actions"]
    context = result["retrieval"].get("context", {})
    clarification = result.get("clarification") or {}
    expected = case.get("action")
    checks = {
        "expected_proposal": (len(actions) == 1
            and actions[0]["payload"]["kind"] == expected
            and actions[0]["status"] == case.get("action_status", "pending_user_confirmation")
        ) if expected else not actions,
        "no_database_write": not result["planner"]["writes_allowed"],
        "no_automatic_training": not result["privacy"]["automatic_training"],
        "valid_citation_ids": not result["citations"]["unknown_chunk_ids"],
    }
    if expected == "replace_exercise" and actions:
        expected_plan = snapshot()
        checks["correct_plan_items"] = (
            actions[0]["payload"].get("workout_day_exercise_id") == expected_plan.workout_exercises[0]["id"]
            and actions[0]["payload"].get("replacement_exercise_id") == expected_plan.exercises[0]["id"]
        )
    if expected == "set_day_activity" and actions:
        checks["correct_activity"] = actions[0]["payload"].get("activity_type") == "rest"
    if "context" in case:
        checks["context"] = context.get("used") is case["context"]
    if "source" in case:
        expected_sources = case["source"]
        if isinstance(expected_sources, str):
            expected_sources = [expected_sources]
        cited_docs = {cid.split(":")[1] for cid in result["citations"]["cited_chunk_ids"]}
        checks["cited_topic"] = bool(cited_docs.intersection(expected_sources))
    if case.get("clarify"):
        checks["asks_for_clarification"] = result["analysis"]["route"] == "clarify"
    if "missing" in case:
        checks["asks_for_missing_item"] = case["missing"] in clarification.get("missing_fields", [])
    if "safety" in case:
        checks["safety"] = (case["safety"] in result["analysis"]["risk"]["labels"]
                             and result["generation"] is None)
    if "answer_has" in case:
        checks["stated_preference"] = case["answer_has"] in result["answer"].casefold()
    if "answer_excludes" in case:
        checks["excludes_old_preference"] = case["answer_excludes"] not in result["answer"].casefold()
    if case.get("other_session"):
        checks["rejects_foreign_proposal"] = "não pertence a esta sessão" in result["answer"]
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--nlp-version", default="1.8.0", choices=["1.8.0", "1.9.0"])
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    key = "local-dialogue-check-" + uuid4().hex
    settings = Settings(key, nlp_version=args.nlp_version)
    paths = ["src/evolv_rag/coach.py", "src/evolv_rag/grounding.py", "src/evolv_api/app.py",
             "configs/retrieval.runtime.v1.json", "configs/openlm.v1.json",
             "scripts/evaluate_multiturn_coach.py"]
    write(output / "protocol.json", {
        "dialogues": DIALOGUES, "nlp_version": args.nlp_version,
        "scope": "authored development cases, real inference, local API, synthetic Planner context",
        "sha256": {path: digest(AI / path) for path in paths},
    })
    plan = snapshot()
    headers = {"Authorization": "Bearer " + key, "X-Evolv-User-ID": plan.actor_id}
    other = {**headers, "X-Evolv-User-ID": str(uuid4())}
    rows = []

    def call(method, path, *, auth=headers, **kwargs):
        response = client.request(method, path, headers=auth, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else None

    def start_session(auth=headers):
        sid = call("POST", "/v1/sessions", auth=auth, json={})["session_id"]
        return "/v1/sessions/" + sid

    with TestClient(create_app(settings)) as client:
        write(output / "runtime.json", call("GET", "/health/ready"))
        for name, cases in DIALOGUES.items():
            session = start_session()
            call("PUT", session + "/planner-context", json=plan.__dict__)
            history = []
            proposal_id = None
            for i, case in enumerate(cases, 1):
                checks = {}
                if case.get("restore"):
                    call("DELETE", session)
                    session = start_session()
                    restored = call("PUT", session + "/history", json={"messages": history})
                    checks["restored_complete_pairs"] = restored == {
                        "restored_messages": len(history), "pending_actions_restored": False}
                target = session
                auth = headers
                body = {"request_id": str(uuid4()), "text": case["text"]}
                if case.get("use_proposal") and proposal_id:
                    body["proposal_id"] = proposal_id
                if case.get("other_session"):
                    denied = client.post(session + "/messages", headers=other, json=body)
                    checks["denies_other_user"] = denied.status_code == 404
                    auth = other
                    target = start_session(auth)
                result = call("POST", target + "/messages", auth=auth, json=body)["result"]
                if target != session:
                    call("DELETE", target, auth=auth)
                else:
                    history.extend([{"role": "user", "content": case["text"]},
                                    {"role": "assistant", "content": result["answer"]}])
                    if result["actions"]:
                        proposal_id = result["actions"][0]["id"]
                checks.update(observe(case, result))
                row = {"dialogue": name, "turn": i, "case": case, "checks": checks, "result": result}
                rows.append(row)
                with (output / "turns.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                failed = [k for k, passed in checks.items() if not passed]
                print(name, i, result["analysis"]["route"], failed, flush=True)
            call("DELETE", session)
    failures = [{"dialogue": r["dialogue"], "turn": r["turn"],
                 "checks": [k for k, passed in r["checks"].items() if not passed]}
                for r in rows if not all(r["checks"].values())]
    write(output / "summary.json", {
        "dialogues": len(DIALOGUES), "turns": len(rows),
        "checks_passed": sum(sum(r["checks"].values()) for r in rows),
        "checks_failed": sum(len(r["checks"]) - sum(r["checks"].values()) for r in rows),
        "turns_with_failures": failures,
    })


if __name__ == "__main__":
    main()

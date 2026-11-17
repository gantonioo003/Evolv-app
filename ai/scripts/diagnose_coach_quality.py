"""Run the 9.02 adjustment dialogues against the actual local Coach API."""

import argparse
from datetime import date
from hashlib import sha256
import json
import os
import re
from pathlib import Path
from secrets import token_hex
import sys
from time import perf_counter
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi import HTTPException

from validate_coach_quality_suite import SUITE, validate

AI = Path(__file__).resolve().parents[1]
SEED = AI.parent / "supabase/seed.sql"
sys.path.insert(0, str(AI / "src"))

from evolv_api.app import Manager, Message, PlannerContext, SessionHistory, Settings
from evolv_nlp.entities import normalize_text


def uid():
    return str(uuid4())


def exercise_catalog():
    pattern = r"(?m)^\s*\(\x27([^\x27]+)\x27, \x27([^\x27]+)\x27, \x27([^\x27]+)\x27, \x27([^\x27]+)\x27(?:\)|,)"
    return {normalize_text(name): {"display_name": name, "muscle_group": group,
                                  "equipment": equipment, "instructions": instructions}
            for name, group, equipment, instructions in re.findall(pattern, SEED.read_text(encoding="utf-8"))}


def snapshot(fixture, owner, catalog):
    workout = fixture.get("workout", {})
    meals = fixture.get("meals", {})
    workout_id = uid() if workout else None
    diet_id = uid() if meals else None
    days = {weekday: uid() for weekday in workout}
    exercise_ids = {
        name: uid() for names in fixture.get("allowed_exercise_replacements", {}).values()
        for name in names
    }
    workout_items = {(day, item["exercise"]): uid() for day, items in workout.items() for item in items}
    repetition_ranges = {
        (day, item["exercise"]): tuple(int(value) for value in re.findall(r"\d+", item.get("reps", "")))
        for day, items in workout.items() for item in items
    }
    meal_items = {f"{meal}:{name}": uid() for meal, items in meals.items() for name in items}
    food_names = fixture.get("allowed_meal_replacements", {})
    food_ids = {name: uid() for names in food_names.values() for name in names}
    context = {
        "actor_id": owner, "revision": "phase-9.02-fixture-v1",
        "workout_plan_id": workout_id, "diet_plan_id": diet_id,
        "days": [{"id": value, "weekday": weekday} for weekday, value in days.items()],
        "workout_exercises": [
            {"id": value, "workout_day_id": days[day], "canonical": name,
             **catalog.get(normalize_text(name), {"display_name": name}),
             **dict(zip(("min_reps", "max_reps"), repetition_ranges[day, name]))}
            for (day, name), value in workout_items.items()
        ],
        "exercises": [{"id": value, "canonical": name} for name, value in exercise_ids.items()],
        "meal_items": [
            {"id": value, "canonical": key.split(":", 1)[1],
             "meal_name": key.split(":", 1)[0].replace("_", " ").replace("cafe manha", "cafe da manha"),
             "approved_replacement_ids": [food_ids[name] for name in food_names.get(key, [])]}
            for key, value in meal_items.items()
        ],
        "foods": [{"id": value, "canonical": name} for name, value in food_ids.items()],
    }

    def expected_payload(spec):
        kind, old, new = spec["kind"], spec["from"], spec["to"]
        if kind == "replace_exercise":
            [item] = [value for (_, name), value in workout_items.items() if name == old]
            return {"kind": kind, "workout_plan_id": workout_id, "workout_day_exercise_id": item,
                    "replacement_exercise_id": exercise_ids[new]}
        if kind == "replace_meal_item":
            return {"kind": kind, "diet_plan_id": diet_id, "meal_item_id": meal_items[old],
                    "replacement_food_id": food_ids[new]}
        if kind == "move_workout_day":
            return {"kind": kind, "workout_plan_id": workout_id, "workout_day_id": days[old],
                    "target_weekday": new}
        return {"kind": kind, "activity_date": old, "activity_type": new}

    return context, expected_payload


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_case(manager, case, fixture, catalog):
    actor = uuid4()
    context, expected_payload = snapshot(fixture, str(actor), catalog)
    validated_context = PlannerContext.model_validate(context)
    account = {"memory_enabled": False}
    if fixture.get("profile", {}).get("preferred_training_time") == "night":
        account["training_time"] = "night"

    def start():
        session = UUID(manager.create(actor)["session_id"])
        manager.context(session, actor, validated_context)
        return session

    path = start()
    pending = None
    confirmed_for_preview = False
    history = []
    try:
        for i, turn in enumerate(case["turns"], 1):
            inp, exp = turn["input"], turn["expect"]
            behavior = exp["behavior"]
            record = {"case": case["id"], "turn": i, "input": inp, "expect": exp}
            if isinstance(inp, dict):
                event = inp["event"]
                if event in {"apply_preview", "undo_application", "inspect_plan"}:
                    record["execution"] = ("outside_fastapi" if confirmed_for_preview or event == "inspect_plan"
                                           else "blocked_by_missing_preview")
                elif event == "new_session":
                    manager.delete(path, actor)
                    path = start()
                    pending, confirmed_for_preview, history = None, False, []
                    record["execution"] = "completed"
                elif event == "reopen_session":
                    manager.delete(path, actor)
                    path = start()
                    restored = manager.restore_history(path, actor, SessionHistory.model_validate({"messages": history[-8:]}))
                    record.update(execution="completed", restored=restored)
                yield record
                continue

            body = {"request_id": uid(), "text": inp, "account_context": account}
            if behavior in {"preview", "reject"}:
                record["has_correct_pending_proposal"] = pending is not None
                if pending:
                    body["proposal_id"] = pending
            started = perf_counter()
            try:
                result = manager.message(path, actor, Message.model_validate(body))["result"]
            except HTTPException as exc:
                record.update(execution="service_error", service_status=exc.status_code, error=exc.detail)
                yield record
                continue
            record["seconds"] = round(perf_counter() - started, 4)
            record.update(execution="completed", result=result)
            actions = result["actions"]
            if behavior == "propose":
                want = expected_payload(exp["proposal"])
                record["expected_payload"] = want
                record["correct_pending_proposal"] = (
                    len(actions) == 1 and actions[0]["status"] == "pending_user_confirmation"
                    and all(actions[0]["payload"].get(field) == value for field, value in want.items())
                )
                pending = actions[0]["id"] if record["correct_pending_proposal"] else None
            elif behavior == "preview":
                confirmed_for_preview = any(a["status"] == "confirmed_for_planner_preview" for a in actions)
                record["forwardable_to_planner"] = confirmed_for_preview
            elif behavior == "reject":
                record["rejected_by_coach"] = any(a["status"] == "rejected" for a in actions)
                if record["rejected_by_coach"]:
                    pending = None

            history.extend([
                {"role": "user", "content": inp},
                {"role": "assistant", "content": result["answer"],
                 "dialogue_context": result.get("dialogue_context")},
            ])
            yield record
    finally:
        manager.delete(path, actor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--nlp-version", choices=["1.8.0", "1.9.0"], default="1.9.0")
    parser.add_argument("--split", choices=["ajuste", "verificacao"], default="ajuste")
    parser.add_argument("--phase", default="9.02")
    args = parser.parse_args()
    validate(SUITE)
    setup = json.loads((SUITE / "fixtures.json").read_text(encoding="utf-8"))
    reference = date.fromisoformat(setup["reference_date"])
    dialogues = json.loads((SUITE / f"{args.split}.json").read_text(encoding="utf-8"))["dialogues"]
    args.output.mkdir(parents=True, exist_ok=False)

    class FixedDate(date):
        @classmethod
        def today(cls):
            return reference

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    key = token_hex(32)
    settings = Settings(key, nlp_version=args.nlp_version)
    catalog = exercise_catalog()
    if "remada cavalinho" not in catalog:
        raise ValueError("Missing remada cavalinho from seed catalog")
    inputs = [
        SEED, SUITE / "manifest.json", Path(__file__).resolve(), AI / "configs/openlm.v1.json",
        AI / f"artifacts/baseline/{settings.nlp_version}/manifest.json",
        AI / f"artifacts/rag/{settings.retrieval_version}/manifest.json",
        AI / "src/evolv_api/app.py", *sorted((AI / "src/evolv_rag").glob("*.py")),
        *sorted((AI / "src/evolv_nlp").glob("*.py")),
    ]
    write(args.output / "protocol.json", {
        "phase": args.phase, "suite": "1.0.0", "split": args.split,
        "reference_date": reference.isoformat(), "fixture_timezone": setup["timezone"],
        "boundary": "real FastAPI session manager and Coach in process; synthetic snapshots and seed catalog; no HTTP, NestJS or persistent database",
        "verification_sent_to_coach": args.split == "verificacao", "dialogues": len(dialogues),
        "input_sha256": {p.relative_to(AI.parent).as_posix(): sha256(p.read_bytes()).hexdigest() for p in inputs},
    })
    print("Loading actual NLP, retrieval and Qwen", flush=True)
    manager = Manager(settings)
    manager.start()
    print("Models ready", flush=True)
    write(args.output / "runtime.json", {
        "status": manager.status, "mode": settings.mode, "variant": settings.variant,
        "nlp_version": settings.nlp_version, "retrieval_version": settings.retrieval_version,
    })
    try:
        with patch("evolv_rag.coach.date", FixedDate), (
            args.output / "turns.jsonl"
        ).open("x", encoding="utf-8", newline="\n") as stream:
            for case in dialogues:
                for row in run_case(manager, case, setup["fixtures"][case["fixture"]], catalog):
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                    stream.flush()
                    print(case["id"], row["turn"], row["execution"], flush=True)
    finally:
        manager.close()
    print("Completed", len(dialogues), "dialogues", flush=True)


if __name__ == "__main__":
    main()

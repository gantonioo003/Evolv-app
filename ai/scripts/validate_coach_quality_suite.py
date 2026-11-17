"""Validate the frozen phase 9.01 suite without starting or calling the Coach."""

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata


SUITE = Path(__file__).resolve().parents[1] / "data/evaluation/coach_quality_9_01/v1"
SPLITS = ("ajuste", "verificacao")
BEHAVIORS = {"social", "answer", "clarify", "guard", "propose", "preview", "reject"}
EVENTS = {
    "apply_preview": ("applied", "apply"),
    "undo_application": ("undone", "undo"),
    "inspect_plan": ("inspect", "none"),
    "new_session": ("inspect", "none"),
    "reopen_session": ("inspect", "none"),
}
KINDS = {"replace_exercise", "replace_meal_item", "move_workout_day", "set_day_activity"}
DIRECT_IDENTIFIERS = re.compile(
    r"https?://|[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in text if not unicodedata.combining(c))))


def validate(root):
    manifest = read(root / "manifest.json")
    paths = {"fixtures.json", *(f"{split}.json" for split in SPLITS)}
    require(set(manifest["sha256"]) == paths, "Unexpected manifest files")
    for name, digest in manifest["sha256"].items():
        actual = sha256((root / name).read_bytes()).hexdigest()
        require(actual == digest, f"Frozen file changed: {name}")

    setup = read(root / "fixtures.json")
    reference_date = date.fromisoformat(setup["reference_date"])
    fixtures = setup["fixtures"]
    seen_ids = set()
    seen_dialogues = set()
    report = {}
    for split in SPLITS:
        suite = read(root / f"{split}.json")
        require(suite["split"] == split and suite["version"] == manifest["version"], split)
        sizes = []
        events = 0
        for case in suite["dialogues"]:
            case_id = case["id"]
            require(case_id not in seen_ids, f"Duplicate ID: {case_id}")
            seen_ids.add(case_id)
            fixture = fixtures[case["fixture"]]
            source = case["source"]
            require(source in manifest["sources"], f"{case_id}: unknown source")
            require(split != "verificacao" or source == "autoral", f"{case_id}: source leaks into verification")
            require(bool(case["tags"]), f"{case_id}: missing tags")
            texts = []
            stage = "none"
            for index, turn in enumerate(case["turns"], 1):
                location = f"{case_id}/{index}"
                user_input, expected = turn["input"], turn["expect"]
                behavior, write = expected["behavior"], expected["plan_write"]
                require(bool(expected["must"].strip()), f"{location}: missing criterion")
                if isinstance(user_input, str):
                    require(bool(normalize(user_input)), f"{location}: empty message")
                    require(not DIRECT_IDENTIFIERS.search(user_input), f"{location}: direct identifier or link")
                    require(behavior in BEHAVIORS and write == "none", f"{location}: unexpected text effect")
                    texts.append(normalize(user_input))
                else:
                    event = user_input["event"]
                    require(EVENTS.get(event) == (behavior, write), f"{location}: invalid event expectation")
                    events += 1
                if behavior == "propose":
                    proposal = expected["proposal"]
                    kind, origin, target = proposal["kind"], proposal["from"], proposal["to"]
                    require(kind in KINDS and origin != target and origin and target, f"{location}: invalid proposal")
                    if kind == "replace_exercise":
                        require(target in fixture["allowed_exercise_replacements"][origin], location)
                    elif kind == "replace_meal_item":
                        require(target in fixture["allowed_meal_replacements"][origin], location)
                    elif kind == "move_workout_day":
                        require(origin in fixture["workout"] and target not in fixture["workout"], location)
                    elif kind == "set_day_activity":
                        require(origin == reference_date.isoformat() and origin in fixture["day_activity"], location)
                    stage = "pending"
                elif behavior in {"preview", "reject", "applied", "undone"}:
                    previous, next_stage = {
                        "preview": ("pending", "preview"),
                        "reject": ("pending", "none"),
                        "applied": ("preview", "applied"),
                        "undone": ("applied", "none"),
                    }[behavior]
                    require(stage == previous, f"{location}: invalid Planner sequence")
                    stage = next_stage
                if isinstance(user_input, dict) and user_input["event"] == "new_session":
                    stage = "none"
            fingerprint = tuple(texts)
            require(len(texts) >= 2 and fingerprint not in seen_dialogues, f"{case_id}: short or duplicate dialogue")
            seen_dialogues.add(fingerprint)
            sizes.append(len(texts))
        report[split] = {
            "dialogues": len(sizes),
            "user_messages": sum(sizes),
            "events": events,
            "long_dialogues": sum(size >= 10 for size in sizes),
            "max_user_messages": max(sizes),
        }
    require(report == manifest["counts"], "Suite counts changed")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=SUITE)
    print(json.dumps(validate(parser.parse_args().suite), indent=2))

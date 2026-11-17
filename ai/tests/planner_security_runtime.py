"""Line protocol for the local Planner security test, using the FastAPI session manager."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from uuid import UUID

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from evolv_api.app import Manager, Message, PlannerContext, SessionHistory, Settings


def main():
    manager = Manager(Settings("planner-security-local-test-key-32", mode=os.environ.get("EVOLV_TEST_LM_MODE", "analyze"), nlp_version=sys.argv[1],
                               interpreter=os.environ.get("EVOLV_AI_INTERPRETER", "nlp")))
    shifted_seconds = 0

    def now():
        return datetime.now(timezone.utc) + timedelta(seconds=shifted_seconds)

    manager.start()
    # Observe actual inference, including the conversational writer whose
    # metadata is not exposed as result.generation. Do not replace its output.
    lm_calls = {"write": 0, "generate": 0, "interpret": 0}
    if manager.prototype.lm is not None:
        def observe(name):
            original = getattr(manager.prototype.lm, name)
            def observed(*args, **kwargs):
                result = original(*args, **kwargs)
                lm_calls[name] += 1
                return result
            return observed
        for name in lm_calls:
            setattr(manager.prototype.lm, name, observe(name))
    print("RESULT " + json.dumps({"ready": True}), flush=True)
    try:
        for line in sys.stdin:
            try:
                call = json.loads(line)
                if call.get("stats"):
                    result = {"lm_calls": lm_calls, "classifier_loaded": manager.prototype.nlp is not None}
                elif call.get("advance") is not None:
                    shifted_seconds += call["advance"]
                    result = {}
                else:
                    actor = UUID(call["user"])
                    body = call.get("body") or {}
                    parts = call["path"].strip("/").split("/")
                    if len(parts) == 2:
                        result = manager.create(actor)
                        entry = manager.sessions[result["session_id"]]
                        entry["coach"].action_session.now = now
                    elif call["method"] == "DELETE":
                        manager.delete(UUID(parts[2]), actor)
                        result = {}
                    elif parts[3] == "planner-context":
                        result = manager.context(UUID(parts[2]), actor, PlannerContext.model_validate(body))
                    elif parts[3] == "history":
                        result = manager.restore_history(UUID(parts[2]), actor, SessionHistory.model_validate(body))
                    elif parts[3] == "messages":
                        result = manager.message(UUID(parts[2]), actor, Message.model_validate(body))
                    else:
                        raise ValueError("Unexpected Planner security runtime route")
                packet = {"result": result}
            except HTTPException as error:
                packet = {"status": error.status_code, "detail": error.detail}
            except Exception as error:
                packet = {"status": 500, "detail": type(error).__name__ + ": " + str(error)}
            print("RESULT " + json.dumps(packet, ensure_ascii=False), flush=True)
    finally:
        manager.close()


if __name__ == "__main__":
    main()

"""Internal-only API. The NestJS caller must authenticate the end user."""
from collections import OrderedDict
from contextlib import asynccontextmanager, contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import secrets
from threading import Lock
import time
from uuid import UUID, uuid4
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

AI_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    service_key: str
    variant: str = "original"
    mode: str = "generate"
    max_sessions: int = 32
    max_sessions_per_user: int = 8
    idle_seconds: int = 1800
    nlp_version: str = "1.8.0"
    retrieval_version: str = "1.1.2"

    def __post_init__(self):
        if len(self.service_key) < 32:
            raise ValueError("EVOLV_AI_SERVICE_KEY must contain at least 32 characters")
        if self.variant not in {"original", "adapted"} or self.mode not in {"generate", "analyze"}:
            raise ValueError("Invalid service model configuration")
        if min(self.max_sessions, self.max_sessions_per_user, self.idle_seconds) < 1:
            raise ValueError("Invalid session limits")
        if self.nlp_version not in {"1.8.0", "1.9.0"}:
            raise ValueError("Invalid NLP version")
        if self.retrieval_version not in {"1.0.0", "1.1.1", "1.1.2"}:
            raise ValueError("Invalid retrieval version")

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("EVOLV_AI_SERVICE_KEY", ""),
                   os.environ.get("EVOLV_AI_VARIANT", "original"),
                   os.environ.get("EVOLV_AI_MODE", "generate"),
                   nlp_version=os.environ.get("EVOLV_AI_NLP_VERSION", "1.8.0"),
                   retrieval_version=os.environ.get("EVOLV_AI_RETRIEVAL_VERSION", "1.1.2"))


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    text: str = Field(strict=True, min_length=1, max_length=8000)
    proposal_id: UUID | None = None

    @field_validator("text")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Empty text")
        return value


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(strict=True, min_length=1, max_length=8000)


class SessionHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[HistoryMessage] = Field(default_factory=list, max_length=8)

    @field_validator("messages")
    @classmethod
    def complete_pairs(cls, messages):
        if len(messages) % 2 or any(m.role != ("user" if i % 2 == 0 else "assistant")
                                    for i, m in enumerate(messages)):
            raise ValueError("Only complete user/assistant pairs may be restored")
        return messages


class NamedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    canonical: str = Field(min_length=1, max_length=200)


class WorkoutItem(NamedItem):
    workout_day_id: UUID


class Day(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    weekday: Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class PlannerContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: UUID
    revision: str = Field(min_length=1, max_length=128)
    workout_plan_id: UUID | None = None
    diet_plan_id: UUID | None = None
    days: list[Day] = Field(default_factory=list, max_length=100)
    workout_exercises: list[WorkoutItem] = Field(default_factory=list, max_length=1000)
    exercises: list[NamedItem] = Field(default_factory=list, max_length=1000)
    meal_items: list[NamedItem] = Field(default_factory=list, max_length=1000)
    foods: list[NamedItem] = Field(default_factory=list, max_length=1000)


class SessionCreated(BaseModel):
    session_id: UUID
    idle_timeout_seconds: int
    persistence: str = "memory_only"


class MessageResponse(BaseModel):
    session_id: UUID
    request_id: UUID
    result: dict


class Manager:
    def __init__(self, settings, loader=None, clock=None):
        self.settings, self.loader = settings, loader
        self.clock = clock or time.monotonic
        self.lock = Lock()
        self.prototype = None
        self.status = "loading"
        self.sessions = {}

    def start(self):
        if self.loader:
            self.prototype = self.loader()
        else:
            from evolv_rag.coach import load_coach
            self.prototype = load_coach(AI_ROOT, generate=self.settings.mode == "generate",
                                        adapted=self.settings.variant == "adapted",
                                        nlp_version=self.settings.nlp_version,
                                        retrieval_version=self.settings.retrieval_version)
        self.status = "ready"

    def close(self):
        for entry in self.sessions.values():
            entry["coach"].clear()
        self.sessions.clear()
        self.prototype = None
        self.status = "stopped"

    @contextmanager
    def exclusive(self):
        if self.status != "ready":
            raise HTTPException(503, "models_unavailable")
        if not self.lock.acquire(blocking=False):
            raise HTTPException(429, "service_busy", headers={"Retry-After": "2"})
        try:
            expired = [sid for sid, e in self.sessions.items()
                       if self.clock() - e["last_used"] >= self.settings.idle_seconds]
            for sid in expired:
                self.sessions.pop(sid)["coach"].clear()
            yield
        finally:
            self.lock.release()

    def owned(self, sid, user):
        entry = self.sessions.get(str(sid))
        if not entry or entry["owner"] != str(user):
            raise HTTPException(404, "session_not_found")
        return entry

    def create(self, user):
        with self.exclusive():
            if len(self.sessions) >= self.settings.max_sessions:
                raise HTTPException(429, "session_capacity")
            if sum(e["owner"] == str(user) for e in self.sessions.values()) >= self.settings.max_sessions_per_user:
                raise HTTPException(429, "user_session_capacity")
            from evolv_rag.coach import Coach
            p = self.prototype
            # Models are shared; history, proposals and deduplication are not.
            coach = Coach(p.nlp, p.search, p.lm)
            sid = str(uuid4())
            self.sessions[sid] = {"owner": str(user), "coach": coach,
                                  "last_used": self.clock(), "requests": OrderedDict()}
            return {"session_id": sid, "idle_timeout_seconds": self.settings.idle_seconds}

    def delete(self, sid, user):
        with self.exclusive():
            entry = self.owned(sid, user)
            entry["coach"].clear()
            del self.sessions[str(sid)]

    def context(self, sid, user, context):
        with self.exclusive():
            entry = self.owned(sid, user)
            if context.actor_id != user:
                raise HTTPException(403, "context_owner_mismatch")
            from evolv_rag.actions import PlannerSnapshot
            from evolv_nlp.entities import normalize_text
            raw = context.model_dump(mode="json")
            catalog = getattr(self.prototype.nlp, "catalog", None)
            aliases = {}
            if catalog:
                for item in catalog.entries:
                    for alias in (*item.aliases, item.canonical):
                        aliases.setdefault((item.entity_type, normalize_text(alias)), set()).add(item.canonical)
            for collection, kind in [("workout_exercises","exercise"),("exercises","exercise"),
                                     ("meal_items","food"),("foods","food")]:
                for item in raw[collection]:
                    matches = aliases.get((kind, normalize_text(item["canonical"])), set())
                    if len(matches) == 1:
                        item["canonical"] = next(iter(matches))
            snapshot = PlannerSnapshot(**raw)
            fingerprint = snapshot.fingerprint()
            entry["coach"].action_session.snapshot = snapshot
            entry["last_used"] = self.clock()
            return {"snapshot_fingerprint": fingerprint}

    def restore_history(self, sid, user, history):
        with self.exclusive():
            entry = self.owned(sid, user)
            from evolv_nlp.privacy import review_text
            from evolv_rag.safety import critical_risks
            restored = []
            for message in history.messages:
                turn = {"role": message.role, "content": review_text(message.content).minimized_text[:8000]}
                if message.role == "user":
                    turn["critical_risks"] = critical_risks(message.content)
                restored.append(turn)
            entry["coach"].clear()
            entry["requests"].clear()
            entry["coach"].history = restored
            entry["last_used"] = self.clock()
            return {"restored_messages": len(history.messages), "pending_actions_restored": False}

    def message(self, sid, user, message):
        with self.exclusive():
            entry = self.owned(sid, user)
            request_id = str(message.request_id)
            fingerprint = hashlib.sha256(json.dumps(
                [message.text, str(message.proposal_id)], ensure_ascii=False).encode()).hexdigest()
            cached = entry["requests"].get(request_id)
            if cached:
                if cached[0] != fingerprint:
                    raise HTTPException(409, "request_id_reused_with_different_content")
                entry["last_used"] = self.clock()
                return deepcopy(cached[1])
            coach = entry["coach"]
            history, pending = deepcopy(coach.history), deepcopy(coach.action_session.pending)
            try:
                result = coach.respond(message.text,
                    proposal_id=str(message.proposal_id) if message.proposal_id else None)
            except Exception as exc:
                coach.history, coach.action_session.pending = history, pending
                # No prompts, paths, tokens, identifiers or tracebacks in HTTP errors.
                if isinstance(exc, ValueError):
                    raise HTTPException(422, "coach_could_not_process_message") from None
                raise HTTPException(503, "generation_unavailable") from None
            response = {"session_id": str(sid), "request_id": request_id, "result": result}
            entry["requests"][request_id] = (fingerprint, deepcopy(response))
            while len(entry["requests"]) > 8:
                entry["requests"].popitem(last=False)
            entry["last_used"] = self.clock()
            return response


class LimitBody:
    """Bound raw UTF-8 body bytes, including chunked uploads, before JSON parsing."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            limit = 262144 if scope.get("path", "").endswith(("/planner-context", "/history")) else 65536
            if size > limit:
                response = JSONResponse({"detail": "request_too_large"}, status_code=413)
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        sent = False
        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)


def create_app(settings=None, loader=None, clock=None):
    settings = settings or Settings.from_env()
    manager = Manager(settings, loader, clock)

    @asynccontextmanager
    async def lifespan(app):
        try:
            await run_in_threadpool(manager.start)
        except Exception:
            manager.status = "failed"
        try:
            yield
        finally:
            await run_in_threadpool(manager.close)

    app = FastAPI(title="Evolv Coach — internal research API", version="1.2.0", lifespan=lifespan)
    app.state.manager = manager
    app.add_middleware(LimitBody)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({"detail": "invalid_request"}, status_code=422)

    def authenticated(authorization: str = Header(default="")):
        supplied = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
        if not secrets.compare_digest(supplied.encode(), settings.service_key.encode()):
            raise HTTPException(401, "invalid_service_credentials", headers={"WWW-Authenticate": "Bearer"})

    def actor(_=Depends(authenticated), x_evolv_user_id: UUID = Header()):
        # Trusted service metadata. Supabase JWT validation belongs in NestJS (7.06.2).
        return x_evolv_user_id

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready", dependencies=[Depends(authenticated)])
    def ready():
        if manager.status != "ready":
            raise HTTPException(503, "models_unavailable")
        return {"status": "ready", "mode": settings.mode, "variant": settings.variant,
                "nlp_version": settings.nlp_version, "retrieval_version": settings.retrieval_version}

    @app.post("/v1/sessions", response_model=SessionCreated, status_code=201)
    def create_session(body: EmptyBody, user=Depends(actor)):
        return manager.create(user)

    @app.delete("/v1/sessions/{session_id}", status_code=204)
    def delete_session(session_id: UUID, user=Depends(actor)):
        manager.delete(session_id, user)

    @app.post("/v1/sessions/{session_id}/messages", response_model=MessageResponse)
    def send_message(session_id: UUID, body: Message, user=Depends(actor)):
        return manager.message(session_id, user, body)

    @app.put("/v1/sessions/{session_id}/planner-context")
    def planner_context(session_id: UUID, body: PlannerContext, user=Depends(actor)):
        return manager.context(session_id, user, body)

    @app.put("/v1/sessions/{session_id}/history")
    def restore_history(session_id: UUID, body: SessionHistory, user=Depends(actor)):
        return manager.restore_history(session_id, user, body)

    return app

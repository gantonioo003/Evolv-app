"""Small, conversation-scoped memory kept alongside the saved transcript."""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .retrieval import fold


class DialogueContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: Literal["daily_hydration", "training_goal", "knowledge", "workout_exercise",
                   "schedule", "meal_routine", "training_log", "equipment", "training_review", "travel",
                   "sleep_recovery", "plan_read", "routine_context"]
    anchor: str = Field(min_length=1, max_length=800)
    details: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(default_factory=list, max_length=6)
    facts: dict[Annotated[str, Field(min_length=1, max_length=32)],
                Annotated[str, Field(min_length=1, max_length=180)]] = Field(default_factory=dict, max_length=12)

    def minimized(self):
        from evolv_nlp.privacy import review_text

        return self.model_copy(update={
            "anchor": review_text(self.anchor).minimized_text[:800],
            "details": [review_text(detail).minimized_text[:300] for detail in self.details],
            "facts": {key: review_text(value).minimized_text[:180] for key, value in self.facts.items()},
        })

    def with_detail(self, text):
        detail = text[:300]
        details = [item for item in self.details if item != detail]
        return self.model_copy(update={"details": (details + [detail])[-6:]})


class ConversationMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topics: list[DialogueContext] = Field(default_factory=list, max_length=12)

    @property
    def active(self):
        return self.topics[-1] if self.topics else None

    def latest(self, topic):
        return next((context for context in reversed(self.topics) if context.topic == topic), None)

    def remembering(self, context):
        remaining = [item for item in self.topics if item.topic != context.topic
                     or (context.topic == "knowledge" and item.anchor != context.anchor)]
        topics = remaining + [context]
        # Keep recent general questions without evicting the user's typed facts.
        general = [i for i, topic in enumerate(topics) if topic.topic == "knowledge"]
        excess = max(0, len(topics) - 12, len(general) - 2)
        drop = set(general[:excess])
        kept = [topic for i, topic in enumerate(topics) if i not in drop]
        return self.model_copy(update={"topics": kept[-12:]})

    def recording(self, topic, text, facts):
        prior = self.latest(topic)
        previous = {key: value for key, value in prior.facts.items() if key not in facts} if prior else {}
        recent = dict(list((previous | facts).items())[-12:])
        context = DialogueContext(topic=topic, anchor=prior.anchor if prior else text[:800],
                                  facts=recent)
        return self.remembering(context)

    def minimized(self):
        return self.model_copy(update={"topics": [topic.minimized() for topic in self.topics]})


_RESUME = re.compile(
    r"(?:voltando(?: ao assunto| de onde paramos)?|voltando pra onde paramos|"
    r"bora voltar|vamos voltar(?: ao assunto)?|continuando|onde paramos)"
)
_RESUME_HYDRATION = re.compile(
    r"(?:voltando|(?:bora|vamos) voltar) (?:a|pra|para|sobre) (?:a )?(?:agua|hidratacao)"
)
_ASIDE = re.compile(
    r"\b(?:e o cara|e a melhor|e o melhor|brincadeira|so zoando|to zoando)\b"
)
_ROUTINE = re.compile(
    r"^(?:(?:hoje |atualmente |eu )*treino|faco (?:so )?(?:academia|musculacao)|"
    r"to comecando|sou iniciante|\d+\s*(?:x|vezes) (?:na|por) semana)\b"
)
_TRAINING_GOAL = re.compile(
    r"\b(?:meu objetivo|quero|queria)\b.{0,70}\b(?:forca|massa muscular|musculo|"
    r"hipertrofia|condicionamento|resistencia|emagrecer|perder peso)\b"
)


def resumes_topic(text):
    return bool(_RESUME.fullmatch(fold(text).strip(" ?.!,…")))


def resumes_hydration(text):
    return bool(_RESUME_HYDRATION.fullmatch(fold(text).strip(" ?.!,…")))


def playful_aside(text):
    clean = fold(text).strip()
    return bool(len(clean) <= 140 and "?" not in clean and _ASIDE.search(clean))


def training_routine(text):
    return bool(_ROUTINE.match(fold(text).strip()))


def training_goal(text):
    return bool(_TRAINING_GOAL.search(fold(text)))


def topic_reference(context):
    return {
        "daily_hydration": "a hidratação",
        "training_goal": "seu objetivo de treino",
        "knowledge": "o que estávamos conversando",
        "workout_exercise": "o exercício da sua ficha",
        "schedule": "seus horários de treino",
        "meal_routine": "suas refeições",
        "training_log": "o treino que você fez",
        "equipment": "o equipamento disponível",
        "training_review": "os ajustes no treino",
        "travel": "sua rotina na viagem",
        "sleep_recovery": "o sono e a recuperação",
        "plan_read": "a consulta à sua ficha",
        "routine_context": "o que você contou sobre sua rotina",
    }[context.topic]

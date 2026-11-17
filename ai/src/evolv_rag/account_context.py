"""Read-only, authenticated account facts and explicitly saved preferences."""

import re
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from evolv_nlp.privacy import review_text
from .retrieval import fold, tokens


class AccountDay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    source: Literal["override", "workout_plan", "profile", "default"]
    activity_type: Literal["rest", "resistance", "cardio", "mixed"]
    nutrition_day_type: Literal["training_day", "rest_day"]
    workout_day_id: UUID | None = None


class ExerciseHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exercise: str = Field(min_length=1, max_length=200)
    date: date
    load_kg: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    sets_completed: int | None = Field(default=None, ge=0, le=30)
    repetitions: int | None = Field(default=None, ge=1, le=1000)
    duration_seconds: int | None = Field(default=None, ge=1, le=86400)


class AccountContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memory_enabled: bool = False
    memories: list[Annotated[str, Field(max_length=180)]] = Field(default_factory=list, max_length=100)
    age: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    level: str | None = Field(default=None, max_length=32)
    training_days: list[Annotated[str, Field(max_length=16)]] = Field(default_factory=list, max_length=7)
    training_time: str | None = Field(default=None, max_length=5)
    disliked_foods: list[Annotated[str, Field(max_length=120)]] = Field(default_factory=list, max_length=20)
    goal: str | None = Field(default=None, max_length=32)
    day: AccountDay | None = None
    exercise_logs: list[ExerciseHistoryEntry] = Field(default_factory=list, max_length=60)


_REMEMBER = re.compile(r"^(?:lembre|lembra|guarde|guarda|salve|salva|anote|anota)(?: na memoria)? que ")
_PREFERENCE = re.compile(r"^(?:eu )?(?:prefiro|gosto de|nao gosto de|costumo|treino|pratico|meu objetivo e)\b")
_PRIVATE = re.compile(
    r"\b(?:senha|token|cpf|rg|cartao|endereco|telefone|email|diagnostic\w*|alerg\w*|doenca|lesao|medicamento|"
    r"remedio|gravidez|diabetes|depressao|ignora|ignore|instrucoes|sempre responda)\b"
)
_MEMORY_LOOKUP = re.compile(
    r"\b(?:o que (?:voce |vc )?(?:lembra|guardou|salvou)(?: de mim)?|"
    r"minhas memorias|(?:que|qual) horario (?:eu )?prefiro treinar|(?:o que|qual) (?:eu )?prefiro)\b"
)
_PROFILE_LOOKUP = re.compile(
    r"\b(?:meu (?:peso|objetivo|perfil|nivel|horario)|minha (?:altura|idade)|"
    r"meus dias de treino|quantos dias (?:eu )?treino|alimentos (?:que )?(?:eu )?nao gosto|"
    r"horario de treino\b.{0,45}\b(?:salvo|perfil|conta))\b"
)
_GOALS = {"hypertrophy": "ganhar massa muscular", "fat_loss": "perder gordura", "strength": "ganhar força",
          "health": "melhorar a saúde", "recomposition": "recomposição corporal", "maintenance": "manter a rotina"}
_LEVELS = {"beginner": "iniciante", "intermediate": "intermediário", "advanced": "avançado"}


def memory_request(text, account):
    match = _REMEMBER.match(fold(text))
    if match is None:
        return None
    if not account.memory_enabled:
        return "Ative a memória entre conversas em Conta → Memória do Coach para eu guardar isso.", None
    content = text[match.end():].strip(" .!?,")
    normalized = fold(content)
    if (not _PREFERENCE.match(normalized) or _PRIVATE.search(normalized) or not 8 <= len(content) <= 180
            or re.search(r"[\[\]<>\n]", content)
            or "?" in text or review_text(content).minimized_text != content):
        return "Posso guardar uma preferência ou hábito, como “Prefiro treinar à noite”.", None
    return "Essa preferência pode ser guardada na memória do Coach.", content


def account_reply(text, account):
    normalized = fold(text).strip()
    if _MEMORY_LOOKUP.search(normalized):
        if not account.memory_enabled:
            return "A memória entre conversas está desativada na sua conta."
        saved = [review_text(item).minimized_text for item in account.memories]
        if not saved:
            return "Sua memória do Coach ainda está vazia. Você pode dizer “Lembre que prefiro treinar à noite”."
        if "prefiro" in normalized:
            keywords = set(tokens(normalized)) - {"prefiro", "horario"}
            saved = [item for item in saved if keywords & set(tokens(item))]
            if not saved:
                return "Ainda não tenho uma preferência salva sobre isso."
        return "Você tem estas informações salvas na memória do Coach. " + " ".join(f"“{item}”" for item in saved[:5])

    if re.search(r"\b(?:outra conta|de outra pessoa|perfil alheio)\b", normalized):
        return None
    saved_schedule = "horario" in normalized and bool(re.search(r"\b(?:salvo|perfil|conta)\b", normalized))
    if not ((_PROFILE_LOOKUP.search(normalized) or saved_schedule)
            and re.match(r"^(?:qual|quais|quando|quanto|quantos|o que|voce sabe|vc sabe|me (?:diz|fala))\b", normalized)):
        return None
    fields = {
        "peso": f"peso de {account.weight_kg:g} kg" if account.weight_kg is not None else None,
        "altura": f"altura de {account.height_cm:g} cm" if account.height_cm is not None else None,
        "idade": f"idade de {account.age} anos" if account.age is not None else None,
        "objetivo": _GOALS.get(account.goal),
        "nivel": _LEVELS.get(account.level),
        "dias": f"{len(account.training_days)} dias disponíveis para treinar" if account.training_days else None,
        "horario": ("horário de treino à noite" if account.training_time == "night"
                    else f"horário de treino às {account.training_time}" if account.training_time else None),
        "alimentos": "alimentos que você prefere evitar: " + ", ".join(
            review_text(item).minimized_text for item in account.disliked_foods
        ) if account.disliked_foods else None,
    }
    if "perfil" in normalized:
        values = [value for value in fields.values() if value]
    else:
        values = [value for key, value in fields.items() if key in normalized and value]
    return ("No seu perfil consta " + ", ".join(values) + "." if values
            else "Esse dado ainda não está preenchido no seu perfil.")


def training_goal_reply(account):
    days = len(account.training_days)
    if days:
        available = "1 dia disponível" if days == 1 else f"{days} dias disponíveis"
        return f"Vi que você tem {available} no perfil. Em que exercício ou movimento você quer progredir primeiro?"
    if account.memory_enabled:
        for item in account.memories:
            if re.match(r"^(?:eu )?(?:prefiro treinar|costumo treinar|treino)\b", fold(item)):
                saved = review_text(item).minimized_text
                return (f"Você me pediu para lembrar desta parte da sua rotina. “{saved}” "
                        "Em que exercício ou movimento você quer progredir primeiro?")
    return None

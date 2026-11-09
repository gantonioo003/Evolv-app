"""Strict local DTO preparation. Snapshots must come from authenticated backend code."""
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
from uuid import UUID, uuid4

KINDS = {
    "move_workout_day": {"workout_plan_id", "workout_day_id", "target_weekday"},
    "replace_exercise": {"workout_plan_id", "workout_day_exercise_id", "replacement_exercise_id"},
    "replace_meal_item": {"diet_plan_id", "meal_item_id", "replacement_food_id"},
    "set_day_activity": {"activity_date", "activity_type"},
}
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def validate_payload(payload):
    kind = payload.get("kind")
    if kind not in KINDS or set(payload) != KINDS[kind] | {"kind", "reason", "source"}:
        raise ValueError("Unknown action or unexpected/missing fields")
    if payload["source"] != "coach" or not isinstance(payload["reason"], str) or not 1 <= len(payload["reason"].strip()) <= 500:
        raise ValueError("Invalid action provenance/reason")
    for key in KINDS[kind]:
        value = payload[key]
        if key.endswith("_id"):
            if not isinstance(value, str) or str(UUID(value)) != value.lower():
                raise ValueError("Invalid UUID")
        elif key == "target_weekday" and value not in WEEKDAYS:
            raise ValueError("Invalid weekday")
        elif key == "activity_type" and value not in {"rest", "resistance", "cardio", "mixed"}:
            raise ValueError("Invalid activity type")
        elif key == "activity_date" and date.fromisoformat(value).isoformat() != value:
            raise ValueError("Invalid date")
    return deepcopy(payload)


@dataclass
class PlannerSnapshot:
    actor_id: str
    revision: str
    workout_plan_id: str | None = None
    diet_plan_id: str | None = None
    days: list = field(default_factory=list)
    workout_exercises: list = field(default_factory=list)
    exercises: list = field(default_factory=list)
    meal_items: list = field(default_factory=list)
    foods: list = field(default_factory=list)

    def fingerprint(self):
        UUID(self.actor_id)
        if not self.revision:
            raise ValueError("Missing backend revision")
        return hashlib.sha256(json.dumps(self.__dict__, sort_keys=True).encode()).hexdigest()


def unique(rows):
    if len(rows) != 1:
        raise ValueError("Alvo ausente ou ambíguo no contexto do plano.")
    return rows[0]


def proposed_payload(analysis, snapshot):
    if not snapshot:
        raise ValueError("Preciso do contexto autenticado do seu plano para identificar os itens.")
    kind = analysis["intent"]["label"]
    if kind not in KINDS:
        raise ValueError("Esta alteração ainda não tem contrato implementado no Planner.")
    entities = [e for e in analysis["entities"]["entities"]
                if not any(e.get("attributes", {}).get(k) for k in
                           ("negated", "requires_context", "hypothetical", "third_party"))]
    def values(name):
        return sorted([e for e in entities if e["entity_type"] == name], key=lambda e: e.get("start", 0))
    def one(name):
        return unique(values(name))["value"]
    payload = {"kind": kind, "source": "coach", "reason": "Alteração solicitada pelo usuário; sujeita à prévia do Planner."}
    if kind == "move_workout_day":
        source = date.fromisoformat(one("source_date"))
        target = date.fromisoformat(one("target_date"))
        # The backend modifies the weekly template, not an arbitrary future occurrence.
        if source.isocalendar()[:2] != target.isocalendar()[:2]:
            raise ValueError("Mover entre semanas exige esclarecer o alcance da mudança.")
        origin = unique([d for d in snapshot.days if d["weekday"] == WEEKDAYS[source.weekday()]])
        if source.weekday() == target.weekday():
            raise ValueError("Origem e destino são iguais.")
        if any(d["weekday"] == WEEKDAYS[target.weekday()] for d in snapshot.days):
            raise ValueError("O destino já tem treino; esclareça o conflito antes de propor.")
        payload.update(workout_plan_id=snapshot.workout_plan_id, workout_day_id=origin["id"],
                       target_weekday=WEEKDAYS[target.weekday()])
    elif kind in {"replace_exercise", "replace_meal_item"}:
        mention_type = "exercise" if kind == "replace_exercise" else "food"
        mentions = sorted(values(mention_type) + values("replacement_" + mention_type),
                          key=lambda e: e.get("start", 0))
        if len(mentions) != 2 or mentions[0]["value"] == mentions[1]["value"]:
            raise ValueError("Diga qual item sai e qual entra, nessa ordem.")
        # Explicit role assignment from the user's span, never inferred from list order alone.
        text = analysis["entities"]["text"]
        between = text[mentions[0]["end"]:mentions[1]["start"]].lower()
        if not re.search(r"\b(?:por|para|pelo|pela)\b", between):
            raise ValueError("Qual item você quer substituir por qual?")
        old, new = [m["value"] for m in mentions]
        if kind == "replace_exercise":
            item = unique([r for r in snapshot.workout_exercises if r["canonical"] == old])
            replacement = unique([r for r in snapshot.exercises if r["canonical"] == new])
            if not any(d["id"] == item["workout_day_id"] for d in snapshot.days):
                raise ValueError("Exercício fora dos dias do plano fornecido.")
            payload.update(workout_plan_id=snapshot.workout_plan_id,
                           workout_day_exercise_id=item["id"], replacement_exercise_id=replacement["id"])
        else:
            item = unique([r for r in snapshot.meal_items if r["canonical"] == old])
            replacement = unique([r for r in snapshot.foods if r["canonical"] == new])
            payload.update(diet_plan_id=snapshot.diet_plan_id, meal_item_id=item["id"],
                           replacement_food_id=replacement["id"])
    else:
        from evolv_nlp.activity_type import usable_activity_values
        candidates = usable_activity_values(analysis["entities"]["text"])
        if len(candidates) != 1:
            raise ValueError("Qual atividade deseja para essa data: descanso, musculação, cardio ou misto?")
        payload.update(activity_date=one("target_date"), activity_type=candidates.pop())
    return validate_payload(payload)


class ActionSession:
    def __init__(self, snapshot=None, now=None):
        self.snapshot = deepcopy(snapshot)
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.pending = None

    def clear(self):
        self.pending = None

    def propose(self, analysis):
        # An uncertain intent never authorizes a change.
        if not analysis["intent"].get("confident") or analysis["risk"]["labels"]:
            raise ValueError("Confirme os detalhes do pedido antes de propor uma alteração.")
        from evolv_nlp.entities import normalize_text
        text = normalize_text(analysis["entities"]["text"])
        if re.search(r"\b(?:nao|nunca|talvez|hipoteticamente)\b|\bse eu\b|"
                     r"\be\s+(?:troque|mude|mova|altere|registre|crie)\b", text):
            raise ValueError("Pedido negado, hipotético ou composto: esclareça uma mudança por vez.")
        payload = proposed_payload(analysis, self.snapshot)
        self.pending = {"id": str(uuid4()), "payload": payload,
                        "snapshot_fingerprint": self.snapshot.fingerprint(),
                        "expires_at": (self.now() + timedelta(minutes=10)).isoformat(),
                        "status": "pending_user_confirmation"}
        return deepcopy(self.pending)

    def transition(self, proposal_id, decision):
        if decision not in {"confirm", "reject"}:
            raise ValueError("Decisão inválida.")
        p = self.pending
        if not p or p["id"] != proposal_id:
            raise ValueError("Proposta não pertence a esta sessão.")
        if p["status"] != "pending_user_confirmation":
            raise ValueError("Proposta já resolvida; não repetir o envio.")
        if self.now() >= datetime.fromisoformat(p["expires_at"]):
            p["status"] = "expired"
            raise ValueError("Proposta vencida. Solicite uma nova prévia.")
        if self.snapshot is None or p["snapshot_fingerprint"] != self.snapshot.fingerprint():
            p["status"] = "stale"
            raise ValueError("Plano alterado. Solicite uma nova prévia.")
        p["status"] = "confirmed_for_planner_preview" if decision == "confirm" else "rejected"
        return deepcopy(p)

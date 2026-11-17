"""Strict local DTO preparation. Snapshots must come from authenticated backend code."""
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
from uuid import UUID, uuid4

from .request_intent import change_scope, exact_swap, explicit_change, meal_qualifiers
from .retrieval import fold

KINDS = {
    "move_workout_day": {"workout_plan_id", "workout_day_id", "target_weekday"},
    "move_workout_occurrence": {"workout_plan_id", "workout_day_id", "source_date", "target_date"},
    "replace_exercise": {"workout_plan_id", "workout_day_exercise_id", "replacement_exercise_id"},
    "replace_meal_item": {"diet_plan_id", "meal_item_id", "replacement_food_id"},
    "set_day_activity": {"activity_date", "activity_type"},
}
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
ORDINAL_MEALS = ("primeira", "segunda", "terceira", "quarta", "quinta", "sexta")


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
        elif key in {"activity_date", "source_date", "target_date"} and date.fromisoformat(value).isoformat() != value:
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
    workout_start: str | None = None
    workout_end: str | None = None
    diet_variants: bool = False
    diet_rotation_size: int = 1
    week: list = field(default_factory=list)

    def fingerprint(self):
        UUID(self.actor_id)
        if not self.revision:
            raise ValueError("Missing backend revision")
        return hashlib.sha256(json.dumps(self.__dict__, sort_keys=True).encode()).hexdigest()


def unique(rows):
    if len(rows) != 1:
        raise ValueError("Alvo ausente ou ambíguo no contexto do plano.")
    return rows[0]


def usable_entities(analysis):
    return [e for e in analysis.get("entities", {}).get("entities", [])
            if not any(e.get("attributes", {}).get(k) for k in
                       ("negated", "requires_context", "hypothetical", "third_party"))]


def meal_targets(snapshot, food, entities, text):
    meals = meal_qualifiers(text) or {fold(e["value"]) for e in entities if e["entity_type"] == "meal"}
    return [item for item in snapshot.meal_items if item["canonical"] == food
            and (not meals or (len(meals) == 1 and fold(item.get("meal_name") or "") in meals))]


def food_matches(rows, name):
    exact = [row for row in rows if fold(row["canonical"]) == name]
    if exact:
        return exact
    if name in {"macarrao", "espaguete", "spaghetti", "macarrao simples tipo spaghetti",
                "macarrao simples tipo espaguete"}:
        heads = (("macarrao", "espaguete", "spaghetti") if name == "macarrao"
                 else ("espaguete", "spaghetti", "macarrao espaguete", "macarrao spaghetti"))
    else:
        heads = (name,)
    return [row for row in rows if any(
        fold(row["canonical"]) == head or fold(row["canonical"]).startswith(head + " ") for head in heads)]


def requested_meal(row, name):
    label = fold(row.get("meal_name") or "")
    if label == name:
        return True
    position = row.get("meal_position")
    if position is None:
        return False
    return (name == f"refeicao {position + 1}"
            or (position < len(ORDINAL_MEALS) and name == f"{ORDINAL_MEALS[position]} refeicao"))


def proposed_payload(analysis, snapshot):
    if not snapshot:
        raise ValueError("Preciso do contexto autenticado do seu plano para identificar os itens.")
    kind = analysis["intent"]["label"]
    if kind not in KINDS:
        raise ValueError("Esta alteração ainda não tem contrato implementado no Planner.")
    entities = usable_entities(analysis)
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
            item = unique(meal_targets(snapshot, old, entities, text))
            replacement = unique([r for r in snapshot.foods if r["canonical"] == new])
            allowed = item.get("approved_replacement_ids")
            if allowed is not None and replacement["id"] not in allowed:
                raise ValueError("O alimento não é uma substituição aprovada para este item.")
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
        self.incomplete_swap = None

    def clear(self):
        self.pending = None
        self.incomplete_swap = None

    def resolve_food_swap(self, swap, today, account_day, *, requested):
        """Resolve the authenticated plan item and only use approved replacement IDs."""
        snapshot = self.snapshot
        if not snapshot:
            return None
        old_known = food_matches(snapshot.foods + snapshot.meal_items, swap.old)
        new_known = food_matches(snapshot.foods, swap.new)
        if not (old_known or new_known or swap.meals):
            return None
        if not snapshot.diet_plan_id:
            return "Preciso de um plano alimentar ativo para conferir essa troca.", None
        rotation = (today - date(1970, 1, 1)).days % snapshot.diet_rotation_size
        if snapshot.diet_variants and not account_day:
            return "Você quer revisar o cardápio de treino ou o de descanso?", None
        rows = [row for row in snapshot.meal_items if row.get("rotation_index", 0) == rotation
                and (not snapshot.diet_variants or row.get("day_type", "every_day")
                     in {"every_day", account_day.nutrition_day_type})]
        if swap.meals:
            rows = [row for row in rows if all(requested_meal(row, meal) for meal in swap.meals)]
        targets = food_matches(rows, swap.old)
        if not targets:
            location = " na refeição indicada" if swap.meals else " no cardápio de hoje"
            return f"Não encontrei {swap.old}{location}. Em qual refeição esse alimento aparece?", None
        if len(targets) != 1:
            return f"Encontrei mais de um item que pode ser {swap.old}. Qual é o nome dele na ficha e em qual refeição está?", None
        item = targets[0]
        approved = [row for row in snapshot.foods if row["id"] in (item.get("approved_replacement_ids") or [])]
        alternatives = food_matches(approved, swap.new)
        label = item.get("meal_name") or "essa refeição"
        if not alternatives:
            options = ", ".join(sorted({row["canonical"] for row in approved})[:3])
            message = f"Entendi a troca de {item['canonical']} por {swap.new} em {label}. Essa opção não está aprovada para o item no seu plano."
            return (f"{message} Entre as alternativas estão {options}." if options else message), None
        if len(alternatives) != 1:
            names = ", ".join(sorted({row["canonical"] for row in alternatives})[:4])
            return f"Qual dessas opções você tem em casa? {names}.", None
        replacement = alternatives[0]
        if not requested:
            return (f"Para {label}, {replacement['canonical']} é uma alternativa aprovada para {item['canonical']}. "
                    "A porção fica na prévia se você quiser fazer a troca."), None
        payload = validate_payload({
            "kind": "replace_meal_item", "source": "coach",
            "reason": "Troca de alimento solicitada pelo usuário; sujeita à prévia do Planner.",
            "diet_plan_id": snapshot.diet_plan_id, "meal_item_id": item["id"],
            "replacement_food_id": replacement["id"],
        })
        pending = self.pending
        if (pending and pending["status"] == "pending_user_confirmation"
                and pending["payload"] == payload and self.now() < datetime.fromisoformat(pending["expires_at"])
                and pending["snapshot_fingerprint"] == snapshot.fingerprint()):
            return "A proposta já está pronta. Abra a prévia para revisar a porção e confirmar.", None
        proposal = self._prepare(payload)
        return (f"Preparei a troca de {item['canonical']} por {replacement['canonical']} em {label}. "
                "Abra a prévia para revisar a porção e confirmar."), proposal

    def propose(self, analysis):
        # An uncertain intent never authorizes a change.
        if not analysis["intent"].get("confident") or analysis["risk"]["labels"]:
            raise ValueError("Confirme os detalhes do pedido antes de propor uma alteração.")
        text = analysis["entities"]["text"]
        if change_scope(text) or not explicit_change(text):
            raise ValueError("Pedido sem uma alteração única e explícita.")
        return self._prepare(proposed_payload(analysis, self.snapshot))

    def propose_explicit_swap(self, analysis):
        """Prepare only a single grounded swap when the model is unsure."""
        if not self.snapshot or analysis["risk"]["labels"] or analysis["intent"].get("confident"):
            return None
        text = analysis["entities"].get("text", "")
        if change_scope(text):
            return None
        entities = usable_entities(analysis)
        for entity_type, kind in (("food", "replace_meal_item"), ("exercise", "replace_exercise")):
            mentions = sorted([e for e in entities if e["entity_type"] in
                               {entity_type, "replacement_" + entity_type}], key=lambda e: e["start"])
            if len(mentions) != 2:
                continue
            meal = entity_type == "food"
            if not exact_swap(text, *mentions, meal=meal):
                continue
            if meal:
                targets = meal_targets(self.snapshot, mentions[0]["value"], entities, text)
                if len(targets) != 1 or not targets[0].get("approved_replacement_ids"):
                    return None
            candidate = {**analysis, "intent": {**analysis["intent"], "label": kind}}
            try:
                return self._prepare(proposed_payload(candidate, self.snapshot))
            except ValueError:
                return None
        return None

    def remember_incomplete_swap(self, analysis, clarification):
        """Keep the destination for one reply to an explicit request for a swap."""
        if not self.snapshot or not clarification or clarification["reason"] != "missing_fields":
            return
        text = analysis.get("entities", {}).get("text", "")
        if change_scope(text) or not explicit_change(text):
            return
        missing = clarification["missing_fields"]
        if missing not in (["exercise"], ["food"]):
            return
        [noun] = missing
        kind = "replace_exercise" if noun == "exercise" else "replace_meal_item"
        targets = self.snapshot.exercises if noun == "exercise" else self.snapshot.foods
        if clarification["candidate_intent"] != kind:
            return
        match = re.search(r"\b(?:por|para|pelo|pela)\s+(?:(?:um|uma|o|a)\s+)?(.+)$", fold(text).strip(" .!"))
        if match is None:
            return
        destination = match[1]
        names = {item["canonical"] for item in targets}
        if destination not in names:
            aliases = {e["value"] for e in usable_entities(analysis)
                       if e["entity_type"] in {noun, "replacement_" + noun}
                       and e["value"] in names and fold(text[e["start"]:e["end"]]) == destination}
            if len(aliases) != 1:
                return
            destination = aliases.pop()
        self.incomplete_swap = (noun, destination, self.snapshot.fingerprint(),
                                self.now() + timedelta(minutes=10))

    def complete_swap(self, analysis):
        pending, self.incomplete_swap = self.incomplete_swap, None
        if not pending or not self.snapshot or analysis["risk"]["labels"]:
            return None
        noun, destination, fingerprint, expires = pending
        text = analysis["entities"].get("text", "")
        if ("?" in text or change_scope(text) or self.now() >= expires
                or self.snapshot.fingerprint() != fingerprint):
            return None
        source_items = self.snapshot.workout_exercises if noun == "exercise" else self.snapshot.meal_items
        names = {r["canonical"] for r in source_items}
        entities = usable_entities(analysis)
        mentions = [e for e in entities if e["entity_type"] == noun and e["value"] in names
                    and e["value"] != destination]
        if len(mentions) != 1:
            return None
        old = mentions[0]
        if fold(text[:old["start"]]).strip(" ,") not in {"", "o", "a", "esse", "essa"}:
            return None
        tail = fold(text[old["end"]:]).strip(" .,!").strip()
        if tail:
            aliases = {fold(text[e["start"]:e["end"]]) for e in entities
                       if e["entity_type"] in {noun, "replacement_" + noun} and e["value"] == destination}
            targets = "|".join(re.escape(name) for name in sorted(aliases | {destination, destination.split()[-1]}))
            if not re.fullmatch(rf"(?:quero )?troc(?:ar|a|e) (?:ele|ela|esse|essa) "
                                rf"(?:por|pelo|pela) (?:{targets})(?: mesmo)?", tail):
                return None

        old_name = old["value"]
        kind = "replace_exercise" if noun == "exercise" else "replace_meal_item"
        phrase = f"Troque {old_name} por {destination}"
        source_start = len("Troque ")
        destination_start = len(phrase) - len(destination)
        candidate = {
            "intent": {"label": kind, "confident": False},
            "risk": {"labels": []},
            "entities": {"text": phrase, "entities": [
                {"entity_type": noun, "value": old_name, "start": source_start,
                 "end": source_start + len(old_name)},
                {"entity_type": "replacement_" + noun, "value": destination,
                 "start": destination_start, "end": len(phrase)},
            ]},
        }
        return self.propose_explicit_swap(candidate)

    def _prepare(self, payload):
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

"""Answer read-only questions using authenticated product data."""
from datetime import date
import re

from .actions import WEEKDAYS
from .request_intent import explicit_change, meal_qualifiers
from .retrieval import fold


_MEAL_LABELS = {
    "cafe da manha": "café da manhã", "almoco": "almoço", "lanche da manha": "lanche da manhã",
    "lanche da tarde": "lanche da tarde",
}
_DIET = re.compile(r"\b(?:minha dieta|meu plano alimentar|nas minhas refeicoes)\b")
_LIST = re.compile(r"\b(?:o que|oq|quais (?:alimentos|itens))\b.{0,30}\b(?:tem|aparece[m]?|consta[m]?)\b")
_WHERE = re.compile(r"\b(?:em qual|em quais|qual|quais) refeic\w*\b")
_WHY = re.compile(r"\b(?:por que|pq|qual o motivo)\b.{0,35}\b(?:colocar|colocaram|aparece|tem|inclui)\b")
_APPROVED = re.compile(r"\b(?:opco\w*|alternativ\w*|substituic\w*)\b.{0,20}\b(?:aprova\w*|do (?:meu )?plano)\b")


def scheduled_days(snapshot, today, account_day=None):
    if not snapshot or not snapshot.workout_plan_id:
        return []
    if account_day and account_day.source == "override":
        if account_day.activity_type == "rest":
            return []
        return [row for row in snapshot.days if row["id"] == str(account_day.workout_day_id)]
    key = today.isoformat()
    if ((snapshot.workout_start and key < snapshot.workout_start)
            or (snapshot.workout_end and key > snapshot.workout_end)):
        return []
    return [row for row in snapshot.days if row["weekday"] == WEEKDAYS[today.weekday()]]


def today_workout_reply(query, snapshot, today, account_day):
    if (not re.search(r"\b(?:treino de hoje|ficha de hoje|treino hoje|"
                      r"hoje\b.{0,30}\b(?:treino|ficha|descanso|folga)|"
                      r"(?:qual|quais) exercici\w*\b.{0,35}\bhoje)\b", query)
            or not re.search(r"\b(?:qual|quais|oq|o que|tem|tenho|e dia|vou fazer|vou treinar)\b", query)
            or re.search(r"\b(?:historico|registr\w*|ultim[oa]|suplement\w*|pre treino|melhor treino)\b", query)):
        return None
    if account_day and account_day.source == "override" and account_day.activity_type == "rest":
        return "Hoje consta como descanso no seu calendário. Você pode consultar a ficha dos outros dias normalmente."
    if account_day and account_day.source == "override" and not account_day.workout_day_id:
        activity = {"resistance": "musculação", "cardio": "cardio", "mixed": "treino misto"}[account_day.activity_type]
        return f"Seu calendário marca {activity} hoje. Esse registro não tem uma ficha de exercícios vinculada."
    if not snapshot or not snapshot.workout_plan_id:
        return "Você ainda não tem uma ficha de treino ativa nesta conta."
    days = scheduled_days(snapshot, today, account_day)
    if not days:
        if account_day and account_day.source == "override":
            return "A atividade de hoje não tem exercícios vinculados à ficha selecionada."
        return "Sua ficha ativa não prevê uma sessão para hoje."
    if (not re.search(r"\b(?:qual (?:e )?(?:o |meu )?treino|o que (?:tem|vou fazer)|quais (?:os )?exercicios|"
                      r"e dia de descanso|tenho treino)\b", query)
            or re.search(r"\bexercici\w* (?:de|para) pernas?\b", query)):
        return None
    day_ids = {row["id"] for row in days}
    exercises = [row.get("display_name") or row["canonical"] for row in snapshot.workout_exercises
                 if row["workout_day_id"] in day_ids]
    if not exercises:
        return "Há uma sessão no calendário de hoje, mas a ficha não tem exercícios cadastrados nesse dia."
    names = ", ".join(dict.fromkeys(exercises[:8]))
    remainder = " e outros exercícios" if len(exercises) > 8 else ""
    return f"Sua ficha de hoje inclui {names}{remainder}."


def exercise_history_reply(text, account, snapshot):
    query = " ".join(fold(text).split())
    if (not re.search(r"\b(?:historico|registros?|registrei|registado|registrado|ultim[oa])\b", query)
            or not re.search(r"\b(?:carga|reps|repetic\w*|peso|segundos?|tempo|exercici\w*|registro|fiz)\b", query)
            or not re.search(r"\b(?:qual|quais|quanto|quantos|quantas|o que|oq|mostra\w*|me diz|me fala|me lembra)\b", query)
            or explicit_change(text)
            or re.search(r"\b(?:outra conta|de outra pessoa|finja|ignore|peso corporal|meu peso)\b", query)):
        return None
    entries = account.exercise_logs
    if not entries:
        return "Ainda não encontrei registros de exercícios no histórico desta conta."
    catalogue = snapshot.exercises if snapshot else []
    names = {fold(entry.exercise) for entry in entries} | {fold(row["canonical"]) for row in catalogue}
    matches = [name for name in names if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", query)]
    matches = [name for name in matches if not any(name != other and name in other for other in matches)]
    if len(matches) > 1:
        return "De qual exercício você quer consultar o último registro?"
    if matches:
        entries = [entry for entry in entries if fold(entry.exercise) == matches[0]]
    elif not re.fullmatch(r"(?:qual (?:foi|e) (?:o |meu )?ultimo registro(?: de (?:exercicio|treino))?|"
                          r"mostra (?:meu |o )?ultimo registro(?: de (?:exercicio|treino))?)[ ?.]*", query):
        return "De qual exercício você quer consultar o histórico?"
    if not entries:
        return "Não encontrei esse exercício nos registros recentes da sua conta."
    entry = entries[0]
    date_label = entry.date.strftime("%d/%m/%Y")
    metrics = []
    if entry.load_kg is not None:
        metrics.append(f"{entry.load_kg:g}".replace(".", ",") + " kg")
    if entry.repetitions is not None:
        metrics.append(f"{entry.repetitions} repetições")
    if entry.duration_seconds is not None:
        metrics.append(f"{entry.duration_seconds} segundos")
    if entry.sets_completed is not None:
        metrics.append(f"{entry.sets_completed} séries")
    name = entry.exercise
    if not metrics:
        return f"Encontrei um registro de {name} em {date_label}, sem carga, repetições ou tempo estruturado."
    return f"No último registro de {name}, em {date_label}, consta " + " e ".join(metrics) + "."


def plan_catalogue_reply(text, snapshot, today=None, account_day=None):
    """Use plan fields for membership and approved options; ask when the target is ambiguous."""
    query = " ".join(fold(text).split())
    if (re.search(r"\b(?:ficha|treino|dieta|plano alimentar|historico|registros?|perfil|peso)\b"
                  r".{0,35}\b(?:outra conta|de outra pessoa)\b", query)
            and re.search(r"\b(?:mostra\w*|ver|consult\w*|aces\w*|qual)\b", query)):
        return "Só consigo consultar os dados desta conta. Quer conferir um exercício ou uma refeição da sua ficha?"
    if (explicit_change(text) or query.count("?") > 1
            or re.search(r"\b(?:finja|ignore|outra conta|de outra pessoa|aplique|execute|"
                         r"estragad\w*|vencid\w*|reacao|alerg\w*|vomit\w*|"
                         r"se eu|mas|passei mal|to sentindo|estou sentindo)\b", query)):
        return None
    today = today or date.today()
    if not _DIET.search(query) and not re.search(r"\b(?:mudar|mude|trocar|troque|alterar|altere)\b", query):
        if day_reply := today_workout_reply(query, snapshot, today, account_day):
            return day_reply
    meals = meal_qualifiers(text)
    diet_question = bool(_DIET.search(query))
    wants_options = bool(_APPROVED.search(query) and (diet_question or meals))
    listing = _LIST.search(query) and meals and diet_question
    where = _WHERE.search(query) and diet_question
    why = _WHY.search(query) and diet_question
    if not (listing or where or why or wants_options):
        return None
    if not snapshot or not snapshot.diet_plan_id:
        return "Não tenho um plano alimentar desta conta para consultar. Qual refeição ou alimento você queria conferir?"
    rows = snapshot.meal_items
    if snapshot.diet_variants:
        requested_types = [kind for pattern, kind in (
            (r"\b(?:dia|dias) de descanso\b", "rest_day"),
            (r"\b(?:dia|dias) de treino\b", "training_day"),
        ) if re.search(pattern, query)]
        if len(requested_types) > 1:
            return "Qual cardápio você quer consultar primeiro, o de treino ou o de descanso?"
        day_type = requested_types[0] if requested_types else (account_day.nutrition_day_type if account_day else None)
        if day_type is None:
            return "Você quer ver o cardápio do dia de treino ou do dia de descanso?"
        rows = [row for row in rows if row.get("day_type", "every_day") in {"every_day", day_type}]
    rotation = (today - date(1970, 1, 1)).days % snapshot.diet_rotation_size
    rows = [row for row in rows if row.get("rotation_index", 0) == rotation]
    if listing:
        if len(meals) != 1:
            return "Qual refeição você quer conferir primeiro?"
        meal = next(iter(meals))
        items = sorted({row["canonical"] for row in rows if fold(row.get("meal_name") or "") == meal})
        name = _MEAL_LABELS.get(meal, meal)
        if not items:
            return f"Não encontrei itens para {name} no seu plano alimentar."
        return f"No seu plano, {name} inclui {', '.join(items)}."
    items = [row for row in rows
             if re.search(rf"(?<!\w){re.escape(fold(row['canonical']))}(?!\w)", query)]
    # Prefer a specific named item ("ovo de codorna") over a substring ("ovo").
    items = [row for row in items if not any(
        fold(row["canonical"]) != fold(other["canonical"]) and re.search(
            rf"(?<!\w){re.escape(fold(row['canonical']))}(?!\w)", fold(other["canonical"]))
        for other in items)]
    names = {row["canonical"] for row in items}
    if len(names) != 1:
        return ("Qual alimento do seu plano você quer conferir?" if names else
                "Não consegui localizar esse alimento na sua dieta. Pode me dizer como ele aparece no plano?")
    name = next(iter(names))
    if where or why:
        labels = sorted({fold(row["meal_name"]) for row in items if row.get("meal_name")})
        locations = " e ".join(_MEAL_LABELS.get(label, label) for label in labels)
        if why:
            return (f"{name.capitalize()} aparece em {locations}. A ficha não registra o motivo dessa escolha."
                    if locations else f"A ficha não registra o motivo de incluir {name}.")
        return (f"No seu plano, {name} aparece em {locations}." if locations else
                f"O plano contém {name}, mas a refeição não está identificada.")
    if meals:
        items = [row for row in items if fold(row.get("meal_name") or "") in meals]
    if len(items) != 1:
        return f"Em qual refeição você quer conferir as opções para {name}?"
    approved = set(items[0].get("approved_replacement_ids") or [])
    options = sorted({food["canonical"] for food in snapshot.foods if food["id"] in approved})
    if not options:
        return f"Não encontrei alternativas aprovadas para {name} nessa refeição."
    return f"Para {name} nessa refeição, o plano aprova {', '.join(options)} como alternativa."

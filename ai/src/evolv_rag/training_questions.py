"""Read-only answers from the active workout and reviewed training guidance."""
import re

from evolv_nlp.entities import WEEKDAYS as PORTUGUESE_WEEKDAYS
from .actions import WEEKDAYS
from .plan_read import scheduled_days
from .retrieval import fold
from .smalltalk import clear_knowledge_question


_DELOAD = re.compile(r"\bdeload\b")
_DISCUSSION = re.compile(
    r"\b(?:vale a pena|(?:o que|oq) (?:vc |voce )?acha|(?:e|seria) melhor|outra saida|outra opcao|faz sentido)\b"
)
_PLATEAU = re.compile(
    r"\b(?:estagn\w*|sem conseguir evoluir|nao consigo (?:evoluir|progredir|subir|aumentar)|"
    r"(?:cargas?|pesos?) (?:travaram|pararam de subir|nao sobem))\b"
)
_FATIGUE = re.compile(r"\b(?:desestimul\w*|cansad\w*|fadiga|desanim\w*|esgotad\w*)\b")
_EXECUTION = re.compile(r"\b(?:como (?:fazer|faco|executar|se faz)|o que (?:e|seria)|oq (?:e|seria)|me explica)\b")
_ACTION = re.compile(
    r"\b(?:troqu\w*|troc\w*|substitu\w*|mud\w*|alter\w*|remov\w*|"
    r"tira\w*|cancela\w*|salv\w*|registr\w*|aplique)\b"
)


def deload_discussion(text, dialogue):
    current = fold(text)
    prior = fold(dialogue.anchor) if dialogue else ""
    if _ACTION.search(current):
        return False
    if _DELOAD.search(current):
        return bool(clear_knowledge_question(text) or _DISCUSSION.search(current)
                    or ("?" in text and (_FATIGUE.search(current) or _PLATEAU.search(current))))
    return bool(_DELOAD.search(prior) and (_DISCUSSION.search(current) or _PLATEAU.search(current)
                                         or _FATIGUE.search(current)))


def answer_deload(text, search, today, result):
    if hasattr(search, "reviewed_document"):
        evidence = search.reviewed_document("deload_meaning", as_of=today)
    else:
        retrieved = search.query("deload redução temporária fadiga recuperação semana de treino",
                                 topics=["deload"], as_of=today)
        evidence = next((row for row in retrieved["matches"] if row.get("document_id") == "deload_meaning"), None)
    if not evidence:
        return None
    result["retrieval"] = {"status": "found", "matches": [evidence]}
    result["grounding"] = {"status": "supported_excerpt", "method": "reviewed_guidance"}
    definition = f"Um deload reduz por um período a exigência do treino para ajudar a administrar a fadiga. [{evidence['id']}]"
    current = fold(text)
    if _PLATEAU.search(current):
        if hasattr(search, "reviewed_document"):
            context = search.reviewed_document("training_plateau_review_context", as_of=today)
        else:
            plateau = search.query("estagnação de carga progressão por exercício", topics=["training_plateau"], as_of=today)
            context = next((row for row in plateau["matches"] if row.get("document_id") == "training_plateau_review_context"), None)
        alternative = ""
        if context:
            result["retrieval"]["matches"].append(context)
            alternative = (f"Se a recuperação está boa e só alguns exercícios travaram, dá para começar "
                           f"revisando a progressão deles. [{context['id']}] ")
        opening = "Entendo como isso pode desanimar. " if _FATIGUE.search(current) else ""
        return (f"{opening}Se as cargas travaram junto com cansaço acumulado, um deload pode fazer sentido. "
                f"{definition} {alternative}"
                "A queda de rendimento está acontecendo em vários exercícios ou em alguns específicos?")
    if _DISCUSSION.search(current):
        return (f"Pode fazer sentido se você está acumulando cansaço. {definition} "
                "Você tem sentido mais fadiga ou queda de rendimento nas últimas sessões?")
    return definition


_DETAIL = re.compile(r"\b(?:trabalha|musculo\w*|reps|repetic\w*|pra que serve|para que serve)\b")
_DAY = re.compile(r"\b(?:de|na|no) (" + "|".join(PORTUGUESE_WEEKDAYS) + r")\b")
_REFERENCE = re.compile(r"\b(?:ele|ela|esse|essa|desse|dessa|dele|dela|mesmo|o meu|a minha)\b")
EXERCISE_REFERENCE = re.compile(r"\b(?:esse|este|aquele|desse|deste|daquele) exerc[ií]cio\b", re.I)
EXERCISE_QUESTION = "Qual exercício da ficha você quer conferir?"
_MUSCLES = {
    "upper_back": "a parte superior das costas", "lats": "as costas", "chest": "o peito",
    "quadriceps": "os quadríceps", "hamstrings": "a parte de trás das coxas",
    "glutes": "os glúteos", "biceps": "os bíceps", "triceps": "os tríceps",
    "shoulders": "os ombros", "core": "a região central do corpo",
}


def plan_exercise(text, snapshot, today, focus=None, account_day=None):
    current = fold(text)
    if not snapshot or _ACTION.search(current):
        return None, None
    weekday = WEEKDAYS[today.weekday()]
    today_ids = {row["id"] for row in scheduled_days(snapshot, today, account_day)}
    requested_weekdays = {WEEKDAYS[PORTUGUESE_WEEKDAYS[d]] for d in _DAY.findall(current)}
    if "hoje" in current:
        requested_weekdays.add(weekday)
    requested_ids = ({row["id"] for row in snapshot.days if row["weekday"] in requested_weekdays}
                     if "hoje" not in current else today_ids)
    matches = [row for row in snapshot.workout_exercises
               if re.search(rf"(?<!\w){re.escape(fold(row['canonical']))}(?!\w)", current)]
    detail = _DETAIL.search(current)
    if not matches and (detail or _EXECUTION.search(current)) and _REFERENCE.search(current) and focus:
        matches = [row for row in snapshot.workout_exercises if row["canonical"] == focus]
    if not matches and re.search(r"\b(?:qual exercicio|quais (?:os )?exercicios)\b", current) and "hoje" in current:
        matches = [row for row in snapshot.workout_exercises if row["workout_day_id"] in today_ids]
        if re.search(r"\b(?:perna|pernas|inferiores)\b", current):
            matches = [row for row in matches if row.get("muscle_group") in {"quadriceps", "hamstrings", "glutes", "calves"}]
        if len(matches) == 1:
            [exercise] = matches
            name = exercise.get("display_name") or exercise["canonical"].capitalize()
            return f"No treino de hoje está {name}.", exercise["canonical"]
        if len(matches) > 1:
            names = [row.get("display_name") or row["canonical"].capitalize() for row in matches[:5]]
            return "Na ficha de hoje aparecem " + ", ".join(names) + ". Sobre qual você quer saber?", None
    if not matches or len({row["canonical"] for row in matches}) != 1:
        return None, None
    row = next((item for item in matches if item["workout_day_id"] in today_ids), matches[0])
    name = row.get("display_name") or row["canonical"].capitalize()
    if detail and re.search(r"\b(?:reps|repetic\w*)\b", current):
        sessions = ([item for item in matches if item["workout_day_id"] in requested_ids]
                    if requested_weekdays else matches)
        ranges = {(item.get("min_reps"), item.get("max_reps")) for item in sessions}
        if not ranges:
            return f"Não encontrei {name} na ficha do dia pedido. Qual sessão você quer consultar?", row["canonical"]
        if len(ranges) > 1:
            return f"A faixa de repetições de {name} varia entre sessões. Qual dia você quer consultar?", row["canonical"]
        [(low, high)] = ranges
        if low is not None:
            count = f"{low} a {high}" if high is not None and high != low else str(low)
            return f"No seu plano, {name} está com {count} repetições por série.", row["canonical"]
    elif detail and (muscle := _MUSCLES.get(row.get("muscle_group"))):
        return f"{name} trabalha principalmente {muscle}.", row["canonical"]
    if not _EXECUTION.search(current):
        return None, None
    instructions = row.get("instructions")
    if not instructions:
        return None, None
    location = "no treino de hoje" if row["workout_day_id"] in today_ids else "no seu plano"
    equipment = " É feita com uma barra apoiada em uma das pontas." if row.get("equipment") == "landmine" else ""
    return f"{name} está {location}.{equipment} {instructions}", row["canonical"]


def complete_exercise_question(text, history, snapshot):
    if not snapshot or len(history) < 2 or history[-1]["content"] != EXERCISE_QUESTION:
        return None
    name = fold(text).strip(" .!").removeprefix("e ").removeprefix("a ").removeprefix("o ")
    matches = {row["canonical"] for row in snapshot.workout_exercises
               if name in {fold(row["canonical"]), fold(row.get("display_name") or "")}}
    if len(matches) != 1:
        return None
    return EXERCISE_REFERENCE.sub(lambda _: next(iter(matches)), history[-2]["content"])

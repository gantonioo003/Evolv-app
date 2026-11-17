"""Interpret the conversation with Qwen and resolve product requests against trusted data."""
from datetime import date, timedelta
import json
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .account_context import account_reply, memory_request
from .actions import WEEKDAYS, food_matches, requested_meal, validate_payload
from .conversation_facts import availability_report, availability_summary, food_equipment_report, observe_report, read_followup, targeted_user_recall
from .conversation_writer import write_conversation
from .dialogue import DialogueContext
from .plan_read import plan_catalogue_reply, scheduled_days, exercise_history_reply
from .request_intent import change_scope, explicit_change, read_swap
from .retrieval import fold
from .reviewed_questions import reviewed_questions, specific_gap
from .safety import execution_boundary_reply, preflight
from .smalltalk import conversational_reply, explicit_information_request

DAYS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
DAY_WORD = r"(?:segunda|terca|quarta|quinta|sexta|sabado|domingo|hoje|hj|amanha)"
_MOVE_QUESTION = re.compile(rf"\b(?:treino|sessao) (?:de )?({DAY_WORD})(?:-feira)? "
                            rf"(?:cabe|da para passar|da pra passar|pode ir) (?:pra|para|na|no) ({DAY_WORD})\b|"
                            rf"\b(?:da pra|da para|posso|poderia) (?:mover|remarcar|passar|adiar) (?:o |a )?"
                            rf"(?:treino|sessao) (?:de )?({DAY_WORD})(?:-feira)? (?:pra|para|na|no) ({DAY_WORD})\b")
_MOVE_DATES = re.compile(rf"\b(?:treino|sessao) de ({DAY_WORD})(?:-feira)? (?:pra|para|na|no|pro) ({DAY_WORD})(?:-feira)?\b")
_PREVIEW = re.compile(r"\b(?:previa|antes de (?:mudar|trocar|aplicar)|revisar antes)\b")
_MOVE_WORD = re.compile(r"\b(?:muda\w*|mov\w*|remarc\w*|jog\w*|adi\w*|pass\w*)\b")
_MOVE_DIRECTIVE = re.compile(
    r"\b(?:muda|mude|move|mova|passa|passe|adia|adie|remarca|remarque|joga|jogue|bota|bote|coloca|coloque)\b"
    r"|\b(?:quero|preciso|pode|gostaria de) (?:mesmo )?(?:mover|mudar|remarcar|passar|adiar|jogar|botar|colocar)\b"
    r"|\b(?:quero|mostra|mostre|prepara|prepare|abre|abra|monta|monte)\b[^.?!]{0,45}\bprevia\b"
)
_FREQUENCY = re.compile(r"\b(?:quantos|quantas|qts) (?:dias|vezes|treinos|sessoes)\b")
_MOVE_REQUEST = re.compile(rf"^(?:(?:entao|beleza|ok|fechou)[, ]+)?(?:pode |quero )?(?:move|mova|mover|passa|passe|passar|adia|adie|remarca|remarque)"
                           rf"(?:\s+(?:o |meu |a |minha )*(?:treino|sessao))?"
                           rf"(?: de ({DAY_WORD})(?:-feira)?)? (?:pra|para|na|no|pro|pra o) ({DAY_WORD})\b")
_KEEP_PLAN = re.compile(r"(?:(?:entao|fechou|mas|ok|pode|desisti da troca)[, ]+)*(?:"
                        r"(?:deixa|deixe|mantem|mantenha|fica) (?:tudo |a dieta |o treino |a ficha |o plano )?"
                        r"como (?:esta|ta)|(?:nao (?:tira|tire|muda|mude|troca|troque)|mantem|mantenha) (?:o treino|a dieta|a ficha)"
                        r"(?: de \w+)?(?:,? (?:(?:tava|estava) so (?:vendo|perguntando)|so queria ver(?: mesmo)?))?)[.! ]*")
_SCHEDULE_HOUR = re.compile(r"\b(\d{1,2}|uma|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze)"
                            r"(?:\s*(?:h|horas?))? (?:d[ae]|pela) (manha|tarde|noite)\b")
_HOUR_VALUES = {word: i for i, word in enumerate(
    ("uma", "duas", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze"), 1
)}
SHORT = Annotated[str, Field(min_length=1, max_length=120)]
CHANGES = {"move_workout", "replace_exercise", "replace_food", "day_activity"}
PROMPT = """Converta a mensagem atual em um JSON com op e somente os campos necessários. Use o histórico para referências e correções, e a ficha para nomes. Uma fala passada do Coach não autoriza mudanças.
LEITURA: week {day?} lê a agenda; hoje/amanhã ou dia da semana. Use exercise {item,day?,fields?} para o exercício individual. O primeiro exercício de um dia é o primeiro nome na lista exercicios_por_dia desse dia. fields: reps, rest, sets, instructions, muscles. diet {meal?} lê dieta. food_options {item,meal?,options?} consulta alternativas. account lê perfil ou registros.
CONVERSA: chat para saudações, relatos cotidianos, lembretes dentro da conversa e correções de disponibilidade. Informar um dia ou dizer que algo seria útil são contexto. recall {turn} recupera uma fala do usuário pelo número; use a correção mais recente. memory {turn} consulta preferência salva. knowledge {query} responde dúvidas gerais, reformuladas com a referência do histórico. safety para relatos com indícios de risco e unclear se realmente incerto.
MUDANÇA: move_workout {day,destination,scope?,period?}, replace_exercise {item,replacement,day?,scope?}, replace_food {item,replacement,meal?,scope?}, day_activity {day,activity,scope?}. activity: rest, resistance, cardio, mixed. purpose: apply para pedido explícito, preview para prévia, inquire para dúvida. Para apply/preview, request_evidence deve ser uma citação literal da mensagem atual. Use scope week para uma semana ou troca temporária, recurring para rotina fixa. Para mover treino, cite scope_evidence literal e omita scope se ainda não foi dito. Não invente valores.
CONTEXTO: ultima_consulta é uma leitura verificada pelo app. Use-a em perguntas como "e amanhã?" e referências como "aquele treino". Se houver um pedido explícito de mover esse treino, use o dia de origem da consulta. A disponibilidade mais recente do usuário pode completar o destino quando ele pedir explicitamente o dia corrigido.
PENDÊNCIA: continue só quando pedido_pendente existir e a mensagem completar ou corrigir um dado dele. Retorne somente os novos campos. Uma refeição não indica duração da mudança. Para novo destino de treino, use destination, não day. Se o usuário disser o período em gíria, interprete o sentido e cite o trecho original em scope_evidence. cancel para desistir. Se normalizar nome de refeição, copie a referência em meal_evidence.
"Qual meu treino de hoje?" → {"op":"week","day":"hoje"}
"Quais reps e descanso no supino?" → {"op":"exercise","item":"Supino","fields":["reps","rest"]}
"Só consigo ir na quinta de noite" → {"op":"chat"}
"Que dia eu disse que consigo ir?" → {"op":"recall","turn":3}
"Posso trocar ovo por tofu?" → {"op":"food_options","item":"ovo","options":["tofu"]}
"Troque ovo por tofu" → {"op":"replace_food","item":"ovo","replacement":"tofu","purpose":"apply","request_evidence":"Troque ovo por tofu"}
"Muda meu treino de hoje pra amanhã" → {"op":"move_workout","day":"hoje","destination":"amanhã","purpose":"apply","request_evidence":"Muda meu treino de hoje pra amanhã"}
Com movimento pendente: "só nesta semana" → {"op":"continue","scope":"week","scope_evidence":"só nesta semana"}
Com movimento pendente: "td smn" → {"op":"continue","scope":"recurring","scope_evidence":"td smn"}"""


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    op: Literal["chat", "week", "exercise", "diet", "food_options", "replace_food",
                "replace_exercise", "move_workout", "day_activity", "continue", "cancel",
                "recall", "memory", "account", "knowledge", "safety", "unclear"]
    item: SHORT | None = None
    replacement: SHORT | None = None
    options: list[SHORT] = Field(default_factory=list, max_length=3)
    meal: SHORT | None = None
    meal_evidence: SHORT | None = None
    day: SHORT | None = None
    destination: SHORT | None = None
    scope: Literal["week", "recurring"] | None = None
    purpose: Literal["apply", "preview", "inquire"] | None = None
    request_evidence: SHORT | None = None
    scope_evidence: SHORT | None = None
    period: SHORT | None = None
    activity: Literal["rest", "resistance", "cardio", "mixed"] | None = None
    fields: list[Literal["reps", "rest", "sets", "instructions", "muscles"]] = Field(default_factory=list, max_length=5)
    turn: int | None = Field(default=None, ge=1, le=100)
    query: Annotated[str, Field(min_length=1, max_length=420)] | None = None


def interpret(coach, text, today, account, pending):
    snapshot = coach.action_session.snapshot
    history = [{"turn": i, "role": row["role"], "text": row["content"][:(360 if row["role"] == "user" else 160)]}
               for i, row in enumerate(coach.history[-24:], 1)]
    exercises_by_day = {}
    if snapshot:
        monday = today - timedelta(days=today.weekday())
        days = [(day.weekday(), row.get("workout_day_id")) for row in snapshot.week
                if monday <= (day := date.fromisoformat(row["date"])) < monday + timedelta(days=7)]
        if not days:
            days = [(WEEKDAYS.index(row["weekday"]), row["id"]) for row in snapshot.days]
        for weekday_index, day_id in days:
            if day_id:
                names = exercises_by_day.setdefault(DAYS[weekday_index], [])
                names.extend(row["canonical"] for row in snapshot.workout_exercises
                             if row["workout_day_id"] == day_id and row["canonical"] not in names)
        exercises_by_day = {day: names[:12] for day, names in exercises_by_day.items()}
    # Only send names that help resolve references, without database identifiers.
    plan = {
        "dias_com_treino": list(dict.fromkeys(DAYS[WEEKDAYS.index(day["weekday"])] for day in snapshot.days)),
        "exercicios": list(dict.fromkeys(row["canonical"] for row in snapshot.workout_exercises))[:24],
        "exercicios_por_dia": exercises_by_day,
        "refeicoes": list(dict.fromkeys(row.get("meal_name") for row in snapshot.meal_items))[:12],
    } if snapshot else {}
    memories = account.memories[:12] if account and account.memory_enabled else []
    meal = coach.memory.latest("meal_routine")
    meal_reference = {key: meal.facts[key] for key in ("read_meal", "read_item") if meal and key in meal.facts}
    payload = {"data": today.isoformat(), "mensagem": text, "ficha": plan, "historico": history,
               "preferencias_salvas": dict(enumerate(memories, 1)),
               "pedido_pendente": pending.model_dump(exclude_defaults=True) if pending else None}
    if read := coach.memory.latest("plan_read"):
        payload["ultima_consulta"] = read.facts
    if availability := availability_summary(coach.memory):
        payload["disponibilidade_mencionada"] = availability
    if meal_reference:
        payload["ultima_refeicao_consultada"] = meal_reference
    while True:
        messages = [{"role": "system", "content": PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")}]
        if coach.lm.count(messages) <= coach.lm.settings["max_input_tokens"]:
            break
        if not history:
            return None, {}, memories
        del history[:2]
    try:
        raw = coach.lm.interpret(messages).strip()
        fenced = re.fullmatch(r"`{3}(?:json)?\s*(.*?)\s*`{3}", raw, re.S | re.I)
        turn = decode(fenced[1] if fenced else raw, preview_requested=bool(_PREVIEW.search(fold(text))))
    except (ValidationError, ValueError, TypeError):
        turn = None
    return turn, {row["turn"]: row["text"] for row in history if row["role"] == "user"}, memories


# Only fields used by an operation survive parsing. The model sometimes adds
# prose or imagined prescription values. Neither is a product input.
FIELDS = {
    "week": {"day"}, "exercise": {"item", "day", "fields"}, "diet": {"meal"},
    "food_options": {"item", "meal", "options"},
    "replace_food": {"item", "replacement", "meal", "scope"},
    "replace_exercise": {"item", "replacement", "day", "scope"},
    "move_workout": {"day", "destination", "scope", "period"},
    "day_activity": {"day", "activity", "scope"}, "continue": {"item", "replacement", "meal", "day",
        "destination", "scope", "period", "activity"},
    "recall": {"turn"}, "memory": {"turn"}, "knowledge": {"query"},
}


def decode(raw, *, preview_requested=False):
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("op"), str):
        return None
    op = data["op"]
    accepted = {key: value for key, value in data.items() if key in FIELDS.get(op, set())}
    if op == "exercise" and isinstance(accepted.get("fields"), dict):
        accepted["fields"] = [key for key, value in accepted["fields"].items()
                              if value is not None and key in {"reps", "rest", "sets", "instructions", "muscles"}]
    if op in {"diet", "food_options", "replace_food", "continue"} and "meal_evidence" in data:
        accepted["meal_evidence"] = data["meal_evidence"]
    if op in CHANGES or op == "continue":
        accepted.update({key: data[key] for key in ("purpose", "scope_evidence")
                         if key in data})
        if preview_requested and data.get("purpose") == "apply":
            accepted["purpose"] = "preview"
        if accepted.get("purpose") == "apply" and "request_evidence" in data:
            accepted["request_evidence"] = data["request_evidence"]
    return Turn.model_validate({"op": op, **accepted})


def weekday(value, today):
    if not value:
        return None
    name = fold(value).strip().removesuffix("-feira").removesuffix(" feira")
    if name in {"hoje", "hj"}:
        return today.weekday()
    if name == "amanha":
        return (today.weekday() + 1) % 7
    return next((i for i, day in enumerate(DAYS) if name in (fold(day), fold(day)[:3], WEEKDAYS[i])), None)


def occurrences(snapshot, today, account_day):
    monday = today - timedelta(days=today.weekday())
    by_date = {row["date"]: row for row in snapshot.week} if snapshot else {}
    for index, label in enumerate(DAYS):
        day = monday + timedelta(days=index)
        row = by_date.get(day.isoformat())
        if row:
            title = "descanso" if row["activity_type"] == "rest" else row["title"] or "treino"
        else:
            items = scheduled_days(snapshot, day, account_day if day == today else None)
            title = " / ".join(item.get("title") or "treino" for item in items) or "descanso"
        yield index, day, title


def week_reply(snapshot, today, account_day, day):
    if not snapshot or not snapshot.workout_plan_id:
        return "Não encontrei uma ficha de treino ativa para consultar."
    selected = weekday(day, today)
    if day and selected is None:
        return "Qual dia da semana você quer consultar?"
    if day and fold(day).strip() == "amanha" and today.weekday() == 6:
        tomorrow = today + timedelta(days=1)
        row = next((row for row in snapshot.week if row["date"] == tomorrow.isoformat()), None)
        if row:
            title = "descanso" if row["activity_type"] == "rest" else row["title"] or "treino"
            return f"Segunda ({tomorrow:%d/%m}): {title}."
        return "A ficha que tenho aqui vai até hoje. Abra a semana seguinte no calendário para conferir amanhã."
    lines = [f"{DAYS[i].capitalize()} ({d:%d/%m}): {title}."
             for i, d, title in occurrences(snapshot, today, account_day)
             if selected is None or i == selected]
    return "\n".join(lines)


def remember_plan_read(coach, message, facts):
    prior = coach.memory.latest("plan_read")
    if prior:
        dates = {key: value for key, value in prior.facts.items() if key in {
            "primeira_data", "primeiro_treino", "ultimo_treino_data", "ultimo_dia_livre_data",
        }}
        facts = dates | facts
        for key in ("primeira_data", "primeiro_treino"):
            if key in dates:
                facts[key] = dates[key]
    coach.memory = coach.memory.remembering(DialogueContext(topic="plan_read", anchor=message[:800], facts=facts))


def remember_calendar(coach, message, today, account_day, day, *, checking_destination=False):
    snapshot = coach.action_session.snapshot
    awaiting_day = day == "choose_day"
    answer = ("Qual dia da semana você quer consultar?" if awaiting_day and snapshot and snapshot.workout_plan_id
              else week_reply(snapshot, today, account_day, day))
    if snapshot and snapshot.workout_plan_id:
        facts = {"tipo": "treino"}
        index = weekday(day, today)
        if index is not None:
            selected = (today + timedelta(days=1) if fold(day).strip() == "amanha" else
                        today + timedelta(days=index - today.weekday()))
            facts.update(dia=DAYS[index], data=selected.isoformat())
            observed = next((title for _, when, title in occurrences(snapshot, today, account_day)
                             if when == selected), None)
            if observed and fold(observed) == "descanso":
                facts.update(foco="dia_livre", ultimo_dia_livre_data=selected.isoformat())
            elif observed and not checking_destination:
                facts.update(primeira_data=selected.isoformat(), primeiro_treino=observed[:180])
                facts["ultimo_treino_data"] = selected.isoformat()
        if awaiting_day:
            facts["aguarda"] = "dia"
        if checking_destination:
            facts["foco"] = "destino"
        remember_plan_read(coach, message, facts)
    return answer


def first_workout_read(last_read, message):
    if (not last_read or not last_read.facts.get("primeiro_treino")
            or not re.search(r"\b(?:treino|sessao)\b.{0,70}\b(?:consultad[oa] primeiro|primeir[oa] (?:que )?(?:eu )?consultei)\b"
                             r"|\bprimeir[oa] (?:treino|sessao) (?:que )?(?:eu )?consultei\b", message)):
        return None
    try:
        when = date.fromisoformat(last_read.facts.get("primeira_data", ""))
    except ValueError:
        return None
    return f"{DAYS[when.weekday()].capitalize()} ({when:%d/%m}): {last_read.facts['primeiro_treino']}."


def calendar_read(turn, message, history, snapshot, today, account_day, last_read=None):
    """Resolve calendar references with the active plan, never with a generated title or date."""
    if missed := re.match(rf"se eu faltar (?:na |no )?({DAY_WORD})(?:-feira)?[, ]+"
                           r"(?:o |meu )?treino (?:e qual|qual e)\?", message):
        return missed[1]
    last_sentence = re.split(r"[.!?]\s+", message)[-1]
    if marked := re.fullmatch(rf"(?:quem|o que|oq) (?:ta|esta) marcad[oa] (?:na|no|pra) ({DAY_WORD})"
                              r"(?:-feira)?[ ?.!]*", last_sentence):
        return marked[1]
    if free_day := re.search(rf"\b({DAY_WORD})(?:-feira)? (?:ta|esta) (?:sobrando|livre|ocupad[oa])"
                             r"(?: mesmo)?(?: na (?:minha )?ficha)?[ ?.!]*$", last_sentence):
        if "?" in last_sentence and not explicit_change(last_sentence):
            return free_day[1]
    if last_read and last_read.facts.get("tipo") == "treino":
        if (re.search(r"\b(?:o que|oq|q|qual treino) (?:ta marcado|tem|fica|cai) (?:nesse|naquele|neste) dia\b", message)
                and (last_day := last_read.facts.get("dia"))
                and (date_key := last_read.facts.get("data"))):
            if any(d.isoformat() == date_key for _, d, _ in occurrences(snapshot, today, account_day)):
                return last_day
        followup = re.fullmatch(rf"(?:e )?(?:(?:n[ao]|[ao]) )?({DAY_WORD})(?:-feira)?"
                                r"(?:,? (?:na|nessa) (?:mesma )?semana)?[ ?.!]*", message)
        if followup and ("?" in message or last_read.facts.get("aguarda") == "dia"):
            return followup[1]
        if last_read.facts.get("aguarda") == "dia":
            selection = re.fullmatch(rf"(?:n[ao] )?({DAY_WORD})(?:-feira)?"
                                      r"(?:,? era o que eu (?:tava|estava) pensando)?[ ?.!]*", message)
            if selection:
                return selection[1]
    if (re.search(r"\b(?:tem treino|qual treino) (?:naquele|nesse|neste) dia\b", message)
            and not re.search(rf"\b{DAY_WORD}\b", message)):
        return "choose_day"
    # Old conversations lack structured read context. The exact calendar lines
    # still identify a read when the immediately preceding answer was an agenda.
    if re.fullmatch(
        r"(?:e )?(?:no )?(hoje|hj|amanha|dia seguinte)(?:,? (?:e )?(?:dia de (?:que|q|que treino)|"
        r"(?:o )?(?:que|q|oq) (?:tem|cai|caiu)|(?:tem|cai|caiu) (?:o )?(?:que|q|oq)))?[ ?.]*",
        message,
    ):
        old_agenda = (last_read is None and history and history[-1]["role"] == "assistant" and
                      set(week_reply(snapshot, today, account_day, None).splitlines()) &
                      set(history[-1]["content"].splitlines()) if snapshot and snapshot.workout_plan_id else ())
        if (last_read and last_read.facts.get("tipo") == "treino") or old_agenda:
            return "amanhã" if "amanha" in message or "dia seguinte" in message else "hoje"
    if not explicit_change(message) and not re.search(r"\b(?:troca\w*|muda\w*|mov\w*|tira\w*|"
                                                        r"reps|repetic\w*|series?|pausa|intervalo)\b", message):
        if restored := re.search(rf"\b(?:o que|oq|qual treino) (?:aparece|ficou|cai|tem) (?:na|no|em) ({DAY_WORD})"
                                 r"(?:-feira)? (?:depois|apos) (?:de )?(?:desfazer|cancelar|rejeitar)\b", message):
            return restored[1]
        if re.search(r"\b(?:treino|sessao)\b.*\bdia original\b", message):
            for entry in reversed(history[-24:]):
                if entry["role"] == "user" and (move_dates := _MOVE_DATES.search(fold(entry["content"]))):
                    return move_dates[1]
        if ask := re.fullmatch(rf"(?:e )?(?:como ficou (?:o |a )?({DAY_WORD})|o treino de ({DAY_WORD}) ficou como)(?:-feira)?[ ?.]*", message):
            return ask[1] or ask[2]
        ask = re.search(rf"\b(?:qual (?:e )?(?:o |meu )?(?:treino|sessao)|(?:o que|oq|q|quem) "
                        rf"(?:tem|caiu|ficou|ta marcado)|(?:mostra|mostre) (?:o |a )?(?:treino|sessao))"
                        rf"(?: (?:de|pra|em|na|no|nesta|nesse))? ({DAY_WORD})(?:-feira)?\b", message)
        if not ask:
            ask = re.search(rf"\b(?:qual (?:o )?treino) (?:eu )?(?:tenho|ta marcado) (?:pra |pro )?({DAY_WORD})\b"
                            rf"|\b(?:da uma olhada|queria ver|quero ver) (?:no |na |o |a )?"
                            rf"(?:treino|sessao) (?:de |d[ao] |em )?({DAY_WORD})(?:-feira)?\b", message)
        if ask:
            return next(value for value in ask.groups() if value)
    if re.fullmatch(r"(?:me )?(?:mostra|mostre|manda|mande|diz|diga|fala)(?: pra mim)? "
                    r"(?:como ficou )?(?:a |minha |a minha )?(?:agenda|semana|rotina)"
                    r"(?: de treino| semanal(?: de treino)?)(?: p(?:ra)? eu ver)?[ ?.]*", message):
        return "week"
    if not turn or turn.op != "exercise" or not turn.item or turn.fields or not snapshot:
        return None
    # The model may send a session title to the exercise route. Resolve that
    # title on the calendar; an actual exercise always keeps its own route.
    if not re.search(r"\b(?:qual|quais|o que|oq|mostra\w*|me diz|me fala)\b", message):
        return None
    if re.search(r"\b(?:exercici\w*|series?|reps|repetic\w*|carga|pausa|intervalo|execucao|"
                 r"como (?:fazer|faco|executar)|troqu\w*|troc\w*|mud\w*|mov\w*|substitu\w*|"
                 r"alter\w*|registr\w*|coloc\w*|adi\w*|remove\w*)\b", message):
        return None
    name = fold(turn.item).strip()
    if not (has_evidence(turn.item, message) or re.search(r"\b(?:treino|ficha|sessao|agenda)\b", message)):
        return None
    if food_matches(snapshot.workout_exercises, name):
        return None
    matches = [index for index, _, title in occurrences(snapshot, today, account_day)
               if fold(title).strip() == name]
    relative = "hoje" if re.search(r"\b(?:hoje|hj)\b", message) else turn.day
    selected = weekday(relative, today)
    if selected is not None and selected in matches:
        return relative
    if relative is None and len(matches) == 1:
        return DAYS[matches[0]]
    return None


def workout_title_read(coach, message, today, account_day):
    snapshot = coach.action_session.snapshot
    if (not snapshot or not snapshot.workout_plan_id
            or not re.search(r"\b(?:onde fica|qual dia|em que dia|em qual dia)\b", fold(message))):
        return None
    query = fold(message)
    weekly = move_scope(None, query) == "recurring"
    if weekly:
        matches = [(DAYS[WEEKDAYS.index(row["weekday"])], row["title"]) for row in snapshot.days
                   if has_evidence(row["title"], query)]
    else:
        matches = [(DAYS[index], title) for index, _, title in occurrences(snapshot, today, account_day)
                   if fold(title) != "descanso" and has_evidence(title, query)]
    if len(matches) != 1:
        return None
    day, title = matches[0]
    if weekly:
        remember_plan_read(coach, message, {"tipo": "treino"})
        return f"{day.capitalize()}: {title} na ficha semanal."
    return remember_calendar(coach, message, today, account_day, day)


def exercise_rows(snapshot, name, day, today, account_day):
    if not snapshot or not name:
        return []
    rows = food_matches(snapshot.workout_exercises, fold(name).strip())
    if day:
        index = weekday(day, today)
        if index is None:
            return []
        monday = today - timedelta(days=today.weekday())
        date = monday + timedelta(days=index)
        effective = next((item for item in snapshot.week if item["date"] == date.isoformat()), None)
        ids = ({effective["workout_day_id"]} if effective else
               {item["id"] for item in scheduled_days(snapshot, date, account_day if date == today else None)})
        rows = [row for row in rows if row["workout_day_id"] in ids]
    return rows


def exercise_reply(snapshot, turn, today, account_day):
    rows = exercise_rows(snapshot, turn.item, turn.day, today, account_day)
    if not rows:
        return "Qual exercício da sua ficha você quer conferir?" if not turn.item else (
            f"Não encontrei {turn.item} na ficha indicada. Qual dia ou exercício você quer consultar?")
    fields = list(dict.fromkeys(turn.fields or ["reps", "rest", "sets"]))
    def values(row):
        return {
            "reps": (row.get("min_reps"), row.get("max_reps")), "rest": row.get("rest_seconds"),
            "sets": row.get("sets"), "instructions": row.get("instructions"),
            "muscles": row.get("muscle_group"),
        }
    row = rows[0]
    if any(row["canonical"] != other["canonical"] or any(values(row)[f] != values(other)[f] for f in fields)
           for other in rows[1:]):
        return "Esse exercício aparece com dados diferentes. Qual dia da ficha você quer consultar?"
    data = values(row)
    labels = {"reps": "Repetições", "rest": "Descanso", "sets": "Séries",
              "instructions": "Execução", "muscles": "Grupo muscular"}
    formatted = []
    for field in fields:
        value = data[field]
        if field == "reps":
            low, high = value
            value = (f"{low} a {high} por série" if high is not None and high != low else f"{low} por série") if low is not None else None
            prescription = fold(row.get("instructions") or "")
            if value and re.search(r"\bpor (?:perna|lado)\b", prescription):
                value = value.replace(" por série", " por perna, em cada série")
        elif field == "rest" and value is not None:
            value = f"{value} segundos"
        elif field == "muscles":
            from .training_questions import _MUSCLES
            value = _MUSCLES.get(value)
        formatted.append(f"{labels[field]}: {value if value is not None else 'sem informação na ficha'}")
    return f"{row.get('display_name') or row['canonical']}\n" + "\n".join(formatted)


def active_meal_rows(snapshot, today, account_day):
    if not snapshot or not snapshot.diet_plan_id or (snapshot.diet_variants and account_day is None):
        return []
    rotation = (today - date(1970, 1, 1)).days % snapshot.diet_rotation_size
    return [item for item in snapshot.meal_items if item.get("rotation_index", 0) == rotation
            and (not snapshot.diet_variants or item.get("day_type") == account_day.nutrition_day_type)]


def named_meals(rows, message):
    mentions = {}
    for row in rows:
        label = row.get("meal_name")
        if label and (match := re.search(rf"\b{re.escape(fold(label))}\b", message)):
            mentions[label] = match.start()
    return sorted(mentions, key=mentions.get)


def previous_meal_mention(rows, history, position):
    for entry in reversed(history[-24:]):
        if entry["role"] == "user":
            names = named_meals(rows, fold(entry["content"]))
            if len(names) > 1:
                return names[position], entry["content"]
    return None, None


def dish_amount(row):
    return row["canonical"] + (f" ({row['amount']})" if row.get("amount") else "")


def option_amounts(snapshot, row):
    names = {food["id"]: food["canonical"] for food in snapshot.foods}
    return [f"{names[option['food_id']]} ({option['amount']})"
            for option in row.get("approved_replacement_portions") or []
            if option["food_id"] in names and option["food_id"] in (row.get("approved_replacement_ids") or [])]


def portion_reply(snapshot, message, history, today, account_day):
    quantity = re.search(r"\b(?:porcao|quantidade|quanto (?:de|tem|desse|deste|dessa|desta)|quantos gramas|gramas)\b", message)
    rows = active_meal_rows(snapshot, today, account_day)
    labels = named_meals(rows, message)
    choices = {r["canonical"] for r in rows if has_evidence(r["canonical"], message)}
    if len(labels) > 1 and len(choices) == 1 and re.search(r"\b(?:tem|consta|aparece|vejo|duplicad[oa])\b", message):
        item, = choices
        matched_rows = [row for row in rows if row["canonical"] == item and row["meal_name"] in labels]
        matches = [label for label in labels if any(row["meal_name"] == label for row in matched_rows)]
        if matches:
            absent = [label for label in labels if label not in matches]
            return (f"{item} aparece em {' e '.join(matches)}."
                    + (f" Não consta em {' e '.join(absent)}." if absent else "")), matched_rows
        return f"{item} não aparece nas refeições indicadas.", []
    item_read = (len(labels) == 1 and len(choices) == 1
                 and re.search(r"\b(?:mostr\w*|tem|aparece|consta|confere|olhar)\b", message)
                 and not re.search(r"\b(?:alternativa|opcao|substitui\w*)\b", message))
    if not quantity and not item_read:
        return None
    if (not labels and re.search(r"\b(?:primeira|segunda) refeicao\b", message)
            and re.search(r"\b(?:repete|repita|daquelas|dessas|que (?:eu )?(?:citei|mencionei|falei))\b", message)):
        index = 1 if "segunda refeicao" in message else 0
        meal, source = previous_meal_mention(rows, history, index)
        if meal:
            labels = [meal]
            choices = {r["canonical"] for r in rows if has_evidence(r["canonical"], fold(source))}
    if not labels and not choices:
        return None
    alternatives = re.search(r"\b(?:opcao|opcoes|alternativa|alternativas|substituto|substituicao|cadastrada)\b", message)
    output = []
    matched_rows = []
    for row in rows:
        if ((labels and row.get("meal_name") not in labels) or (choices and row["canonical"] not in choices)):
            continue
        item = dish_amount(row) if row.get("amount") else f"{row['canonical']} (porção não informada)"
        options = option_amounts(snapshot, row) if alternatives else []
        matched_rows.append(row)
        output.append(f"{row.get('meal_name') or 'Refeição'}: {item}"
                      + (f". Opção cadastrada: {', '.join(options)}" if options else "") + ".")
    return ("\n".join(output), matched_rows) if output else None


def meal_rows(snapshot, meal, today, account_day):
    rows = active_meal_rows(snapshot, today, account_day)
    name = fold(meal).strip() if meal else ""
    if name in {"ultima", "ultima refeicao"}:
        positions = [row["meal_position"] for row in rows if row.get("meal_position") is not None]
        return [row for row in rows if positions and row.get("meal_position") == max(positions)]
    return [row for row in rows if not name or requested_meal(row, name)]


def diet_reply(snapshot, turn, today, account_day):
    groups = {}
    for row in meal_rows(snapshot, turn.meal, today, account_day):
        groups.setdefault(row.get("meal_name") or "Refeição", []).append(dish_amount(row))
    return "\n".join(f"{label}: {', '.join(dict.fromkeys(names))}." for label, names in groups.items()) or (
        "Não encontrei essa refeição no cardápio ativo de hoje." if turn.meal else "Não encontrei um cardápio ativo de hoje.")


def remember_meal_read(coach, message, rows):
    prior = coach.memory.latest("meal_routine")
    meal_facts = {key: value for key, value in prior.facts.items() if key not in {"read_meal", "read_item"}} if prior else {}
    if rows:
        facts = {"tipo": "dieta"}
        meals = {row["meal_name"] for row in rows if row.get("meal_name")}
        if len(meals) == 1:
            meal_facts["read_meal"] = facts["refeicao"] = next(iter(meals))[:180]
        items = {row["canonical"] for row in rows}
        if len(items) == 1:
            meal_facts["read_item"] = next(iter(items))[:180]
        remember_plan_read(coach, message, facts)
    if prior or meal_facts:
        coach.memory = coach.memory.remembering(DialogueContext(
            topic="meal_routine", anchor=prior.anchor if prior else message[:800], facts=meal_facts,
            details=prior.details if prior else [],
        ))


def remember_diet(coach, message, turn, today, account_day):
    snapshot = coach.action_session.snapshot
    remember_meal_read(coach, message, meal_rows(snapshot, turn.meal, today, account_day))
    return diet_reply(snapshot, turn, today, account_day)


def diet_read(message, snapshot, today, account_day, last_read):
    rows = active_meal_rows(snapshot, today, account_day)
    labels = named_meals(rows, message)
    if (not labels and last_read and last_read.facts.get("tipo") == "dieta"
            and re.search(r"\b(?:qual alimento|o que|oq|q) (?:ficou|tem|aparece|consta) (?:nessa|nesta|naquela) refeicao\b", message)
            and (previous := last_read.facts.get("refeicao"))
            and any(row.get("meal_name") == previous for row in rows)):
        labels = [previous]
    if len(labels) != 1:
        return None
    meal, = labels
    subject = re.search(r"\b(?:o que|oq|q|quais alimentos|qual alimento|qual refeicao)\b.{0,38}"
                        r"\b(?:como|comer|tem|ta no plano|aparece|consta|ficou)\b", message)
    followup = (last_read and last_read.facts.get("tipo") == "dieta"
                and re.fullmatch(rf"(?:e )?(?:(?:n[ao]|d[ao]|o|a) )?{re.escape(fold(meal))}[ ?.]*", message))
    if (subject or followup) and not re.search(r"\b(?:amanha|ontem|substitu\w*|troc\w*|opco\w*|alternativ\w*)\b", message):
        return Turn(op="diet", meal=meal)
    return None


def weekday_in_current_week(date_key, today):
    monday = today - timedelta(days=today.weekday())
    return next((day for index, day in enumerate(DAYS)
                 if (monday + timedelta(days=index)).isoformat() == date_key), None)


def last_consulted_workout_day(read, today):
    if not read:
        return None
    date_key = read.facts.get("ultimo_treino_data")
    if not date_key and read.facts.get("tipo") == "treino" and read.facts.get("foco") not in {"destino", "dia_livre"}:
        date_key = read.facts.get("data")
    return weekday_in_current_week(date_key, today)


def verified_move_references(coach, message, today, turn, pending):
    if not (_MOVE_WORD.search(message) and _MOVE_DIRECTIVE.search(message)) or change_scope(message) is not None:
        return {}
    fields = {}
    read = coach.memory.latest("plan_read")
    if re.search(r"\b(?:aquele treino|esse treino|o treino (?:desse dia|daquele dia|que (?:(?:voce|vc|tu) )?viu|consultado))\b", message):
        if source := last_consulted_workout_day(read, today):
            fields["day"] = source
    availability = coach.memory.latest("schedule")
    if availability and re.search(r"\b(?:dia corrigido|dia (?:que )?(?:eu )?(?:to|estou|ta) livre)\b", message):
        days = [key for key in availability.facts if key in {fold(day) for day in DAYS}]
        if len(days) == 1:
            fields["destination"] = days[0]
    if (pending and pending.op == "move_workout" and pending.destination
            and re.search(r"\b(?:(?:pra|para) (?:esse|aquele|este) dia|(?:pro|para o) dia livre (?:que )?(?:falei|citei|mencionei))\b", message)):
        fields["destination"] = pending.destination
    if read and re.search(r"\b(?:nesse|naquele|neste|esse|aquele) dia livre\b", message):
        if target := weekday_in_current_week(read.facts.get("ultimo_dia_livre_data"), today):
            fields["destination"] = target
            if availability and (source := availability.facts.get("treino_dificil")):
                fields["day"] = source
    if turn:
        return {key: value for key, value in fields.items()
                if not has_evidence(getattr(turn, key), message)}
    return fields


def food_locations(snapshot, message, today, account_day):
    question = re.search(r"\b(?:em quais refeicoes|quais refeicoes|aparece (?:de )?manha e (?:de )?tarde)\b", message)
    aside = re.search(r"\b(?:achou|jurou|disse) q(?:ue)? .{1,60} (?:era|aparecia|tava)\b", message)
    if not (question or aside) or change_scope(message) or explicit_change(message):
        return None
    rows = active_meal_rows(snapshot, today, account_day)
    items = {row["canonical"] for row in rows if has_evidence(row["canonical"], message)}
    if len(items) != 1:
        return None
    item, = items
    meals = list(dict.fromkeys(row["meal_name"] for row in rows
                               if row["canonical"] == item and row.get("meal_name")))
    return f"{item.capitalize()} aparece em {', '.join(meals)}." if meals else None


def meal_options(snapshot, turn, today, account_day):
    rows = meal_rows(snapshot, turn.meal, today, account_day)
    if not turn.item:
        return "Qual alimento você quer conferir?", None, []
    rows = food_matches(rows, fold(turn.item).strip())
    if len(rows) != 1:
        if not rows:
            return "Não encontrei esse alimento no cardápio indicado. Como ele aparece na ficha?", None, []
        labels = list(dict.fromkeys(row.get("meal_name") or "refeição sem nome" for row in rows))
        return "Em qual refeição? " + " ou ".join(labels) + "?", None, []
    item = rows[0]
    approved_ids = set(item.get("approved_replacement_ids") or [])
    approved = [row for row in snapshot.foods if row["id"] in approved_ids]
    return None, item, approved


def meal_reference(coach, turn, message, today, account_day):
    """Use a previous verified meal lookup only when it uniquely identifies an item."""
    context = coach.memory.latest("meal_routine")
    if not context or not re.search(
        r"\b(?:dele|dela|aquele peixe|aquela comida|esse alimento|essa refeicao|nessa refeicao)\b", message
    ):
        return turn
    facts = context.facts
    previous_meal = facts.get("read_meal")
    previous_item = facts.get("read_item")
    if not previous_meal or not previous_item:
        return turn
    if turn.meal and fold(turn.meal) != fold(previous_meal):
        return turn
    if turn.item and not (fold(turn.item) == fold(previous_item) or
                          fold(turn.item) in {"peixe", "aquele peixe", "alimento", "item", "comida"}):
        return turn
    rows = food_matches(meal_rows(coach.action_session.snapshot, previous_meal, today, account_day), fold(previous_item))
    if len(rows) != 1:
        return turn
    return turn.model_copy(update={"meal": previous_meal, "item": previous_item})


def referenced_food_option(coach, message, today, account_day):
    """Ground a follow-up about an alternative in the item that was actually read."""
    context = coach.memory.latest("meal_routine")
    snapshot = coach.action_session.snapshot
    if (not snapshot or not context or not context.facts.get("read_item") or explicit_change(message)
            or _PREVIEW.search(message)
            or re.search(r"\b(?:pode (?:efetuar|aplicar|fazer) (?:essa|a) troca|(?:e pra|quero) aplicar agora)\b", message)
            or not re.search(r"\b(?:cadastrad\w*|aprovad\w*|cabe|opcao|alternativa|substitut[oa]|no lugar|procurando)\b", message)):
        return None
    rows = active_meal_rows(snapshot, today, account_day)
    labels = named_meals(rows, message)
    meal = labels[0] if len(labels) == 1 else context.facts.get("read_meal") if not labels else None
    if not meal or re.search(r"\b(?:nao quero (?:essa|aquela) opcao|nao (?:use|usa|quero usar))\b", message):
        return None
    turn = Turn(op="replace_food", item=context.facts["read_item"], meal=meal, purpose="inquire")
    error, _, approved = meal_options(snapshot, turn, today, account_day)
    if error:
        return None
    named = mentioned_exercise(snapshot.foods, message)
    matches = approved_matches(approved, named) if named else approved
    selected = matches[0]["canonical"] if len(matches) == 1 else None
    return turn.model_copy(update={"replacement": selected, "options": [selected] if selected else []})


def approved_matches(approved, name):
    name = fold(name).strip()
    matches = food_matches(approved, name)
    if matches or len(name) < 4:
        return matches
    return [row for row in approved if re.search(
        rf"\b{re.escape(name)}\b", fold(row["canonical"])
    )]


def payload(kind, **fields):
    return validate_payload({"kind": kind, "source": "coach",
                             "reason": "Mudança solicitada pelo usuário no Coach.", **fields})


def move(coach, turn, today):
    snapshot = coach.action_session.snapshot
    if not snapshot or not snapshot.workout_plan_id:
        return "Você precisa de uma ficha ativa para mover o treino.", None, None
    origin, destination = weekday(turn.day, today), weekday(turn.destination, today)
    if origin is None:
        return "De qual dia você quer mover o treino?", None, turn
    if destination is None:
        return "Para qual dia você quer levar esse treino?", None, turn
    if origin == destination:
        return ("A origem e o destino são o mesmo dia. Para qual dia você quer mover?",
                None, turn.model_copy(update={"destination": None}))
    start = today - timedelta(days=today.weekday())
    current = {entry["date"]: entry for entry in snapshot.week}
    free = [DAYS[i] for i in range(7) if start + timedelta(days=i) >= today and i != origin
            and current.get((start + timedelta(days=i)).isoformat(), {}).get("activity_type") == "rest"]
    target_date = start + timedelta(days=destination)
    target = current.get(target_date.isoformat())
    if turn.scope is None and target and target["activity_type"] != "rest" and any(
        day["weekday"] == WEEKDAYS[destination] for day in snapshot.days
    ):
        alternatives = f" Dias livres nesta semana: {', '.join(free)}." if free else ""
        return (f"{DAYS[destination].capitalize()} já tem {target['title'] or 'treino'}.{alternatives} Qual dia funciona para você?",
                None, turn.model_copy(update={"destination": None}))
    if turn.scope is None:
        return "Você quer mover só nesta semana ou mudar o dia em todas as semanas da ficha?", None, turn
    if turn.period:
        return ("Posso mover a sessão no calendário. Esta operação não muda o horário do perfil. "
                "Quer abrir a prévia apenas com a troca de dia?", None, turn.model_copy(update={"period": None}))
    days = [day for day in snapshot.days if day["weekday"] == WEEKDAYS[origin]]
    if turn.scope == "week":
        source_date = start + timedelta(days=origin)
        if min(source_date, target_date) < today:
            return "Um desses dias já passou nesta semana. Qual data futura você quer usar?", None, None
        actual = current.get(source_date.isoformat())
        if not actual or not actual["workout_day_id"] or actual["activity_type"] == "rest":
            return f"Não há treino da ficha em {DAYS[origin]} nesta semana.", None, None
        if not target or target["activity_type"] != "rest":
            choices = f" Tenho {', '.join(free)} livres nesta semana." if free else ""
            return (f"{DAYS[destination].capitalize()} já tem atividade.{choices} Qual dia funciona para você?",
                    None, turn.model_copy(update={"destination": None}))
        action = payload("move_workout_occurrence", workout_plan_id=snapshot.workout_plan_id,
                         workout_day_id=actual["workout_day_id"], source_date=source_date.isoformat(),
                         target_date=target_date.isoformat())
    else:
        if len(days) != 1:
            return f"Não encontrei um treino recorrente único em {DAYS[origin]}.", None, None
        occupied = {day["weekday"] for day in snapshot.days}
        if WEEKDAYS[destination] in occupied:
            free = [DAYS[i] for i, day in enumerate(WEEKDAYS) if day not in occupied]
            choices = f" Na ficha, tenho {', '.join(free)} livres." if free else ""
            return (f"Já há treino em {DAYS[destination]}.{choices} Qual dia encaixa na sua rotina?",
                    None, turn.model_copy(update={"destination": None}))
        action = payload("move_workout_day", workout_plan_id=snapshot.workout_plan_id,
                         workout_day_id=days[0]["id"], target_weekday=WEEKDAYS[destination])
    scope = "só nesta semana" if turn.scope == "week" else "na ficha semanal"
    return f"Preparei a proposta de mover o treino de {DAYS[origin]} para {DAYS[destination]} {scope}. Abra a prévia para conferir.", action, None


def action_for(coach, turn, today, account_day):
    snapshot = coach.action_session.snapshot
    if turn.op == "move_workout":
        return move(coach, turn, today)
    if turn.op == "day_activity":
        index = weekday(turn.day, today)
        if index is None or not turn.activity:
            return "Qual dia e qual atividade você quer marcar?", None, turn
        chosen = today + timedelta(days=(index - today.weekday()) % 7)
        return ("Preparei a proposta de atividade. Abra a prévia para conferir.",
                payload("set_day_activity", activity_date=chosen.isoformat(), activity_type=turn.activity), None)
    if turn.op == "replace_food":
        error, item, approved = meal_options(snapshot, turn, today, account_day)
        if error:
            return error, None, turn
        if not turn.replacement:
            return "Qual alimento você quer colocar no lugar?", None, turn
        options = approved_matches(approved, turn.replacement)
        if len(options) != 1:
            names = ", ".join(row["canonical"] for row in (options or approved)[:4])
            if options:
                reply = f"Encontrei mais de uma opção: {names}. Qual delas você quer no lugar?"
            elif names:
                reply = f"Essa troca não está entre as opções equivalentes da refeição. Posso trocar por {names}. Alguma serve para você?"
            else:
                reply = "Não encontrei uma opção equivalente cadastrada para esse item. Quer conferir outra refeição?"
            return reply, None, turn
        replacement = options[0]
        action = payload("replace_meal_item", diet_plan_id=snapshot.diet_plan_id,
                         meal_item_id=item["id"], replacement_food_id=replacement["id"])
        return (f"Preparei a proposta de trocar {item['canonical']} por {replacement['canonical']} em "
                f"{item['meal_name']}. Abra a prévia para conferir a porção.", action, None)
    if not snapshot or not snapshot.workout_plan_id:
        return "Você precisa de uma ficha ativa para trocar um exercício.", None, None
    rows = exercise_rows(snapshot, turn.item, turn.day, today, account_day)
    if len(rows) != 1:
        return "Qual exercício e qual dia da ficha você quer alterar?", None, turn
    replacements = food_matches(snapshot.exercises, fold(turn.replacement).strip()) if turn.replacement else []
    if len(replacements) != 1:
        return "Qual exercício do catálogo você quer colocar no lugar?", None, turn
    row, replacement = rows[0], replacements[0]
    if fold(row["canonical"]) == fold(replacement["canonical"]):
        return "Esse exercício já está na ficha. Qual exercício deve entrar?", None, turn
    action = payload("replace_exercise", workout_plan_id=snapshot.workout_plan_id,
                     workout_day_exercise_id=row["id"], replacement_exercise_id=replacement["id"])
    return (f"Preparei a proposta de trocar {row['canonical']} por {replacement['canonical']}. Abra a prévia para conferir.",
            action, None)


def substitution_reply(snapshot, turn, today, account_day):
    error, item, approved = meal_options(snapshot, turn, today, account_day)
    if error:
        return error
    if not approved:
        return f"O plano não tem alternativas aprovadas para {item['canonical']} nessa refeição."
    matching = {row["id"]: row["canonical"] for option in turn.options for row in approved_matches(approved, option)}
    amounts = {row["food_id"]: row["amount"] for row in item.get("approved_replacement_portions") or []}
    label = f"Em {item['meal_name']}, para substituir {item['canonical']},"
    if matching:
        options = [f"{name} ({amounts[key]})" if key in amounts else name for key, name in matching.items()]
        return f"{label} o plano aprova {', '.join(options)}."
    options = ", ".join(row["canonical"] for row in approved[:5])
    return f"{label} as opções aprovadas incluem {options}."


# Restrict clearly hypothetical/negated requests from producing even a preview.
# Check the verb itself, so "não consigo comer salmão" doesn't negate a later request.
_READ_ONLY = re.compile(
    r"\b(?:posso|poderia eu|devo|vale a pena|faz sentido|e se|se eu|queria saber|queria entender|nao acha)\b|"
    r"\b(?:da (?:pra|para)|seria possivel|pode avaliar|poderia)\s+"
    r"(?:avaliar\s+)?(?:trocar|mudar|mover|substituir|alterar|passar)\b|"
    r"\b(?:nao|nunca)\s+(?:(?:quero|pode|preciso)\s+)?"
    r"(?:troqu\w*|troc\w*|mud\w*|mov\w*|substitu\w*|alter\w*|registr\w*|salv\w*|ajust\w*)\b")
_CONTEXT_ONLY = re.compile(
    r"\b(?:so (?:anotando|informando|comentando|um relato|contexto)|isso e contexto|"
    r"teria (?:que|q) ficar na ficha|ainda (?:vou|to) (?:escolher|decidindo))\b"
)


def has_evidence(quote, message):
    evidence = " ".join(fold(quote or "").split()).strip(" .!?,")
    return bool(evidence) and bool(re.search(rf"(?<!\w){re.escape(evidence)}(?!\w)", message))


def move_scope(turn, message):
    if re.search(r"\b(?:nao|n|nem)\b.*\b(?:todas|toda|tds|fixo|sempre|nesta|nessa|uma vez)\b", message):
        return None
    recurring = re.search(
        r"\b(?:toda semana|todas (?:as )?semanas|fixo|fixar (?:esse|este|o) dia|"
        r"permanente(?:mente)?|recorrente|daqui pra frente|a partir de agora)\b", message
    )
    one_week = re.search(r"\b(?:nesta|nessa|esta|essa|desta|dessa) semana\b|"
                         r"\bso agora\b.{0,40}\bsem (?:mexer|mudar|alterar)\b.{0,25}\boutras semanas\b|"
                         r"\b(?:so|somente|apenas) (?:uma vez|na data|desta vez|dessa vez)\b|\b(?:dessa|desta) vez so\b", message)
    if recurring and one_week:
        return None
    if recurring:
        return "recurring"
    if one_week:
        return "week"
    return turn.scope if turn and has_evidence(turn.scope_evidence, message) else None


def standalone_move_scope(message):
    # Only a plain answer to the scope question qualifies as recovery when the
    # model cannot parse it. No new date, question, cancellation or authorization.
    if not re.fullmatch(r"(?:(?:e )?(?:so|somente|apenas) )?(?:(?:nesta|nessa|esta|essa|desta|dessa) semana|"
                        r"uma vez|(?:em )?todas (?:as )?semanas|toda semana|"
                        r"(?:pra |para )?sempre|fixo|recorrente)(?: mesmo| ai)?[.! ]*", message):
        return None
    if "uma vez" in message:
        return "week"
    if "sempre" in message:
        return "recurring"
    return move_scope(None, message)


def pending_detail(pending, message, snapshot, today, account_day):
    if not pending or "?" in message or change_scope(message) == "negated":
        return None
    if pending.op == "move_workout" and pending.destination is None:
        chosen = re.fullmatch(
            r"(?:(?:entao|pode ser|deixa|coloca|joga|passa) )*(?:(?:n[ao]|pra|para) )?"
            r"(segunda|terca|quarta|quinta|sexta|sabado|domingo|hoje|amanha)(?:-feira)?"
            r"(?: (?:toda semana|todas (?:as )?semanas|so (?:nessa|nesta) semana))?[.! ]*", message
        )
        if chosen:
            return Turn(op="continue", destination=chosen[1])
    if pending.op != "replace_food":
        return None
    rows = meal_rows(snapshot, pending.meal, today, account_day)
    if not pending.meal:
        intent = re.fullmatch(r"(?:por enquanto )?(?:quero )?(?:so |apenas )?(?:quero )?"
                              r"(?:(?:(?:ver|abrir) )?(?:a )?previa|pra saber|para saber) "
                              r"(?:no|na|do|da) (.+?)(?: mesmo|,? antes de decidir)?[.! ]*", message)
        if intent:
            label = intent[1].strip()
            choices = {row["meal_name"] for row in active_meal_rows(snapshot, today, account_day)
                       if row.get("meal_name") and (requested_meal(row, label)
                           or fold(row["meal_name"]).startswith(label + " "))
                       and fold(row["canonical"]) == fold(pending.item or "")}
            if len(choices) == 1:
                purpose = "preview" if "previa" in message else "inquire"
                return Turn(op="continue", meal=next(iter(choices)), meal_evidence=intent[1], purpose=purpose)
        if change_scope(message) == "hypothetical":
            return None
        selection = re.fullmatch(
            r"(?:(?:to|estou) falando )?(?:(?:e|no|na|do|da|o|a) )*(.+?)(?:[,;] (?:deixa|mantem) .{1,60} (?:quiet[oa]|igual|como est[aá]))?[.! ]*",
            message,
        )
        labels = {row["meal_name"] for row in rows if row.get("meal_name")}
        if selection:
            matching = [label for label in labels if fold(label) == selection[1]]
            if len(matching) == 1:
                return Turn(op="continue", meal=matching[0], meal_evidence=selection[1])
    return None


def move_inquiry(snapshot, turn, today, account_day):
    if not snapshot:
        return None
    origin, destination = weekday(turn.day, today), weekday(turn.destination, today)
    if origin is None or destination is None or origin == destination:
        return None
    calendar = {index: (day, title) for index, day, title in occurrences(snapshot, today, account_day)}
    if turn.scope == "recurring":
        titles = {WEEKDAYS.index(row["weekday"]): row["title"] or "treino" for row in snapshot.days}
    else:
        titles = {index: title for index, (_, title) in calendar.items() if fold(title) != "descanso"}
    if origin not in titles:
        return "Qual sessão da ficha você quer mover?"
    target = DAYS[destination].capitalize()
    if destination in titles:
        free = [DAYS[index] for index, (day, _) in calendar.items() if index not in titles
                and (turn.scope == "recurring" or day >= today)]
        alternative = f" Dias livres: {', '.join(free)}." if free else ""
        return f"{target} já tem {titles[destination]}.{alternative} Quer ver outro dia?"
    if turn.scope == "week":
        return f"{target} está livre. Mover só nesta semana alteraria apenas o calendário desta semana; a ficha semanal continuaria igual."
    return f"{target} está livre na ficha. Dá para pedir a mudança dessa sessão."


def contextual_move(message, pending, snapshot, today, account_day, last_read):
    if not snapshot:
        return None, None, False
    classification = change_scope(message)
    if not pending or (pending.op == "move_workout" and pending.purpose == "inquire"):
        tentative = re.search(rf"^(?:(?:e )?se (?:passar|mover|remarcar) (?:pra|para)|pensei em encaixar (?:na|no)) "
                              rf"({DAY_WORD})(?:-feira)?\b", message)
        if not tentative and message.startswith("talvez ") and not _MOVE_DIRECTIVE.search(message):
            tentative = re.search(rf"\b(?:de|da) (?:pra|para) ir (?:na|no) ({DAY_WORD})(?:-feira)?\b", message)
        corrected = re.fullmatch(rf"(?:eu )?disse {DAY_WORD}\?[, ]+sim[, ]+(?:e )?({DAY_WORD})"
                                 r"(?:[- ]feira)?(?: (?:msm|mesmo))?\.? *(?:[^?]{0,65}semana\.?)?", message)
        origin = pending.day if pending else last_consulted_workout_day(last_read, today)
        if origin and (candidate := tentative or corrected):
            scope = move_scope(None, message) or (pending.scope if pending else None)
            plan = Turn(op="move_workout", day=origin, destination=candidate[1], scope=scope, purpose="inquire")
            if corrected:
                return f"Entendi, o dia que você está considerando é {candidate[1]}.", plan, False
            if answer := move_inquiry(snapshot, plan, today, account_day):
                return answer, plan, False
    inquiry = _MOVE_QUESTION.search(message)
    dates = _MOVE_DATES.search(message)
    if not inquiry and classification == "inquiry":
        inquiry = re.search(
            rf"\b(?:da (?:pra|para)|posso|poderia) (?:mover|remarcar|passar|adiar) "
            rf"[^?;]{{1,100}}?\b(?:na|no|de) ({DAY_WORD})(?:-feira)?[, ]+"
            rf"(?:pra|para|n[ao]) ({DAY_WORD})(?:-feira)?\b", message,
        )
    if inquiry or (dates and classification == "inquiry" and _MOVE_WORD.search(message)):
        origin, destination = (value for value in (inquiry or dates).groups() if value)
        plan = Turn(op="move_workout", day=origin, destination=destination, purpose="inquire")
        answer = move_inquiry(snapshot, plan.model_copy(update={"scope": move_scope(None, message)}), today, account_day)
        return answer, plan if answer else None, bool(answer)
    if "?" in message or _READ_ONLY.search(message) or classification in {"negated", "hypothetical"}:
        return None, None, False
    if dates and _MOVE_WORD.search(message) and _PREVIEW.search(message):
        origin, destination = dates.groups()
        return None, Turn(op="move_workout", day=origin, destination=destination, purpose="preview"), False
    if match := _MOVE_REQUEST.search(message):
        origin, destination = match.groups()
        if not origin and pending and pending.op == "move_workout":
            origin = pending.day
        if origin:
            # Explicit follow-ups to a consultation can only prepare a preview.
            # A known collision can also be explained immediately, without an action.
            if not pending:
                target = weekday(destination, today)
                if move_scope(None, message) or not any(
                    row['weekday'] == WEEKDAYS[target] for row in snapshot.days
                ):
                    return None, None, False
                monday = today - timedelta(days=today.weekday())
                target_date = (monday + timedelta(days=target)).isoformat()
                if not any(row['date'] == target_date and row['activity_type'] != 'rest' for row in snapshot.week):
                    return None, None, False
            return None, Turn(op="move_workout", day=origin, destination=destination, purpose="preview"), False
    return None, None, False


def mentioned_exercise(rows, message):
    hits = {(match.span(), row["canonical"]) for row in rows
            if (match := re.search(rf"\b{re.escape(fold(row['canonical']))}\b", message))}
    names = {name for (start, end), name in hits
             if not any(left <= start and end <= right and (left, right) != (start, end)
                        for (left, right), _ in hits)}
    return next(iter(names)) if len(names) == 1 else None


def exercise_inquiry(snapshot, message, today, account_day):
    if (not snapshot or change_scope(message) not in {"inquiry", "hypothetical"}
            or not re.search(r"\b(?:troc\w*|alternativ\w*|substitu\w*)\b", message)
            or re.search(r"\b(?:por|pelo|pela|no lugar)\b", message)):
        return None
    name = mentioned_exercise(snapshot.workout_exercises, message)
    day = re.search(rf"\b(?:treino|sessao) (?:de|na|no) ({DAY_WORD})(?:-feira)?\b", message)
    day = day[1] if day else None
    if not name or len(exercise_rows(snapshot, name, day, today, account_day)) != 1:
        return None
    return Turn(op="replace_exercise", item=name, day=day, purpose="inquire")


def rest_followup(message, history, snapshot):
    if not snapshot or not history or history[-1]['role'] != 'assistant':
        return None
    previous = history[-1]['content']
    interval = re.search(r'(?m)^Descanso: (\d+) segundos$', previous)
    if not interval or not re.search(r'\b(?:dobro|dobrar|duplicar)\b', message):
        return None
    if not re.search(r'\b(?:so (?:quero|queria) (?:discutir|saber)|faz sentido|vale a pena|posso|da pra)\b', message):
        return None
    label = previous.splitlines()[0]
    if not any(fold(row.get('display_name') or row['canonical']) == fold(label)
               and row.get('rest_seconds') == int(interval[1]) for row in snapshot.workout_exercises):
        return None
    seconds = int(interval[1])
    return (f"Na ficha, o dobro de {seconds} segundos seria {2 * seconds} segundos. "
            "Um intervalo mais longo dá mais tempo para recuperar o esforço entre as séries. "
            "O tempo adequado depende do exercício e do objetivo.")


def conversation_schedule(coach, clean, message):
    schedule = coach.memory.latest('schedule')
    saved = schedule.facts.get('mentioned_training_time') if schedule else None
    if saved and re.fullmatch(r'(?:e )?(?:que|qual) (?:hora|horario) (?:ficou|eu (?:disse|falei))(?: mesmo)?[ ?.]*', message):
        return f"Ficou às {saved}, como você comentou aqui."
    if '?' in message or explicit_change(clean) or not re.match(
        r'^(?:(?:eu )?(?:vou (?:conseguir|poder) (?:ir|treinar)|consigo (?:ir|treinar))|'
        r'(?:viajei|corrigindo|corrigindo aqui|na verdade|quer dizer)\b)', message
    ):
        return None
    hour = _SCHEDULE_HOUR.search(message)
    if not hour or (message.startswith(('viajei', 'corrigindo', 'na verdade', 'quer dizer')) and not saved):
        return None
    number = int(hour[1]) if hour[1].isdecimal() else _HOUR_VALUES[hour[1]]
    if not 1 <= number <= 12:
        return None
    if hour[2] in {'tarde', 'noite'} and number < 12:
        number += 12
    value = f'{number}h'
    coach.memory = coach.memory.recording('schedule', clean, {'mentioned_training_time': value})
    return f"Entendi. Vou considerar {value} aqui na conversa."


def respond(coach, clean, today, account, recalled, result):
    account_day = account.day if account else None
    snapshot = coach.action_session.snapshot
    if boundary := execution_boundary_reply(clean):
        return boundary
    if account and (saved := memory_request(clean, account)):
        reply, item = saved
        result["memory_item"] = item
        result["analysis"]["route"] = "conversation"
        return reply
    now = coach.action_session.now()
    draft = coach.router_draft
    if draft and (now >= draft[1] or not snapshot or draft[2] != snapshot.fingerprint()):
        draft = None
    coach.router_draft = None
    pending = draft[0] if draft else None
    message = " ".join(fold(clean).split())
    last_read = coach.memory.latest("plan_read")
    recent_replies = [item["content"] for item in coach.history[-8:] if item["role"] == "assistant"]
    social = conversational_reply(clean, recent_replies)
    if social and social[0] in {"greeting", "acknowledgment", "conversation_check_in"}:
        coach.router_draft = draft
        result["analysis"]["intent"]["label"] = social[0]
        result["analysis"]["route"] = "conversation"
        return social[1]
    aside = re.sub(r"^(?:ali[aá]s|troquei de assunto(?: rapidinho)?|mudando de assunto)[,:! ]+", "", clean, flags=re.I)
    if aside != clean and aside.strip() and "?" not in aside and not (
            explicit_change(aside) or explicit_information_request(aside) or _MOVE_DIRECTIVE.search(fold(aside))):
        coach.router_draft = draft
        result["analysis"]["route"] = "conversation"
        topic = re.sub(r"[.!] +mas (?:bora|vamos) voltar (?:pra|pro|ao|para [oa]) "
                       r"(?:ficha|plano|treino) depois[.! ]*$", "", aside, flags=re.I)
        return write_conversation(coach.lm, [], topic, None) or "Entendi. Pode continuar."
    if account and re.fullmatch(
        r"(?:(?:e|me (?:diz|lembra)|repete|repita|qual (?:e )?) )?(?:a |minha )?"
        r"(?:preferencia (?:gravada|salva|guardada)(?: (?:na minha conta|no perfil))?|"
        r"em qual turno (?:eu )?prefiro treinar segundo a memoria da conta)[ ?.]*", message
    ):
        coach.router_draft = draft
        return account_reply('Minhas memórias', account)
    if schedule_reply := conversation_schedule(coach, clean, message):
        coach.router_draft = draft
        result['analysis']['route'] = 'conversation'
        return schedule_reply
    difficulty = re.search(rf"\b(?:ficou|ta ficando|esta ficando|fica|ta) (?:ruim|dificil|apertado) "
                           rf"(?:ir|treinar)(?: n[ao])? ({DAY_WORD})(?:-feira)?\b", message)
    if difficulty and snapshot and "?" not in clean and not explicit_change(clean):
        index = weekday(difficulty[1], today)
        if index is not None and any(row["weekday"] == WEEKDAYS[index] for row in snapshot.days):
            coach.memory = coach.memory.recording("schedule", clean, {"treino_dificil": difficulty[1]})
    if re.fullmatch(r"(?:(?:ok|blz|beleza|entao|agora|sim)[, .!]+)*"
                    r"(?:vamos|bora) voltar (?:pro|pra|para o|para a|ao|a) (?:plano|ficha|treino)"
                    r"(?: mesmo| agora)?[.! ]*", message):
        coach.router_draft = draft
        result["analysis"]["route"] = "conversation"
        return "Certo, voltamos à ficha. O que você quer conferir?"
    if (re.search(r"\b(?:aplica\w*|confirm\w*)\b", message)
            and re.search(r"\b(?:qualquer (?:troca|mudanca|alteracao|proposta)|o que (?:estiver|tiver) ai)\b", message)):
        coach.router_draft = draft
        return "Nenhuma alteração foi confirmada com esse pedido. Abra uma prévia específica para conferir e confirmar."
    if _KEEP_PLAN.fullmatch(message) or re.fullmatch(
        r"(?:(?:deixa pra la[, ]+)?(?:pode )?cancel(?:a|ar|e)(?: (?:a|essa) troca)?"
        r"(?:,? nao vou (?:fazer|trocar|mudar))?|(?:entao )?(?:deixa|deixe) do jeito que (?:esta|ta)"
        r"(?: por enquanto)?)[.! ]*", message
    ):
        if coach.action_session.pending and coach.action_session.pending["status"] == "pending_user_confirmation":
            coach.action_session.clear()
        return "Certo. Vou manter seu plano como está."
    if re.search(r"\b(?:outr[oa] (?:chat|conversa))\b", message) and re.search(
        r"\b(?:aplica|aplique|confirma|confirme|faz|faca|pode fazer|pode aplicar)\b", message
    ):
        coach.router_draft = draft
        return "Qual mudança você quer pedir nesta conversa? Me diga o que precisa mudar."
    if (re.search(r"\b(?:outr[oa] (?:chat|conversa|conta))\b", message)
            and re.search(r"\b(?:contar|recuperar|lembr\w*|contei|falei|instrucao|lembrete|historico)\b", message)):
        coach.router_draft = draft
        return "Não consigo recuperar aqui o que ficou em outra conversa ou conta. Abra a conversa original pelo histórico da conta."
    if pending is None and re.fullmatch(
        r"(?:(?:sim|ok|beleza)[, ]+)?(?:pode (?:fazer|aplicar)|"
        r"(?:faca|faz|aplica|aplique|confirma|confirme) (?:a |essa )?(?:troca|mudanca|alteracao))"
        r"[.! ]*",
        message,
    ):
        if coach.action_session.pending:
            return "Abra a prévia da proposta para conferir e confirmar."
        return "Qual troca você quer fazer? Me diga o que sai e o que entra."
    reported = availability_report(coach.memory, clean)
    if reported is not coach.memory:
        coach.memory = reported
        coach.router_draft = draft
        result["analysis"]["route"] = "conversation"
        return f"Entendi. Você consegue treinar {availability_summary(reported)}."
    reported = food_equipment_report(coach.memory, clean)
    if reported is not coach.memory:
        coach.memory = reported
        coach.router_draft = draft
        result["analysis"]["route"] = "conversation"
        facts = reported.latest("meal_routine").facts
        return ("Entendi. Você tem uma bolsa térmica para levar a comida." if "bolsa termica" in message
                else f"Entendi. Você tem {facts['heating_device']} para esquentar a comida.")
    if hasattr(coach.search, 'reviewed_document') and (not explicit_change(clean) or '?' in clean):
        docs = ('rest_between_sets_context',)
        if answer := rest_followup(message, coach.history, snapshot):
            coach.router_draft = draft
            return coach._answer_reviewed(docs, clean, today, result, answer=answer)
        if re.search(r'\b(?:descansar|pausa|descanso|intervalo)\b.{0,45}\bentre (?:as )?series\b', message):
            normalized = re.sub(r'\bdescansar (?:mais |menos )?entre\b', 'descanso entre', clean, flags=re.I)
            if reviewed_questions(normalized) == docs:
                answer = None
                if re.search(r'\b(?:tecnica|execucao)\b.{0,30}\b(?:pior\w*|cai\w*)\b', message):
                    answer = ("Pode fazer sentido dar mais tempo entre as séries se você percebe que a execução piora com a fadiga. "
                              "O descanso ajuda a recuperar parte da capacidade para o esforço seguinte. "
                              "O intervalo adequado depende do exercício e do objetivo.")
                coach.router_draft = draft
                return coach._answer_reviewed(docs, clean, today, result, answer=answer)
    if change_scope(clean) is None and not explicit_change(clean):
        note = re.sub(r"(?:,? (?:ta|ok|beleza))\?$", "", message)
        if "?" not in note and _CONTEXT_ONLY.search(note):
            if re.search(r"\b(?:nao comi|nao consegui comer|deixei de comer)\b", note):
                meals = active_meal_rows(snapshot, today, account_day)
                names = named_meals(meals, note)
                selected = [row for row in meals if row.get("meal_name") in names
                            and has_evidence(row["canonical"], note)]
                if len(names) == len(selected) == 1:
                    remember_meal_read(coach, clean, selected)
            coach.memory = coach.memory.remembering(DialogueContext(topic="routine_context", anchor=clean[:800]))
            coach.router_draft = draft
            result["analysis"]["route"] = "conversation"
            return "Entendi. Vou considerar isso nesta conversa."
        if (routine := coach.memory.latest("routine_context")) and re.search(
            r"\b(?:motivo|rotina)\b", message
        ) and re.search(r"\b(?:disse|tinha dito|falei|contei|comentei)\b", message):
            coach.router_draft = draft
            result["analysis"]["route"] = "conversation"
            return f"Você me contou: “{routine.anchor[:300]}”"
        if recalled_answer := targeted_user_recall(coach.history, message):
            coach.router_draft = draft
            result["analysis"]["route"] = "conversation"
            return recalled_answer
        if first := first_workout_read(last_read, message):
            coach.router_draft = draft
            result["analysis"]["intent"]["label"] = "week"
            return first
        if read := workout_title_read(coach, clean, today, account_day):
            coach.router_draft = draft
            result["analysis"]["intent"]["label"] = "week"
            return read
        if (_FREQUENCY.search(message)
                and re.search(r"\b(?:semana|semanais|semanal|ficha|cadastrad\w*)\b", message)
                and re.search(r"\b(?:meu|minha|ficha|cadastrad\w*|ficaram)\b", message)):
            coach.router_draft = draft
            result["analysis"]["intent"]["label"] = "week"
            if not snapshot or not snapshot.workout_plan_id:
                return "Não encontrei uma ficha de treino ativa nesta conta para informar a frequência."
            if not last_read or last_read.facts.get("tipo") != "treino":
                remember_plan_read(coach, clean, {"tipo": "treino"})
            if re.search(r"\b(?:nesta|nessa|esta|essa) semana\b", message):
                total = sum(fold(title) != "descanso" for _, _, title in occurrences(snapshot, today, account_day))
                return f"Há {total} {'dia' if total == 1 else 'dias'} de treino no calendário desta semana."
            total = len({day["weekday"] for day in snapshot.days})
            return f"Sua ficha tem {total} {'dia' if total == 1 else 'dias'} de treino por semana."
        if (re.search(r"\b(?:refeicao|porcao)\b", message)
                and re.search(r"\b(?:eu )?(?:acabei de consultar|consultei|tinha consultado)\b", message)):
            coach.router_draft = draft
            context = coach.memory.latest("meal_routine")
            facts = context.facts if context else {}
            rows = meal_rows(snapshot, facts["read_meal"], today, account_day) if facts.get("read_meal") else []
            if facts.get("read_item"):
                rows = food_matches(rows, fold(facts["read_item"]))
            if rows and last_read and last_read.facts.get("tipo") == "dieta":
                return "\n".join(f"{row['meal_name']}: {dish_amount(row)}." for row in rows)
            return "Não encontrei essa consulta nesta conversa da sua conta."
        if re.search(r"\b(?:meu plano|minha dieta|minha ficha|meu cardapio) (?:tem|inclui|preve) ceia\b", message):
            coach.router_draft = draft
            if not snapshot or not snapshot.diet_plan_id:
                return "Não encontrei um cardápio ativo nesta conta."
            rows = active_meal_rows(snapshot, today, account_day)
            if not rows:
                return "Não encontrei refeições do plano para hoje."
            if not named_meals(rows, "ceia"):
                return "Seu cardápio ativo de hoje não prevê ceia."
            return remember_diet(coach, clean, Turn(op="diet", meal="ceia"), today, account_day)
        if read := portion_reply(snapshot, message, coach.history, today, account_day):
            coach.router_draft = draft
            result["analysis"]["intent"]["label"] = "diet"
            answer, rows = read
            remember_meal_read(coach, clean, rows)
            return answer
        if meal_read := diet_read(message, snapshot, today, account_day, last_read):
            coach.router_draft = draft
            result["analysis"]["intent"]["label"] = "diet"
            return remember_diet(coach, clean, meal_read, today, account_day)
        if day := calendar_read(None, message, coach.history, snapshot, today, account_day, last_read):
            result["analysis"]["intent"]["label"] = "week"
            coach.router_draft = draft
            return remember_calendar(coach, clean, today, account_day, None if day == "week" else day)
        if snapshot:
            explicit_rest = re.search(r"\b(?:quanto tempo|qual (?:e )?(?:a pausa|o intervalo|o descanso))\b", message) and re.search(
                r"\b(?:meu plano|minha ficha|na ficha|previst\w*|pausa|intervalo|descanso)\b", message
            )
            continuation_rest = coach.history and coach.history[-1]['role'] == 'assistant' and re.fullmatch(
                r"(?:e )?quanto (?:eu )?(?:espero|descanso|pauso) (?:de uma serie pra outra|entre (?:as )?series)[ ?.]*", message
            )
            previous = coach.history[-1]['content'] if continuation_rest else ''
            if not previous.startswith(tuple(row.get('display_name') or row['canonical'] for row in snapshot.workout_exercises)):
                previous = ''
            exercises = {row['canonical'] for row in snapshot.workout_exercises
                         if (explicit_rest and has_evidence(row['canonical'], message))
                         or (previous and previous.splitlines()[0] == (row.get('display_name') or row['canonical']))}
            if len(exercises) == 1:
                coach.router_draft = draft
                result["analysis"]["intent"]["label"] = "exercise"
                return exercise_reply(snapshot, Turn(op="exercise", item=next(iter(exercises)), fields=["rest"]),
                                      today, account_day)
        color_question = re.search(r"\b(?:qual (?:era a )?cor|de que cor|lembra a cor)\b", message)
        if color_question and not re.search(r"\b(?:conta|perfil)\b", message):
            object_name = re.search(r"\b(?:mochila|bolsa|camiseta|garrafa)\b", message)
            previous = next((row["content"] for row in reversed(coach.history)
                             if row["role"] == "user" and re.search(r"\b(?:levo|levei|vou levar)\b", fold(row["content"]))
                             and (not object_name or has_evidence(object_name[0], fold(row["content"])))
                             and "?" not in row["content"] and not preflight(row["content"])), None)
            if previous and re.search(r"\b(?:mochila|bolsa|camiseta|garrafa)\b", fold(previous)):
                coach.router_draft = draft
                return f"Você me disse: “{previous[:260]}”"
            if object_name:
                coach.router_draft = draft
                return "Qual era o objeto ou a cor que você quer retomar? Não encontrei esse detalhe aqui."
        if locations := food_locations(snapshot, message, today, account_day):
            coach.router_draft = draft
            result["analysis"]["intent"]["label"] = "diet"
            return locations
        if followup := read_followup(coach.memory, clean):
            coach.router_draft = draft
            return coach._answer_continuation(followup, today, result)
        if hasattr(coach.search, "reviewed_document"):
            docs = reviewed_questions(clean)
            if not docs and re.search(r"\bdeload e (?:folga|descanso)\b", message):
                docs = ("deload_meaning",)
            prior = coach.memory.latest("knowledge")
            if not docs and "deload" in message:
                docs = reviewed_questions(re.sub(r"\b(?:o que|oq) seria\b", "o que é", clean, flags=re.I))
            if not docs and prior and prior.facts.get("document") == "deload_meaning" and re.match(
                r"^(?:e )?(?:isso |deload )?(?:significa|quer dizer|preciso|tenho que) "
                r"(?:parar|ficar sem)\b", message
            ):
                docs = ("deload_meaning",)
            if docs and docs[0] in {"deload_meaning", "rest_between_sets_context"}:
                coach.router_draft = draft
                coach.memory = coach.memory.remembering(DialogueContext(
                    topic="knowledge", anchor=clean[:800], facts={"document": docs[0]}
                ))
                if answer := coach._answer_reviewed(docs, clean, today, result):
                    return answer
        if draft is None and re.search(r"\bpeixe d[oe] jantar\b", message) and re.search(
            r"\b(?:qual|que peixe)\b", message
        ):
            rows = meal_rows(snapshot, "jantar", today, account_day)
            if len(rows) == 1 and re.search(r"\b(?:peixe|salmao|atum|tilapia|sardinha|bacalhau)\b",
                                             fold(rows[0]["canonical"])):
                coach.memory = coach.memory.recording("meal_routine", clean, {
                    "read_meal": rows[0]["meal_name"], "read_item": rows[0]["canonical"],
                })
                return f"No jantar, o peixe é {rows[0]['canonical']}."
    food_option = (referenced_food_option(coach, message, today, account_day)
                   if not pending or (pending.op == "replace_food" and pending.purpose == "inquire") else None)
    if food_option:
        coach.router_draft = (food_option, now + timedelta(minutes=10), snapshot.fingerprint())
        result["analysis"]["intent"]["label"] = "food_options"
        return substitution_reply(snapshot, food_option, today, account_day)
    consult, direct, checks_target = contextual_move(message, pending, snapshot, today, account_day, last_read)
    if consult:
        if direct:
            coach.router_draft = (direct, now + timedelta(minutes=10), snapshot.fingerprint())
            if checks_target:
                remember_calendar(coach, clean, today, account_day, direct.destination, checking_destination=True)
        return consult
    if exercise_read := exercise_inquiry(snapshot, message, today, account_day):
        coach.router_draft = (exercise_read, now + timedelta(minutes=10), snapshot.fingerprint())
        result["analysis"]["intent"]["label"] = "exercise"
        return (f"Encontrei {exercise_read.item} na ficha. "
                "Se quiser avaliar a troca, me diga o exercício que você está considerando.")
    if snapshot and not pending and (swap := read_swap(clean)) and not swap.meals:
        foods = active_meal_rows(snapshot, today, account_day)
        # A broad read can narrow the meal on a subsequent turn. A direct
        # request with duplicate items needs the same resolution before preview.
        matches = food_matches(foods, swap.old)
        if len(matches) > 1 and len({row["meal_name"] for row in matches}) > 1:
            request = Turn(op="replace_food", item=swap.old, replacement=swap.new,
                           purpose="inquire" if swap.inquiry else "preview")
            coach.router_draft = (request, now + timedelta(minutes=10), snapshot.fingerprint())
            result["analysis"]["intent"]["label"] = "replace_food"
            return substitution_reply(snapshot, request, today, account_day)
    detail = pending_detail(pending, message, snapshot, today, account_day)
    explicit_review = bool(_PREVIEW.search(message) or re.search(
        r"\b(?:pode (?:efetuar|aplicar|fazer) (?:essa|a) troca|(?:e pra|quero) aplicar agora)\b", message
    ))
    food_request = re.sub(r"(?:^|(?<=[.!]) )(?:(?:o|a) (?:d[eo]|da) )[^.!?]{1,60} "
                          r"(?:segue igual|fica igual|fica como esta|fica)[.!](?: |$)", "", message)
    if (pending and pending.op == "replace_food" and pending.purpose == "inquire" and pending.replacement
            and explicit_review and re.search(r"\b(?:essa troca|a troca|substitui\w*|troca(?:r)? (?:o|so esse) item|"
                                              r"se estiver, quero usar de agora em diante)\b", food_request)
            and change_scope(message) is None and not _READ_ONLY.search(message)
            and not _CONTEXT_ONLY.search(message) and not named_meals(active_meal_rows(snapshot, today, account_day), food_request)
            and not mentioned_exercise(snapshot.foods, message)):
        detail = Turn(op="continue", purpose="preview")
    if (pending and pending.op == "replace_exercise" and pending.purpose == "inquire"
            and _PREVIEW.search(message) and re.search(r"\b(?:essa troca|a troca|escolh\w*)\b", message)
            and change_scope(message) not in {"negated", "inquiry", "hypothetical"}):
        if replacement := mentioned_exercise(snapshot.exercises, message):
            detail = Turn(op="continue", replacement=replacement, purpose="preview")
    if (pending and pending.op == "move_workout" and pending.purpose == "inquire"
            and move_scope(None, message) and _PREVIEW.search(message)
            and re.search(r"\b(?:faz|faca|prepara|prepare|quero)\b", message)
            and change_scope(message) not in {"negated", "hypothetical", "inquiry"}):
        detail = Turn(op="continue", purpose="preview")
    verified_move = verified_move_references(coach, message, today, None, pending) if snapshot else {}
    if not detail and not direct and len(verified_move) == 2 and move_scope(None, message):
        direct = Turn(op="move_workout", purpose="preview", **verified_move)
    if detail or direct:
        turn, history, preferences = detail or direct, {}, []
    else:
        turn, history, preferences = interpret(coach, clean, today, account, pending)
    if day := calendar_read(turn, message, coach.history, snapshot, today, account_day, last_read):
        coach.router_draft = draft
        result["analysis"]["intent"]["label"] = "week"
        return remember_calendar(coach, clean, today, account_day, None if day == "week" else day)
    if (turn is None or turn.op in {"move_workout", "unclear", "chat"}
            or (turn.op == "continue" and pending and pending.op == "move_workout")):
        references = verified_move_references(coach, message, today, turn, pending)
        if references and (turn and turn.op in {"move_workout", "continue"} or len(references) == 2):
            turn = (turn if turn and turn.op in {"move_workout", "continue"}
                    else Turn(op="move_workout", purpose="preview")).model_copy(update=references)
    else:
        references = {}
    recovered_scope = None
    if (pending and pending.op == "move_workout" and pending.scope is None
            and weekday(pending.day, today) is not None and weekday(pending.destination, today) is not None
            and (not turn or turn.op not in {"continue", "move_workout"} or not move_scope(turn, message))):
        recovered_scope = standalone_move_scope(message)
        if recovered_scope:
            turn = Turn(op="continue")
    if turn is None:
        coach.router_draft = draft
        return "Não consegui entender esse pedido. Você pode dizer qual informação ou mudança precisa?"
    scope = recovered_scope or (move_scope(turn, message) if turn.op in {"move_workout", "continue"} else None)
    continued = turn.op == "continue"
    scope_only = bool(pending and pending.op == "move_workout" and scope and not references
                      and not (explicit_change(clean) or _PREVIEW.search(message))
                      and not re.search(rf"\b{DAY_WORD}\b", message))
    if scope_only and "?" not in message:
        continued = continued or turn.op == "move_workout"
    if (pending and pending.op == turn.op == "move_workout" and pending.destination is None
            and weekday(turn.day, today) in {None, weekday(pending.day, today)}
            and turn.destination and scope is None):
        continued = True
    if continued:
        if not pending:
            result["analysis"]["route"] = "conversation"
            coach.memory = observe_report(coach.memory, clean)
            return write_conversation(coach.lm, coach.history, clean, None) or "Entendi. Pode continuar."
        fields = turn.model_dump(exclude_defaults=True, exclude={"op", "scope_evidence"})
        allowed = {"request_evidence"} if scope_only else FIELDS[pending.op] | {"request_evidence", "meal_evidence"}
        if pending.op == "move_workout":
            allowed = allowed - {"scope"}
        if turn.purpose in {"inquire", "preview"}:
            allowed |= {"purpose"}
        updates = {key: value for key, value in fields.items() if key in allowed}
        if pending.op == "move_workout" and not scope_only:
            for key in ("day", "destination"):
                if key in updates and key not in references and not has_evidence(updates[key], message):
                    del updates[key]
        if pending.op == "replace_food":
            for key in ("item", "replacement"):
                if key in updates and not has_evidence(updates[key], message):
                    del updates[key]
            if "meal" in updates and not (
                has_evidence(updates["meal"], message) or has_evidence(turn.meal_evidence, message)
            ):
                del updates["meal"]
        preview_selected = turn.purpose == "preview" and pending.op == "replace_food" and explicit_review
        if not scope and not preview_selected and not (set(updates) & FIELDS[pending.op]):
            coach.router_draft = draft
            result["analysis"]["route"] = "conversation"
            return write_conversation(coach.lm, coach.history, clean, None) or "Entendi. Pode continuar."
        turn = pending.model_copy(update=updates)
        if turn.op == "move_workout":
            turn = turn.model_copy(update={"scope": scope or pending.scope})
    elif turn.op == "move_workout":
        turn = turn.model_copy(update={"scope": scope})
    if turn.op == "week" and re.search(r"\b(?:da|desta|dessa|esta|essa) semana\b", message):
        if not re.search(r"\b(?:segunda|terca|quarta|quinta|sexta|sabado|domingo|hoje|amanha)\b", message):
            turn = turn.model_copy(update={"day": None})
    if turn.op == "exercise":
        fields = [key for key, pattern in (
            ("reps", r"\b(?:reps|repetic\w*|por perna|ou total)\b"),
            ("rest", r"\b(?:intervalo|descanso|pausa)\b"),
            ("sets", r"\bseries?\b"),
            ("instructions", r"\b(?:como (?:faco|executar|fazer)|execucao)\b"),
        ) if re.search(pattern, message)]
        if fields:
            turn = turn.model_copy(update={"fields": list(dict.fromkeys(turn.fields + fields))})
    if turn.op in {"diet", "food_options", "replace_food"}:
        # A model-supplied meal must be grounded in the current request or an
        # earlier validated draft. Never choose between duplicated food items.
        rows = active_meal_rows(snapshot, today, account_day)
        labels = {row["meal_name"] for row in rows
                  if row.get("meal_name")}
        selected_text = food_request if continued and turn.op == "replace_food" else message
        mentioned = [label for label in labels if re.search(rf"\b{re.escape(fold(label))}\b", selected_text)]
        ordinal = re.search(r"\b(?:ultima|primeira|segunda|terceira|quarta|quinta|sexta) refeicao\b|\brefeicao [1-9]\b", message)
        meal = ordinal[0] if ordinal else mentioned[0] if len(mentioned) == 1 else None
        if relative_meal := re.search(r"\b(?:naquela|nessa|daquela|dessa) (primeira|segunda) refeicao\b", message):
            meal, _ = previous_meal_mention(rows, coach.history, int(relative_meal[1] == "segunda"))
            if not meal:
                coach.router_draft = draft
                return "Qual era a refeição que você mencionou? Me diga o nome para eu conferir na ficha."
        if not meal and not mentioned and turn.meal and has_evidence(turn.meal_evidence, message):
            if meal_rows(snapshot, turn.meal, today, account_day):
                meal = turn.meal
        pending_food = draft[0] if draft and draft[0].op == "replace_food" else None
        if (pending_food and meal and not pending_food.meal and turn.op in {"food_options", "replace_food"}
                and (not turn.item or fold(turn.item) == fold(pending_food.item or ""))
                and ("quis dizer" in message or re.match(r"^(?:e )?a fruta d[oa]\b", message))):
            turn = pending_food.model_copy(update={"meal": meal})
        elif turn.op in {"food_options", "replace_food"} and not continued:
            verified_previous = (pending_food.meal if pending_food and
                                 fold(pending_food.item or "") == fold(turn.item or "") else None)
            turn = turn.model_copy(update={"meal": meal or verified_previous})
        elif meal:
            turn = turn.model_copy(update={"meal": meal})
        if turn.op in {"food_options", "replace_food"}:
            turn = meal_reference(coach, turn, message, today, account_day)
    if turn.op == "food_options" and len(turn.options) == 1 and re.match(
        r"^(?:por favor )?(?:troca|troque|substitua|quero abrir a previa d[ea])\b", message
    ) and "?" not in clean:
        turn = turn.model_copy(update={"op": "replace_food", "replacement": turn.options[0]})
    if (turn.op == "day_activity" and not re.search(
        r"\b(?:marc[ae]|registr[ae]|coloc[ae]|defin[ae]|quero descansar)\b", message
    ) and not (continued and draft and draft[0].op == "day_activity")):
        turn = turn.model_copy(update={"op": "chat"})
    if turn.op == "chat":
        # Preserve the pending question through a greeting/aside, and keep factual
        # account and plan data out of unrestricted social prose.
        coach.router_draft = draft
        coach.memory = observe_report(coach.memory, clean)
        result["analysis"]["route"] = "conversation"
        return write_conversation(coach.lm, coach.history, clean, None) or "Pode falar. Como posso ajudar?"
    result["analysis"]["intent"]["label"] = turn.op
    if turn.op in CHANGES:
        if (turn.op == "replace_food" and pending and pending.op == "replace_food"
                and pending.purpose == "inquire" and not explicit_review and not explicit_change(clean)):
            coach.router_draft = draft
            return substitution_reply(snapshot, pending, today, account_day)
        if turn.op == "move_workout" and turn.purpose != "inquire" and not (
            _MOVE_DIRECTIVE.search(message) or explicit_change(message)
            or (continued and pending and pending.purpose in {"preview", "apply"})
        ):
            # A weekday or a scope mentioned in conversation is useful context.
            # It can complete an existing request, but cannot start a proposal.
            coach.router_draft = draft
            if snapshot and turn.day and weekday(turn.destination, today) is not None and has_evidence(turn.destination, message):
                coach.router_draft = (turn.model_copy(update={"purpose": "inquire"}),
                                      now + timedelta(minutes=10), snapshot.fingerprint())
            result["analysis"]["route"] = "conversation"
            return "Entendi o dia que você mencionou. Posso preparar a prévia se você decidir mover o treino."
        if (turn.purpose == "inquire" or _READ_ONLY.search(message) or _CONTEXT_ONLY.search(message)
                or change_scope(clean) in {"negated", "inquiry", "hypothetical"}
                or (not continued and message.strip(" .!?") in {"ok", "sim", "confirmo", "beleza"})):
            coach.router_draft = draft
            if (turn.op == "move_workout" and (turn.purpose == "inquire" or change_scope(clean) == "inquiry")
                    and has_evidence(turn.day, message) and has_evidence(turn.destination, message)):
                if answer := move_inquiry(snapshot, turn, today, account_day):
                    remember_calendar(coach, clean, today, account_day, turn.destination, checking_destination=True)
                    return answer
            if turn.op == "replace_food":
                if snapshot and turn.item and turn.replacement and not turn.meal:
                    coach.router_draft = (turn.model_copy(update={"purpose": "inquire"}),
                                          now + timedelta(minutes=10), snapshot.fingerprint())
                return substitution_reply(snapshot, turn.model_copy(update={"options": [turn.replacement] if turn.replacement else []}),
                                          today, account_day)
            return "Posso consultar a ficha e explicar as opções. O plano permanece como está."
        temporary = re.search(
            r"\b(?:so|somente|apenas) (?:por )?"
            r"(?:hoje|hj|(?:nesta|nessa|esta|essa|desta|dessa) semana|uma vez)\b", message
        ) or (turn.scope == "week" and (turn.op != "replace_food" or (
            has_evidence(turn.scope_evidence, message)
            and re.search(r"\b(?:hoje|hj|semana|uma vez)\b", fold(turn.scope_evidence or ""))
        )))
        if turn.op == "replace_food" and temporary:
            return ("Posso consultar as alternativas da refeição de hoje. A troca disponível no Planner altera "
                    "o cardápio. Se é só por hoje, você pode registrar o que comeu na Dieta. Quer ver as opções?")
        if turn.op == "replace_exercise" and temporary:
            return ("A troca de exercício disponível altera a ficha. Se a mudança é só para a sessão de hoje, "
                    "posso conversar sobre alternativas. Qual equipamento você tem disponível?")
        if turn.op == "day_activity" and turn.scope == "recurring":
            return "Consigo marcar uma atividade para um dia específico. Quer ajustar algum treino da ficha semanal?"
        if _PREVIEW.search(message):
            turn = turn.model_copy(update={"purpose": "preview"})
        elif turn.op == "move_workout" and turn.purpose is None and _MOVE_DIRECTIVE.search(message):
            turn = turn.model_copy(update={"purpose": "preview"})
        elif ((turn.purpose is None and explicit_change(clean) and "?" not in message)
              or (turn.op == "move_workout" and turn.purpose == "preview" and explicit_change(clean)
                  and "pode ser?" in message)):
            turn = turn.model_copy(update={"purpose": "apply", "request_evidence": clean[:120]})
        reply, action, waiting = action_for(coach, turn, today, account_day)
        if action:
            if turn.op == "replace_food":
                chosen = [row for row in active_meal_rows(snapshot, today, account_day)
                          if row["id"] == action["meal_item_id"]]
                remember_meal_read(coach, clean, chosen)
            result["actions"] = [coach.action_session._prepare(action)]
            result["analysis"]["route"] = "draft_for_confirmation"
        elif waiting and snapshot:
            if waiting.purpose == "apply" and not continued and not has_evidence(waiting.request_evidence, message):
                waiting = waiting.model_copy(update={"purpose": None})
            coach.router_draft = (waiting, now + timedelta(minutes=10), snapshot.fingerprint())
        return reply
    if turn.op == "cancel":
        if coach.action_session.pending and coach.action_session.pending["status"] == "pending_user_confirmation":
            coach.action_session.clear()
        return "Certo. Vou manter seu plano como está."
    if turn.op in {"week", "exercise", "diet", "food_options", "recall", "memory", "account", "knowledge"}:
        coach.router_draft = draft
    if turn.op == "week":
        return remember_calendar(coach, clean, today, account_day, turn.day)
    if turn.op == "exercise":
        return exercise_reply(snapshot, turn, today, account_day)
    if turn.op == "diet":
        if re.search(r"\b(?:amanha|ontem)\b", message):
            return "Posso consultar o cardápio de hoje aqui. Qual refeição de hoje quer ver?"
        return remember_diet(coach, clean, turn, today, account_day)
    if turn.op == "food_options":
        return substitution_reply(snapshot, turn, today, account_day)
    if turn.op == "recall":
        recalled_text = history.get(turn.turn)
        if not recalled_text and recalled:
            recalled_text = recalled[-1]
        if recalled_text:
            return f"Você me disse: “{recalled_text}”"
        return "Não encontrei esse detalhe na conversa. Qual assunto você quer retomar?"
    if turn.op == "memory":
        if not preferences:
            return "Não tenho uma preferência salva disponível para esta pergunta."
        if turn.turn and turn.turn <= len(preferences):
            return f"Você deixou esta preferência salva: “{preferences[turn.turn - 1]}”"
        if len(preferences) == 1:
            return f"Você deixou esta preferência salva: “{preferences[0]}”"
        return "Qual preferência salva você quer consultar?"
    if turn.op == "account" and account:
        return exercise_history_reply(clean, account, snapshot) or account_reply(clean, account) or (
            "Qual dado da conta você quer conferir?")
    if turn.op == "safety":
        return "Não consigo avaliar sintomas pelo chat. Se houver risco imediato, interrompa a atividade e procure atendimento de emergência."
    if turn.op == "knowledge":
        followup = read_followup(coach.memory, clean)
        if followup:
            return coach._answer_continuation(followup, today, result)
        query = turn.query or clean
        if preflight(query):
            return "Não consigo avaliar esse caso individual pelo chat. Procure orientação profissional."
        if gap := specific_gap(query):
            return gap
        docs = reviewed_questions(query)
        if docs and hasattr(coach.search, "reviewed_document"):
            reviewed = coach._answer_reviewed(docs, query, today, result)
            if reviewed:
                return reviewed
        return coach._answer_with_sources(query, today, result)
    return plan_catalogue_reply(clean, snapshot, today, account_day) or "Qual informação ou mudança você quer conferir?"

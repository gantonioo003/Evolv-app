"""Remember user-reported facts per conversation and resolve read-only follow-ups."""
from dataclasses import dataclass
import re

from .dialogue import DialogueContext
from .retrieval import explicit_switch, fold


def targeted_user_recall(history, message):
    if re.search(r"\b(?:lembrete|recado)\b", message) and (
        re.search(r"\b(?:repet\w*|lembr\w*|qual)\b", message) or "?" in message
    ):
        clue = re.compile(r"\b(?:preciso|tenho que|lembrar de|lembrete|recado)\b.*"
                          r"\b(?:sair|saida|levar|pegar|separar|deixar|guardar|carregar)\b")
    elif (re.search(r"\b(?:disse|falei|contei|mencionei)\b", message)
          and re.search(r"\b(?:tempo|atraso|horario apertado|motivo)\b", message)):
        clue = re.compile(r"\b(?:meu tempo|tempo (?:ta|esta) curto|meu horario|atras\w*|"
                          r"horario apertado|tempo (?:apertado|encurtou)|"
                          r"motivo (?:e|foi)|pra (?:explicar|dar) contexto)\b")
    else:
        return None
    for entry in reversed(history[-24:]):
        if entry["role"] == "user" and not entry.get("critical_risks") and "?" not in entry["content"]:
            if clue.search(fold(entry["content"])):
                return f"Você me disse: “{entry['content'][:300]}”"
    return None


_DAY = r"segunda(?:-feira)?|terca(?:-feira)?|quarta(?:-feira)?|quinta(?:-feira)?|sexta(?:-feira)?|sabado|domingo"
_DAYS = dict(zip(("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"),
                 ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")))
_PERIOD = {"manha": "manhã", "tarde": "tarde", "noite": "noite"}
_AVAILABILITY = re.compile(
    r"\b(?:so (?:da pra|consigo|posso)|consigo|tenho disponibilidade|"
    r"treinos? so cabem|tenho tempo)\b"
)
_FREE_CORRECTION = re.compile(rf"\b({_DAY}) e que (?:ta|esta) livre[.! ]*$")
_SLOT = re.compile(
    rf"\b({_DAY})(?:\s+(?:(?:e|ficou)\s+)?(?:de|a|pela|na|no horario d[oe])?\s*"
    r"(manha|cedo|tarde|noite|almoco))?\b"
)
_CORRECTED_DAY = re.compile(r"\b(?:virou|mudou (?:pra|para)|(?:na verdade|corrigindo|ops))\b")
_AVAILABILITY_QUERY = re.compile(r"\b(?:horarios?|disponibilidade|dia e periodo|dias?)\b")
_FOOD_EQUIPMENT = re.compile(r"\b(micro-?ondas|bolsa termica)\b")
_FOOD_CONTEXT = re.compile(r"\b(?:comida|refeic\w*|marmitas?|esquentar|levar)\b")
_DAY_SEQUENCE = rf"({_DAY})(?:(?:\s*,\s*|\s+e\s+)({_DAY}))+"
_MEAL = re.compile(r"\b(?:jantar|refeic\w*|comida feita em casa|cozinh\w*|marmita|lanche|comer perto do treino)\b")
_TIME = re.compile(r"\b(?:meia hora|(\d{1,3}|dez|doze|quinze|vinte|trinta|quarenta) minutos?)\b")
_TIME_WORDS = {"dez": "10", "doze": "12", "quinze": "15", "vinte": "20", "trinta": "30", "quarenta": "40"}
_SCHEDULE = re.compile(r"\btrein(?:o|ar) (?:depois das |as )(\d{1,2})(?:h| horas?)\b")
_TRAINING_VISIT = re.compile(
    rf"^(?:(?:so )?(?:consigo|posso|vou) (?:ir|treinar)|(?:eu )?vou a academia)"
    rf"(?: (?:pra|para a|a|na) academia)? (?:n[oa] )?({_DAY})(?: de (manha|tarde|noite))?\b"
)
_SET_DEFINITION = re.compile(r"\b(?:o que (?:e|significa)|oq (?:e|significa)|como (?:explico|explicar))\b.{0,55}\bserie\b")
_SET_REST = re.compile(r"\b(?:sem (?:pausa|intervalo)|(?:pausa|descanso|intervalo) entre (?:elas|as series))\b")
_EQUIPMENT = re.compile(r"\bs[oó] tenho (?:acesso a |um par de |um |uma )?([^.!?,;]{2,80})", re.IGNORECASE)
_EQUIPMENT_WORD = re.compile(r"\b(?:halter\w*|elastico\w*|faixa\w*|barra\w*|esteira|bicicleta|banco|colchonete|kettlebell\w*)\b")
_LIFT = re.compile(r"\bfiz (\d+) (?:reps|repeticoes) com (\d+(?:[.,]\d+)?)\s*kg\b")
_DURATION = re.compile(r"\b(?:fiquei|segurei|mantive) (\d+)\s*(?:s|segundos?)\s+n[oa] ([\w -]{2,40})")
_INTERVALS = re.compile(r"\b(?:foram|fiz) (\d+)\s+(subidas|tiros|intervalos) de (\d+)\s*(s|segundos?|minutos?)\b")
_NIGHT_MEAL = re.compile(r"\b(?:sono|dormir|deitar)\b")
_PREPARING = re.compile(r"\b(?:deixar|deixo|adiantar|separar|fazer)\b.{0,35}\b(?:pront[oa]|domingo|antes|antecedencia)\b")
_RESUME = re.compile(r"^(?:voltando|continuando|retomando)\b")
_IDEAS = re.compile(r"\b(?:ideias?|opcoes|o que (?:posso|da pra) (?:fazer|levar|comer))\b")
_RECALL = re.compile(r"\b(?:falei|disse|comentei|mesmo|afinal|eu fiquei|eu tinha)\b")
_TRAVEL = re.compile(r"\b(?:viaj\w*|hotel|pousada|hospedagem)\b")
_RETURN = re.compile(rf"\b(?:volto|vou voltar|retorno) (?:n[oa] )?({_DAY})(?: de (manha|tarde|noite))?\b")
_UNAVAILABLE = re.compile(r"\b(?:quebrad[oa]|indisponivel|fora de uso|nao funciona)\b")
_LOGISTICS = re.compile(
    r"\b(?:geladeira|esquentar|mochila|armario|folgo|hotel|pousada|hospedagem|turno|viajar|volto)\b"
)
_NO_FRIDGE = re.compile(r"\b(?:sem|longe d[aeo]) geladeira\b")
_STORAGE_REPORT = re.compile(
    r"(?:(?:meu )?armario fica longe da geladeira|(?:eu )?(?:fico|estou|trabalho) sem geladeira|sem geladeira)"
)
_CLOSED_SNACK = re.compile(
    r"(?:e )?(?:qual|que) (?:opcao|lanche) (?:eu )?(?:posso|da pra|da para) levar fechad[oa]"
)
_SLEEP = re.compile(r"\b(?:sono|dorm\w+|durm\w+)\b")
_HOURS = r"(\d{1,2})(?:\s*(?:/|a|ou|[-–])\s*(\d{1,2}))?\s*(?:h|horas?)\b"
_SLEEP_HOURS = re.compile(rf"\b(?:dorm\w+|durm\w+|sono de)\b[^.!?,;]{{0,55}}?\b{_HOURS}")
_HOURS_REPLY = re.compile(rf"(?:na verdade[, ]+)?(?:foi |foram |so |cerca de )?{_HOURS}(?: por (?:noite|dia))?")
_SLEEP_PERIOD = re.compile(r"\b(?:por|durante|faz|ha) ((?:uma?|duas|tres|\d{1,2}) (?:semanas?|noites?|dias?))\b")
_SLEEP_PERFORMANCE = re.compile(r"\b(?:progresso|rend\w*|desempenho|recupera\w*|trein\w*|academia|musculacao)\b")
_SLEEP_ASK = re.compile(r"\b(?:quanto|impact\w*|afet\w*|atrapalh\w*|importan\w*|por que|pq|explic\w*)\b")
_SLEEP_WHY = re.compile(r"\b(?:por que|pq|explic\w*)\b")
_SLEEP_INDIVIDUAL = re.compile(r"\b(?:mesm[ao] (?:quantidade|numero|horas?)|igual pra tod\w+|igual para tod\w+)\b")
_SLEEP_REFERENCE = re.compile(r"^(?:e )?(?:por que|pq|quanto (?:isso|essa falta)|como (?:isso|essa falta)|"
                              r"isso (?:afeta|atrapalha|prejudica)|qual (?:e )?o impacto)\b")
_SLEEP_ONLY_REPORT = re.compile(rf"(?:eu )?(?:dormi|durmo|estou dormindo|to dormindo) "
                               rf"(?:so |cerca de )?{_HOURS}(?: por (?:noite|dia))?")


def availability_report(memory, text):
    """Update availability from a report or a correction to an existing slot."""
    from .request_intent import explicit_change

    clean = fold(text)
    clauses = re.split(r"[,;.!]|\b(?:e|entao|por isso)\b", text)
    if "?" in text or any(explicit_change(clause) for clause in clauses) or re.search(
        r"\b(?:quero|preciso|gostaria de|pode) (?:mudar|trocar|mover|remarcar|colocar)\b", clean
    ):
        return memory
    correction = _FREE_CORRECTION.search(clean)
    matches = list(_SLOT.finditer(clean, correction.start() if correction else 0))
    slots = [(m[1].split("-")[0], m[2]) for m in matches]
    if not slots:
        return memory
    periods = {"manha": " de manhã", "cedo": " cedo", "tarde": " à tarde", "noite": " à noite",
               "almoco": " no horário do almoço"}
    schedule = memory.latest("schedule")
    facts = dict(schedule.facts) if schedule else {}
    current = {key: value for key, value in facts.items() if key in _DAYS}
    if correction or _AVAILABILITY.search(clean):
        if not correction and re.search(r"\b(?:nao|nunca|nem)\b", clean):
            return memory
        current = {day: periods.get(period, " (horário não informado)") for day, period in slots}
        if len(slots) > 1 and all(not period for _, period in slots[:-1]) and slots[-1][1]:
            current = {day: periods[slots[-1][1]] for day in current}
    elif current and _CORRECTED_DAY.search(clean):
        if (len(slots) >= 2 and slots[0][0] in current
                and re.search(r"\b(?:virou|mudou (?:pra|para)|nao (?:rola|da|funciona|serve))\b",
                              clean[matches[0].end():matches[1].start()])):
            old, new = slots[0][0], slots[1]
            new_period = periods.get(new[1], current[old])
            current = {new[0] if day == old else day: new_period if day == old else value
                       for day, value in current.items()}
        elif slots[0][0] in current and slots[0][1] and not re.search(r"\bnao\b", clean):
            current[slots[0][0]] = periods[slots[0][1]]
        else:
            return memory
    elif current and len(slots) == 1 and slots[0][0] in current and slots[0][1] and re.search(
        rf"\b(?:{_DAY}) (?:e|ficou) (?:de |a )?(?:manha|tarde|noite)\b", clean
    ):
        current[slots[0][0]] = periods[slots[0][1]]
    else:
        return memory
    facts = {key: value for key, value in facts.items() if key not in _DAYS}
    return memory.remembering(DialogueContext(topic="schedule", anchor=text[:800], facts=facts | current))


def availability_summary(memory):
    schedule = memory.latest("schedule")
    if not schedule:
        return ""
    return "; ".join(f"{_DAYS[day]} {period.strip()}" for day, period in schedule.facts.items() if day in _DAYS)


def food_equipment_report(memory, text):
    from .request_intent import explicit_change

    clean = fold(text)
    if ("?" in text or any(explicit_change(part) for part in re.split(r"[,;.!]|\b(?:e|entao)\b", clean))
            or not _FOOD_CONTEXT.search(clean) or not re.search(r"\b(?:tenho|uso|levo)\b", clean)):
        return memory
    equipment = _FOOD_EQUIPMENT.search(clean)
    if not equipment or re.search(r"\b(?:nao|sem|nunca)\b", clean):
        return memory
    if equipment[1] == "bolsa termica":
        return memory.recording("meal_routine", text, {"transport": "uma bolsa térmica"})
    return memory.recording("meal_routine", text, {"heating_device": "micro-ondas"})


def remembers_availability(memory, clean):
    if not (_AVAILABILITY_QUERY.search(clean) and re.search(
        r"\b(?:disse|falei|afinal|fim das contas|disponibilidade)\b", clean
    )):
        return None
    slots = availability_summary(memory)
    if not slots:
        if re.search(r"\b(?:disse|falei)\b", clean) and re.search(r"\b(?:horarios?|dia e periodo)\b", clean):
            return "Qual dia e horário você tem disponível?"
        return None
    reply = f"Você disse que consegue treinar {slots}."
    meal = memory.latest("meal_routine")
    if meal and _FOOD_CONTEXT.search(clean):
        for key, label in (("heating_device", "Para esquentar a comida"),
                           ("transport", "Para levar a comida")):
            if value := meal.facts.get(key):
                if (key == "heating_device" and "esquentar" in clean) or (key == "transport" and "levar" in clean):
                    reply += f" {label}, você tem {value}."
    return reply


@dataclass(frozen=True)
class Continuation:
    answer: str | None = None
    query: str | None = None
    document: str | None = None
    clarify: bool = False


def sleep_details(clean, active_sleep):
    match = _SLEEP_HOURS.search(clean)
    if not match and active_sleep:
        match = _HOURS_REPLY.fullmatch(clean.strip(" .!"))
    if not match:
        return {}
    first = int(match[1])
    last = int(match[2]) if match[2] else first
    if not 0 < first <= last <= 24:
        return {}
    details = {"hours": f"{first} a {last}" if first != last else str(first)}
    if period := _SLEEP_PERIOD.search(clean):
        details["period"] = period[1].replace("tres", "três")
    elif active_sleep and clean.startswith("na verdade") and "period" in active_sleep.facts:
        details["period"] = active_sleep.facts["period"]
    return details


def sleep_followup(memory, clean):
    active = memory.active
    active_sleep = active if active and active.topic == "sleep_recovery" else None
    mentions_sleep = bool(_SLEEP.search(clean))
    details = sleep_details(clean, active_sleep)
    if mentions_sleep and _SLEEP_INDIVIDUAL.search(clean):
        return Continuation(answer="A quantidade de sono varia entre pessoas. Para adultos de 18 a 60 anos, "
                                   "a referência geral é dormir pelo menos sete horas por noite. "
                                   "Regularidade e qualidade do sono também importam.",
                            document="sleep_duration_adults", query=clean)
    if ((mentions_sleep and _SLEEP_PERFORMANCE.search(clean) and _SLEEP_ASK.search(clean))
            or (active_sleep and _SLEEP_REFERENCE.search(clean)
                and (_SLEEP_PERFORMANCE.search(clean) or re.fullmatch(r"(?:e )?(?:por que|pq)[? ]*", clean)))):
        facts = details or (active_sleep.facts if active_sleep else {})
        explanation = ("Dormir faz parte da recuperação entre treinos. Quando você descansa bem, "
                       "fica mais fácil chegar disposto e atento à próxima sessão.")
        if hours := facts.get("hours"):
            period = f" durante {facts['period']}" if "period" in facts else ""
            scenario = f"No cenário de {hours} horas de sono por noite{period}, você pode render abaixo do habitual."
            if _SLEEP_WHY.search(clean):
                answer = f"{explanation} {scenario}"
            else:
                answer = f"{scenario} Só com as horas de sono, não dá para estimar quanto isso afetaria seu progresso."
        else:
            answer = explanation
        return Continuation(answer=answer, document="sleep_recovery_explanation", query=clean)
    if details and (_SLEEP_ONLY_REPORT.fullmatch(clean.strip(" .!"))
                    or (active_sleep and _HOURS_REPLY.fullmatch(clean.strip(" .!")))):
        return Continuation(answer=f"Entendi, {details['hours']} horas de sono. Quer entender como isso pode pesar no treino?")
    return None


def observe_report(memory, text):
    """Keep reported facts in their topic, including sleep scenarios discussed in questions."""
    clean = fold(text)
    if explicit_switch(text):
        return memory
    if sleep_followup(memory, clean):
        active = memory.active
        active_sleep = active if active and active.topic == "sleep_recovery" else None
        details = sleep_details(clean, active_sleep)
        return memory.remembering(DialogueContext(
            topic="sleep_recovery", anchor=text[:800], facts=details or (active_sleep.facts if active_sleep else {}),
        ))
    if "?" in text:
        return memory
    memory = availability_report(memory, text)
    memory = food_equipment_report(memory, text)
    schedule = memory.latest("schedule")
    meal = memory.latest("meal_routine")
    travel = memory.latest("travel")
    if travel or _TRAVEL.search(clean):
        facts = {}
        if match := _RETURN.search(clean):
            facts["return_day"] = _DAYS[match[1].split("-")[0]] + (
                f" de {_PERIOD[match[2]]}" if match[2] else ""
            )
        if match := re.search(rf"\b(?:vou(?: viajar)?|viajo) (?:n[oa] )?({_DAY})\b", clean):
            facts["departure_day"] = _DAYS[match[1].split("-")[0]]
        if "esteira" in clean and _UNAVAILABLE.search(clean):
            facts["equipment"] = "esteira indisponível"
        elif "esteira" in clean and re.search(r"\b(?:so tem|tem uma|tem esteira|tem acesso)\b", clean):
            facts["equipment"] = "possível acesso a uma esteira"
        if facts or (not travel and _TRAVEL.search(clean)):
            return memory.recording("travel", text, facts)
    review = memory.latest("training_review")
    if match := _TRAINING_VISIT.search(clean):
        day = _DAYS[match[1].split("-")[0]]
        period = f" de {_PERIOD[match[2]]}" if match[2] else ""
        return memory.recording("schedule", text, {"next_visit": day + period})
    if (match := _SCHEDULE.search(clean)) and not re.search(r"\b(?:nao|nunca) treino\b", clean):
        hour = int(match[1])
        if hour < 24:
            return memory.recording("schedule", text, {"hour": str(hour)})
    if match := re.search(rf"\btreino\b[^.!?]{{0,35}}?(?<!\w){_DAY_SEQUENCE}(?!\w)", clean):
        days = re.findall(_DAY, match[0].split("treino", 1)[1])
        return memory.recording("schedule", text, {"days": " e ".join(_DAYS[d.split("-")[0]] for d in days),
                                                   **({"period": "à noite"} if "noite" in clean else {})})
    if schedule and re.search(r"\b(?:nao|n) treino nos outros dias\b", clean):
        return memory.recording("schedule", text, {"other_days": "sem treino"})
    if (match := _EQUIPMENT.search(text)) and _EQUIPMENT_WORD.search(fold(match[1])):
        item = re.sub(r" agora$", "", match[1].strip(), flags=re.IGNORECASE)
        return memory.recording("equipment", text, {"available": item})
    if match := _LIFT.search(clean):
        return memory.recording("training_log", text, {"reps": match[1], "load": match[2]})
    if match := _DURATION.search(clean):
        return memory.recording("training_log", text, {"seconds": match[1], "timed_activity": match[2].strip()})
    if match := _INTERVALS.search(clean):
        return memory.recording("training_review", text, {
            "intervals": f"{match[1]} {match[2]} de {match[3]} {match[4]}",
            **({"pace": "ritmo caiu"} if "ritmo caiu" in clean else {}),
        })
    if review and re.search(r"\b(?:mais inclinad[oa]|maior inclinacao|subida mais forte)\b", clean):
        return memory.recording("training_review", text, {"terrain": "trecho mais inclinado"})

    if _MEAL.search(clean) or (meal and memory.active == meal) or (_FOOD_EQUIPMENT.search(clean) and _FOOD_CONTEXT.search(clean)):
        facts = {}
        if match := _TIME.search(clean):
            facts["minutes"] = _TIME_WORDS.get(match[1], match[1]) if match[1] else "30"
        if re.search(r"\bfogao pequeno\b", clean):
            facts["stove"] = "fogão pequeno"
        if _NO_FRIDGE.search(clean):
            facts["cold_storage"] = "sem geladeira"
        if re.search(r"\b(?:n(?:ao)? da p(?:ara|ra)?|sem como) esquentar\b", clean):
            facts["heating"] = "sem esquentar"
        if re.search(r"\bgosto de feijao\b", clean):
            facts["food"] = "feijão"
        if match := re.search(rf"\b({_DAY})\s+(?:eu )?folgo\b", clean):
            facts["day_off"] = _DAYS[match[1].split("-")[0]]
        if "turno" in clean:
            facts["work_schedule"] = "turnos de trabalho"
        if facts or (not meal and _MEAL.search(clean)):
            return memory.recording("meal_routine", text, facts)
    return memory


def _meal_ideas(facts):
    if facts.get("cold_storage"):
        return ("Para levar sem geladeira, uma opção é uma fruta inteira com torradas fechadas; outra é "
                "fruta inteira com um pacote de aveia. Se você precisa abrir só na hora, leve as embalagens fechadas. "
                "Escolha produtos que o rótulo permita manter em temperatura ambiente.")
    minutes = facts.get("minutes")
    if not minutes:
        return None
    intro = f"Com os {minutes} minutos que você tem"
    if facts.get("stove"):
        intro += " e o fogão pequeno"
    first = "monte um prato com feijão já preparado e legumes" if facts.get("food") == "feijão" else "faça uma omelete simples com legumes"
    return f"{intro}, dá para ir de duas opções simples. Primeiro, {first}. Outra ideia é cuscuz com ovo feito na hora, em etapas curtas."


def logistics_report(text):
    return bool(_LOGISTICS.search(fold(text)))


def safe_storage_turn(memory, text, followup):
    """Recognize a storage constraint or a request for sealed, shelf-stable options."""
    meal = memory.latest("meal_routine")
    if meal is None:
        return False
    clean = fold(text).strip(" .?!")
    return bool((memory.active == meal and _STORAGE_REPORT.fullmatch(clean))
                or (followup and _CLOSED_SNACK.fullmatch(clean)))


def read_followup(memory, text):
    """Use only recorded user facts or a reviewed knowledge lookup."""
    if explicit_switch(text):
        return None
    clean = fold(text)
    if sleep := sleep_followup(memory, clean):
        return sleep
    question = "?" in text or bool(re.match(r"^(?:qual|quais|que dia|me lembra|oq|o que|como|resume)\b", clean))
    if question and (answer := remembers_availability(memory, clean)):
        return Continuation(answer=answer)
    travel = memory.latest("travel")
    if travel:
        facts = travel.facts
        if question and _RECALL.search(clean) and "dia" in clean and "volto" in clean and facts.get("return_day"):
            return Continuation(answer=f"Você disse que volta {facts['return_day']}.")
        if question and _RECALL.search(clean) and "dia" in clean and re.search(r"\b(?:vou|viajo)\b", clean) and facts.get("departure_day"):
            return Continuation(answer=f"Você disse que viaja na {facts['departure_day']}.")
        asks_for_travel_idea = bool(re.search(r"\b(?:o que tem la|na viagem|no hotel|muda a ideia|ajusta a ideia)\b", clean))
        if asks_for_travel_idea and (question or "ideia" in clean) and facts.get("equipment"):
            if facts["equipment"] == "esteira indisponível":
                return Continuation(answer="Com a esteira indisponível, uma caminhada em local seguro ou movimentos "
                                    "leves que você já faz são opções simples. Sua ficha continua como está.")
            return Continuation(answer="Se a esteira estiver disponível, caminhar em ritmo confortável é uma "
                                "opção simples. Você também pode caminhar fora, se tiver um lugar seguro.")
    if question and _SET_DEFINITION.search(clean):
        return Continuation(query="O que é uma série de treino e uma repetição em linguagem simples?",
                            document="sets_repetitions_plain")
    active = memory.active
    if (question and _SET_REST.search(clean) and active and active.topic == "knowledge"
            and active.facts.get("document") in {"sets_repetitions_plain", "sets_reps_load_basics", "rest_between_sets_context"}):
        return Continuation(query="Por que fazer uma pausa de descanso entre séries de musculação?",
                            document="rest_between_sets_context")

    schedule = memory.latest("schedule")
    if schedule and schedule.facts:
        facts = schedule.facts
        if (question and facts.get("next_visit") and _RECALL.search(clean) and "dia" in clean
                and re.search(r"\b(?:ia|vou|vamos|vai)\b", clean)):
            return Continuation(answer=f"Você disse que vai à academia {facts['next_visit']}.")
        if question and facts.get("days") and _RECALL.search(clean) and "dia" in clean and "trein" in clean:
            period = " " + facts["period"] if facts.get("period") else ""
            return Continuation(answer=f"Você disse que treina{period} nestes dias: {facts['days']}.")
        if question and "outros dias" in clean and _MEAL.search(clean):
            return Continuation(answer="E nos outros dias, você treina em algum horário ou são dias sem treino?", clarify=True)
        if "nao treino nos outros dias" in clean and facts.get("other_days"):
            return Continuation(answer="Entendi. Nos dias sem treino, pode organizar o jantar pelo seu horário normal, "
                                "pela fome e pelo conforto. Nos dias de treino à noite, vale considerar o tempo até dormir.")
        if (question and _MEAL.search(clean) and _NIGHT_MEAL.search(clean)
                and (facts.get("period") == "à noite" or facts.get("hour") in {str(hour) for hour in range(18, 24)})):
            return Continuation(query="Como organizar a refeição depois de treinar à noite perto de dormir?",
                                document="late_training_meals_sleep")

    meal = memory.latest("meal_routine")
    if meal:
        if question and _PREPARING.search(clean) and (memory.active == meal or _RESUME.search(clean) or _MEAL.search(clean)):
            return Continuation(query="Preparar com antecedência uma parte das refeições e guardar com segurança",
                                document="grocery_and_meal_prep_support_adherence")
        resumes_meal = _RESUME.search(clean) and (
            _MEAL.search(clean) or re.search(r"\b(?:tempo que eu falei|pra comer|para comer)\b", clean)
        )
        if (question and meal.facts.get("day_off") and "dia" in clean and _RECALL.search(clean)
                and re.search(r"\b(?:folgo|folga|lanche|levar|comida)\b", clean)):
            return Continuation(answer=f"Você disse que folga na {meal.facts['day_off']}.")
        food_to_go = meal.facts.get("cold_storage") and re.search(
            r"\b(?:levar|fechad[oa]|abrir na hora|pra comer|para comer)\b", clean)
        if ((_IDEAS.search(clean) or food_to_go or (resumes_meal and "simplific" in clean)) and (question or resumes_meal)
                and (memory.active == meal or resumes_meal or food_to_go)):
            facts = dict(meal.facts)
            if match := _TIME.search(clean):
                facts["minutes"] = _TIME_WORDS.get(match[1], match[1]) if match[1] else "30"
            if answer := _meal_ideas(facts):
                if food_to_go and (match := _TIME.search(clean)):
                    minutes = _TIME_WORDS.get(match[1], match[1]) if match[1] else "30"
                    answer = f"Com {minutes} minutos, deixe o lanche separado antes de sair. {answer}"
                return Continuation(answer=answer)

    equipment = memory.latest("equipment")
    if equipment and equipment.facts.get("available") and question and _RECALL.search(clean) and "equipamento" in clean:
        return Continuation(answer=f"Você disse que tem {equipment.facts['available']} disponível.")

    log = memory.latest("training_log")
    if log and question and re.search(r"\b(?:fiz|reps|repeticoes|carga|peso|tempo)\b", clean):
        if log.facts.get("reps") and log.facts.get("load") and re.search(r"\b(?:isso que fiz|foi \d+|quantas repeti)\b", clean):
            return Continuation(answer=f"Foram {log.facts['reps']} repetições com {log.facts['load']} kg.")
        if log.facts.get("seconds") and log.facts.get("timed_activity") and "medido" in clean and "tempo" in clean:
            return Continuation(answer=f"A atividade medida por tempo foi {log.facts['timed_activity']}, por {log.facts['seconds']} segundos.")

    review = memory.latest("training_review")
    if review and review.facts.get("intervals") and question and re.search(r"\b(?:nesses dados|nessas subidas|nesses tiros|ritmo caiu)\b", clean):
        return Continuation(answer=f"Nas {review.facts['intervals']}, eu compararia o esforço percebido, "
                            "o descanso e a inclinação de cada trecho. A queda de ritmo, isoladamente, não mostra a causa.")
    if review and review.facts.get("terrain") and re.search(r"\b(?:mais inclinad[oa]|maior inclinacao|subida mais forte)\b", clean):
        return Continuation(answer="Isso muda a comparação. Num trecho mais inclinado, o ritmo pode cair mesmo com esforço semelhante. "
                            "Compare os intervalos em trechos parecidos e use também o esforço percebido.")
    if (review and review.facts.get("focus") == "bíceps" and "rosca" in clean
            and re.search(r"\b(?:enjoei|variar|outra)\b", clean)):
        return Continuation(answer="Podemos variar a rosca mantendo o trabalho de bíceps. "
                            "Uma opção é mudar a pegada ou o equipamento. Se quiser, posso ajudar a comparar as opções.")
    return None

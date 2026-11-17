"""Conservative dialogue-act checks at the boundary of Planner proposals."""
import re
from dataclasses import dataclass

from .retrieval import fold


_LEAD_IN = re.compile(
    r"^(?:(?:oi|ola|opa|e ai|bom dia|boa tarde|boa noite|ta|ok|beleza|entao|agora|por favor)"
    r"[\s,!.]+)+"
)
_CHANGE = (
    r"(?:troc(?:a|ar)|troque|substitu(?:a|i|ir)|mud(?:a|ar|e)|mov(?:a|e|er)|"
    r"alter(?:a|ar|e)|ajust(?:a|ar|e)|remov(?:a|e|er)|retir(?:a|ar|e)|tir(?:a|ar|e)|"
    r"coloc(?:a|ar|que)|marc(?:a|ar|que)|defin(?:a|e|ir)|"
    r"registr(?:a|ar|e)|salv(?:a|ar|e)|cri(?:a|ar|e)|mont(?:a|ar|e)|"
    r"aument(?:a|ar|e)|reduz(?:a|ir)|descansar)"
)
_CHANGE_WORD = re.compile(rf"\b{_CHANGE}\b")
_REQUEST = re.compile(
    rf"^(?:(?:hoje|amanha|essa semana|nesta semana)[ ,]+)?"
    rf"(?:(?:eu )?(?:quero|preciso|gostaria de|pode)[ ]+|voce (?:pode|consegue)[ ]+)?{_CHANGE}\b"
)
_NEGATED = re.compile(rf"\b(?:nao|n|num|nunca|sem)\s+(?:[\w]+\s+){{0,5}}{_CHANGE}\b")
_HYPOTHETICAL = re.compile(
    r"\b(?:talvez|hipoteticamente|se eu|e se|se der|se tiver|caso|estou pensando|to pensando|"
    r"ainda (?:estou|to) decidindo|so (?:estou |to )?avaliando)\b"
)
_INQUIRY = re.compile(
    r"\b(?:posso|devo|vale a pena|faz sentido|sera que|d[aá] (?:para|pra)|"
    r"o que|oq|qual|como|por que|queria saber|gostaria de saber|me explica)\b"
)
_CHANGE_OBJECT_REFERENCE = re.compile(
    rf"\b({_CHANGE}) (?:o|a) que (?:(?:a gente )?(?:falou|combinou|conversou)|"
    r"falamos|combinamos|conversamos|foi (?:falad[oa]|combinad[oa]))\b"
)
_MULTIPLE = re.compile(
    rf"(?:\b(?:e|mas|ou|tambem|depois)\s+|[,;.!]\s*)"
    rf"(?:(?:por favor|agora|depois|tambem|me|pode|quero|nao|n)[\s,]+)*{_CHANGE}\b"
)
_SEPARATE_ASK = re.compile(
    r"\b(?:e|tambem|depois)\s+(?:(?:me )?(?:diz|diga|fala|explica|explique)|qual|como|quanto|pq|por que)\b"
)
_SWAP_PREFIX = re.compile(
    r"(?:(?:quero|pode) (?:trocar|substituir)|troca|troque|substitui|substitua)(?: [oa]| um| uma)?"
)
_SWAP_LINK = r"(?:por|para|pelo|pela)(?: [oa]| um| uma)?"
_MEAL_NAME = r"(?:cafe da manha|almoco|jantar|lanche(?: da (?:manha|tarde)| [12])?|ceia)"
_MEAL_QUALIFIER = re.compile(rf"\b(?:do|da|de|no|na) ({_MEAL_NAME})\b")
_MEAL_LINK = rf"(?:(?:do|da|de|no|na) {_MEAL_NAME} )?{_SWAP_LINK}"
_SWAP_SUFFIXES = {"", "na minha dieta", "no meu plano", "no meu treino", "na minha ficha", "por favor"}
_IMPACT = re.compile(r"\bnao vai mudar (?:tanta coisa|muita coisa|muito)\b")
_CHANGE_EFFECT = re.compile(
    r"\b(?:o que|oq|quanto|como) (?:e que )?(?:muda|mudaria|ficaria|funcionaria|aconteceria) "
    r"(?:se|no caso de)\b"
)
_PLAN_MENTION = re.compile(r"\b(?:treino|sessao|ficha|cardapio|dieta|refeicao)\b")
_MEAL_SLOT = rf"(?:{_MEAL_NAME}|refeicao [1-9]|(?:primeira|segunda|terceira|quarta|quinta|sexta) refeicao)"
_ITEM = r"[a-z][a-z ]{0,99}?"
_SWAP_PAIR = (
    rf"(?:(?:o|a) )?(?:(?:meu|minha) )?(?P<old>{_ITEM})(?: (?:do|da|de|no|na) (?P<before>{_MEAL_SLOT}))?"
    rf" {_SWAP_LINK} (?P<new>{_ITEM})(?: (?:do|da|de|no|na) (?P<after>{_MEAL_SLOT}))?"
)
_DIRECT_SWAP = re.compile(rf"^{_SWAP_PREFIX.pattern} {_SWAP_PAIR}$")
_ASK_SWAP = re.compile(rf"\b(?:posso|poderia|da para|da pra) (?:trocar|substituir) {_SWAP_PAIR}$")
_ASK_INSTEAD = re.compile(
    rf"\b(?:posso|poderia|da para|da pra) (?:por|colocar|usar|comer) (?:o |a |um |uma )?"
    rf"(?P<new>{_ITEM}) no lugar d[oea] (?P<old>{_ITEM})"
    rf"(?: (?:no|na) (?P<after>{_MEAL_SLOT}))?$"
)
_ASK_MISSING_FOOD = re.compile(
    rf"\bnao (?:vou conseguir comer|tenho) (?:o |a )?(?P<old>{_ITEM})[ ,]+"
    rf"(?:posso|poderia) trocar {_SWAP_LINK} (?P<new>{_ITEM})$"
)
_REMOVE_AND_ADD = re.compile(
    rf"^(?:(?:eu )?quero que voce (?:mude|troque|altere)[ ,]+)?"
    rf"(?:pegue (?:o |a )?(?P<taken>{_ITEM})[ ,]+tire|(?:tire|retire) (?:o |a )?(?P<old>{_ITEM}))"
    rf" e (?:coloque|ponha) (?:o |a )?(?P<new>{_ITEM})(?: (?:no|na) (?P<after>{_MEAL_SLOT}))?$"
)
_LEAVE_AND_ENTER = re.compile(
    rf"^(?:o |a )?(?P<old>{_ITEM}) deve sair (?:do|da) (?P<before>{_MEAL_SLOT})"
    rf" e (?:deve )?entrar (?:o |a )?(?P<new>{_ITEM})$"
)


@dataclass(frozen=True)
class SwapRequest:
    old: str
    new: str
    meals: frozenset[str]
    inquiry: bool


def read_swap(text):
    """Read a single swap with explicit item roles, independently of NLP confidence."""
    message = _LEAD_IN.sub("", " ".join(fold(text).split())).rstrip(" .!?")
    scope = change_scope(text)
    if scope in {"negated", "hypothetical"} or (scope == "compound" and "?" in text):
        return None
    inquiry = scope == "inquiry" or "?" in text
    if inquiry:
        question = re.sub(r"[?.!,]+ (?:e )?(?:so (?:uma )?pergunta|pergunta so|so (?:pra|para) saber)$", "", message)
        match = _ASK_SWAP.search(question) or _ASK_MISSING_FOOD.search(question) or _ASK_INSTEAD.search(question)
    else:
        message = re.sub(r" (?:pra mim|por favor|pfv)$", "", message)
        patterns = (_REMOVE_AND_ADD, _LEAVE_AND_ENTER) if scope == "compound" else (
            _DIRECT_SWAP, _REMOVE_AND_ADD, _LEAVE_AND_ENTER)
        match = next((match for pattern in patterns
                      if (match := pattern.fullmatch(message))), None)
    if not match:
        return None
    slots = match.groupdict()
    leading_meal = meal_qualifiers(message[:match.start()])
    return SwapRequest(slots.get("old") or slots["taken"], slots["new"],
                       frozenset(value for value in (slots.get("before"), slots.get("after")) if value) | leading_meal,
                       inquiry)


def asks_to_resume_swap(text):
    message = _LEAD_IN.sub("", " ".join(fold(text).split())).rstrip(" .!")
    return bool(re.fullmatch(r"(?:faca|faz|pode fazer) (?:a|essa) troca", message))


def discusses_swap_impact(text):
    return bool(_IMPACT.search(fold(text)) and re.search(r"\bpor\b", fold(text))
                and change_scope(text) == "inquiry")


def change_scope(text):
    """Classify explicit reasons a change phrase must stay read-only."""
    message = _LEAD_IN.sub("", " ".join(fold(text).split()))
    impact = bool(_IMPACT.search(message) and "?" in message)
    if impact:
        message = _IMPACT.sub("tem pouco impacto", message)
    if _CHANGE_EFFECT.search(message) and _PLAN_MENTION.search(message):
        return "inquiry"
    if not impact and not _CHANGE_WORD.search(message):
        return None
    if _NEGATED.search(message):
        return "negated"
    if _HYPOTHETICAL.search(message):
        return "hypothetical"
    if _CHANGE_EFFECT.search(message):
        return "inquiry"
    if ((len(_CHANGE_WORD.findall(message)) > 1 and _MULTIPLE.search(message))
            or _SEPARATE_ASK.search(message)):
        return "compound"
    question = _CHANGE_OBJECT_REFERENCE.sub(r"\1 o item mencionado", message)
    if "?" in message or _INQUIRY.search(question):
        return "inquiry"
    return None


def explicit_change(text):
    return bool(_REQUEST.match(_LEAD_IN.sub("", " ".join(fold(text).split()))))


def meal_qualifiers(text):
    return set(_MEAL_QUALIFIER.findall(" ".join(fold(text).split())))


def exact_swap(text, old, new, *, meal):
    prefix = _LEAD_IN.sub("", " ".join(fold(text[:old["start"]]).split())).strip()
    between = " ".join(fold(text[old["end"]:new["start"]]).split())
    suffix = " ".join(fold(text[new["end"]:]).strip(" .,!").split())
    return bool(_SWAP_PREFIX.fullmatch(prefix)
                and re.fullmatch(_MEAL_LINK if meal else _SWAP_LINK, between)
                and suffix in _SWAP_SUFFIXES)


def is_plan_inquiry(text):
    return discusses_swap_impact(text) or bool(re.search(
        r"\b(?:troc\w*|substitu\w*|mov(?:a|e|er)|mud(?:a|ar|e)|alter(?:a|ar|e))\b",
        fold(text),
    ))


def change_inquiry_reply(analysis, snapshot=None, today=None, account_day=None):
    text = analysis["entities"].get("text", "")
    entities = analysis["entities"]["entities"]
    entity_types = {e["entity_type"] for e in entities}
    swap = read_swap(text)
    if swap and snapshot and (entity_types & {"exercise", "replacement_exercise"}
                              or "no treino de hoje" in fold(text)):
        old = swap.old.removeprefix("no treino de hoje ")
        candidates = snapshot.workout_exercises
        if today and "treino de hoje" in fold(text):
            from .plan_read import scheduled_days
            day_ids = {day["id"] for day in scheduled_days(snapshot, today, account_day)}
            candidates = [row for row in candidates if row["workout_day_id"] in day_ids]
        def named(rows, raw):
            names = {raw}
            names.update(fold(e["value"]) for e in entities
                         if e["entity_type"] in {"exercise", "replacement_exercise"}
                         and fold(text[e["start"]:e["end"]]) == raw)
            return [row for row in rows if fold(row["canonical"]) in names]

        original = named(candidates, old)
        if len(original) != 1:
            return f"Não consegui localizar um único exercício chamado {old} nessa ficha. Qual é o nome que aparece no treino?"
        replacement = named(snapshot.exercises, swap.new)
        if len(replacement) != 1:
            return f"Encontrei {original[0]['canonical']} na ficha. Como o exercício que você quer colocar aparece no catálogo?"
        return (f"Encontrei {original[0]['canonical']} na ficha e {replacement[0]['canonical']} no catálogo. "
                "Para validar a troca, o Planner confere o tipo do exercício, o músculo principal e o padrão de movimento. "
                "Sua ficha segue como está.")
    if entity_types & {"exercise", "replacement_exercise"}:
        return ("Pode ser uma opção se o substituto cumprir o mesmo objetivo na sessão. "
                "Compare o movimento e a dificuldade: trocar barra ou halteres por peso corporal "
                "muda como você regula e progride a carga. A ficha continua como está.")
    if entity_types & {"food", "replacement_food"}:
        return ("Uma troca pode funcionar se a porção e o papel do alimento na refeição "
                "forem compatíveis. Os valores nutricionais podem mudar. A dieta continua como está.")
    if entity_types & {"source_date", "target_date"}:
        return ("A troca de dia pode fazer sentido se couber na sua agenda e preservar o intervalo "
                "entre sessões exigentes. A ficha continua como está.")
    return ("Posso ajudar a avaliar a mudança. Qual item ou dia você tem em mente? "
            "Seu plano continua como está.")

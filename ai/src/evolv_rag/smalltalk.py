"""Short conversational replies for messages that do not request advice or an action."""

import re
from random import choice

from evolv_nlp.entities import normalize_text

from .retrieval import fold


_GREETING = r"(?:o+i+|ola|opa|salve|e ai|bom dia|boa tarde|boa noite|fala coach)(?: coach(?: evolv)?)?"
_CHECK_IN = r"(?:tudo bem|tudo certo|como vai|como voce ta|como vc ta|beleza)"
_HELLO = re.compile(rf"{_GREETING}(?: {_CHECK_IN})?")
_HOW_ARE_YOU = re.compile(rf"(?:{_GREETING} )?{_CHECK_IN}(?: por ai| e (?:voce|vc))?")
_CHECK_IN_REPLIES = (
    "Tudo bem por aqui. E com você?",
    "Tudo certo! Pode falar quando quiser.",
    "Opa, tudo bem! Tô por aqui.",
)
_WELCOME_REPLIES = (
    "Oi! Como posso te ajudar hoje?",
    "Opa! O que você tem em mente?",
    "Oi! Pode falar. Por onde você quer começar?",
)
_OPENING_REPLIES = (
    "Claro! Quer me contar como estão indo seus treinos ou sua alimentação?",
    "Bora. Tem alguma coisa no treino ou no plano alimentar que você quer entender melhor?",
    "Pode falar. O que você quer melhorar na sua rotina?",
)
CLARIFY_REPLIES = (
    "Me conta um pouco mais. Você quer conversar sobre o treino ou fazer alguma mudança no seu plano?",
    "Em que parte da sua rotina você quer ajuda agora?",
    "Me conta o que aconteceu ou o que você quer ajustar. Pode começar pelo treino ou pela alimentação.",
)
_OPENERS = (
    (r"(?:posso (?:te perguntar algo|fazer uma pergunta)|tenho uma duvida|quero tirar uma duvida)",
     "Claro! Me conta qual é a sua dúvida."),
    (r"(?:como voce pode me ajudar|o que voce faz|como funciona o coach|com o que voce pode me ajudar)",
     "Posso conversar sobre treino, alimentação e recuperação, tirar dúvidas e ajudar a ajustar seu plano. Por onde quer começar?"),
)
_CASUAL_OPENER = re.compile(
    r"(?:(?:quero|queria|gostaria de) (?:conversar|trocar uma ideia|falar com voce)|"
    r"(?:so )?(?:queria|quero) (?:bater um papo|trocar uma ideia|conversar um pouco)|"
    r"vamos conversar|bora conversar|me ajuda|preciso de ajuda|vim dar um oi)"
)
_CASUAL_CHECK_IN = re.compile(
    r"(?:(?:eu )?(?:estou|to|tava) (?:bem|de boa|tranquil[oa]|otim[oa])(?: hoje)?|"
    r"tudo (?:bem|tranquilo|certo) por aqui|por aqui tudo (?:bem|certo))"
)
_CASUAL_REPLIES = (
    "Boa! Tô aqui com você.",
    "Que bom. Pode falar no seu ritmo.",
    "Fechado. Podemos ir conversando.",
)
_TOPIC_PREFIX = r"(?:(?:quero|queria|gostaria de) (?:falar|conversar) (?:de|sobre) )?"
_TOPICS = (
    (rf"(?:{_TOPIC_PREFIX}(?:treino|musculacao)|(?:quero|queria) (?:comecar a |voltar a )?treinar)",
     "Me conta como está sua rotina de treino e o que você gostaria de melhorar."),
    (rf"(?:{_TOPIC_PREFIX}(?:alimentacao|dieta|comida)|(?:quero|queria) melhorar (?:minha |a )?alimentacao)",
     "Me conta como é sua alimentação hoje e o que você gostaria de ajustar."),
    (rf"(?:{_TOPIC_PREFIX}(?:sono|recuperacao)|(?:quero|queria) dormir melhor)",
     "Como tem sido seu descanso nos últimos dias?"),
)
_THANKS = re.compile(
    r"(?:(?:isso|boa|fechou|era isso|era isso mesmo|era isso msm) )*"
    r"(?:obrigad[oa]|valeu|brigad[oa]|brigadao|muito obrigad[oa])(?: pela ajuda| msm| mesmo)?"
    r"|(?:fechou )?era isso (?:mesmo|msm)"
)
_ACKNOWLEDGMENT = {"entendi", "entendi sim", "ta bom", "beleza entendi", "show", "boa", "ok", "fechou", "legal"}


_INFO_REQUEST = re.compile(
    r"\b(?:(?:quero|queria|qria) (?:entender|saber)|gostaria de (?:entender|saber)|"
    r"me (?:explica|explique|fala|diz|diga)|me (?:da|de|passa) (?:\d+ |uma |duas |tres )?ideias?)\b"
)
_QUESTION_START = re.compile(r"^(?:o que|oq|qual|quais|quanto|quanta|quantos|quantas|como|por que)\b")
_COACH_SUBJECT = re.compile(
    r"\b(?:rir|rpe|1rm|trein\w*|exercici\w*|musculacao|serie\w*|repeti\w*|hipertrofia|cardio|"
    r"corrida|forca|volume|potencia|deload|remada\w*|proteina\w*|carboidrato\w*|fibra\w*|refeic\w*|aliment\w*|"
    r"caloria\w*|dieta|marmita\w*|porcao|fruta\w*|legume\w*|gordura\w*|sal|sodio|"
    r"agua|hidrat\w*|isotonico\w*|gel|creatina|suplement\w*|sono|dormir|recupera\w*)\b"
)
_CHANGE_WORD = re.compile(
    r"\b(?:troc\w*|substitu\w*|mud\w*|alter\w*|remov\w*|retir\w*|tirar|"
    r"registr\w*|confirm\w*|agend\w*|atuali\w*|cancel\w*|salv\w*|"
    r"edita\w*|crie|criar|mova|mover)\b"
)
_EXPLICIT_REQUEST = re.compile(
    r"\b(?:como|qual|quais|quanto|quantos|posso|devo|por que|pq|explica|explique|"
    r"troca|troque|trocar|muda|mude|mudar|altera|altere|alterar|"
    r"registra|registre|registrar|salva|salve|salvar|monta|monte|cria|crie|ajusta|ajuste|coloca|coloque|"
    r"confirma|confirmo|confirme|confirmar|cancela|cancelo|cancelar)\b|"
    r"\b(?:quero|queria|gostaria de) (?:entender|saber)\b|"
    r"\b(?:vale a pena|faz sentido|sera que|da pra|da para|me passa|me ajuda a|"
    r"me recomenda|recomende|me sugere|sugira|me da|me diga|me diga se)\b"
)
_REPORTS = (
    (r"(?:(?:hoje|ontem|agora) )?(?:treinei|fiz (?:meu |o |um )?treino|voltei a treinar)\b",
     "Entendi. Como você se sentiu durante o treino?"),
    (r"(?:(?:hoje|ontem) )?(?:comi|almocei|jantei|tomei cafe da manha)\b",
     "Entendi. O que você gostaria de observar nessa refeição?"),
    (r"(?:(?:hoje|ontem) )?(?:dormi|tenho dormido|ando dormindo)\b",
     "Entendi. Como você se sentiu ao acordar?"),
    (r"(?:meu objetivo (?:e|agora e)|(?:quero|queria) (?:ganhar|perder|melhorar))\b",
     "Entendi seu objetivo. Como está sua rotina hoje?"),
    (r"(?:eu )?prefiro\b",
     "Entendi sua preferência. Como ela se encaixa na sua rotina hoje?"),
)


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", normalize_text(text)).split())


def explicit_information_request(text: str) -> bool:
    return bool(_INFO_REQUEST.search(_words(text)))


def wants_information(text: str) -> bool:
    return "?" in text or explicit_information_request(text)


def clear_knowledge_question(text: str) -> bool:
    words = _words(text)
    return bool((_QUESTION_START.match(words) or _INFO_REQUEST.search(words))
                and _COACH_SUBJECT.search(words) and not _CHANGE_WORD.search(words))


def is_statement(text: str) -> bool:
    return "?" not in text and not _EXPLICIT_REQUEST.search(_words(text))


_SET_REPORT = re.compile(r"^(?:(?:hoje|ontem) )?fiz (\d+) (?:reps|repeticoes) com (\d+(?:[.,]\d+)?)\s*kg\b")
_CONTEXT_REPORTS = (
    (r"^(?:(?:essa semana|hoje|ultimamente) )?(?:to|estou|ando) (?:saindo tarde|chegando tarde)|"
     r"^(?:meus dias tao|minha rotina (?:ta|esta))",
     "Entendi, seus horários estão pesando na rotina. Pode continuar."),
    (r"^(?:(?:hoje|hj) )?(?:cheguei|acordei|to|estou) (?:meio |bem |muito )?(?:cansad[oa]|enrolad[oa])",
     "Entendi, parece que o dia foi puxado. Pode falar no seu ritmo."),
    (r"^(?:ai |as vezes )?(?:acabo pedindo|acabo comendo|janto|peco) .{1,120}\b(?:jantar|comida|refeicao)\b",
     "Entendi, a decisão da refeição acaba ficando para a última hora."),
    (r"^(?:tenho (?:uns |so |apenas )?.{1,75}\b(?:minutos?|hora|horas|fogao|geladeira)\b|"
     r"(?:na real|na verdade) (?:da|sao|fica|tenho)|acho q(?:ue)? expliquei mal)",
     "Entendi esse detalhe. Pode continuar."),
    (r"^(?:eu )?gosto\b",
     "Entendi do que você gosta e do que prefere evitar no preparo."),
    (r"^(?:(?:eu )?(?:nao curto|nao gosto|nao como)\b|.+\bnao desce de jeito nenhum$)",
     "Entendi que esse alimento não funciona para você desse jeito."),
    (r"^(?:quero|queria) .{0,65}\b(?:comida feita em casa|cozinhar mais)\b",
     "Dá para começar por uma refeição da semana: escolha algo simples que você já sabe preparar "
     "e deixe os ingredientes separados com antecedência."),
    (r"^(?:nessa|nesta|essa|esta) semana (?:vou|so vou)|^treino (?:depois|antes|a noite|de manha)|"
     r"^so que depois (?:durmo|vou dormir)",
     "Entendi como ficou sua rotina. Pode continuar."),
    (r"^(?:to|estou) pensando em (?:fazer|experimentar)|^.+(?:mas |e )dps vejo isso$",
     "Tudo bem, a gente pode falar disso quando você quiser."),
    (r"^(?:no (?:meu )?treino de hoje tem|ontem fiz um treino|foram \d+\s+\w+)|"
     r"^to usando o chat como diario",
     "Entendi o que você está me contando sobre o treino. Pode continuar."),
    (r"^(?:so to contando|so estou contando|eu queria olhar o que fiz)",
     "Entendi, você está falando do que já fez. Sua ficha continua como está."),
    (r"^(?:a proposito|por sinal|alias) (?:to|estou) com saudade",
     "Boa, dá vontade de retomar mesmo."),
    (r"^(?:(?:bom|hoje|ontem|hj|depois) )?(?:perdi|passei (?:na|no)|sai d[oea]|cheguei|fui d[oea]|peguei)\b",
     "Entendi. E como ficou o resto do seu dia?"),
    (r"^(?:ainda bem|pior que|pior q|tava tocando|isso melhorou|nem choveu)\b",
     "Ah, entendi. Pode continuar."),
    (r"^(?:ele|ela|meu amigo|minha amiga) (?:me chamou|vai comigo|vem junto)\b",
     "Boa. Como foi isso?"),
    (r"^(?:to com uma semana|eu tinha dito|faco um turno|entre um e outro|as vezes eu termino|"
     r"so pra situar|minha mochila|nao tenho interesse em levar|so quero continuar)\b",
     "Entendi o que mudou na sua rotina. Pode continuar."),
    (r"^(?:quero|queria) .{0,60}\bcomer perto do treino\b",
     "Dá para pensar num lanche que caiba na sua rotina. Quanto tempo você costuma ter para comer?"),
)


def report_followup(text: str) -> str | None:
    message = _words(text)
    if re.fullmatch(
        r"so (?:to|estou) contando como (?:foi|aconteceu)(?: (?:n|nao) mexe na ficha)?", message
    ):
        return "Entendi, você só está me contando como foi. Sua ficha continua como está."
    if not is_statement(text):
        return None
    message = re.sub(rf"^{_GREETING} ", "", message, count=1)
    if re.fullmatch(r"(?:(?:to|estou) brincando|so brincadeira)(?: n(?:ao)? vou fazer isso)?", message):
        return "Entendi, foi só brincadeira."
    if re.fullmatch(r"(?:e )?so uma ideia(?: pra hoje)? n(?:ao)? (?:guarda|guarde|salva|salve) como preferencia", message):
        return "Claro. Essa ideia fica só nesta conversa."
    for pattern, reply in (*_REPORTS, *_CONTEXT_REPORTS):
        if re.match(pattern, message):
            return reply
    match = _SET_REPORT.match(fold(text).strip())
    if match:
        repetitions, load = match.groups()
        return f"Entendi, foram {repetitions} repetições com {load} kg. Sua ficha continua como está."
    return None


def varied_reply(options, recent_replies):
    return choice([reply for reply in options if reply not in recent_replies] or options)


def conversational_reply(text: str, recent_replies=()) -> tuple[str, str] | None:
    normalized = _words(text)
    if _HOW_ARE_YOU.fullmatch(normalized):
        return "greeting", varied_reply(_CHECK_IN_REPLIES, recent_replies)
    if _HELLO.fullmatch(normalized):
        return "greeting", varied_reply(_WELCOME_REPLIES, recent_replies)

    # Strip a greeting only while looking for a complete conversational phrase.
    message = re.sub(rf"^{_GREETING} (?:{_CHECK_IN} )?", "", normalized, count=1)
    if _THANKS.fullmatch(message):
        return "acknowledgment", "De nada! Se quiser continuar, é só mandar."
    if message in _ACKNOWLEDGMENT:
        return "acknowledgment", varied_reply(("Beleza.", "Fechado!", "Show, seguimos quando você quiser."), recent_replies)
    if _CASUAL_CHECK_IN.fullmatch(message):
        return "conversation_check_in", varied_reply(_CASUAL_REPLIES, recent_replies)
    if re.fullmatch(r"(?:eu )?n(?:ao)? sei (?:nem )?por onde comecar(?: k+)?", message):
        return "conversation_opening", "Sem pressa. Pode começar pelo que aconteceu hoje."
    if _CASUAL_OPENER.fullmatch(message):
        return "conversation_opening", varied_reply(_OPENING_REPLIES, recent_replies)
    for pattern, reply in _OPENERS:
        if re.fullmatch(pattern, message):
            return "conversation_opening", reply
    for pattern, reply in _TOPICS:
        if re.fullmatch(pattern, message):
            return "conversation_topic", reply
    return None

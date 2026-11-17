"""Query vocabulary for drinking water during physical activity."""
import re

from .retrieval import HybridSearch, fold


_ACTIVITY = re.compile(r"\b(?:trein\w*|exercici\w*|academia|corr(?:ida|er|endo)|musculacao|pedal\w*)\b")
_WATER = r"(?:agua|liquidos?)"
_INTAKE = re.compile(
    rf"\b(?:beber|bebo|bebe|beberia|tomar|tomo|toma) (?:mais |menos |muita |pouca )?{_WATER}\b|"
    rf"\b(?:quant[oa]s?|quantidade|qtd|volume|litros?|ml)\b.{{0,38}}\b{_WATER}\b|"
    rf"\b{_WATER}\b.{{0,28}}\b(?:quanto|quantidade|qtd)\b"
)
_COOKING = re.compile(r"\b(?:cozinh\w*|receita|diluir|dissolver)\b")
_DAILY = re.compile(r"\b(?:por dia|ao dia|no dia|todo dia|diari\w*|dia a dia)\b")
_QUANTITY = re.compile(r"\b(?:quant[oa]s?|quantidade|qtd|volume|litros?|ml)\b")
_DRINK = re.compile(r"\b(?:beber|bebo|tomar|tomo)\b")
_AMOUNT_ONLY = re.compile(r"\b(?:quant[oa]s?|quantidade|qtd|volume) (?:de )?(?:litros? de )?agua "
                          r"(?:por dia|ao dia)[?!. ]*$")
_MEASURE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:kg|quilos?|metros?)\b")
_MEASURE_FOLLOWUP = re.compile(
    r"(?:e se (?:eu )?)?(?:tenho|peso|com) \d+(?:[.,]\d+)?\s*(?:kg|quilos?)[?!. ]*"
)
_DAY_FOLLOWUP = re.compile(
    r"^(?:(?:em|no|num|nos|nuns) )?dias? (normal|normais|comum|comuns|de treino)\b"
)
_AGE = re.compile(r"\b\d{1,3} anos\b")
_FREQUENCY = re.compile(r"\b\d+\s*(?:x|vezes) (?:por|na) semana\b")
_ROUTINE_FOLLOWUP = re.compile(
    r"(?:(?:treino|dura|duracao de) )?(?:uns |umas |cerca de )?\d+(?:[.,]\d+)?\s*"
    r"(?:h|horas?|min|minutos?)(?: (?:e )?(?:eu )?suo (?:pouco|muito|bastante))?[?!. ]*"
)
_QUANTITY_FOLLOWUP = re.compile(
    r"(?:e |entao )?(?:quantos litros(?: de agua)?|quanto (?:eu )?(?:bebo|devo beber|preciso beber))"
    r"(?: (?:por dia|ao dia|entao|nesse caso))*[?!. ]*"
)
_OTHER_SUBJECT = re.compile(
    r"\b(?:sal|suplement\w*|creatina|whey|isotonic\w*|alcool|remedio\w*|"
    r"hiponatremia|restricao|injec\w*|destilad\w*|"
    r"mud[ae]|mudar|troc[ae]|trocar|alter[ae]|alterar|registr[ae]|registrar|"
    r"ajust[ae]|ajustar|salv[ae]|salvar|cancel[ae]|cancelar)\b"
)
_WORKOUT_PERIOD = re.compile(r"\b(?:antes|durante|depois|pos|pre) (?:d[oa] )?(?:trein\w*|corrida|exercicio)\b")

_DAILY_TEXT = (
    "A quantidade de água que você precisa ao longo do dia varia com a idade, o peso, "
    "a atividade física e a temperatura do ambiente."
)


def is_daily_hydration_request(text):
    text = fold(text)
    return bool(_DAILY.search(text) and _QUANTITY.search(text)
                and (_AMOUNT_ONLY.search(text) or _DRINK.search(text))
                and not _COOKING.search(text) and not _OTHER_SUBJECT.search(text)
                and not _WORKOUT_PERIOD.search(text))


def hydration_detail(text):
    current = fold(text).strip()
    if _OTHER_SUBJECT.search(current) or _COOKING.search(current):
        return False
    if _MEASURE_FOLLOWUP.fullmatch(current) or _ROUTINE_FOLLOWUP.fullmatch(current):
        return True
    if "?" in current:
        return False
    return bool(_DAY_FOLLOWUP.match(current)
                or (_AGE.search(current) and _MEASURE.search(current))
                or (_ACTIVITY.search(current) and _FREQUENCY.search(current)))


def hydration_training_followup(text):
    current = fold(text).strip()
    return bool(re.match(r"^(?:e |e se |nesse caso|num dia|em dia)", current)
                and _ACTIVITY.search(current)
                and re.search(r"\b(?:calor|quente|suor|su[oae]|a tarde|durante)\b", current)
                and not _OTHER_SUBJECT.search(current) and not _COOKING.search(current))


def hydration_quantity_followup(text):
    return bool(_QUANTITY_FOLLOWUP.fullmatch(fold(text).strip()))


def daily_hydration_guidance(text, details=(), *, resuming=False):
    """Offer a reviewed general answer and ask only for relevant context."""
    current = fold(text).strip()
    normalized_details = [fold(detail).strip() for detail in (*details, current)]
    day_reply = next((match[1] for detail in reversed(normalized_details)
                      if (match := _DAY_FOLLOWUP.match(detail))), None)
    routine_reply = any(_ROUTINE_FOLLOWUP.fullmatch(detail) for detail in normalized_details)
    measurements = any(_MEASURE.search(detail) for detail in normalized_details)
    evidence = {
        "id": "kb:daily_hydration:v1.0.0:001",
        "title": "Hidratação ao longo do dia",
        "citations": [{
            "title": "Guia Alimentar para a População Brasileira — Ministério da Saúde, p. 85",
            "url": "https://www.gov.br/saude/pt-br/assuntos/saude-brasil/eu-quero-ter-peso-saudavel/documentos/pdf/guia_alimentar_populacao_brasileira_2ed.pdf",
        }],
        "generation_context": {"text": _DAILY_TEXT},
    }
    reply = _DAILY_TEXT
    if day_reply in {"normal", "normais", "comum", "comuns"}:
        reply = ("Voltando à água nos dias comuns. " if resuming else "Entendi, você está pensando nos dias comuns. ")
        reply += ("Nesses dias, considere quanto você se movimenta e o calor do ambiente. "
                  "Idade, peso e altura, por si só, não definem uma meta de litros.")
        followup = "Dá para começar observando como você distribui a água ao longo do dia."
    elif routine_reply:
        reply = "Entendi. Em dias de treino, a atividade física e o calor do ambiente entram na conta."
        followup = "Quer focar em como se hidratar antes, durante ou depois do treino?"
    elif measurements:
        reply = ("Com as medidas que você passou, ainda faltam detalhes da sua rotina para falar do seu caso. "
                 "A atividade física e o calor também influenciam quanta água você precisa.")
        followup = "Quanto tempo costuma durar seu treino e você costuma suar muito?"
    elif day_reply == "de treino" or _ACTIVITY.search(current):
        followup = "Quanto tempo costuma durar seu treino e você costuma suar muito?"
    else:
        followup = "Você está pensando num dia comum ou num dia de treino?"
    return f"{reply} [{evidence['id']}] {followup}", evidence


class HydrationSearch(HybridSearch):
    def lexical(self, text):
        normalized = fold(text)
        if _ACTIVITY.search(normalized) and _INTAKE.search(normalized) and not _COOKING.search(normalized):
            text += "\nhidratação líquido suor"
        return super().lexical(text)

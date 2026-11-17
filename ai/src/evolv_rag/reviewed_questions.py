"""Recognize common educational questions with an explicitly reviewed answer."""
import re

from .retrieval import fold


_INDEPENDENT_QUESTION = re.compile(
    r"\b(?:o que|oq|qual|quais|quanto|quantos|quando|como|por que|pra que|para que|"
    r"queria saber|sabe se|vale|serve|significa|quer dizer|obrigatori[oa]|precisa)\b"
)
_COMPOUND = re.compile(r"\b(?:e|tambem) (?:qual|quanto|quais|como|por que|me diz|me fala)\b")
_UNSUPPORTED_DETAIL = re.compile(
    r"\b(?:hormonio\w*|mecanismo\w*|mol[eé]cul\w*|exat\w*|garant\w*|"
    r"remedio\w*|medic\w*|diagnostic\w*|suplement\w*|lesao|fratura|"
    r"dor no peito|falta de ar|alerg\w*|(?:meu|minha) (?:ficha|plano|dieta))\b"
)
_UNRELATED = re.compile(r"\b(?:preco|quanto custa|mensalidade|marca|vendedor|receita|modo de preparo|"
                        r"quantas calorias|como calcular|sql|ignore|finja|prometa)\b")
_DELOAD_CALENDAR = re.compile(r"\b(?:frequencia|intervalo|calendario|obrigatori[oa]|a cada|de quanto em quanto)\b")
_DELOAD_DEFINITION = re.compile(
    r"\b(?:oq e|o que (?:e|significa)) (?:um |o )?deload\b|"
    r"\bdeload\b.{0,45}\b(?:significa|quer dizer|(?:precis[ao] )?parar de treinar)\b"
)

# These cues pick passages by the question they answer, including their scope.
_TOPICS = (
    ("rest_between_sets_context", r"\b(?:pausa|descanso|intervalo)s? entre (?:as )?series\b"),
    ("concurrent_training_tradeoffs",
     r"\b(?:cardio|aerobio|aerobico)\b.{0,50}\b(?:junto|separad[oa]|combinar|mesm[oa])\b.{0,50}\b(?:musculacao|forca)\b"),
    ("progressive_overload_gradual", r"\b(?:o que|oq|significa|conceito)\b.{0,40}\bsobrecarga progressiva\b"),
    ("early_training_food_options",
     r"\b(?:comer|alimentacao|refeicao|lanche)\b.{0,65}\bantes de trein\w*(?: bem)? (?:cedo|de manha)\b"),
    ("late_training_meals_sleep",
     r"(?=.*\b(?:trein\w*) a noite\b)(?=.*\b(?:comer|refeicao|jantar|alimentacao)\b)(?=.*\b(?:dormir|deitar|sono)\b)"),
    ("fiber_food_sources", r"(?=.*\bfontes? de fibras?\b)(?=.*\b(?:feija\w*|aveia|frutas?|legumes?|verduras?)\b)"),
    ("protein_amino_acids_mechanism", r"\b(?:pra que|para que) serve\b.{0,35}\bproteina\b"),
    ("sleep_recovery_explanation",
     r"(?=.*\b(?:sono|dormir)\b)(?=.*\b(?:recupera\w*)\b)(?=.*\b(?:treino|exercicio|musculacao)\b)"),
    ("soreness_is_not_progress_requirement",
     r"\b(?:sem|nao senti|nao sentir)\b.{0,25}\bdor muscular\b.{0,75}\b(?:evolu\w*|progres\w*|funcion\w*|adiant\w*)\b"),
    ("hydration_is_individual",
     r"\b(?:todo mundo|todas as pessoas)\b.{0,45}\b(?:mesma|igual)\b.{0,30}\b(?:agua|liquido)\b"
     r".{0,35}\b(?:trein\w*|exercicio|musculacao)\b"),
)


def reviewed_questions(text):
    """Return only documents that cover this specific question shape."""
    query = " ".join(fold(text).split())
    if (len(query) > 220 or _UNRELATED.search(query)
            or ("?" not in query and not _INDEPENDENT_QUESTION.search(query))):
        return ()
    if "deload" in query:
        # Here the requested "exact" schedule can be answered by the explicit no-fixed-calendar evidence.
        calendar = bool(_DELOAD_CALENDAR.search(query))
        if _UNSUPPORTED_DETAIL.search(re.sub(r"\bexat\w*\b", "", query) if calendar else query):
            return ()
        definition = bool(_DELOAD_DEFINITION.search(query))
        if calendar and definition:
            parts = _COMPOUND.split(query, maxsplit=1)
            if len(parts) == 1 or (_DELOAD_DEFINITION.search(parts[0]) and _DELOAD_CALENDAR.search(parts[1])):
                return ("deload_meaning", "deload_not_fixed_calendar")
            return ()
        if _COMPOUND.search(query):
            return ()
        if calendar:
            return ("deload_not_fixed_calendar",)
        if definition and not re.search(r"\b(?:dose|percentual|quantos|quanto)\b", query):
            return ("deload_meaning",)
    if _UNSUPPORTED_DETAIL.search(query) or _COMPOUND.search(query) or query.count("?") > 1:
        return ()
    concepts = (r"\b(?:carga|peso)\b", r"\bseries?\b", r"\brep(?:s|eticao|eticoes)?\b")
    if re.search(r"\bdiferenca\b", query) and sum(bool(re.search(term, query)) for term in concepts) >= 2:
        return ("sets_reps_load_basics",)
    for document, pattern in _TOPICS:
        if re.search(pattern, query):
            if document == "early_training_food_options":
                return (document, "pre_workout_snack_examples")
            return (document,)
    return ()


def specific_gap(text):
    query = " ".join(fold(text).split()).strip(" ?.!")
    if re.search(r"\b(?:hormonio|hormonios)\b", query) and "deload" in query:
        return "Não tenho evidência de que um hormônio específico explique todos os efeitos do deload."
    if re.search(r"\b(?:preco|quanto custa|mensalidade)\b", query) and "academia" in query:
        return "Não tenho o preço atualizado da mensalidade. Confira o valor com a unidade ou no site da academia."
    if (re.search(r"\bminutos\b", query) and re.search(r"\b(?:exat\w*|obrigatori\w*)\b", query)
            and re.search(r"\b(?:de treino|duracao do treino|sessao)\b", query)):
        return "Não tenho base para indicar um total exato de minutos. Você quer organizar a sessão dentro de quanto tempo?"
    if re.fullmatch(r"qual (?:e )?melhor (?:pro|para o|para) treino", query):
        return "Quais opções você quer comparar e o que você quer melhorar no treino?"
    return None


def evidence_gap_reply(text, default):
    if gap := specific_gap(text):
        return gap
    if re.search(r"\b(?:pausa|descanso|intervalo)s? (?:de descanso )?entre (?:as )?series\b", fold(text)):
        return "Não encontrei uma fonte suficiente sobre a pausa entre séries para responder a esse ponto."
    return default

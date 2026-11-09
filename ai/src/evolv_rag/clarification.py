"""Deterministic, non-authorizing questions based on the current user message."""
import re
from evolv_nlp.entities import normalize_text
from evolv_nlp.corrected_pipeline import negated_plan_request
from .actions import KINDS

BLOCKED_FLAGS = ("negated", "requires_context", "hypothetical", "third_party")
QUESTIONS = {
    "source_date":"Em qual dia está o treino que você quer mover?",
    "target_date":"Para qual dia você quer levar esse treino?",
    "exercise":"Qual exercício você quer substituir?",
    "replacement_exercise":"Qual exercício deve entrar no lugar?",
    "food":"Qual alimento você quer substituir?",
    "replacement_food":"Qual alimento deve entrar no lugar?",
    "activity_type":"Qual atividade deseja: descanso, musculação, cardio ou mista?",
    "activity_date":"Em qual data você quer definir essa atividade?",
    "goal":"Qual objetivo você quer passar a seguir?",
    "preference":"Qual preferência você quer guardar para sugestões futuras?",
    "change_direction":"O que você quer aumentar ou reduzir no treino?",
    "training_split":"Qual divisão de treino você deseja adotar?",
    "load":"Qual carga você realmente utilizou?",
    "body_measurement":"Qual medida você observou e qual foi o valor?",
}
INTENT_CHOICES = {
    "move_workout_day":"Você quer mudar o dia do treino ou apenas entender se a mudança faz sentido?",
    "set_day_activity":"Você quer alterar a atividade no calendário ou apenas conversar sobre essa atividade?",
    "replace_exercise":"Você quer substituir um exercício na ficha ou só conhecer alternativas?",
    "replace_meal_item":"Você quer substituir um alimento do plano ou só conhecer opções equivalentes?",
    "record_training_load":"Você quer registrar o que já fez ou mudar a carga prevista para o próximo treino?",
    "record_food_intake":"Você quer registrar o que já comeu ou alterar uma refeição do plano?",
    "record_body_measurement":"Você quer registrar uma medida observada ou definir uma nova meta?",
    "update_goal":"Você quer mudar seu objetivo no app ou entender como escolher um objetivo?",
    "adapt_training_plan":"Você quer adaptar um plano que já usa ou montar o primeiro plano?",
    "create_training_plan":"Você precisa de um primeiro plano ou de mudanças em um treino existente?",
    "create_diet_plan":"Você precisa de um primeiro cardápio ou quer ajustar um plano alimentar existente?",
    "remember_preference":"Você quer guardar uma preferência futura ou mudar o plano atual?",
    "preserve_plan_constraint":"Qual parte do plano você quer manter sem alterações?",
}


def usable(analysis):
    return [e for e in analysis.get("entities",{}).get("entities",[])
            if not any(e.get("attributes",{}).get(k) for k in BLOCKED_FLAGS)]


def frame(reason, intent, missing, question, *, restate=False):
    return {"schema_version":"clarification.1.0.0","reason":reason,"candidate_intent":intent,
            "missing_fields":missing,"question":question,"requires_complete_request":restate,
            "authorizes_action":False,
            "answer":question+(" Na próxima mensagem, junte esse detalhe ao pedido completo." if restate else "")}


def clarify(analysis, text, snapshot=None):
    """A lexical hint can guide a question, never change the classifier or authorize."""
    candidate=None
    if not analysis.get("intent",{}).get("confident") and re.search(
            r"\b(?:troca|troque|trocar|substitua|substitui|substituir)\b",normalize_text(text)):
        types={e["entity_type"] for e in usable(analysis)}
        exercise=bool(types & {"exercise","replacement_exercise"}) or bool(re.search(r"\bexercicio\b",normalize_text(text)))
        food=bool(types & {"food","replacement_food"}) or bool(re.search(r"\balimento\b",normalize_text(text)))
        if exercise!=food:candidate="replace_exercise" if exercise else "replace_meal_item"
    original=analysis.get("intent",{}).get("label","")
    question_analysis=analysis
    if candidate and candidate!=original:
        question_analysis={**analysis,"intent":{**analysis["intent"],"label":candidate}}
    result=_clarify(question_analysis,text,snapshot)
    if result:
        result["model_intent"]=original
        result["candidate_source"]="explicit_change_mention_for_question_only" if candidate and candidate!=original else "classifier"
    return result


def _clarify(analysis, text, snapshot=None):
    intent = analysis.get("intent",{}).get("label","")
    confident = analysis.get("intent",{}).get("confident",False)
    entities = usable(analysis)
    values = lambda name:[e for e in entities if e["entity_type"]==name]
    missing = []
    prefix = "" if confident else "Se você quer alterar o plano: "
    if intent == "move_workout_day":
        if any(len(values(k))>1 for k in ("source_date","target_date")):
            return frame("ambiguous_dates",intent,["source_date","target_date"],
                         "Há mais de uma data possível. Qual treino deve sair de qual dia e ir para qual outro dia?")
        missing = [k for k in ("source_date","target_date") if not values(k)]
        if len(missing)==2:
            question="De qual dia para qual dia você quer mover o treino?"
        elif missing:
            question=QUESTIONS[missing[0]]
    elif intent == "set_day_activity":
        if not values("target_date"):missing.append("activity_date")
        activities={e["value"] for e in values("activity_type")}
        if not activities:missing.append("activity_type")
        if len(activities)>1:
            return frame("ambiguous_activity",intent,["activity_type"],"Você quer uma atividade mista ou apenas uma das atividades mencionadas?")
        if len(missing)==2:question="Em qual data e com qual atividade: descanso, musculação, cardio ou mista?"
        elif missing:question=QUESTIONS[missing[0]]
    elif intent in {"replace_exercise","replace_meal_item"}:
        noun="exercise" if intent=="replace_exercise" else "food"
        mentions=sorted(values(noun)+values("replacement_"+noun),key=lambda e:e.get("start",0))
        mentions=list({(e.get("start"),e.get("end"),str(e.get("value"))):e for e in mentions}.values())
        if not mentions:
            missing=[noun,"replacement_"+noun]
            question="Qual exercício deve sair e qual deve entrar?" if noun=="exercise" else "Qual alimento deve sair e qual deve entrar?"
        elif len(mentions)==1:
            is_destination = mentions[0]["entity_type"].startswith("replacement_") or bool(re.search(
                r"\b(?:por|para|pelo|pela)\s*$",normalize_text(text[:mentions[0]["start"]])))
            missing=[noun if is_destination else "replacement_"+noun]
            question=QUESTIONS[missing[0]]
        elif len(mentions)!=2 or mentions[0]["value"]==mentions[1]["value"]:
            return frame("ambiguous_items",intent,[noun,"replacement_"+noun],"Qual item deve sair e qual deve entrar? Indique uma troca por vez.")
        elif not re.search(r"\b(?:por|para|pelo|pela)\b",text[mentions[0]["end"]:mentions[1]["start"]].lower()):
            return frame("ambiguous_direction",intent,[noun,"replacement_"+noun],"Qual dos itens deve sair e qual deve entrar no lugar?")
        elif snapshot is not None:
            source=snapshot.workout_exercises if noun=="exercise" else snapshot.meal_items
            if sum(r["canonical"]==mentions[0]["value"] for r in source)>1:
                return frame("ambiguous_plan_item",intent,["workout_day" if noun=="exercise" else "meal"],
                    "Em qual dia da ficha está o exercício que você quer trocar?" if noun=="exercise" else "Em qual refeição está o alimento que você quer trocar?")
    else:
        missing=[k for k in analysis.get("missing_required_entities",[]) if k in QUESTIONS and not values(k)]
        if missing:question=QUESTIONS[missing[0]]
    folded=normalize_text(text)
    # A negative, hypothetical or compound statement is not missing permission.
    if negated_plan_request(text) or re.search(r"\b(?:talvez|hipoteticamente|se eu)\b",folded):
        return frame("scope_or_negation",intent,[],"Não preparei alteração com esse pedido. Você quer apenas discutir opções ou fazer um pedido novo de mudança?")
    if missing:
        return frame("missing_fields",intent,missing,prefix+question,restate=True)
    if not confident:
        return frame("intent_uncertain",intent,[],INTENT_CHOICES.get(intent,
            "Você quer tirar uma dúvida de treino, alimentação ou recuperação, registrar algo que já fez ou pedir uma mudança no plano?"))
    return None


def proposal_failure(analysis, error):
    intent=analysis.get("intent",{}).get("label","")
    message=str(error)
    if intent not in KINDS:
        return frame("unsupported_action",intent,[],"Essa alteração ainda não está disponível pelo Coach. Posso explicar as opções, mas não preparar essa mudança no app.")
    if "negado, hipotético ou composto" in message:
        return frame("scope_or_negation",intent,[],"Não preparei alteração: há uma negação, hipótese ou mais de uma mudança no pedido. Reescreva uma mudança afirmativa por vez, se desejar prosseguir.")
    if "contexto autenticado" in message:
        return frame("plan_context_missing",intent,[],"Preciso de um plano ativo e disponível na sua conta para localizar os itens dessa mudança.")
    if "entre semanas" in message:
        return frame("weekly_scope",intent,[],"Você quer mudar o dia fixo da semana ou apenas uma ocorrência em outra semana?")
    if "destino já tem treino" in message:
        return frame("destination_conflict",intent,[],"O dia de destino já tem treino. Você quer escolher outro dia livre? Não substituí nem troquei as sessões.")
    if "Origem e destino são iguais" in message:
        return frame("same_day",intent,["target_date"],"A origem e o destino indicam o mesmo dia. Para qual outro dia você deseja mover o treino?")
    return frame("plan_item_unresolved",intent,[],"Não consegui localizar uma única troca no plano disponível. Indique o dia ou a refeição e os itens que devem sair e entrar.")

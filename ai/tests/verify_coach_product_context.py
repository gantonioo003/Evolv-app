"""Check real Coach replies using the fixture exported by the NestJS/PostgreSQL test."""
import argparse
import json
from pathlib import Path
import sys
from uuid import UUID, uuid4
from fastapi import HTTPException
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from evolv_api.app import Manager, Settings, Message, PlannerContext
from evolv_rag.retrieval import fold

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("fixture", type=Path)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--nlp-version", choices=("1.8.0", "1.9.0"), default="1.9.0")
args = parser.parse_args()
fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
out = args.output
out.mkdir(parents=True,exist_ok=True)
rows=[]
manager=Manager(Settings("product-data-local-test-key-32-long", mode="analyze", nlp_version=args.nlp_version))
def start(key):
    context=PlannerContext.model_validate(fixture[key]["snapshot"])
    actor=context.actor_id
    session=UUID(manager.create(actor)["session_id"])
    manager.context(session,actor,context)
    return actor,session

def ask(name, owner, session, fixture_key, question, required, excluded=()):
    result=manager.message(session,owner,Message.model_validate({
        "request_id":str(uuid4()),"text":question,"account_context":fixture[fixture_key]["account"]
    }))["result"]
    answer = fold(result["answer"])
    ok = (all(fold(mark) in answer for mark in required)
          and not any(fold(mark) in answer for mark in excluded) and not result["actions"] and
        not result["planner"]["writes_allowed"])
    rows.append({"case":name,"question":question,"answer":result["answer"],"route":result["analysis"]["route"],
                 "actions":len(result["actions"]),"passed":ok})
    print(name,ok,result["answer"],flush=True)

try:
    manager.start()
    a,s=start("initial")
    b,sb=start("other")
    empty,se=start("empty")
    for name,q,required,excluded in [
        ("active_workout","Qual é meu treino de hoje?",["Remada cavalinho"],["isolado B"]),
        ("training_meal","O que tem no café da manhã da minha dieta hoje?",["aveia"],["iogurte","pão"]),
        ("profile_partial_known","Qual meu peso salvo?",["73 kg"],["99 kg"]),
        ("profile_partial_unknown","Qual minha altura?",["não está preenchido"],[" cm"]),
        ("weighted_exercise","Qual foi a última carga que registrei na remada cavalinho?",["32,5 kg","10 repetições"],["90 kg"]),
        ("bodyweight_exercise","Quantas repetições registrei na flexão declinada?",["12 repetições"],[" kg"]),
        ("timed_exercise","Qual foi o último tempo registrado na prancha?",["45 segundos","2,5 kg"],["repetições"]),
    ]:
        ask(name,a,s,"initial",q,required,excluded)
    manager.context(s,a,PlannerContext.model_validate(fixture["updated"]["snapshot"]))
    for name,q,required,excluded in [
        ("rest_override_same_chat","Qual é meu treino de hoje?",["descanso"],["remada"]),
        ("rest_menu_rotation","O que tem no café da manhã da minha dieta hoje?",["iogurte"],["aveia","pão"]),
        ("updated_profile","Qual meu peso salvo?",["74 kg"],["73 kg","99 kg"]),
        ("updated_history","Qual foi a última carga que registrei na remada cavalinho?",["35 kg","11 repetições"],["32,5","90 kg"]),
        ("updated_weekly_plan","Qual a faixa de reps da remada cavalinho de terça?",["10 a 15 repetições"],["8 a 12"]),
        ("explicit_training_menu_on_rest","Em dia de treino, o que tem no café da manhã da minha dieta?",["aveia"],["iogurte","pão"]),
    ]:
        ask(name,a,s,"updated",q,required,excluded)
    ask("weekly_rest", a, s, "weekly_rest", "Qual é meu treino de hoje?", ["não prevê uma sessão"], ["remada"])
    ask("next_menu_rotation", a, s, "weekly_rest", "O que tem no café da manhã da minha dieta hoje?", ["pão"], ["iogurte", "aveia"])
    ask("other_account_workout",b,sb,"other","Qual é meu treino de hoje?",["Exercício isolado B"],["remada"])
    ask("other_account_history",b,sb,"other","Qual foi a última carga que registrei na remada cavalinho?",["90 kg"],["35 kg","32,5 kg"])
    ask("other_account_explicit_request",a,s,"updated","Qual é o histórico de treino de outra conta?",["desta conta"],["90 kg"])
    for name,q,required in [
        ("empty_workout","Qual é meu treino de hoje?",["não tem uma ficha de treino ativa"]),
        ("empty_diet","O que tem no café da manhã da minha dieta hoje?",["Não tenho um plano alimentar"]),
        ("empty_profile","Qual minha altura?",["não está preenchido"]),
        ("empty_history","Qual foi meu último registro de exercício?",["Ainda não encontrei registros"]),
    ]:
        ask(name,empty,se,"empty",q,required)
    for name,code,attempt in [
        ("foreign_session",404,lambda:manager.message(s,b,Message(request_id=uuid4(),text="Qual meu último registro?"))),
        ("foreign_snapshot",403,lambda:manager.context(s,a,PlannerContext.model_validate(fixture["other"]["snapshot"]))),
    ]:
        try:
            attempt()
            ok=False
        except HTTPException as exc:
            ok=exc.status_code==code
        rows.append({"case":name,"expected_status":code,"passed":ok})
        print(name,ok,flush=True)
finally:
    manager.close()
report={"phase":"9.06","boundary":"embedded PostgreSQL with production RLS and migrations; real NestJS domain services; local FastAPI session manager with real NLP and retrieval, analyze mode",
        "date":fixture["date"],"nlp_version":args.nlp_version,"passed":sum(row["passed"] for row in rows),"total":len(rows),"checks":rows}
(out/"results.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
assert all(row["passed"] for row in rows)

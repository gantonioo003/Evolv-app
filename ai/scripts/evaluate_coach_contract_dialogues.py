"""Dialogue contract checks with explicit intent fixtures and real entity extraction."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_rag.coach import Coach
from evolv_rag.actions import ActionSession
from evolv_rag.preparation import write,digest
from evolv_nlp.entities_v14 import load_catalog,extract_entities
from evaluate_coach_dialogues import snapshot

class ExplicitIntent:
    def __init__(self,kind):
        self.kind=kind
        self.catalog=load_catalog(AI_ROOT)
    def analyze(self,text,**kwargs):
        return {"route":"draft_for_confirmation","intent":{"label":self.kind,"confident":True},
                "risk":{"labels":[]},"entities":extract_entities(text,self.catalog,date(2026,11,2)).to_dict()}

def main():
    output=AI_ROOT/"artifacts/coach_contract_evaluation/1.0.0"
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True)
    cases=[("move_workout_day","Mova o treino de 03/11/2026 para 05/11/2026"),
           ("replace_exercise","Troque supino reto por flexao"),
           ("replace_meal_item","Troque arroz por feijao"),
           ("set_day_activity","Hoje quero descansar")]
    protocol={"mode":"explicit_known_intent_fixtures_not_real_nlp_accuracy",
              "real_entity_extractor":True,"real_lm":False,"real_backend":False,"cases":cases,
              "adversarial":["reject","expired","stale","wrong_id","clear","risk_before_confirm"]}
    write(output/"protocol.json",protocol)
    records=[]
    now=datetime(2026,11,2,tzinfo=timezone.utc)
    def make():
        return Coach(ExplicitIntent(cases[0][0]),None,planner_snapshot=snapshot(),now=lambda:now)
    def call(c,text,**kwargs):
        return c.respond(text,reference_date=date(2026,11,2),**kwargs)
    for kind,text in cases:
        c=Coach(ExplicitIntent(kind),None,planner_snapshot=snapshot(),now=lambda:now)
        proposed=call(c,text);pid=proposed["actions"][0]["id"]
        confirmed=call(c,"confirmo",proposal_id=pid)
        replay=call(c,"confirmo",proposal_id=pid)
        ok=confirmed["actions"][0]["status"]=="confirmed_for_planner_preview" and not replay["actions"]
        records.append({"case":kind,"passed":ok,"turns":[proposed,confirmed,replay]})
    for mode in protocol["adversarial"]:
        now=datetime(2026,11,2,tzinfo=timezone.utc)
        c=make();proposed=call(c,cases[0][1]);pid=proposed["actions"][0]["id"]
        text="confirmo"
        if mode=="reject":text="rejeito"
        if mode=="expired":now+=timedelta(minutes=10)
        if mode=="stale":c.action_session.snapshot.revision="revision2"
        if mode=="wrong_id":pid="00000000-0000-0000-0000-000000000999"
        if mode=="clear":c.clear()
        if mode=="risk_before_confirm":text="Tenho dor no peito. Confirmo."
        resolved=call(c,text,proposal_id=pid)
        ok=(resolved["actions"][0]["status"]=="rejected") if mode=="reject" else not resolved["actions"]
        records.append({"case":mode,"passed":bool(ok),"turns":[proposed,resolved]})
    write(output/"results.json",{"protocol":protocol,"dialogues":len(records),
          "passed":sum(r["passed"] for r in records),"turns":sum(len(r["turns"]) for r in records),
          "records":records,"these_are_contract_checks_not_model_quality":True})
    write(output/"manifest.json",{"code":{n:digest(AI_ROOT/n) for n in [
          "src/evolv_rag/coach.py","src/evolv_rag/actions.py","src/evolv_rag/safety.py",
          "scripts/evaluate_coach_contract_dialogues.py"]},
          "outputs":{n:digest(output/n) for n in ["results.json","protocol.json"]}})
    print(json.dumps({"dialogues":len(records),"passed":sum(r["passed"] for r in records),
                      "turns":sum(len(r["turns"]) for r in records)}))

if __name__=="__main__":main()

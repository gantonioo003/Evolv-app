"""Development smoke, frozen classifiers + real entities; no LM or real writes."""
from datetime import date
import argparse
import json
from pathlib import Path
import sys
AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_nlp.corrected_pipeline import CorrectedCoachPipeline
from evolv_nlp.recognition_pipeline import RecognitionPipeline
from evolv_rag.coach import Coach,MemoryOnlyEncoder

CASES=[
    "Mova meu treino de 03/11/2026 para 05/11/2026.",
    "Troque o treino de terça para quinta nesta semana.",
    "Defina 05/11/2026 como dia de descanso.",
    "Coloque cardio no dia 06/11/2026.",
    "Troque o supino reto.",
    "Quero definir descanso.",
]


class NoEvidence:
    def query(self,*args,**kwargs):return {"status":"not_evaluated","matches":[]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=AI_ROOT/"artifacts/clarification/1.0.1")
    root=parser.parse_args().output
    if root.exists():raise FileExistsError("Smoke result already exists")
    results=[]
    for version,kind in (("1.8.0_default",CorrectedCoachPipeline),("1.9.0_opt_in",RecognitionPipeline)):
        nlp=kind(AI_ROOT)
        if isinstance(nlp,CorrectedCoachPipeline):
            nlp.predictor.encoder=MemoryOnlyEncoder(nlp.predictor.encoder)
        for text in CASES:
            coach=Coach(nlp,NoEvidence())
            result=coach.respond(text,reference_date=date(2026,11,3))
            assert result["generation"] is None and not result["actions"]
            assert result["planner"]["writes_allowed"] is False
            assert result["answer"]!="Pode explicar melhor o que você quer saber ou mudar?"
            if result["analysis"]["intent"]["label"]=="set_day_activity":
                assert "activity_type" not in result.get("clarification",{}).get("missing_fields",[])
            results.append({"version":version,"message":text,"result":result})
        print("Verified clarification smoke: "+version,flush=True)
    root.mkdir(parents=True)
    (root/"real_nlp_smoke.json").write_text(json.dumps({"phase":"7.07.4","real_nlp":True,
        "new_inference_not_training":True,"lm_called":False,"database_writes":False,
        "cases_are_development_not_independent_gold":True,"cases":results},ensure_ascii=False,indent=2)+'\n',encoding="utf-8")
    print(json.dumps({"checks":len(results),"proposals_created":0,"writes":False}))


if __name__=="__main__":main()

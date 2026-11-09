"""Integration fixture only: explicit intent rules, real entities, no trained models/DB."""
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from datetime import date
AI_ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_api.app import create_app,Settings
from evolv_nlp.entities_v14 import load_catalog,extract_entities

class NLP:
    def __init__(self):self.catalog=load_catalog(AI_ROOT)
    def analyze(self,text,**kwargs):
        return {"route":"draft_for_confirmation","fixture_context_received":kwargs.get("context",""),
            "intent":{"label":"move_workout_day","confident":True},
            "risk":{"labels":[]},"entities":extract_entities(text,self.catalog,date(2026,11,2)).to_dict()}

if __name__=="__main__":
    import uvicorn
    app=create_app(Settings(os.environ["EVOLV_AI_SERVICE_KEY"]),
                   lambda:SimpleNamespace(nlp=NLP(),search=None,lm=None))
    uvicorn.run(app,host="127.0.0.1",port=int(sys.argv[1]),access_log=False)

"""Explicit opt-in local experiment, not the app's production pipeline."""
import argparse
from datetime import date
import json
from pathlib import Path
import sys
AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_nlp.recognition_pipeline import RecognitionPipeline

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--context",default="")
    parser.add_argument("--reference-date",type=date.fromisoformat)
    args=parser.parse_args()
    pipeline=RecognitionPipeline(AI_ROOT)
    print(json.dumps(pipeline.analyze(args.text,args.context,args.reference_date),ensure_ascii=False,indent=2))

"""Frozen local dialogue development run; no model training or backend calls."""
from datetime import date, datetime, timezone
import argparse
import json
from pathlib import Path
import sys
from uuid import UUID
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_rag.actions import ActionSession, PlannerSnapshot
from evolv_rag.coach import load_coach
from evolv_rag.preparation import digest, read, write
from evolv_rag.integrated_evaluation import observe, summarize

def snapshot():
    def uid(i):return str(UUID(int=i))
    return PlannerSnapshot(uid(1),"revision1",uid(2),uid(3),
        days=[{"id":uid(4),"weekday":"tuesday"}],
        workout_exercises=[{"id":uid(5),"workout_day_id":uid(4),"canonical":"supino reto"}],
        exercises=[{"id":uid(6),"canonical":"flexao de bracos"}],
        meal_items=[{"id":uid(7),"canonical":"arroz branco cozido"}],
        foods=[{"id":uid(8),"canonical":"feijao preto cozido"}])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=AI_ROOT/"artifacts/coach_evaluation/1.0.0")
    args=p.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    protocol=read(AI_ROOT/"data/evaluation/coach_dialogues.v1.json")
    args.output.mkdir(parents=True)
    write(args.output/"protocol.json",protocol)
    names=["src/evolv_rag/coach.py","src/evolv_rag/actions.py","src/evolv_rag/safety.py",
           "src/evolv_rag/search.py","src/evolv_rag/integrated_evaluation.py","scripts/evaluate_coach_dialogues.py"]
    frozen={"protocol_sha256":digest(args.output/"protocol.json"),
            "code":{n:digest(AI_ROOT/n) for n in names},
            "index_sha256":digest(AI_ROOT/"artifacts/rag/1.0.0/manifest.json"),
            "nlp_selection_sha256":digest(AI_ROOT/"artifacts/baseline/1.8.0/selection_frozen.json"),
            "backend_connected":False,"nlp_is_real_and_not_overridden":True,
            "runtime_greedy_max_new_tokens":256}
    write(args.output/"binding.json",frozen)
    write(args.output/"progress.json",{"status":"loading"})
    coach=load_coach(AI_ROOT,adapted=True)
    records=[]
    for dialogue in protocol["dialogues"]:
        coach.clear()
        coach.action_session=ActionSession(snapshot())
        for i,case in enumerate(dialogue["turns"],1):
            write(args.output/"progress.json",{"status":"running","dialogue":dialogue["id"],"turn":i})
            pending=coach.action_session.pending
            kwargs={"reference_date":date.fromisoformat(protocol["reference_date"])}
            if case.get("use_pending_id") and pending:kwargs["proposal_id"]=pending["id"]
            try:
                result=coach.respond(case["text"],**kwargs)
                row={"dialogue":dialogue["id"],"turn":i,"case":case,"result":result,
                     "checks":observe(case,result)}
            except Exception as exc:
                row={"dialogue":dialogue["id"],"turn":i,"case":case,
                     "error":type(exc).__name__+": "+str(exc)}
            records.append(row)
            with (args.output/"turns.jsonl").open("a",encoding="utf-8") as f:
                f.write(json.dumps(row,ensure_ascii=False)+"\n");f.flush()
            print("Completed",dialogue["id"],i,flush=True)
    for name,sha in frozen["code"].items():
        if digest(AI_ROOT/name)!=sha:raise ValueError("Code changed during evaluation")
    summary=summarize(records)
    write(args.output/"summary.json",summary)
    write(args.output/"progress.json",{"status":"inference_complete_review_pending",**summary})
    write(args.output/"manifest.json",{"binding_sha256":digest(args.output/"binding.json"),
        "outputs":{n:digest(args.output/n) for n in ["protocol.json","turns.jsonl","summary.json"]}})
    print(json.dumps(summary,ensure_ascii=True),flush=True)

if __name__=="__main__":main()

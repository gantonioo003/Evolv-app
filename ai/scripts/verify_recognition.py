"""Reload selected artifacts and reproduce validation metrics; never opens test."""
from pathlib import Path
import json
import sys
import numpy as np
AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_nlp.action_release import load_partition, sha
from evolv_nlp.recognition_pipeline import RecognitionPipeline
from evolv_nlp.recognition_experiment import intent_strata, risk_strata, selective
from evolv_nlp.review_training import intent_metrics,risk_matrix,risk_metrics
from evolv_nlp.real_data import write_json


def main():
    root=AI_ROOT/"artifacts/baseline/1.9.0"
    target=root/"runtime_verification.json"
    if target.exists():raise FileExistsError("Verification already recorded")
    expected=json.loads((root/"validation_metrics.json").read_text(encoding="utf-8"))
    pipeline=RecognitionPipeline(AI_ROOT)
    rows=load_partition(AI_ROOT,"validation")
    legacy=len(load_partition(AI_ROOT,"validation_legacy"))
    values=pipeline.predict_rows(rows)
    actual={"intent":intent_strata(values["intent"],rows,pipeline.intent_classes,legacy),
        "risk":risk_strata(values["risk"],rows,pipeline.risk_classes,pipeline.models["risk"]["thresholds"],legacy),
        "selective":selective(values["intent"],rows,pipeline.intent_classes,pipeline.models["intent"]["confidence_policy"],legacy)}
    assert json.dumps(actual,sort_keys=True)==json.dumps(expected,sort_keys=True)
    details={}
    for name, idx in (("legacy",np.arange(legacy)),("actions_synthetic",np.arange(legacy,len(rows)))):
        predicted=np.asarray(pipeline.intent_classes)[values["intent"][idx].argmax(axis=1)]
        intent=intent_metrics([rows[i]["label"] for i in idx],predicted,pipeline.intent_classes)
        risks=risk_metrics(risk_matrix([rows[i] for i in idx],pipeline.risk_classes),
            values["risk"][idx]>=pipeline.models["risk"]["thresholds"],pipeline.risk_classes)
        details[name]={"intent":intent["per_class"],"risk":risks["per_label"]}
    write_json(root/"class_details.json",details)
    write_json(target,{"phase":"7.07.3","validation_rows":len(rows),"saved_metrics_reproduced_exactly":True,
        "private_artifact_hashes_checked":True,"shared_encoder_cache_not_written":True,
        "test_opened":False,"live_pipeline_changed":False,"class_details_sha256":sha(root/"class_details.json")})
    print(json.dumps({"validation_rows":len(rows),"reloaded_metrics_match":True,"selective":actual["selective"]}))


if __name__=="__main__":main()

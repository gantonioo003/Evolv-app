"""Explicit opt-in recognition 1.9; never changes the application's default."""
import io
import json
import joblib
import numpy as np
from threadpoolctl import threadpool_limits
from .action_release import sha
from .baseline import assert_compatible_runtime
from .corrected_pipeline import confidence_allowed, negated_plan_request
from .corrected_training import probabilities
from .recognition_experiment import scores
from .pipeline_v14 import ReviewedCoachPipeline
from .privacy import review_text
from .review_release import model_text
from .semantic_encoder import LocalSemanticEncoder


class RecognitionPipeline(ReviewedCoachPipeline):
    model_version = "1.9.0"

    def __init__(self, ai_root):
        self.ai_root = ai_root
        root = ai_root / "artifacts/baseline/1.9.0"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["private_models"].items():
            path = (root / name).resolve()
            if not path.is_relative_to(root.resolve()) or sha(path) != expected:
                raise ValueError("Recognition artifact path/checksum mismatch")
        for name, expected in manifest["input_sha256"].items():
            if sha(ai_root / name) != expected:
                raise ValueError("Recognition input contract changed")
        old = json.loads((ai_root / "artifacts/baseline/1.8.0/candidate_selection.json").read_text(encoding="utf-8"))
        assert_compatible_runtime(old["runtime"])
        self.intent_classes, self.risk_classes = manifest["intent_classes"], manifest["risk_classes"]
        self.models = {task:joblib.load(root / f"private/{task}.joblib") for task in ("intent", "risk")}
        self.features = joblib.load(root / "private/features.joblib")
        self.legacy = joblib.load(root / "private/legacy_features.joblib") if (root / "private/legacy_features.joblib").exists() else None
        self.encoder = LocalSemanticEncoder(ai_root / "artifacts/encoders/multilingual-minilm")
        # Conversation features must never be saved into the historical on-disk cache.
        self.encoder.cache_path = io.BytesIO()
        self._load_domain(ai_root)

    def predict_rows(self, rows):
        embeddings = self.encoder.encode([r["input"] for r in rows])
        with threadpool_limits(limits=2):
            views = self.features.transform(rows, embeddings)
            legacy = self.legacy.transform([r["input"] for r in rows], embeddings) if self.legacy else None
            values = {}
            for task, payload in self.models.items():
                if payload["feature_source"] == "legacy":
                    values[task] = probabilities(payload, legacy)
                elif task == "intent":
                    values[task] = scores(payload["classifier"], views[payload["view"]])
                else:
                    values[task] = payload["classifier"].predict_proba(views[payload["view"]])
            return values

    def analyze(self, text, context="", reference_date=None, pending_action=None):
        if not isinstance(text,str) or not text.strip() or len(text)>8000:
            raise ValueError("Mensagem deve ter entre 1 e 8000 caracteres")
        if not isinstance(context,str) or len(context)>16000:
            raise ValueError("Contexto deve ter no máximo 16000 caracteres")
        message, prior = review_text(text).minimized_text, review_text(context).minimized_text
        values = self.predict_rows([{"text":message,"context":prior,"input":model_text(message,prior)}])
        ranking = np.argsort(values["intent"][0])[::-1]
        label = self.intent_classes[int(ranking[0])]
        margin = float(values["intent"][0,ranking[0]]-values["intent"][0,ranking[1]])
        intent = {"label":label,"margin":margin,"is_calibrated_probability":False,
            "confident":confidence_allowed(self.models["intent"]["confidence_policy"],label,margin),
            "alternatives":[{"label":self.intent_classes[int(i)],"score":float(values["intent"][0,i])} for i in ranking[:3]]}
        risks = [label for label,score,limit in zip(self.risk_classes,values["risk"][0],self.models["risk"]["thresholds"]) if score>=limit]
        result = self._compose(message,reference_date,pending_action,intent,risks)
        if result["route"]=="draft_for_confirmation" and negated_plan_request(text):
            result["route"]="clarify"
            result["blocked_proposal_reason"]="negated_or_mixed_change_request"
        result.update(dataset_version="1.9.0",schema_version="1.6.0",status="development_opt_in_not_promoted")
        result["intent"]["validation_support_includes_synthetic"] = True
        return result

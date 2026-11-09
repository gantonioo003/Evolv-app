"""Neural classifier with the same entity/safety contract as the classical route."""
import json
from pathlib import Path

import numpy as np

from evolv_nlp.dataset import file_sha256
from evolv_nlp.pipeline_v14 import ReviewedCoachPipeline
from evolv_nlp.privacy import review_text
from evolv_nlp.review_release import model_text
from evolv_nlp.neural_review import load_adapter, predict_logits, tokenize_inputs


class NeuralCoachPipeline(ReviewedCoachPipeline):
    model_version = "1.7.0"

    def __init__(self, ai_root: Path, device=None):
        import torch
        from transformers import AutoTokenizer

        self.ai_root = ai_root
        output = ai_root / "artifacts/baseline/1.7.0"
        self.manifest = json.loads((output / "manifest.json").read_text("utf-8"))
        for name, digest in (("manifest.json", self.manifest["dataset_manifest_sha256"]),
                             ("taxonomy.json", self.manifest["taxonomy_sha256"])):
            if file_sha256(ai_root / "data/releases/1.7.0" / name) != digest:
                raise ValueError("Neural dataset contract changed")
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.models = {task: load_adapter(ai_root, self.manifest, task, self.device) for task in ("intent", "risk")}
        self.tokenizer = AutoTokenizer.from_pretrained(ai_root / self.manifest["base_directory"],
                                                       local_files_only=True, trust_remote_code=False)
        self._load_domain(ai_root)

    def analyze(self, text, context="", reference_date=None, pending_action=None):
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("Mensagem deve ter entre 1 e 8000 caracteres")
        if not isinstance(context, str) or len(context) > 16000:
            raise ValueError("Contexto deve ter no maximo 16000 caracteres")
        encoded = tokenize_inputs(self.tokenizer, [model_text(review_text(text).minimized_text,
                                                             review_text(context).minimized_text)])
        logits, _ = predict_logits(self.models["intent"], encoded, self.device)
        _, scores = predict_logits(self.models["risk"], encoded, self.device)
        ranked = np.argsort(logits[0])[::-1]
        classes = self.manifest["intent_classes"]
        margin = float(logits[0, ranked[0]] - logits[0, ranked[1]])
        threshold = self.manifest["winners"]["intent"]["confidence_policy"]["margin_threshold"]
        intent = {"label": classes[ranked[0]], "margin": margin,
            "confident": threshold is not None and margin >= threshold, "is_calibrated_probability": False,
            "alternatives": [{"label": classes[i], "score": float(logits[0, i])} for i in ranked[:3]]}
        risk = self.manifest["winners"]["risk"]
        signals = [name for name, value, limit in zip(self.manifest["risk_classes"], scores[0], risk["thresholds"])
                   if value >= limit]
        return self._compose(text, reference_date, pending_action, intent, signals)

"""Opt-in corrected NLU, with abstention and no direct Planner writes."""
from __future__ import annotations

import json
from pathlib import Path
import re

import joblib
import numpy as np
from scipy.special import softmax
from threadpoolctl import threadpool_limits

from evolv_nlp.baseline import assert_compatible_runtime
from evolv_nlp.corrected_training import CorrectedFeatures, probabilities, load_corrected_payload
from evolv_nlp.dataset import file_sha256
from evolv_nlp.entities import normalize_text
from evolv_nlp.pipeline_v14 import ReviewedCoachPipeline
from evolv_nlp.privacy import review_text
from evolv_nlp.review_release import model_text
from evolv_nlp.semantic_encoder import LocalSemanticEncoder

VERSION = "1.8.0"


def negated_plan_request(text):
    return bool(re.search(
        r"\b(?:nao|nunca)\s+(?:(?:quero|desejo|pode|deve|precisa|va|vai|que|voce|mais|o|a)\s+){0,6}"
        r"(?:trocar|troca|troque|mudar|muda|mude|alterar|altera|altere|aumentar|aumenta|aumente|"
        r"reduzir|reduza|registrar|registra|registre|criar|crie|gerar|gere)\b", normalize_text(text)))


def checked_feature_load(root, metadata):
    root = root.resolve()
    path = (root / metadata["file"]).resolve()
    if not path.is_relative_to(root) or file_sha256(path) != metadata["sha256"]:
        raise ValueError("Feature path/hash mismatch")
    value = joblib.load(path)
    if not isinstance(value, CorrectedFeatures):
        raise TypeError("Unexpected feature artifact")
    return value


def confidence_allowed(policy, label, margin):
    limit = policy.get("margin_threshold")
    supported = policy.get("validation_label_support", {}).get(label, 0)
    return bool(limit is not None and margin >= limit and
                supported >= policy.get("minimum_label_validation_support", 5))


class CorrectedPredictor:
    def __init__(self, ai_root, selection):
        self.ai_root, self.selection = ai_root, selection
        self.classes, self.risk_classes = selection["intent_classes"], selection["risk_classes"]
        if file_sha256(ai_root / "data/releases/1.8.0/manifest.json") != selection["dataset_manifest_sha256"]:
            raise ValueError("Corrected dataset manifest mismatch")
        self.candidates = {}
        for family, metadata in selection["candidate_manifests"].items():
            if family not in {"classical", "neural"}:
                raise ValueError("Unknown model family")
            version = "1.8.0" if family == "classical" else "1.8.1"
            root = ai_root / f"artifacts/baseline/{version}"
            path = root / "candidate_selection.json"
            if file_sha256(path) != metadata["sha256"]:
                raise ValueError("Candidate manifest changed after selection")
            self.candidates[family] = json.loads(path.read_text("utf-8"))
        self.cpu_models, self.neural_models = {}, {}
        self.features = self.encoder = self.tokenizer = None
        if "classical" in selection["chosen"].values():
            root = ai_root / "artifacts/baseline/1.8.0"
            metadata = self.candidates["classical"]
            assert_compatible_runtime(metadata["runtime"])
            self.features = checked_feature_load(root, metadata["features"])
            self.encoder = LocalSemanticEncoder(ai_root / "artifacts/encoders/multilingual-minilm")
            for task, family in selection["chosen"].items():
                if family == "classical":
                    self.cpu_models[task] = load_corrected_payload(root, metadata["models"][task])
        if "neural" in selection["chosen"].values():
            import torch
            from transformers import AutoTokenizer
            from evolv_nlp.corrected_neural import checked_weights, load_model

            torch.set_num_threads(2)
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            weights, _ = checked_weights(ai_root)
            self.tokenizer = AutoTokenizer.from_pretrained(weights, local_files_only=True, trust_remote_code=False)
            for task, family in selection["chosen"].items():
                if family == "neural":
                    self.neural_models[task] = load_model(ai_root, self.candidates["neural"], task, self.device)

    def policy(self):
        if "intent" in self.cpu_models:
            return self.cpu_models["intent"]["confidence_policy"]
        return self.candidates["neural"]["winners"]["intent"]["confidence_policy"]

    def risk_thresholds(self):
        if "risk" in self.cpu_models:
            return np.asarray(self.cpu_models["risk"]["thresholds"])
        return np.asarray(self.candidates["neural"]["winners"]["risk"]["thresholds"])

    def scores(self, texts):
        output = {}
        if self.cpu_models:
            embedded = self.encoder.encode(texts)
            with threadpool_limits(limits=2):
                views = self.features.transform(texts, embedded)
                for task, payload in self.cpu_models.items():
                    output[task] = probabilities(payload, views)
        if self.neural_models:
            from evolv_nlp.corrected_neural import tokenize
            from evolv_nlp.neural_review import predict_logits

            encoded = tokenize(self.tokenizer, texts)
            for task, model in self.neural_models.items():
                intent, risk = predict_logits(model, encoded, self.device, batch_size=24)
                output[task] = softmax(intent, axis=1) if task == "intent" else risk
        return output


class CorrectedCoachPipeline(ReviewedCoachPipeline):
    model_version = VERSION

    def __init__(self, ai_root: Path):
        self.ai_root = ai_root
        root = ai_root / f"artifacts/baseline/{VERSION}"
        manifest = json.loads((root / "manifest.json").read_text("utf-8"))
        frozen_path = root / "selection_frozen.json"
        if file_sha256(frozen_path) != manifest["selection_frozen_sha256"]:
            raise ValueError("Selected model contract changed")
        selection = json.loads(frozen_path.read_text("utf-8"))
        self.predictor = CorrectedPredictor(ai_root, selection)
        self._load_domain(ai_root)

    def analyze(self, text, context="", reference_date=None, pending_action=None):
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("Mensagem deve ter entre 1 e 8000 caracteres")
        if not isinstance(context, str) or len(context) > 16000:
            raise ValueError("Contexto deve ter no maximo 16000 caracteres")
        message, prior = review_text(text), review_text(context)
        scores = self.predictor.scores([model_text(message.minimized_text, prior.minimized_text)])
        ranking = np.argsort(scores["intent"][0])[::-1]
        classes = self.predictor.classes
        label = classes[int(ranking[0])]
        margin = float(scores["intent"][0, ranking[0]] - scores["intent"][0, ranking[1]])
        intent = {"label": label, "margin": margin,
            "confident": confidence_allowed(self.predictor.policy(), label, margin),
            "is_calibrated_probability": False,
            "alternatives": [{"label": classes[int(i)], "score": float(scores["intent"][0, i])} for i in ranking[:3]]}
        model_risks = [label for label, score, limit in zip(self.predictor.risk_classes, scores["risk"][0],
                       self.predictor.risk_thresholds()) if score >= limit]
        result = self._compose(text, reference_date, pending_action, intent, model_risks)
        if result["route"] == "draft_for_confirmation" and negated_plan_request(text):
            result["route"] = "clarify"
            result["blocked_proposal_reason"] = "negated_or_mixed_change_request"
        result["schema_version"] = "1.5.0"
        result["dataset_version"] = "1.8.0"
        result["component_families"] = self.predictor.selection["chosen"]
        result["intent"]["low_support_labels_require_clarification"] = True
        return result

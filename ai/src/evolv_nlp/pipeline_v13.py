from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from evolv_nlp.baseline import assert_compatible_runtime, classify, load_trusted_model
from evolv_nlp.entities import load_entity_catalog, normalize_text
from evolv_nlp.entities_v12 import extract_entities
from evolv_nlp.pipeline import STATUS_BY_ROUTE, confidence_payload, load_taxonomy
from evolv_nlp.risk_rules_v12 import detect_risks
from evolv_nlp.topics import load_topic_rules, load_topics, match_topics


class ContextCoachPipeline:
    """Opt-in PT-BR analysis; no API, model generation or Planner writes."""

    def __init__(self, ai_root: Path, baseline_version: str = "1.3.0"):
        if baseline_version not in {"1.2.0", "1.3.0"}:
            raise ValueError("Versao experimental desconhecida")
        self.baseline_version = baseline_version
        output = ai_root / f"artifacts/baseline/{baseline_version}"
        manifest = json.loads((output / "manifest.json").read_text("utf-8"))
        if manifest.get("artifact_version") != baseline_version:
            raise ValueError("Manifesto experimental incompativel")
        assert_compatible_runtime(manifest["dependencies"])
        models = {}
        for task, metadata in manifest["model_artifacts"].items():
            if Path(metadata["file"]).name != metadata["file"]:
                raise ValueError("Caminho de artefato invalido")
            models[task] = load_trusted_model(output / metadata["file"], metadata["sha256"])
        policy_meta = manifest["reports"]["policy"]
        if Path(policy_meta["file"]).name != policy_meta["file"]:
            raise ValueError("Caminho de politica invalido")
        from evolv_nlp.dataset import file_sha256
        if file_sha256(output / policy_meta["file"]) != policy_meta["sha256"]:
            raise ValueError("Politica de confianca alterada")
        self.models = models
        self.policy = json.loads((output / policy_meta["file"]).read_text("utf-8"))
        self.catalog = load_entity_catalog(ai_root / "data/catalogs/entity_catalogs.v1.json")
        self.intents = load_taxonomy(ai_root / "data/taxonomy/intents.v1.json", "intents")
        self.risks = load_taxonomy(ai_root / "data/taxonomy/risks.v1.json", "risks")
        extension = json.loads((ai_root / "data/taxonomy/expansion.v1.1.json").read_text("utf-8"))
        self.intents.update({r["id"]: r for r in extension["intents"]})
        self.risks.update({r["id"]: r for r in extension["risks"]})
        if baseline_version == "1.3.0":
            from evolv_nlp.entities_v13 import load_catalog
            self.catalog = load_catalog(ai_root)
            extension = json.loads((ai_root / "data/taxonomy/expansion.v1.2.json").read_text("utf-8"))
            self.intents.update({r["id"]: r for r in extension["intents"]})
            self.risks.update({r["id"]: r for r in extension["risks"]})
        _, self.topics = load_topics(ai_root / "data/taxonomy/topics.v1.json")
        self.topic_rules = load_topic_rules(ai_root / "data/pipeline/topic_rules.v1.json", set(self.topics))

    def analyze(self, text: str, reference_date: date) -> dict[str, Any]:
        if not isinstance(text, str) or not text.strip() or len(text) > 8_000:
            raise ValueError("Mensagem deve ter entre 1 e 8000 caracteres")
        if not isinstance(reference_date, date):
            raise ValueError("Data de referencia deve ser explicita")
        intent_result = classify(self.models["intent_classification"], text)
        risk_result = classify(self.models["risk_classification"], text)
        confidence = self.policy["intent_classification"]
        intent = confidence_payload(intent_result, confidence["minimum_confidence"], confidence["minimum_margin"])
        risk_confidence = self.policy["risk_classification"]
        risk = confidence_payload(risk_result, risk_confidence["minimum_confidence"], risk_confidence["minimum_margin"])
        if getattr(self, "baseline_version", "1.2.0") == "1.3.0":
            from evolv_nlp.entities_v13 import extract_entities as extract_current
            from evolv_nlp.risk_rules_v13 import detect_risks as detect_current
        else:
            extract_current, detect_current = extract_entities, detect_risks
        signals = detect_current(text)
        extraction = extract_current(text, self.catalog, reference_date)
        entities = [e.to_dict() for e in extraction.entities]
        usable_types = {e["entity_type"] for e in entities if not e["attributes"].get("negated")
                        and not e["attributes"].get("requires_context")}
        definition = self.intents[intent["label"]]
        missing = [e for e in definition.get("required_entities", []) if e not in usable_types]
        reasons, clarification = [], None
        route = definition["route"]
        status = STATUS_BY_ROUTE.get(route, "answer_candidate")
        if status == "answer":
            status = "answer_candidate"
        if signals.risks:
            order = {"emergency": 3, "high": 2, "medium": 1, "none": 0}
            primary = max(signals.risks, key=lambda label: order[self.risks[label]["severity"]])
            route, status = self.risks[primary]["route"], "safety_review"
            reasons.append("explicit_risk_signals")
        elif risk["label"] != "none":
            route, status = "clarify", "clarify"
            reasons.append("model_risk_requires_review")
            clarification = "Pode explicar um pouco mais o contexto dessa duvida?"
        elif not intent["accepted"] or missing:
            route, status = "clarify", "clarify"
            reasons.append("low_intent_confidence" if not intent["accepted"] else "missing_required_entities")
            clarification = "Voce quer uma explicacao ou uma proposta de mudanca? Pode dar mais um detalhe?"
        if any(e["entity_type"] == "ambiguous_weight" for e in entities) and status != "safety_review":
            route, status = "clarify", "clarify"
            reasons.append("ambiguous_weight")
            clarification = "Esse peso e sua carga no exercicio, seu peso corporal ou uma quantidade de alimento?"
        if re.search(r"\b(?:how do i|can you|should i|what is|i want to)\b", text, re.I) and status != "safety_review":
            route, status = "unsupported_language", "clarify"
            reasons.append("english_signal_not_a_reliable_language_detector")
            clarification = "Esta versao do NLP foi avaliada apenas em portugues. Pode escrever em portugues?"
        parent = definition.get("parent", intent["label"])
        topics = match_topics(text, self.topics, self.topic_rules, parent, usable_types)
        proposal = None
        from evolv_nlp.response_policy import response_scope
        scope = response_scope(text)
        if scope["planner_proposal_blocked"]:
            if status != "safety_review":
                route = "emergency_guidance" if scope["mode"] == "urgent_referral" else "cautious_response"
            status = "safety_review"
            reasons.append("response_scope_boundary")
            clarification = None
        if route == "planner_preview":
            negated_change = re.search(
                r"\b(?:nao|n)\s+(?:(?:quero|vou|preciso|posso|devo)\s+)?"
                r"(?:troca(?:r)?|troque|muda(?:r)?|mude|altera(?:r)?|altere|"
                r"move(?:r)?|mova|aumenta(?:r)?|aumente|reduz(?:ir|a)|"
                r"adiciona(?:r)?|adicione|retira(?:r)?|retire|registra(?:r)?|registre)\b",
                normalize_text(text),
            )
            if negated_change:
                route, status = "clarify", "clarify"
                reasons.append("negated_change_request")
                clarification = "Entendi que voce nao quer essa mudanca. Quer apenas uma explicacao?"
            elif not risk["accepted"]:
                route, status = "clarify", "clarify"
                reasons.append("low_risk_confidence_for_proposal")
                clarification = "Antes de montar a proposta, pode esclarecer o contexto da mudanca?"
            else:
                status = "planner_preview"
                proposal = {"action": definition.get("planner_action"), "arguments": entities,
                            "requires_confirmation": True, "writes_allowed": False}
        return {
            "pipeline_version": "1.2.0-development", "model_version": getattr(self, "baseline_version", "1.2.0"),
            "supported_language": "pt-BR", "status": "experimental_not_default",
            "decision": {"status": status, "route": route, "reasons": reasons},
            "intent": {**intent, "parent": parent},
            "risk_model": risk, "risk_rules": signals.to_dict(),
            "safety_assessment": "unknown_not_medical_clearance",
            "entities": entities, "missing_required_entities": missing,
            "topics": topics,
            "clarification": clarification, "proposal": proposal,
            "writes_allowed": False, "requires_confirmation": True,
            "uses_lm": False, "stores_message": False,
            "response_scope": scope,
        }



from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from evolv_nlp import BASELINE_VERSION, PIPELINE_VERSION
from evolv_nlp.baseline import (
    ClassificationResult,
    assert_compatible_runtime,
    classify,
    load_trusted_model,
)
from evolv_nlp.entities import EntityCatalog, extract_entities, load_entity_catalog
from evolv_nlp.topics import (
    TopicDefinition,
    load_topic_rules,
    load_topics,
    match_topics,
)


STATUS_BY_ROUTE = {
    "knowledge_answer": "answer",
    "plan_read": "answer",
    "planner_preview": "planner_preview",
    "planner_confirmation": "clarify",
    "planner_rejection": "clarify",
    "planner_undo": "clarify",
    "clarify": "clarify",
    "conversation": "conversation",
    "unsupported_modality": "unsupported",
    "out_of_scope": "out_of_scope",
}

ENTITY_QUESTIONS = {
    "exercise": "Qual exercicio voce quer usar ou alterar?",
    "source_date": "Qual treino ou data de origem voce quer mover?",
    "target_date": "Para qual data voce quer fazer a mudanca?",
    "food": "Qual alimento voce quer usar ou alterar?",
    "activity_type": "O dia sera descanso, musculacao, cardio ou atividade mista?",
    "preference": "Qual preferencia voce quer que eu guarde?",
    "change_direction": "Voce quer aumentar ou reduzir?",
    "training_split": "Qual divisao de treino voce quer usar?",
    "goal": "Qual objetivo voce quer definir?",
    "load": "Qual carga foi utilizada?",
    "pending_action": "Qual proposta pendente voce quer confirmar ou rejeitar?",
    "previous_action": "Qual alteracao anterior voce quer desfazer?",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Objeto JSON esperado em {path}")
    return payload


def load_taxonomy(path: Path, collection: str) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    rows = payload.get(collection)
    if not isinstance(rows, list):
        raise ValueError(f"Colecao ausente em {path}: {collection}")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = row.get("id")
        if not isinstance(row_id, str) or row_id in result:
            raise ValueError(f"ID invalido ou duplicado em {path}: {row_id}")
        result[row_id] = row
    return result


def confidence_payload(
    result: ClassificationResult,
    minimum_confidence: float,
    minimum_margin: float,
) -> dict[str, Any]:
    runner_up = result.alternatives[1].confidence if len(result.alternatives) > 1 else 0.0
    margin = round(result.confidence - runner_up, 6)
    accepted = result.confidence >= minimum_confidence and margin >= minimum_margin
    return {
        "label": result.label,
        "confidence": result.confidence,
        "margin": margin,
        "accepted": accepted,
        "thresholds": {
            "minimum_confidence": minimum_confidence,
            "minimum_margin": minimum_margin,
        },
        "alternatives": [asdict(item) for item in result.alternatives],
        "probability_warning": "Uncalibrated model score; not a real-world probability.",
    }


class CoachPipeline:
    def __init__(
        self,
        intent_model: Any,
        risk_model: Any,
        entity_catalog: EntityCatalog,
        intents: dict[str, dict[str, Any]],
        risks: dict[str, dict[str, Any]],
        topics: dict[str, TopicDefinition],
        topic_rules: dict[str, Any],
        policy: dict[str, Any],
    ) -> None:
        self.intent_model = intent_model
        self.risk_model = risk_model
        self.entity_catalog = entity_catalog
        self.intents = intents
        self.risks = risks
        self.topics = topics
        self.topic_rules = topic_rules
        self.policy = policy
        if policy.get("version") != PIPELINE_VERSION:
            raise ValueError("Versao da politica incompativel com a pipeline")

    def analyze(self, text: str, reference_date: date) -> dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("A mensagem nao pode estar vazia")
        maximum = int(self.policy["limits"]["maximum_text_characters"])
        if len(text) > maximum:
            raise ValueError(f"A mensagem excede o limite de {maximum} caracteres")

        intent_result = classify(
            self.intent_model, text, top_k=int(self.policy["intent"]["top_k"])
        )
        risk_result = classify(
            self.risk_model, text, top_k=int(self.policy["risk"]["top_k"])
        )
        intent_confidence = confidence_payload(
            intent_result,
            float(self.policy["intent"]["minimum_confidence"]),
            float(self.policy["intent"]["minimum_margin"]),
        )
        risk_definition = self.risks[risk_result.label]
        risk_thresholds = self.policy["risk"]
        if risk_result.label == "none":
            risk_confidence = confidence_payload(
                risk_result,
                float(risk_thresholds["safe_minimum_confidence"]),
                float(risk_thresholds["safe_minimum_margin"]),
            )
        else:
            risk_confidence = confidence_payload(
                risk_result,
                float(risk_thresholds["escalate_minimum_confidence"]),
                float(risk_thresholds["escalate_minimum_margin"]),
            )
        risk_confidence.update(
            {
                "severity": risk_definition["severity"],
                "route": risk_definition["route"],
                "response_rule": risk_definition.get("response_rule"),
                "escalated": risk_result.label != "none"
                and risk_confidence["accepted"],
                "review_required": risk_result.label != "none"
                and not risk_confidence["accepted"],
            }
        )

        extraction = extract_entities(text, self.entity_catalog, reference_date)
        entities = [
            {
                "entity_type": entity.entity_type,
                "text": entity.text,
                "value": entity.value,
                "start": entity.start,
                "end": entity.end,
                "source": entity.source,
                "attributes": entity.attributes,
            }
            for entity in extraction.entities
        ]
        entity_types = {entity["entity_type"] for entity in entities}
        intent_definition = self.intents[intent_result.label]
        required_entities = list(intent_definition.get("required_entities", []))
        missing_required = [
            entity_type
            for entity_type in required_entities
            if entity_type not in entity_types
        ]
        detected_topics = match_topics(
            text,
            self.topics,
            self.topic_rules,
            intent_result.label,
            entity_types,
        )

        status, route, reasons = self._decide(
            intent_confidence,
            risk_confidence,
            intent_definition,
            missing_required,
        )
        clarification = self._clarification(
            status,
            reasons,
            missing_required,
            intent_confidence,
            risk_confidence,
        )
        proposal = None
        if status == "planner_preview":
            proposal = {
                "action": intent_definition.get("planner_action"),
                "arguments": entities,
                "requires_confirmation": True,
                "writes_allowed": False,
            }

        return {
            "pipeline_version": PIPELINE_VERSION,
            "input": {
                "reference_date": reference_date.isoformat(),
                "character_count": len(text),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_stored": False,
            },
            "decision": {
                "status": status,
                "route": route,
                "reasons": reasons,
            },
            "intent": {
                **intent_confidence,
                "category": intent_definition["category"],
                "route": intent_definition["route"],
                "planner_action": intent_definition.get("planner_action"),
                "required_entities": required_entities,
                "missing_required_entities": missing_required,
            },
            "risk": risk_confidence,
            "entities": entities,
            "topics": detected_topics,
            "clarification": clarification,
            "planner_proposal": proposal,
            "guardrails": {
                "planner_writes_allowed": False,
                "planner_confirmation_required": True,
                "risk_overrides_intent": True,
                "medical_diagnosis_allowed": False,
                "confidence_calibrated": False,
            },
        }

    def _decide(
        self,
        intent: dict[str, Any],
        risk: dict[str, Any],
        intent_definition: dict[str, Any],
        missing_required: list[str],
    ) -> tuple[str, str, list[str]]:
        if risk["escalated"]:
            return "safety", risk["route"], ["accepted_risk_override"]
        if risk["review_required"]:
            return "clarify", "clarify", ["uncertain_risk_candidate"]
        if not intent["accepted"]:
            return "clarify", "clarify", ["low_intent_confidence"]
        if missing_required:
            return "clarify", "clarify", ["missing_required_entities"]
        route = str(intent_definition["route"])
        return STATUS_BY_ROUTE.get(route, "clarify"), route, ["accepted_intent"]

    def _clarification(
        self,
        status: str,
        reasons: list[str],
        missing_required: list[str],
        intent: dict[str, Any],
        risk: dict[str, Any],
    ) -> dict[str, Any] | None:
        if status != "clarify":
            return None
        if "uncertain_risk_candidate" in reasons:
            question = (
                "Antes de continuar, existe dor, reacao, uso de medicamento "
                "ou outro risco importante relacionado a esse pedido?"
            )
        elif missing_required:
            question = ENTITY_QUESTIONS.get(
                missing_required[0], "Pode informar o detalhe que ficou faltando?"
            )
        else:
            question = (
                "Voce quer tirar uma duvida, consultar seu plano ou pedir uma mudanca?"
            )
        return {
            "reason": reasons[0],
            "question": question,
            "candidate_intents": [
                item["label"] for item in intent["alternatives"][:2]
            ],
            "risk_candidate": risk["label"] if risk["label"] != "none" else None,
        }


def load_pipeline(ai_root: Path) -> CoachPipeline:
    artifact_root = ai_root / "artifacts" / "baseline" / BASELINE_VERSION
    manifest = load_json(artifact_root / "manifest.json")
    assert_compatible_runtime(manifest["dependencies"])
    models = {
        task: load_trusted_model(
            artifact_root / value["file"], value["sha256"]
        )
        for task, value in manifest["model_artifacts"].items()
    }
    topic_version, topics = load_topics(
        ai_root / "data" / "taxonomy" / "topics.v1.json"
    )
    if topic_version != "1.0.0":
        raise ValueError("Versao de topicos incompativel")
    topic_rules = load_topic_rules(
        ai_root / "data" / "pipeline" / "topic_rules.v1.json", set(topics)
    )
    return CoachPipeline(
        intent_model=models["intent_classification"],
        risk_model=models["risk_classification"],
        entity_catalog=load_entity_catalog(
            ai_root / "data" / "catalogs" / "entity_catalogs.v1.json"
        ),
        intents=load_taxonomy(
            ai_root / "data" / "taxonomy" / "intents.v1.json", "intents"
        ),
        risks=load_taxonomy(
            ai_root / "data" / "taxonomy" / "risks.v1.json", "risks"
        ),
        topics=topics,
        topic_rules=topic_rules,
        policy=load_json(
            ai_root / "data" / "pipeline" / "confidence_policy.v1.json"
        ),
    )

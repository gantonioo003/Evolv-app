from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_ROOT = AI_ROOT / "data" / "taxonomy"
RESEARCH_ROOT = AI_ROOT / "data" / "research"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

ALLOWED_CATEGORIES = {"question", "request", "conversation"}
ALLOWED_STATUSES = {
    "answer_only",
    "implemented_contract",
    "planned_contract",
    "implemented_operation",
    "conversation",
}
ALLOWED_SEVERITIES = {"none", "medium", "high", "emergency"}
ALLOWED_CAPABILITY_STATUSES = {"implemented", "planned", "answer_only"}
ALLOWED_SOURCE_TYPES = {
    "private_conversation",
    "public_forum",
    "public_dataset",
    "research_dataset",
}
ALLOWED_INGESTION_STATUSES = {
    "patterns_only",
    "taxonomy_discovery_only",
    "candidate_requires_content_audit",
    "methodology_reference_only",
}
IMPLEMENTED_PLANNER_ACTIONS = {
    "move_workout_day",
    "replace_exercise",
    "replace_meal_item",
    "set_day_activity",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_unique_ids(kind: str, items: list[dict[str, Any]], errors: list[str]) -> None:
    seen: set[str] = set()
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not ID_PATTERN.fullmatch(item_id):
            errors.append(f"{kind} com ID invalido: {item_id!r}")
            continue
        if item_id in seen:
            errors.append(f"{kind} duplicado: {item_id}")
        seen.add(item_id)


def validate() -> list[str]:
    errors: list[str] = []
    intents = load_json(TAXONOMY_ROOT / "intents.v1.json")["intents"]
    entities = load_json(TAXONOMY_ROOT / "entities.v1.json")["entities"]
    risks = load_json(TAXONOMY_ROOT / "risks.v1.json")["risks"]
    hierarchy = load_json(TAXONOMY_ROOT / "hierarchy.v1.json")
    topics = load_json(TAXONOMY_ROOT / "topics.v1.json")["topics"]
    capabilities = load_json(TAXONOMY_ROOT / "capabilities.v1.json")["capabilities"]
    research_sources = load_json(RESEARCH_ROOT / "source_catalog.v1.json")["sources"]

    validate_unique_ids("intencao", intents, errors)
    validate_unique_ids("entidade", entities, errors)
    validate_unique_ids("risco", risks, errors)
    validate_unique_ids("dominio", hierarchy["domains"], errors)
    validate_unique_ids("familia", hierarchy["families"], errors)
    validate_unique_ids("topico", topics, errors)
    validate_unique_ids("capacidade", capabilities, errors)
    validate_unique_ids("fonte de pesquisa", research_sources, errors)

    intent_ids = {intent["id"] for intent in intents}
    domain_ids = {domain["id"] for domain in hierarchy["domains"]}
    family_ids = {family["id"] for family in hierarchy["families"]}

    entity_ids = {entity["id"] for entity in entities}
    for entity in entities:
        if not entity.get("description"):
            errors.append(f"Entidade sem descricao: {entity['id']}")
        if not entity.get("examples"):
            errors.append(f"Entidade sem exemplos: {entity['id']}")

    for intent in intents:
        intent_id = intent["id"]
        category = intent.get("category")
        status = intent.get("implementation_status")
        route = intent.get("route")
        planner_action = intent.get("planner_action")
        required = set(intent.get("required_entities", []))
        optional = set(intent.get("optional_entities", []))

        if category not in ALLOWED_CATEGORIES:
            errors.append(f"Categoria invalida em {intent_id}: {category}")
        if status not in ALLOWED_STATUSES:
            errors.append(f"Status invalido em {intent_id}: {status}")
        if not route:
            errors.append(f"Rota ausente em {intent_id}")
        if not intent.get("description"):
            errors.append(f"Descricao ausente em {intent_id}")
        if required & optional:
            errors.append(
                f"{intent_id} repete entidades obrigatorias como opcionais: "
                f"{sorted(required & optional)}"
            )
        unknown_entities = (required | optional) - entity_ids
        if unknown_entities:
            errors.append(
                f"{intent_id} referencia entidades desconhecidas: {sorted(unknown_entities)}"
            )

        if category == "question" and planner_action is not None:
            errors.append(f"Pergunta {intent_id} nao pode executar planner_action")
        if status == "implemented_contract" and planner_action not in IMPLEMENTED_PLANNER_ACTIONS:
            errors.append(
                f"Contrato marcado como implementado nao existe no backend: {intent_id}"
            )
        if status == "planned_contract" and not planner_action:
            errors.append(f"Contrato planejado sem planner_action: {intent_id}")
        if route == "planner_preview" and category != "request":
            errors.append(f"Somente pedidos podem usar planner_preview: {intent_id}")

    if {intent["category"] for intent in intents} != ALLOWED_CATEGORIES:
        errors.append("A taxonomia precisa cobrir question, request e conversation")

    assignments = hierarchy.get("intent_assignments", [])
    assignment_ids = [assignment.get("intent_id") for assignment in assignments]
    duplicate_assignments = {
        intent_id for intent_id in assignment_ids if assignment_ids.count(intent_id) > 1
    }
    if duplicate_assignments:
        errors.append(
            f"Intencoes repetidas na hierarquia: {sorted(duplicate_assignments)}"
        )
    if set(assignment_ids) != intent_ids:
        errors.append(
            "Hierarquia nao cobre exatamente as intencoes: "
            f"faltando={sorted(intent_ids - set(assignment_ids))}, "
            f"extras={sorted(set(assignment_ids) - intent_ids)}"
        )
    for assignment in assignments:
        intent_id = assignment.get("intent_id")
        domain = assignment.get("domain")
        family = assignment.get("family")
        secondary_domains = set(assignment.get("secondary_domains", []))
        if domain not in domain_ids:
            errors.append(f"Dominio desconhecido em {intent_id}: {domain}")
        if family not in family_ids:
            errors.append(f"Familia desconhecida em {intent_id}: {family}")
        unknown_secondary = secondary_domains - domain_ids
        if unknown_secondary:
            errors.append(
                f"Dominios secundarios desconhecidos em {intent_id}: "
                f"{sorted(unknown_secondary)}"
            )
        if domain in secondary_domains:
            errors.append(f"{intent_id} repete o dominio principal como secundario")

    topic_domains: set[str] = set()
    for topic in topics:
        topic_id = topic["id"]
        domain = topic.get("domain")
        topic_domains.add(domain)
        if domain not in domain_ids:
            errors.append(f"Topico {topic_id} usa dominio desconhecido: {domain}")
        if not topic.get("description") or not topic.get("aliases"):
            errors.append(f"Topico incompleto: {topic_id}")
    expected_topic_domains = {"training", "nutrition", "recovery", "progress", "product", "conversation"}
    if not expected_topic_domains <= topic_domains:
        errors.append(
            "Topicos nao cobrem dominios necessarios: "
            f"{sorted(expected_topic_domains - topic_domains)}"
        )

    for capability in capabilities:
        capability_id = capability["id"]
        domain = capability.get("domain")
        status = capability.get("implementation_status")
        parent_intents = set(capability.get("parent_intents", []))
        planner_action = capability.get("planner_action")
        if domain not in domain_ids:
            errors.append(
                f"Capacidade {capability_id} usa dominio desconhecido: {domain}"
            )
        if status not in ALLOWED_CAPABILITY_STATUSES:
            errors.append(f"Status invalido em {capability_id}: {status}")
        if not parent_intents:
            errors.append(f"Capacidade sem intencao pai: {capability_id}")
        unknown_parents = parent_intents - intent_ids
        if unknown_parents:
            errors.append(
                f"Capacidade {capability_id} referencia intencoes desconhecidas: "
                f"{sorted(unknown_parents)}"
            )
        if not isinstance(capability.get("confirmation_required"), bool):
            errors.append(f"Capacidade sem regra de confirmacao: {capability_id}")
        if planner_action and planner_action not in IMPLEMENTED_PLANNER_ACTIONS:
            errors.append(
                f"Capacidade {capability_id} afirma planner_action inexistente: "
                f"{planner_action}"
            )
        if planner_action and status != "implemented":
            errors.append(
                f"Capacidade {capability_id} tem planner_action mas nao esta implementada"
            )

    for risk in risks:
        risk_id = risk["id"]
        severity = risk.get("severity")
        if severity not in ALLOWED_SEVERITIES:
            errors.append(f"Severidade invalida em {risk_id}: {severity}")
        if not risk.get("route") or not risk.get("description"):
            errors.append(f"Risco incompleto: {risk_id}")
        if risk_id == "none":
            if severity != "none" or risk["route"] != "normal":
                errors.append("Risco none deve ter severity none e route normal")
        elif not risk.get("response_rule"):
            errors.append(f"Risco sem regra de resposta: {risk_id}")

    for source in research_sources:
        source_id = source["id"]
        source_type = source.get("type")
        ingestion_status = source.get("ingestion_status")
        if source_type not in ALLOWED_SOURCE_TYPES:
            errors.append(f"Tipo de fonte de pesquisa invalido em {source_id}: {source_type}")
        if ingestion_status not in ALLOWED_INGESTION_STATUSES:
            errors.append(
                f"Status de ingestao invalido em {source_id}: {ingestion_status}"
            )
        if not source.get("license"):
            errors.append(f"Fonte de pesquisa sem licenca registrada: {source_id}")
        if not source.get("allowed_use") or not source.get("prohibited_use"):
            errors.append(f"Fonte de pesquisa sem politica de uso: {source_id}")
        if not source.get("observed_patterns"):
            errors.append(f"Fonte de pesquisa sem padroes registrados: {source_id}")
        for url in source.get("urls", []):
            if not url.startswith("https://"):
                errors.append(f"URL insegura em {source_id}: {url}")
        if source_type in {"private_conversation", "public_forum"}:
            if source.get("factual_authority") is not False:
                errors.append(
                    f"Conversa ou forum nao pode ser autoridade factual: {source_id}"
                )

    annotation_guide = TAXONOMY_ROOT / "annotation-guidelines.md"
    if not annotation_guide.exists():
        errors.append("Guia de anotacao ausente")

    return errors


if __name__ == "__main__":
    validation_errors = validate()
    if validation_errors:
        print("Falhas na taxonomia:")
        for error in validation_errors:
            print(f"- {error}")
        sys.exit(1)

    intents = load_json(TAXONOMY_ROOT / "intents.v1.json")["intents"]
    entities = load_json(TAXONOMY_ROOT / "entities.v1.json")["entities"]
    risks = load_json(TAXONOMY_ROOT / "risks.v1.json")["risks"]
    topics = load_json(TAXONOMY_ROOT / "topics.v1.json")["topics"]
    capabilities = load_json(TAXONOMY_ROOT / "capabilities.v1.json")["capabilities"]
    print(
        "Taxonomia valida: "
        f"{len(intents)} intencoes, {len(topics)} topicos, "
        f"{len(entities)} entidades, {len(risks)} riscos e "
        f"{len(capabilities)} capacidades."
    )

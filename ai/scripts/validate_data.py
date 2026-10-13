from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_ROOT.parent
DATA_ROOT = AI_ROOT / "data"
SPLITS = ("train", "validation", "test")
DATASET_VERSION = "1.2.0"
IMPLEMENTED_ACTIONS = {
    "move_workout_day",
    "replace_exercise",
    "replace_meal_item",
    "set_day_activity",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"JSON invalido em {path}:{line_number}: {error}") from error
    return rows


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def duplicate_values(values: list[str]) -> set[str]:
    counts = Counter(values)
    return {value for value, count in counts.items() if count > 1}


def validate_taxonomies(
    errors: list[str],
) -> tuple[set[str], set[str], set[str], set[str]]:
    intents = load_json(DATA_ROOT / "taxonomy" / "intents.v1.json")["intents"]
    entities = load_json(DATA_ROOT / "taxonomy" / "entities.v1.json")["entities"]
    risks = load_json(DATA_ROOT / "taxonomy" / "risks.v1.json")["risks"]
    topics = load_json(DATA_ROOT / "taxonomy" / "topics.v1.json")["topics"]

    intent_ids = [item["id"] for item in intents]
    entity_ids = [item["id"] for item in entities]
    risk_ids = [item["id"] for item in risks]
    topic_ids = [item["id"] for item in topics]

    for name, values in (
        ("intencao", intent_ids),
        ("entidade", entity_ids),
        ("risco", risk_ids),
        ("topico", topic_ids),
    ):
        duplicates = duplicate_values(values)
        if duplicates:
            errors.append(f"IDs duplicados em {name}: {sorted(duplicates)}")

    entity_set = set(entity_ids)
    for intent in intents:
        referenced = set(intent["required_entities"] + intent["optional_entities"])
        unknown = referenced - entity_set
        if unknown:
            errors.append(f"{intent['id']} referencia entidades desconhecidas: {sorted(unknown)}")
        if intent["implementation_status"] == "implemented_contract":
            if intent["planner_action"] not in IMPLEMENTED_ACTIONS:
                errors.append(
                    f"{intent['id']} afirma contrato implementado invalido: {intent['planner_action']}"
                )

    return set(intent_ids), entity_set, set(risk_ids), set(topic_ids)


def validate_source_examples(
    intent_ids: set[str],
    risk_ids: set[str],
    topic_ids: set[str],
    entity_ids: set[str],
    errors: list[str],
) -> None:
    intent_source = load_json(DATA_ROOT / "source" / "intent_examples.v1.json")
    risk_source = load_json(DATA_ROOT / "source" / "risk_examples.v1.json")
    real_source = load_json(DATA_ROOT / "source" / "real_pattern_examples.v1.json")
    challenge_source = load_json(DATA_ROOT / "source" / "ambiguity_examples.v1.json")
    research_sources = load_json(
        DATA_ROOT / "research" / "source_catalog.v1.json"
    )["sources"]
    intent_map = intent_source["examples_by_intent"]
    risk_map = risk_source["examples_by_risk"]
    real_intent_map = real_source["intent_examples_by_label"]
    real_risk_map = real_source["risk_examples_by_label"]
    research_source_ids = {item["id"] for item in research_sources}

    if real_source.get("version") != "1.1.0":
        errors.append("Versao incorreta dos padroes reais reescritos")
    if challenge_source.get("version") != "1.1.0":
        errors.append("Versao incorreta do conjunto de desafio")

    if set(intent_map) != intent_ids:
        errors.append(
            "Rotulos do dataset de intencao diferem da taxonomia: "
            f"faltando={sorted(intent_ids - set(intent_map))}, "
            f"extras={sorted(set(intent_map) - intent_ids)}"
        )
    if set(risk_map) != risk_ids:
        errors.append(
            "Rotulos do dataset de risco diferem da taxonomia: "
            f"faltando={sorted(risk_ids - set(risk_map))}, "
            f"extras={sorted(set(risk_map) - risk_ids)}"
        )
    if set(real_intent_map) != intent_ids:
        errors.append(
            "Rotulos dos padroes reais de intencao diferem da taxonomia: "
            f"faltando={sorted(intent_ids - set(real_intent_map))}, "
            f"extras={sorted(set(real_intent_map) - intent_ids)}"
        )
    if set(real_risk_map) != risk_ids:
        errors.append(
            "Rotulos dos padroes reais de risco diferem da taxonomia: "
            f"faltando={sorted(risk_ids - set(real_risk_map))}, "
            f"extras={sorted(set(real_risk_map) - risk_ids)}"
        )

    allowed_styles = set(real_source["allowed_styles"])
    allowed_difficulties = set(real_source["allowed_difficulties"])
    for task_name, mapping, real_mapping in (
        ("intencao", intent_map, real_intent_map),
        ("risco", risk_map, real_risk_map),
    ):
        all_normalized: list[str] = []
        for label, examples in mapping.items():
            if len(examples) < 6:
                errors.append(f"{task_name} {label} tem menos de 6 exemplos")
            if any(not isinstance(text, str) or len(text.strip()) < 3 for text in examples):
                errors.append(f"{task_name} {label} possui texto vazio ou invalido")
            all_normalized.extend(normalize_text(text) for text in examples)
        for label, examples in real_mapping.items():
            if len(examples) < 2:
                errors.append(
                    f"{task_name} {label} tem menos de 2 padroes reais reescritos"
                )
            if len(mapping.get(label, [])) + len(examples) < 8:
                errors.append(f"{task_name} {label} tem menos de 8 exemplos totais")
            for item in examples:
                text = item.get("text")
                if not isinstance(text, str) or len(text.strip()) < 3:
                    errors.append(
                        f"{task_name} {label} possui padrao real vazio ou invalido"
                    )
                    continue
                all_normalized.append(normalize_text(text))
                if item.get("style") not in allowed_styles:
                    errors.append(
                        f"Estilo invalido em {task_name} {label}: {item.get('style')}"
                    )
                if item.get("difficulty") not in allowed_difficulties:
                    errors.append(
                        f"Dificuldade invalida em {task_name} {label}: "
                        f"{item.get('difficulty')}"
                    )
                if item.get("source_id") not in research_source_ids:
                    errors.append(
                        f"Fonte desconhecida em {task_name} {label}: "
                        f"{item.get('source_id')}"
                    )
        duplicates = duplicate_values(all_normalized)
        if duplicates:
            errors.append(f"Textos duplicados no dataset de {task_name}: {sorted(duplicates)}")

    challenge_examples = challenge_source["examples"]
    challenge_ids = [item.get("id") for item in challenge_examples]
    if duplicate_values(challenge_ids):
        errors.append("Ha IDs duplicados no conjunto de desafio")
    challenge_texts = [normalize_text(item.get("text", "")) for item in challenge_examples]
    if duplicate_values(challenge_texts):
        errors.append("Ha textos duplicados no conjunto de desafio")
    if len(challenge_examples) < 30:
        errors.append("O conjunto de desafio precisa ter ao menos 30 casos")

    allowed_ambiguity_types = set(challenge_source["allowed_ambiguity_types"])
    allowed_behaviors = set(challenge_source["allowed_expected_behaviors"])
    observed_ambiguity_types: set[str] = set()
    observed_behaviors: set[str] = set()
    for item in challenge_examples:
        item_id = item.get("id")
        primary_intent = item.get("primary_intent")
        secondary_intents = set(item.get("secondary_intents", []))
        topics = set(item.get("topics", []))
        risks = set(item.get("risk_labels", []))
        missing_entities = set(item.get("missing_entities", []))
        ambiguity_type = item.get("ambiguity_type")
        expected_behavior = item.get("expected_behavior")
        observed_ambiguity_types.add(ambiguity_type)
        observed_behaviors.add(expected_behavior)

        if primary_intent not in intent_ids:
            errors.append(f"Intencao principal invalida em {item_id}: {primary_intent}")
        if primary_intent in secondary_intents:
            errors.append(f"Intencao principal repetida como secundaria em {item_id}")
        if secondary_intents - intent_ids:
            errors.append(
                f"Intencoes secundarias invalidas em {item_id}: "
                f"{sorted(secondary_intents - intent_ids)}"
            )
        if topics - topic_ids:
            errors.append(
                f"Topicos invalidos em {item_id}: {sorted(topics - topic_ids)}"
            )
        if not risks or risks - risk_ids:
            errors.append(
                f"Riscos invalidos em {item_id}: {sorted(risks - risk_ids)}"
            )
        if "none" in risks and len(risks) > 1:
            errors.append(f"Risco none combinado com outro risco em {item_id}")
        if missing_entities - entity_ids:
            errors.append(
                f"Entidades ausentes invalidas em {item_id}: "
                f"{sorted(missing_entities - entity_ids)}"
            )
        if ambiguity_type not in allowed_ambiguity_types:
            errors.append(f"Tipo de ambiguidade invalido em {item_id}")
        if expected_behavior not in allowed_behaviors:
            errors.append(f"Comportamento esperado invalido em {item_id}")
        if expected_behavior == "safety_response" and risks == {"none"}:
            errors.append(f"Resposta de seguranca sem risco em {item_id}")
        if item.get("requires_image") and primary_intent != "image_context_request":
            errors.append(f"Caso com imagem sem image_context_request em {item_id}")

    if observed_ambiguity_types != allowed_ambiguity_types:
        errors.append(
            "Conjunto de desafio nao cobre todos os tipos de ambiguidade: "
            f"{sorted(allowed_ambiguity_types - observed_ambiguity_types)}"
        )
    if observed_behaviors != allowed_behaviors:
        errors.append(
            "Conjunto de desafio nao cobre todos os comportamentos: "
            f"{sorted(allowed_behaviors - observed_behaviors)}"
        )


def validate_splits(
    expected_intents: set[str], expected_risks: set[str], errors: list[str]
) -> None:
    texts_by_task_and_split: dict[str, dict[str, set[str]]] = {
        "intent": {},
        "risk": {},
    }

    for split in SPLITS:
        for task, file_name, expected_labels in (
            ("intent", "intent_examples.jsonl", expected_intents),
            ("risk", "risk_examples.jsonl", expected_risks),
        ):
            path = DATA_ROOT / "splits" / split / file_name
            if not path.exists():
                errors.append(f"Split ausente: {path.relative_to(REPO_ROOT)}")
                continue
            rows = load_jsonl(path)
            labels = {row.get("label") for row in rows}
            if labels != expected_labels:
                errors.append(
                    f"{split}/{file_name} nao cobre todos os rotulos: "
                    f"faltando={sorted(expected_labels - labels)}"
                )
            texts_by_task_and_split[task][split] = {
                normalize_text(row["text"]) for row in rows
            }
            for row in rows:
                if row.get("dataset_version") != DATASET_VERSION:
                    errors.append(f"Versao incorreta em {path.name}: {row.get('id')}")
                if row.get("source_type") not in {
                    "synthetic_curated",
                    "real_pattern_rewrite",
                }:
                    errors.append(f"Origem invalida no split: {row.get('id')}")
                for field in ("style", "difficulty"):
                    if not row.get(field):
                        errors.append(f"Campo {field} ausente no split: {row.get('id')}")

    for task, splits in texts_by_task_and_split.items():
        if len(splits) != len(SPLITS):
            continue
        for index, left in enumerate(SPLITS):
            for right in SPLITS[index + 1 :]:
                overlap = splits[left] & splits[right]
                if overlap:
                    errors.append(
                        f"Vazamento em {task} entre {left} e {right}: {sorted(overlap)}"
                    )

    challenge_source = load_json(DATA_ROOT / "source" / "ambiguity_examples.v1.json")
    challenge_path = DATA_ROOT / "splits" / "challenge" / "ambiguity_examples.jsonl"
    if not challenge_path.exists():
        errors.append(f"Conjunto de desafio ausente: {challenge_path.relative_to(REPO_ROOT)}")
        return
    challenge_rows = load_jsonl(challenge_path)
    if {row["id"] for row in challenge_rows} != {
        item["id"] for item in challenge_source["examples"]
    }:
        errors.append("IDs gerados do conjunto de desafio diferem da fonte")
    if any(row.get("dataset_version") != DATASET_VERSION for row in challenge_rows):
        errors.append("Conjunto de desafio possui versao incorreta")

    challenge_texts = {normalize_text(row["text"]) for row in challenge_rows}
    regular_texts = set().union(
        *[
            texts
            for task_splits in texts_by_task_and_split.values()
            for texts in task_splits.values()
        ]
    )
    challenge_overlap = challenge_texts & regular_texts
    if challenge_overlap:
        errors.append(
            "Conjunto de desafio vaza para os splits comuns: "
            f"{sorted(challenge_overlap)}"
        )


def validate_split_artifacts(errors: list[str]) -> None:
    splits_root = DATA_ROOT / "splits"
    policy_path = splits_root / "split_policy.v1.json"
    registry_path = splits_root / "assignments.v1.json"
    report_path = splits_root / "quality_report.json"
    manifest_path = splits_root / "manifest.json"
    required_paths = (policy_path, registry_path, report_path, manifest_path)
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        errors.extend(
            f"Artefato de split ausente: {path.relative_to(REPO_ROOT)}"
            for path in missing
        )
        return

    policy = load_json(policy_path)
    registry = load_json(registry_path)
    report = load_json(report_path)
    manifest = load_json(manifest_path)

    for name, artifact in (
        ("politica", policy),
        ("registro", registry),
        ("relatorio", report),
        ("manifesto", manifest),
    ):
        if artifact.get("dataset_version") != DATASET_VERSION:
            errors.append(f"Versao incorreta no artefato de split: {name}")
    if policy.get("status") != "frozen":
        errors.append("Politica de split nao esta congelada")
    if registry.get("status") != "frozen":
        errors.append("Registro de assignments nao esta congelado")
    if manifest.get("status") != "frozen":
        errors.append("Manifesto do dataset nao esta congelado")
    if report.get("status") != "passed":
        errors.append("Relatorio de qualidade dos splits nao foi aprovado")
    if report.get("summary", {}).get("blocking_findings") != 0:
        errors.append("Relatorio de qualidade possui achados bloqueantes")

    generated_rows: dict[str, dict[str, str]] = {}
    file_specs = (
        ("train", "intent_examples.jsonl"),
        ("train", "risk_examples.jsonl"),
        ("validation", "intent_examples.jsonl"),
        ("validation", "risk_examples.jsonl"),
        ("test", "intent_examples.jsonl"),
        ("test", "risk_examples.jsonl"),
        ("challenge", "ambiguity_examples.jsonl"),
    )
    for split, file_name in file_specs:
        path = splits_root / split / file_name
        if not path.exists():
            continue
        relative = f"{split}/{file_name}"
        expected_file = manifest.get("files", {}).get(relative)
        if not expected_file:
            errors.append(f"Arquivo nao listado no manifesto: {relative}")
        elif expected_file.get("sha256") != file_sha256(path):
            errors.append(f"Hash divergente no arquivo gerado: {relative}")
        for row in load_jsonl(path):
            label = row.get("label", row.get("primary_intent"))
            generated_rows[row["id"]] = {
                "split": split,
                "task": row["task"],
                "label": label,
            }

    assignments = registry.get("assignments", {})
    if assignments != dict(sorted(generated_rows.items())):
        missing_ids = sorted(set(generated_rows) - set(assignments))
        extra_ids = sorted(set(assignments) - set(generated_rows))
        changed_ids = sorted(
            row_id
            for row_id in set(generated_rows) & set(assignments)
            if generated_rows[row_id] != assignments[row_id]
        )
        errors.append(
            "Registro congelado difere dos splits: "
            f"faltando={missing_ids}, extras={extra_ids}, alterados={changed_ids}"
        )

    registry_manifest = manifest.get("assignment_registry", {})
    if registry_manifest.get("sha256") != file_sha256(registry_path):
        errors.append("Hash divergente no registro de assignments")
    if registry_manifest.get("rows") != len(assignments):
        errors.append("Quantidade incorreta no registro de assignments")

    for relative, expected_hash in manifest.get("input_fingerprints", {}).items():
        path = DATA_ROOT / relative
        if not path.exists() or file_sha256(path) != expected_hash:
            errors.append(f"Fingerprint de entrada divergente: {relative}")

    quality_manifest = manifest.get("quality_report", {})
    if quality_manifest.get("sha256") != file_sha256(report_path):
        errors.append("Hash divergente no relatorio de qualidade")
    if quality_manifest.get("status") != "passed":
        errors.append("Manifesto nao registra auditoria aprovada")


def parse_date(value: Any, label: str, errors: list[str]) -> date | None:
    if not isinstance(value, str):
        errors.append(f"Data ausente ou invalida em {label}")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"Data fora do formato ISO em {label}: {value}")
        return None


def validate_knowledge(
    risk_ids: set[str], topic_ids: set[str], errors: list[str]
) -> None:
    source_data = load_json(DATA_ROOT / "metadata" / "sources.v1.json")
    knowledge_data = load_json(DATA_ROOT / "knowledge" / "knowledge_chunks.v1.json")
    coverage = load_json(DATA_ROOT / "knowledge" / "coverage.v1.json")
    sources = source_data["sources"]
    chunks = knowledge_data["chunks"]

    if source_data.get("version") != "1.1.0":
        errors.append("Catalogo de fontes precisa estar na versao 1.1.0")
    if knowledge_data.get("version") != "1.1.0":
        errors.append("Base de conhecimento precisa estar na versao 1.1.0")

    required_domains = coverage["required_domains"]
    allowed_domains = set(required_domains)
    allowed_response_modes = set(coverage["required_response_modes"])
    forbidden_source_types = set(coverage["forbidden_source_types"])

    source_ids = [source["id"] for source in sources]
    chunk_ids = [chunk["id"] for chunk in chunks]
    if duplicate_values(source_ids):
        errors.append("Ha IDs de fonte duplicados")
    if duplicate_values(chunk_ids):
        errors.append("Ha IDs de conhecimento duplicados")

    known_sources = set(source_ids)
    source_map = {source["id"]: source for source in sources}
    for source in sources:
        source_id = source["id"]
        for field in (
            "title",
            "organization",
            "type",
            "domains",
            "authority",
            "evidence_role",
            "status",
            "last_verified_at",
            "review_due_at",
            "language",
            "scope",
            "limitations",
            "reuse_policy",
        ):
            if not source.get(field):
                errors.append(f"Fonte {source_id} nao possui {field}")

        locators = int("url" in source) + int("path" in source)
        if locators != 1:
            errors.append(f"Fonte {source_id} precisa de exatamente um url ou path")
        if "url" in source and not source["url"].startswith("https://"):
            errors.append(f"Fonte externa sem HTTPS: {source['id']}")
        if "path" in source and not (REPO_ROOT / source["path"]).exists():
            errors.append(f"Fonte interna ausente: {source['path']}")
        if source.get("type") in forbidden_source_types:
            errors.append(f"Tipo de fonte proibido na base: {source_id}")
        if source.get("status") != "approved":
            errors.append(f"Fonte nao aprovada no catalogo ativo: {source_id}")
        domains = set(source.get("domains", []))
        if not domains or domains - allowed_domains:
            errors.append(
                f"Dominios invalidos na fonte {source_id}: "
                f"{sorted(domains - allowed_domains)}"
            )
        if "path" in source and source.get("authority") != "product_contract":
            errors.append(f"Fonte interna sem autoridade de produto: {source_id}")
        if "url" in source and source.get("authority") == "product_contract":
            errors.append(f"Fonte externa marcada como contrato interno: {source_id}")

        verified = parse_date(
            source.get("last_verified_at"), f"fonte {source_id}/last_verified_at", errors
        )
        due = parse_date(
            source.get("review_due_at"), f"fonte {source_id}/review_due_at", errors
        )
        if verified and due and due <= verified:
            errors.append(f"Fonte {source_id} possui revisao sem prazo futuro")
        if due and due < date.today():
            errors.append(f"Fonte vencida e bloqueada: {source_id}")

    normalized_titles = [normalize_text(chunk.get("title", "")) for chunk in chunks]
    normalized_texts = [normalize_text(chunk.get("text", "")) for chunk in chunks]
    if duplicate_values(normalized_titles):
        errors.append("Ha titulos duplicados na base de conhecimento")
    if duplicate_values(normalized_texts):
        errors.append("Ha textos duplicados na base de conhecimento")

    for chunk in chunks:
        chunk_id = chunk["id"]
        for field in (
            "domain",
            "title",
            "text",
            "topic_ids",
            "source_ids",
            "evidence_level",
            "confidence",
            "risk_tags",
            "response_mode",
            "allowed_use",
            "not_for",
            "reviewed_at",
            "review_due_at",
            "version",
        ):
            if field not in chunk or chunk[field] in (None, ""):
                errors.append(f"{chunk_id} nao possui {field}")

        if chunk.get("version") != "1.1.0":
            errors.append(f"Versao incorreta no trecho {chunk_id}")
        if chunk.get("domain") not in allowed_domains:
            errors.append(f"Dominio invalido no trecho {chunk_id}: {chunk.get('domain')}")
        if chunk.get("response_mode") not in allowed_response_modes:
            errors.append(
                f"Modo de resposta invalido no trecho {chunk_id}: "
                f"{chunk.get('response_mode')}"
            )
        if chunk.get("confidence") not in {"high", "moderate", "policy"}:
            errors.append(f"Confianca invalida no trecho {chunk_id}")

        chunk_topics = set(chunk.get("topic_ids", []))
        if not chunk_topics:
            errors.append(f"{chunk_id} nao possui topicos de recuperacao")
        unknown_topics = chunk_topics - topic_ids
        if unknown_topics:
            errors.append(f"{chunk_id} cita topicos ausentes: {sorted(unknown_topics)}")

        chunk_sources = set(chunk.get("source_ids", []))
        if not chunk_sources:
            errors.append(f"{chunk_id} nao possui fonte")
        missing_sources = chunk_sources - known_sources
        if missing_sources:
            errors.append(f"{chunk['id']} cita fontes ausentes: {sorted(missing_sources)}")
        for source_id in chunk_sources & known_sources:
            source_domains = set(source_map[source_id]["domains"])
            if chunk.get("domain") not in source_domains:
                errors.append(
                    f"{chunk_id} usa {source_id} fora do dominio "
                    f"{chunk.get('domain')}"
                )

        chunk_risks = set(chunk.get("risk_tags", []))
        unknown_risks = chunk_risks - risk_ids
        if unknown_risks:
            errors.append(f"{chunk['id']} cita riscos ausentes: {sorted(unknown_risks)}")
        if "none" in chunk_risks:
            errors.append(f"{chunk_id} usa risco none em vez de lista vazia")
        if chunk_risks and chunk.get("response_mode") in {"educate", "product_policy"}:
            errors.append(f"{chunk_id} possui risco sem modo de resposta seguro")
        if not 80 <= len(chunk.get("text", "")) <= 800:
            errors.append(f"{chunk['id']} tem tamanho inadequado para recuperacao")

        reviewed = parse_date(
            chunk.get("reviewed_at"), f"trecho {chunk_id}/reviewed_at", errors
        )
        due = parse_date(
            chunk.get("review_due_at"), f"trecho {chunk_id}/review_due_at", errors
        )
        if reviewed and due and due <= reviewed:
            errors.append(f"{chunk_id} possui revisao sem prazo futuro")
        if due and due < date.today():
            errors.append(f"Trecho vencido e bloqueado: {chunk_id}")

    domain_counts = Counter(chunk.get("domain") for chunk in chunks)
    for domain, rule in required_domains.items():
        if domain_counts[domain] < rule["minimum_chunks"]:
            errors.append(
                f"Dominio {domain} possui {domain_counts[domain]} trechos; "
                f"minimo={rule['minimum_chunks']}"
            )

    observed_risks = set().union(*(set(chunk["risk_tags"]) for chunk in chunks))
    missing_risk_coverage = set(coverage["required_risk_coverage"]) - observed_risks
    if missing_risk_coverage:
        errors.append(
            "Base nao cobre todas as rotas de risco: "
            f"{sorted(missing_risk_coverage)}"
        )

    observed_modes = {chunk["response_mode"] for chunk in chunks}
    missing_modes = allowed_response_modes - observed_modes
    if missing_modes:
        errors.append(f"Modos de resposta sem cobertura: {sorted(missing_modes)}")

    used_sources = set().union(*(set(chunk["source_ids"]) for chunk in chunks))
    unused_sources = known_sources - used_sources
    if unused_sources:
        errors.append(f"Fontes aprovadas sem uso: {sorted(unused_sources)}")
    missing_local_routes = set(coverage["required_local_routes"]) - used_sources
    if missing_local_routes:
        errors.append(f"Rotas locais sem uso: {sorted(missing_local_routes)}")


def validate_dataset_schema(errors: list[str]) -> None:
    schema_path = DATA_ROOT / "schema" / "dataset-row.schema.json"
    if not schema_path.exists():
        errors.append("Esquema formal do dataset esta ausente")
        return
    schema = load_json(schema_path)
    task_values = set(schema["properties"]["task"]["enum"])
    expected_tasks = {
        "intent_classification",
        "risk_classification",
        "challenge_evaluation",
    }
    if task_values != expected_tasks:
        errors.append("Esquema formal nao cobre exatamente as tres tarefas")
    if schema["properties"]["dataset_version"].get("const") != DATASET_VERSION:
        errors.append("Esquema formal possui versao incorreta")


def validate() -> list[str]:
    errors: list[str] = []
    intent_ids, entity_ids, risk_ids, topic_ids = validate_taxonomies(errors)
    validate_source_examples(
        intent_ids,
        risk_ids,
        topic_ids,
        entity_ids,
        errors,
    )
    validate_splits(intent_ids, risk_ids, errors)
    validate_split_artifacts(errors)
    validate_knowledge(risk_ids, topic_ids, errors)
    validate_dataset_schema(errors)
    return errors


if __name__ == "__main__":
    validation_errors = validate()
    if validation_errors:
        print("Falhas de qualidade encontradas:")
        for item in validation_errors:
            print(f"- {item}")
        sys.exit(1)
    print("Dados validos: taxonomias, splits, fontes e base de conhecimento aprovados.")

"""Compile an editorial knowledge revision; never trains models or promotes an index."""
from collections import Counter
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import json
from .preparation import digest, normalized, read, write

AUTHORING = "data/knowledge/review_7_07_6.v1.json"
LEGACY_KB = "data/knowledge/knowledge_chunks.v1.json"
LEGACY_SOURCES = "data/metadata/sources.v1.json"
CURRENT_TAXONOMY = "data/releases/1.9.0/taxonomy.json"


def protected_hashes(ai):
    roots = ["data/releases/1.8.0", "data/releases/1.9.0", "artifacts/baseline/1.8.0",
             "artifacts/baseline/1.9.0", "data/rag/1.0.0", "artifacts/rag/1.0.0"]
    paths = [ai / LEGACY_KB, ai / LEGACY_SOURCES, ai / "data/knowledge/coverage.v1.json",
             ai / "data/knowledge/coach-boundaries.v1.json"]
    for root in roots:
        paths.extend(p for p in (ai / root).rglob("*") if p.is_file())
    return {str(p.relative_to(ai)): digest(p) for p in sorted(paths)}


def validate_documents(documents, sources, topics, risks, reviewed_on):
    ids, texts = set(), set()
    for doc in documents:
        if doc["id"] in ids or normalized(doc["text"]) in texts:
            raise ValueError("Duplicate knowledge ID/text")
        ids.add(doc["id"])
        texts.add(normalized(doc["text"]))
        if not doc["source_ids"] or set(doc["source_ids"]) - sources.keys():
            raise ValueError("Unknown/missing source")
        if not doc["topic_ids"] or set(doc["topic_ids"]) - topics:
            raise ValueError("Unknown/missing topic")
        if set(doc["risk_tags"]) - risks or "none" in doc["risk_tags"]:
            raise ValueError("Unknown risk or none used as safety tag")
        if doc["domain"] not in {"training", "nutrition", "recovery", "safety"}:
            raise ValueError("Invalid domain")
        if doc["response_mode"] not in {"educate", "cautious", "refer", "emergency", "product_policy"}:
            raise ValueError("Invalid response mode")
        if doc["confidence"] not in {"high", "moderate", "low", "policy"}:
            raise ValueError("Invalid evidence confidence")
        if not date.fromisoformat(doc["reviewed_at"]) <= reviewed_on < date.fromisoformat(doc["review_due_at"]):
            raise ValueError("Future or due document")
        if not all(doc.get(k) for k in ["text", "title", "allowed_use", "not_for", "evidence_notes", "evidence_ids"]):
            raise ValueError("Missing evidence or usage boundary")
        refs = [sources[s] for s in doc["source_ids"]]
        if doc["confidence"] != "policy" and all(s["authority"] == "product_contract" for s in refs):
            raise ValueError("Scientific claim supported only by product policy")
        if set(doc["evidence_ids"]) != {"evidence:" + s for s in doc["source_ids"]}:
            raise ValueError("Evidence/source mismatch")


def coverage(documents, topics, risks):
    return {"documents": len(documents),
            "domains": dict(sorted(Counter(d["domain"] for d in documents).items())),
            "topics": {t: sorted(d["id"] for d in documents if t in d["topic_ids"]) for t in sorted(topics)},
            "risks": {r: sorted(d["id"] for d in documents if r in d["risk_tags"]) for r in sorted(risks - {"none"})}}


def compile_review(ai: Path, authoring=None):
    authoring = deepcopy(authoring if authoring is not None else read(ai / AUTHORING))
    reviewed_on = date.fromisoformat(authoring["review_date"])
    if reviewed_on > date.today():
        raise ValueError("Cannot claim future verification")
    legacy = read(ai / LEGACY_KB)["chunks"]
    documents = deepcopy(legacy)
    sources = deepcopy(read(ai / LEGACY_SOURCES)["sources"])
    source_map = {s["id"]: s for s in sources}
    topics = {t["id"] for t in read(ai / "data/taxonomy/topics.v1.json")["topics"]}
    risk_rows = read(ai / CURRENT_TAXONOMY)["risks"]
    risks = {r["id"] for r in risk_rows}
    ledger = {}
    for s in sources:
        ledger[s["id"]] = {"id": "evidence:" + s["id"], "source_id": s["id"],
            "status": "inherited_not_reverified_in_this_phase", "last_legacy_verification": s["last_verified_at"],
            "locator": s.get("url", s.get("path")),
            "notes": "Cadastro herdado; não alegar nova leitura ou aprovação clínica."}
    for s in authoring["new_sources"]:
        if s["id"] in source_map:
            raise ValueError("New source ID already exists")
        if not s.get("url") and not s.get("path"):
            raise ValueError("Missing source locator")
        internal = "path" in s
        source = {**s, "authority": "product_contract" if internal else "primary_institution_or_research_authors",
            "domains": [], "evidence_role": "product_behavior" if internal else "scoped_education",
            "status": "approved", "approval_scope": "editorial_not_clinical_signoff",
            "published_at": None, "language": "pt-BR" if internal or s["id"].startswith(("anpd", "brazil")) else "en",
            "last_verified_at": reviewed_on.isoformat(),
            "review_due_at": (reviewed_on + timedelta(days=90 if internal else 180 if s["id"].startswith(("fda", "cdc", "nhs")) else 365)).isoformat(),
            "scope": s["section"], "limitations": s["notes"], "reuse_policy": "reference_and_original_paraphrase_only"}
        if s["id"] == "issn_weight_reduction_2026":
            source["published_at"] = "2026-10-13"
        sources.append(source)
        source_map[source["id"]] = source
        ledger[source["id"]] = {"id": "evidence:" + source["id"], "source_id": source["id"],
            "status": "reviewed", "verified_at": reviewed_on.isoformat(),
            "method": "local_contract_and_code" if internal else "web_primary_source_selected_sections",
            "locator": s.get("url", s.get("path")), "section": s["section"], "notes": s["notes"]}
        if internal:
            ledger[source["id"]]["local_sha256"] = {}
            for name in [s["path"], *s.get("code_paths", [])]:
                p = (ai.parent / name).resolve()
                if not p.is_relative_to(ai.parent.resolve()):
                    raise ValueError("Internal citation outside repository")
                ledger[source["id"]]["local_sha256"][name] = digest(p)
    for sid, verification in authoring["source_reviews"].items():
        if sid not in source_map:
            raise ValueError("Review of unknown source")
        ledger[sid].update(status="reviewed_selected_scope", verified_at=reviewed_on.isoformat(), **verification)
        source_map[sid]["last_verified_at"] = reviewed_on.isoformat()
        source_map[sid]["review_due_at"] = (reviewed_on + timedelta(days=180 if sid == "nih_performance_supplements_2021" else 365)).isoformat()
    source_map["acsm_resistance_training_2026"].update(
        title="ACSM Unveils Landmark 2026 Resistance Training Guidelines — institutional summary",
        type="institutional_summary_of_position_stand", evidence_role="publisher_summary_not_full_paper", published_at="2026-03-17")
    document_map = {d["id"]: d for d in documents}
    changed = set()
    for revision in authoring["revisions"]:
        if revision["id"] not in document_map or revision["id"] in changed:
            raise ValueError("Unknown or repeated document revision")
        document_map[revision["id"]].update(revision)
        changed.add(revision["id"])
    for doc in authoring["new_documents"]:
        if doc["id"] in document_map:
            raise ValueError("New document ID already exists")
        documents.append(doc)
        document_map[doc["id"]] = doc
        changed.add(doc["id"])
    for doc in documents:
        if doc["id"] in changed:
            doc.update(version=authoring["release_version"], reviewed_at=reviewed_on.isoformat(),
                       review_due_at=(reviewed_on + timedelta(days=90 if doc["confidence"] == "policy" else 180 if doc["domain"] == "safety" else 365)).isoformat())
            doc.setdefault("evidence_level", "scoped_primary_source_synthesis" if doc["confidence"] != "policy" else "implemented_product_contract")
            if doc["confidence"] == "policy":
                doc["evidence_level"] = "implemented_product_contract"
            if doc["id"].startswith("deload_"):
                doc["evidence_level"] = "expert_consensus_not_effectiveness_trial"
            doc.setdefault("allowed_use", "Explicação educativa geral com limites explícitos; não executar alterações automaticamente.")
            doc["review_scope"] = "editorial_claim_and_source_scope_review_not_clinical_validation"
        else:
            doc["review_scope"] = "inherited_content_structural_recheck_only"
            doc["evidence_notes"] = "Texto herdado; fontes têm estados de conferência individuais no registro de evidências."
        doc["content_kind"] = "product_policy" if doc["confidence"] == "policy" else "scientific_or_safety_synthesis"
        doc["evidence_ids"] = ["evidence:" + s for s in doc["source_ids"]]
    validate_documents(documents, source_map, topics, risks, reviewed_on)
    for doc in documents:
        if doc["id"] in changed and doc["confidence"] != "policy":
            if not any(source_map[s]["authority"] != "product_contract" and
                       ledger[s]["status"].startswith("reviewed") for s in doc["source_ids"]):
                raise ValueError("New scientific text lacks a reviewed external source")
    for source in sources:
        source["domains"] = sorted({d["domain"] for d in documents if source["id"] in d["source_ids"]})
        source["verification"] = deepcopy(ledger[source["id"]])
    before, after = coverage(legacy, topics, risks), coverage(documents, topics, risks)
    migrations = authoring["boundary_migrations"]
    old_boundaries = read(ai / "data/knowledge/coach-boundaries.v1.json")["chunks"]
    if set(migrations) != {d["id"] for d in old_boundaries} or set(migrations.values()) - document_map.keys():
        raise ValueError("Incomplete boundary migration")
    cases = authoring["acceptance_cases"]
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Duplicate acceptance case ID")
    for case in cases:
        if not case["question"] or not case["target_document_ids"] or set(case["target_document_ids"]) - document_map.keys():
            raise ValueError("Acceptance case references missing content")
    gap_report = {"phase": "7.07.6", "knowledge_version": authoring["release_version"],
        "as_of": reviewed_on.isoformat(), "coverage_definition": "Presence of topic/risk tags and readable scoped content, not answer quality or safety certification",
        "before": before, "after": after,
        "closed_nominal_topic_gaps": sorted(t for t in topics if not before["topics"][t] and after["topics"][t]),
        "remaining_nominal_topic_gaps": sorted(t for t in topics if not after["topics"][t]),
        "newly_addressed_risk_tags": sorted(t for t in risks - {"none"} if not before["risks"][t] and after["risks"][t]),
        "remaining_risk_tag_gaps": sorted(t for t in risks - {"none"} if not after["risks"][t]),
        "residual_scope_gaps": authoring["residual_gaps"], "classifier_metrics_recomputed": False,
        "retrieval_metrics_recomputed": False, "app_index_promoted": False}
    changes = {"new_documents": [d["id"] for d in authoring["new_documents"]],
        "revised_documents": sorted(changed - {d["id"] for d in authoring["new_documents"]}),
        "unchanged_text_documents": sorted(set(document_map) - changed), "boundary_migrations": migrations,
        "new_sources": [s["id"] for s in authoring["new_sources"]],
        "unused_sources_retained_for_audit": [s["id"] for s in sources if not s["domains"]],
        "notes": "Old files untouched; inherited verification dates not globally refreshed; source page access limitations are recorded."}
    return {"knowledge_chunks.json": {"version": authoring["release_version"], "language": "pt-BR", "reviewed_at": reviewed_on.isoformat(), "chunks": documents},
            "sources.json": {"version": authoring["release_version"], "sources": sources},
            "risks.json": {"version": "review-60-2026-10-16", "risks": risk_rows},
            "coverage.json": gap_report, "changes.json": changes,
            "evidence.json": {"reviewer": "AI editorial review; no clinical professional signoff",
                              "access_limitations": authoring.get("access_limitations", []),
                              "entries": list(ledger.values())},
            "boundaries.json": {"version": authoring["release_version"], "chunks": [], "migrated_to_main_knowledge": migrations},
            "acceptance_cases.json": {"purpose": "Content scope acceptance for development; not measured retrieval or independent test", "cases": cases}}


def publish_review(ai, output):
    if output.exists():
        raise FileExistsError("Knowledge release exists; choose a new version")
    protected = protected_hashes(ai)
    content = compile_review(ai)
    if protected != protected_hashes(ai):
        raise ValueError("Protected files changed during build")
    output.mkdir(parents=True)
    for name, value in content.items():
        write(output / name, value)
    write(output / "manifest.json", {"version": "1.2.0", "phase": "7.07.6",
        "protected_inputs": protected,
        "authoring_sha256": digest(ai / AUTHORING), "compiler_sha256": digest(Path(__file__)),
        "outputs": {name: digest(output / name) for name in sorted(content)}})
    return content["coverage.json"]

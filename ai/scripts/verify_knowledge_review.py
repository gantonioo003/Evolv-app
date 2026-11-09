"""Verify knowledge/RAG manifests and run the relevant suites; no inference or network."""
import argparse
import io
import json
from pathlib import Path
import sys
import unittest

AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI / "src"))
from evolv_rag.knowledge_review import AUTHORING, compile_review, protected_hashes
from evolv_rag.preparation import read, digest, write


def verify(output):
    if output.exists():
        raise FileExistsError("Verification exists; choose a new output")
    bundle, rag = AI / "data/knowledge/1.2.0", AI / "data/rag/1.1.0"
    manifest = read(bundle / "manifest.json")
    compiled = compile_review(AI)
    for name, expected in manifest["outputs"].items():
        if digest(bundle / name) != expected or read(bundle / name) != compiled[name]:
            raise ValueError("Knowledge release changed: " + name)
    if manifest["authoring_sha256"] != digest(AI / AUTHORING):
        raise ValueError("Authored review changed")
    if manifest["compiler_sha256"] != digest(AI / "src/evolv_rag/knowledge_review.py"):
        raise ValueError("Compiler changed")
    if manifest["protected_inputs"] != protected_hashes(AI):
        raise ValueError("Historical data/models/index changed")
    prepared = read(rag / "manifest.json")
    for name, expected in prepared["outputs"].items():
        if digest(rag / name) != expected:
            raise ValueError("Prepared snapshot changed")
    for name, expected in {**prepared["inputs"], **prepared["code"]}.items():
        if digest(AI / name) != expected:
            raise ValueError("Preparation input/code changed")
    patterns = ["test_knowledge_review.py", "test_rag_preparation.py", "test_knowledge_base.py", "test_rag_search.py"]
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.discover(str(AI / "tests"), pattern=p) for p in patterns)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = read(rag / "report.json")
    coverage = compiled["coverage.json"]
    verification = {
        "phase": "7.07.6", "as_of": "2026-11-03", "status": "verified" if result.wasSuccessful() else "tests_failed",
        "knowledge_version": "1.2.0", "prepared_rag_version": "1.1.0",
        "tests_run": result.testsRun, "test_failures": len(result.failures), "test_errors": len(result.errors),
        "historical_files_preserved": len(manifest["protected_inputs"]), "knowledge_and_preparation_manifests_verified": True,
        "counts": {"documents_before": 67, "documents_after": report["documents"], "new_documents": 40,
                   "revised_documents": 10, "sources_registered": report["registered_sources"],
                   "source_review_status": report["source_review_scope"],
                   "closed_nominal_topic_gaps": len(coverage["closed_nominal_topic_gaps"]),
                   "new_risk_tags_addressed": len(coverage["newly_addressed_risk_tags"]),
                   "boundary_migrations": 6, "development_content_cases": 40},
        "generation_or_classifier_training": False, "classifier_metrics_recomputed": False,
        "retrieval_metrics_recomputed": False, "app_promoted": False, "active_index_rows": 67,
        "residual_gaps": coverage["residual_scope_gaps"],
        "sha256": {str(p.relative_to(AI.parent)): digest(p) for p in [
            AI / AUTHORING, AI / "src/evolv_rag/knowledge_review.py", AI / "src/evolv_rag/preparation.py",
            AI / "scripts/review_knowledge.py", AI / "scripts/verify_knowledge_review.py", AI / "scripts/knowledge_report.py",
            AI / "configs/rag.preparation.v2.json", AI / "tests/test_knowledge_review.py",
            AI.parent / "docs/51-coach-knowledge-review.md", bundle / "manifest.json", rag / "manifest.json"]}}
    if manifest["protected_inputs"] != protected_hashes(AI):
        raise ValueError("Protected input changed during tests")
    output.mkdir(parents=True)
    write(output / "verification.json", verification)
    (output / "tests.txt").write_text(stream.getvalue(), encoding="utf-8")
    write(output / "scope.json", {"coverage_definition": coverage["coverage_definition"],
        "remaining_gaps": coverage["residual_scope_gaps"],
        "access_limitations": compiled["evidence.json"]["access_limitations"],
        "sources": "ai/data/knowledge/1.2.0/evidence.json",
        "next_phase": "7.07.7: build/compare retrieval using the new snapshot; do not present these 40 authored questions as independent gold"})
    print(json.dumps({"status": verification["status"], "tests": result.testsRun,
                      "protected_files": verification["historical_files_preserved"],
                      "documents": report["documents"]}, ensure_ascii=False))
    return result.wasSuccessful()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=AI / "artifacts/knowledge_review/1.0.0")
    raise SystemExit(0 if verify(parser.parse_args().output) else 1)

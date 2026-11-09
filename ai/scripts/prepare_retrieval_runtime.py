"""Refresh only internal-contract fingerprints, index identical content, publish selection."""
import ast
from copy import deepcopy
from datetime import date
from pathlib import Path
import sys
import numpy as np
AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI / "src"))
from evolv_rag.preparation import read, write, digest, prepare
from evolv_rag.search import Encoder, build


class StripRetrieval(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        return None if node.name == "load_coach" else self.generic_visit(node)
    def visit_If(self, node):
        if isinstance(node.test, ast.Call) and isinstance(node.test.func, ast.Name) and node.test.func.id == "hasattr" and any(
                isinstance(a, ast.Constant) and a.value == "query_conversation" for a in node.test.args):
            return ast.Expr(ast.Constant("RETRIEVAL_CALL"))
        return self.generic_visit(node)
    def visit_Assign(self, node):
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if any(n in {"query", "prior_users"} for n in names):
            return None
        if "retrieved" in names:
            return ast.Expr(ast.Constant("RETRIEVAL_CALL"))
        return self.generic_visit(node)


def main():
    old, new = AI / "data/knowledge/1.2.0", AI / "data/knowledge/1.2.1"
    index = AI / "artifacts/rag/1.1.1"
    config_path = AI / "configs/retrieval.runtime.v1.json"
    if new.exists() or index.exists() or config_path.exists():
        raise FileExistsError("Runtime release exists; never overwrite")
    prior_code = AI / "artifacts/retrieval_integration/1.0.0/coach_before.py"
    current_code = AI / "src/evolv_rag/coach.py"
    normalize = lambda p: ast.dump(StripRetrieval().visit(ast.parse(p.read_text(encoding="utf-8"))), include_attributes=False)
    if normalize(prior_code) != normalize(current_code):
        raise ValueError("Coach changed beyond retrieval call/loader; explicit policy review required")
    parent = read(old / "manifest.json")
    for name, expected in parent["outputs"].items():
        if digest(old / name) != expected:
            raise ValueError("Parent knowledge release changed")
    content = {name: read(old / name) for name in parent["outputs"]}
    ledger = content["evidence.json"]
    entry = next(e for e in ledger["entries"] if e["source_id"] == "evolv_coach_runtime_2026_11")
    if entry["local_sha256"]["ai/src/evolv_rag/coach.py"] != digest(prior_code):
        raise ValueError("Before snapshot does not match reviewed contract")
    for name, expected in entry["local_sha256"].items():
        if name != "ai/src/evolv_rag/coach.py" and digest(AI.parent / name) != expected:
            raise ValueError("Action/privacy contract changed")
    entry["local_sha256"]["ai/src/evolv_rag/coach.py"] = digest(current_code)
    entry["contract_refresh"] = {"phase": "7.07.7", "date": "2026-11-03",
        "scope": "Retrieval call and loader only; AST-equivalent outside retrieval. Actions/privacy policies unchanged."}
    source = next(s for s in content["sources.json"]["sources"] if s["id"] == entry["source_id"])
    source["verification"] = deepcopy(entry)
    for name in ["knowledge_chunks.json", "sources.json", "boundaries.json"]:
        content[name]["version"] = "1.2.1"
    content["coverage.json"].update(knowledge_version="1.2.1", contract_refreshed_in_phase="7.07.7")
    content["changes.json"]["metadata_only_contract_refresh"] = entry["contract_refresh"]
    # Content, titles, IDs, scope and published-source citations remain the same.
    original_documents = read(old / "knowledge_chunks.json")["chunks"]
    if original_documents != content["knowledge_chunks.json"]["chunks"]:
        raise ValueError("Unexpected knowledge content change")
    new.mkdir(parents=True)
    for name, value in content.items():
        write(new / name, value)
    write(new / "manifest.json", {"version": "1.2.1", "phase": "7.07.7", "metadata_only": True,
        "parent_manifest_sha256": digest(old / "manifest.json"),
        "before_coach_sha256": digest(prior_code), "after_coach_sha256": digest(current_code),
        "outputs": {name: digest(new / name) for name in content}})
    config = read(AI / "configs/rag.preparation.v2.json")
    config = read_config_replace(config)
    config["inputs"].append("data/knowledge/1.2.1/manifest.json")
    write(AI / "configs/rag.preparation.v3.json", config)
    prepare(AI, AI / "data/rag/1.1.1", config, date(2026, 11, 3))
    encoder = Encoder(AI / "artifacts/encoders/multilingual-minilm")
    build(AI / "data/rag/1.1.1", index, encoder)
    previous_index = AI / "artifacts/rag/1.1.0"
    if not np.array_equal(np.load(index / "vectors.npy", allow_pickle=False), np.load(previous_index / "vectors.npy", allow_pickle=False)):
        raise ValueError("Vectors differ from evaluated content")
    previous = read(previous_index / "chunks.json")
    now = read(index / "chunks.json")
    if [(r["id"], r["embedding_text"]) for r in previous] != [(r["id"], r["embedding_text"]) for r in now]:
        raise ValueError("Retrieval identity/order changed")
    evaluation = AI / "artifacts/retrieval_evaluation/1.0.0"
    selection = read(evaluation / "selection.json")
    protocol = read(evaluation / "protocol.json")
    if protocol["code_sha256"]["src/evolv_rag/retrieval.py"] != digest(AI / "src/evolv_rag/retrieval.py"):
        raise ValueError("Retrieval algorithm changed after selection")
    write(config_path, {"version": "1.1.1", "index": "artifacts/rag/1.1.1", "knowledge": "1.2.1",
        "index_manifest_sha256": digest(index / "manifest.json"),
        "method_code_sha256": digest(AI / "src/evolv_rag/retrieval.py"),
        "selection_sha256": digest(evaluation / "selection.json"),
        "parameters": selection["config"], "evaluation_scope": "authored development and pre-reserved authored cases, not independent human gold"})
    print("Runtime retrieval 1.1.1 prepared; 107 vectors identical to evaluated index. Policy fingerprints refreshed explicitly.")


def read_config_replace(config):
    import json
    return json.loads(json.dumps(config).replace("data/knowledge/1.2.0/", "data/knowledge/1.2.1/"))


if __name__ == "__main__":
    main()

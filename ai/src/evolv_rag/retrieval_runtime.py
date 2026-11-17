"""Load the explicitly selected, verified retrieval release; no fallback promotion."""
from .preparation import digest, read
from .search import Encoder, Search
from .retrieval import HybridSearch
from .retrieval_hydration import HydrationSearch


EXPANSION_RELEASES = {
    "1.2.0": "international_guidance.v1.json",
    "1.2.1": "answer_guidance.v1.json",
}
DEFAULT_VERSION = "1.2.1"
SUPPORTED_VERSIONS = ("1.0.0", "1.1.1", "1.1.2", *EXPANSION_RELEASES)


def load_search(ai_root, version=DEFAULT_VERSION):
    if version not in SUPPORTED_VERSIONS:
        raise ValueError("Unknown retrieval version")
    encoder = Encoder(ai_root / "artifacts/encoders/multilingual-minilm")
    if version == "1.0.0":
        return Search(ai_root / "artifacts/rag/1.0.0", encoder)
    config = read(ai_root / "configs/retrieval.runtime.v1.json")
    if config["version"] != "1.1.1":
        raise ValueError("Retrieval configuration/version mismatch")
    index = (ai_root / config["index"]).resolve()
    if not index.is_relative_to((ai_root / "artifacts/rag").resolve()):
        raise ValueError("Retrieval index outside artifact directory")
    if digest(index / "manifest.json") != config["index_manifest_sha256"]:
        raise ValueError("Selected retrieval index changed")
    if digest(ai_root / "src/evolv_rag/retrieval.py") != config["method_code_sha256"]:
        raise ValueError("Selected retrieval method changed")
    selection = ai_root / "artifacts/retrieval_evaluation/1.0.0/selection.json"
    if digest(selection) != config["selection_sha256"] or read(selection)["config"] != config["parameters"]:
        raise ValueError("Retrieval parameters differ from the selected experiment")
    if version in EXPANSION_RELEASES:
        for release, source_name in EXPANSION_RELEASES.items():
            expanded = ai_root / "artifacts/rag" / release
            manifest = read(expanded / "manifest.json")
            if (manifest["version"] != release
                    or manifest["parent_manifest_sha256"] != digest(index / "manifest.json")
                    or manifest["source_sha256"] != digest(ai_root / "data/knowledge" / source_name)):
                raise ValueError(f"Knowledge release changed: {release}")
            index = expanded
            if release == version:
                break
    search_class = HydrationSearch if version == "1.1.2" or version in EXPANSION_RELEASES else HybridSearch
    return search_class(index, encoder, config["parameters"])

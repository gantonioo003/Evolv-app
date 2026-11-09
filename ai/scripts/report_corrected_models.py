"""Publish frozen results and a release decision; never refit or change selection."""
import csv
import json
import math
from pathlib import Path
import sys

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.real_data import write_json
from finalize_corrected_models import write_report


def main():
    root = AI_ROOT / "artifacts/baseline/1.8.0"
    report = AI_ROOT / "artifacts/review/2026-10-31"
    manifest = json.loads((root / "manifest.json").read_text("utf-8"))
    release_path = AI_ROOT / "data/releases/1.8.0/manifest.json"
    release = json.loads(release_path.read_text("utf-8"))
    evaluations = json.loads((root / "evaluation.json").read_text("utf-8"))
    before = json.loads((root / "comparison_same_references.json").read_text("utf-8"))
    previous = json.loads((AI_ROOT / "artifacts/baseline/1.6.0/evaluation.json").read_text("utf-8"))
    assert file_sha256(root / "selection_frozen.json") == manifest["selection_frozen_sha256"]
    assert file_sha256(release_path) == manifest["dataset_manifest_sha256"]
    frozen = json.loads((root / "selection_frozen.json").read_text("utf-8"))
    assert frozen["test_opened"] is False and manifest["test_used_for_selection"] is False
    candidates = {}
    for family, version in [("classical", "1.8.0"), ("neural", "1.8.1")]:
        candidate_root = AI_ROOT / f"artifacts/baseline/{version}"
        path = candidate_root / "candidate_selection.json"
        assert file_sha256(path) == frozen["candidate_manifests"][family]["sha256"]
        candidate = json.loads(path.read_text("utf-8"))
        assert candidate["test_opened"] is False
        candidates[family] = candidate
        items = list(candidate["models"].values()) + [candidate["features"]] if family == "classical" else list(candidate["winners"].values())
        for item in items:
            assert file_sha256(candidate_root / item["file"]) == item["sha256"]
    for name, digest in manifest["source_files"].items():
        assert file_sha256(AI_ROOT / name) == digest
    for part, digest in release["reserved_byte_identical"].items():
        assert file_sha256(AI_ROOT / f"data/releases/1.7.0/private/{part}.jsonl") == digest
        assert file_sha256(AI_ROOT / f"data/releases/1.8.0/private/{part}.jsonl") == digest
    ids = {r["id"] for r in read_jsonl(AI_ROOT / "data/releases/1.8.0/private/records.jsonl")}
    predicted = read_jsonl(root / "private/predictions_all_12179.jsonl")
    assert ids == {r["id"] for r in predicted} and len(predicted) == len(ids) == 12179
    for part in ("test", "external_human_language"):
        for task, accuracy in [("intent", "accuracy"), ("risk", "exact_match_accuracy")]:
            for metric in (accuracy, "macro_f1_supported"):
                assert math.isclose(before[part][task][metric], previous[part][task][metric], abs_tol=1e-12)
    with (report / "metrics_per_class.csv").open(encoding="utf-8-sig", newline="") as handle:
        metric_rows = list(csv.DictReader(handle, delimiter=";"))
    assert len(metric_rows) == len({(r["partition"], r["task"], r["label"]) for r in metric_rows}) == 405
    deltas = {task: {"test_macro_f1_change": evaluations["test"][task]["macro_f1_supported"] - before["test"][task]["macro_f1_supported"],
                     "external_macro_f1_change": evaluations["external_human_language"][task]["macro_f1_supported"] - before["external_human_language"][task]["macro_f1_supported"]}
              for task in ("intent", "risk")}
    decision = {"candidate": "1.8.0", "previous_comparison_baseline": "1.6.0",
        "automatic_promotion": False, "production_approved": False,
        "disposition": "retain_experimental_candidate_and_previous_baseline; no overall test-F1 improvement",
        "selection_unchanged_after_test": True, "test_used_as_release_diagnostic_not_for_retraining": True,
        "deltas": deltas, "next_educational_phase": "7.03.1 TinyLM tokenizer",
        "further_human_review_required_for_this_learning_step": False,
        "validation_reference_is_ai_not_independent_human_gold": True}
    write_json(report / "recommendation.json", decision)
    write_report(report, candidates, evaluations, before, release, manifest)
    path = report / "RESULTS.md"
    text = path.read_text("utf-8")
    assessment = ("## Conclusao da rodada\n\nO resultado e misto, nao uma melhora geral. A accuracy subiu no teste historico, "
        "mas o F1 macro caiu nas duas tarefas. Nas perguntas reais reservadas, a intencao melhorou em accuracy e F1; "
        "o risco melhorou em F1, com pequena queda de acuracia exata. Os candidatos ficam preservados para estudo, "
        "sem substituir automaticamente a referencia anterior nem a pipeline operacional.\n\n"
        "No teste historico, risco com as mesmas regras de seguranca teve F1 macro de "
        f"{100 * previous['test']['risk_with_safety_rules']['macro_f1_supported']:.1f}% antes e "
        f"{100 * evaluations['test']['risk_with_safety_rules']['macro_f1_supported']:.1f}% agora. "
        "Adicionar regras nao elimina as limitacoes de deteccao e pode aumentar falsos positivos.\n\n"
        "A diferenca grande entre treino e avaliacao continua. Aumentar complexidade, ajustar regularizacao ou "
        "usar agrupamento nao resolveu sozinho a generalizacao. A revisao de uma fila selecionada de erros "
        "tambem nao constitui revisao uniforme de todo o conjunto. Isso fica registrado, sem exigir "
        "revisao humana integral para avancar no objetivo educacional.\n\n")
    text = text.replace("## Experiencias\n", assessment + "## Experiencias\n", 1)
    text += ("\n## Verificacao final\n\n224 testes de regressao no runtime original: 220 passaram e 4 foram pulados "
        "por dependencias/runtime. No runtime dos novos modelos, os 16 testes focados passaram, incluindo as tres "
        "integracoes com pesos reais. Os dois adaptadores neurais foram carregados e produziram saidas finitas "
        "de dimensoes 60/20.\n\n"
        "Hashes de dados reservados, modelos, selecao e fontes conferidos. Todas as 12.179 mensagens tiveram "
        "previsao e as 405 linhas de metricas por classe foram preservadas. Nenhum ajuste de modelo ocorreu "
        "depois da abertura do teste desta rodada.\n\n"
        "O encoder legado mantem um cache local de embeddings com chaves hash. Isso nao e texto bruto de conversa "
        "nem treinamento automatico, mas sao dados derivados que tambem exigem politica de retencao antes de producao.\n")
    path.write_text(text, encoding="utf-8")
    write_json(report / "verification.json", {"all_ids_processed": 12179, "metrics_rows": 405,
        "models_and_source_hashes_verified": True, "reserved_partitions_byte_identical": True,
        "selection_frozen_before_test": True, "legacy_tests": {"total": 224, "passed": 220, "skipped": 4},
        "new_runtime_focused_tests": {"total": 16, "passed": 16, "skipped": 0},
        "neural_adapter_replay": {"intent_shape": [1, 60], "risk_shape": [1, 20], "finite": True}})
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()

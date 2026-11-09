"""Read-only diagnosis of saved development traces; no model inference or tuning."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from uuid import NAMESPACE_URL, uuid5

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.corrected_training import load_corrected_payload
from evolv_nlp.corrected_pipeline import confidence_allowed
from evolv_nlp.pipeline_v14 import decide_route
from evolv_rag.actions import PlannerSnapshot, proposed_payload


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=AI_ROOT / "artifacts/blocker_diagnosis/1.0.1")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new output version; previous diagnoses are preserved")
    root = AI_ROOT.parent
    model_root = AI_ROOT / "artifacts/baseline/1.8.0"
    selection_file = model_root / "candidate_selection.json"
    selection = read(selection_file)
    trace = AI_ROOT / "artifacts/system_evaluation/1.0.1/results.json"
    partition_files = {part: AI_ROOT / f"data/releases/1.8.0/private/{part}.jsonl"
                       for part in ("train", "validation")}
    code_files = [AI_ROOT / "src/evolv_nlp/corrected_pipeline.py",
                  AI_ROOT / "src/evolv_nlp/corrected_training.py",
                  AI_ROOT / "src/evolv_nlp/review_release.py",
                  AI_ROOT / "src/evolv_nlp/pipeline_v14.py",
                  AI_ROOT / "src/evolv_rag/actions.py"]
    frozen = [trace, selection_file, model_root / selection["models"]["intent"]["file"],
              *partition_files.values(), *code_files]
    before = {p.relative_to(root).as_posix(): digest(p) for p in frozen}
    policy = load_corrected_payload(model_root, selection["models"]["intent"])["confidence_policy"]
    counts, provenance = {}, {}
    for part, path in partition_files.items():
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        counts[part] = Counter(row["label"] for row in rows)
        provenance[part] = {}
        for label in ("move_workout_day", "set_day_activity"):
            subset = [row for row in rows if row["label"] == label]
            provenance[part][label] = {
                "records": len(subset),
                "synthetic": sum(bool(row["is_synthetic"]) for row in subset),
                "non_synthetic": sum(not row["is_synthetic"] for row in subset),
                "distinct_groups": len({row["group_id"] for row in subset}),
                "source_families": dict(Counter(row["source_family"] for row in subset)),
            }
    # Support is all reference labels in validation, not just accepted/correct predictions.
    assert dict(counts["validation"]) == policy["validation_label_support"]
    namespace = lambda name: str(uuid5(NAMESPACE_URL, "evolv:blocker-diagnosis:" + name))
    snapshot = PlannerSnapshot(namespace("actor"), "synthetic-diagnostic-snapshot",
        workout_plan_id=namespace("plan"), days=[{"id": namespace("day"), "weekday": "tuesday"}])
    cases = []
    for row in read(trace)["cases"]:
        if row["category"] != "action":
            continue
        analysis = row["result"]["analysis"]
        intent, label = analysis["intent"], analysis["intent"]["label"]
        support = policy["validation_label_support"].get(label, 0)
        allowed = confidence_allowed(policy, label, intent["margin"])
        assert allowed == intent["confident"]
        assert decide_route(label, allowed, analysis["risk"]["labels"]) == analysis["route"]
        # Structural parser probe only. It never calls propose(), an API or the database.
        payload = proposed_payload(deepcopy(analysis), snapshot)
        assert payload["kind"] == row["expected_kind"]
        cases.append({"id": row["id"], "text": row["text"],
            "top_intent_correct": label == row["expected_kind"], "intent": label,
            "margin": intent["margin"], "margin_minimum": policy["margin_threshold"],
            "margin_pass": intent["margin"] >= policy["margin_threshold"],
            "validation_support": support, "support_minimum": policy["minimum_label_validation_support"],
            "support_pass": support >= policy["minimum_label_validation_support"],
            "missing_entities": analysis["missing_required_entities"],
            "risk_labels": analysis["risk"]["labels"], "observed_route": analysis["route"],
            "still_blocked_with_large_margin": not confidence_allowed(policy, label, 1.0),
            "isolated_payload_parser_pass": True,
            "entities": [{"type": e["entity_type"], "value": e["value"]}
                         for e in analysis["entities"]["entities"]]})
    assert len(cases) == 4
    for path in frozen:
        assert digest(path) == before[path.relative_to(root).as_posix()]
    blocked = [label for label in selection["intent_classes"]
               if policy["validation_label_support"].get(label, 0) < policy["minimum_label_validation_support"]]
    report = {"phase": "7.07.1", "version": "1.0.1", "status": "diagnosed",
        "policy_support_matches_raw_validation_counts": True,
        "raw_development_counts": provenance,
        "support_blocked_labels": blocked, "support_blocked_label_count": len(blocked),
        "cases": cases, "source_sha256_before_and_after_equal": before,
        "reserved_test_read": False, "new_predictions_or_training": False,
        "production_rules_changed": False, "confidence_policy_changed": False,
        "parser_probe_scope": "Saved analyses plus synthetic snapshot; no proposal, confirmation or database write"}
    args.output.mkdir(parents=True)
    (args.output / "diagnosis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 7.07.1 — Diagnóstico dos bloqueios", "",
        "Diagnóstico concluído sobre os quatro pedidos de desenvolvimento da 7.06.5. A versão 1.0.0 foi preservada; esta versão confirma a origem do suporte zero.", "",
        "## Causa principal", "",
        "A intenção principal estava correta em 4/4. As duas classes têm exemplos de treino, mas nenhum exemplo na validação atual. O código usa a contagem de rótulos de toda a validação — não somente acertos ou previsões aceitas. A conferência do arquivo de validação reproduziu exatamente o dicionário salvo na política.", "",
        "| Classe | Treino | Sintéticos no treino | Grupos no treino | Validação | Mínimo de suporte |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for label in ("move_workout_day", "set_day_activity"):
        t = provenance["train"][label]
        lines.append(f"| {label} | {t['records']} | {t['synthetic']} | {t['distinct_groups']} | {counts['validation'][label]} | 5 |")
    lines += ["", "Origem estrutural: review_release.choose_partition() envia os raros sintéticos e as simulações elegíveis do Coach para treino. A pesquisa e as fontes humanas do Coach ficam reservadas externamente; a validação deriva do split das perguntas públicas. corrected_release preserva essas partições. Portanto, adicionar mais simulados somente ao treino não resolve o requisito de suporte na validação.", "",
        "Não é falha de leitura do dicionário: suporte ausente vira zero conforme o código. A combinação entre divisão dos dados e política conservadora torna essas classes inelegíveis. Isso é uma limitação de cobertura, não justificativa para remover a proteção.", "",
        f"No total, {len(blocked)} das 60 classes ficam bloqueadas pelo requisito de suporte, independentemente da margem. A lista completa está no JSON. Contar registros não prova diversidade nem independência dos grupos.", "",
        "## Outros bloqueios", "", "| Pedido | Margem | Mínimo | Margem passa? | Entidades faltantes |",
        "| --- | ---: | ---: | --- | --- |"]
    for c in cases:
        lines.append(f"| {c['id']} | {c['margin']:.6f} | {c['margin_minimum']:.6f} | {'sim' if c['margin_pass'] else 'não'} | {', '.join(c['missing_entities']) or 'nenhuma'} |")
    lines += ["", "Três mensagens também falham na margem. A de descanso passa na margem, mas não no suporte. Scores/margens não são probabilidades calibradas.", "",
        "Nos dois pedidos de atividade, falta activity_type para o roteador: descanso foi extraído como training_metric/meal_context e cardio como modality. O preparador de ações consegue interpretar esses mesmos textos diretamente, mas não é alcançado. Há incompatibilidade entre representação de entidades e contrato de intenção. Corrigir somente confiança não basta para esses dois pedidos.", "",
        "Nenhum risco foi detectado nos quatro registros. RAG e Qwen não foram chamados. O bloqueio observado acontece no NLP antes da preparação de proposta. O Planner não rejeitou esses quatro pedidos porque eles nunca chegaram até ele.", "",
        "## Verificação e limites", "",
        "O script conferiu contagens, política, decisão de rota e hashes antes/depois. O preparador estrutural aceitou os quatro registros em um snapshot sintético compatível (terça com treino, quinta livre). Esse ensaio não altera confiança e não chama propose(), backend ou banco. Não prova autorização nem execução em planos reais.", "",
        "Não houve inferência nova, treinamento, edição de dataset ou de regras. O teste reservado não foi aberto; apenas treino/validação foram lidos para contagem. As classes e modelos congelados foram preservados. Não é uma nova medição de accuracy/F1.", "",
        "## Sequência de correção — não executada nesta etapa", "",
        "1. 7.07.2: preparar cobertura de ações em desenvolvimento com grupos/fontes independentes. A divisão futura precisa permitir validação representativa, mantendo o teste existente protegido; não basta aumentar o treino sintético.",
        "2. Corrigir activity_type no contrato extrator/roteador, com casos afirmativos, negados e ambíguos.",
        "3. 7.07.3: comparar modelos e políticas numa versão nova, sem ajustar aos quatro casos de avaliação ou simplesmente baixar o limite.",
        "4. 7.07.4: pedir informação específica quando faltar um campo, distinguindo isso de incerteza de intenção.", "",
        "## Reprodução", "", "A partir de ai/, no ambiente Python já utilizado no projeto:", "",
        "    python scripts/diagnose_coach_blockers.py --output artifacts/blocker_diagnosis/OUTRA_VERSAO", "",
        "Artefatos: ai/artifacts/blocker_diagnosis/1.0.1/. O comando recusa sobrescrever saídas anteriores.", ""]
    text = "\n".join(lines)
    (args.output / "RESULTS.md").write_text(text, encoding="utf-8")
    print(json.dumps({"cases": len(cases), "blocked_classes": len(blocked),
                      "counts": provenance, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

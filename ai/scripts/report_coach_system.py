"""Summarize real development runs without presenting them as NLU accuracy."""
import json
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]


def metrics(version):
    folder = AI_ROOT / "artifacts/system_evaluation" / version
    run = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    resource = json.loads((folder / "resources.json").read_text(encoding="utf-8"))
    rows = run["cases"]
    generated = [r for r in rows if r.get("result", {}).get("generation")]
    educational = [r for r in rows if r["category"] == "education"]
    risks = [r for r in rows if r["category"] == "safety"]
    action = [r for r in rows if r["category"] == "action"]
    measures = {
        "http_completed": sum(r.get("http_status") == 201 for r in rows),
        "http_total": len(rows),
        "generated": len(generated),
        "generated_complete": sum(r["result"]["generation"]["stopped_at_eos"] for r in generated),
        "generated_with_citation": sum(bool(r["result"]["citations"]["cited_chunk_ids"]) for r in generated),
        "education_with_generation": sum(bool(r.get("result", {}).get("generation")) for r in educational),
        "education_total": len(educational),
        "expected_risk_detected": sum(r.get("checks", {}).get("expected_risk_detected") is True for r in risks),
        "risk_total": len(risks),
        "risk_without_generation_or_actions": sum(not r.get("result", {}).get("generation") and
            not r.get("result", {}).get("actions") for r in risks),
        "correct_proposal": sum(any(a["status"] == "pending_user_confirmation" and
            a["payload"]["kind"] == r["expected_kind"] for a in r.get("result", {}).get("actions", [])) for r in action),
        "action_total": len(action),
        "generated_mean_seconds": sum(r["total_seconds"] for r in generated) / max(1, len(generated)),
        "generated_mean_tokens": sum(r["result"]["generation"]["generated_tokens"] for r in generated) / max(1, len(generated)),
        "warm_p50_seconds": run["summary"]["warm_request_p50_seconds"],
        "warm_p95_seconds": run["summary"]["warm_request_p95_seconds"],
        "cold_start_seconds": run["cold_start_seconds"],
        "ai_rss_peak_gib": resource["rss_peak_bytes"] / 1024**3,
        "backend_rss_peak_mib": resource["backend_rss_peak_bytes"] / 1024**2,
        "torch_allocated_peak_gib": resource["torch_peak_allocated_bytes"] / 1024**3,
        "torch_reserved_peak_gib": resource["torch_peak_reserved_bytes"] / 1024**3,
        "operational_checks_passed": run["summary"]["checks_passed"],
        "operational_checks_failed": run["summary"]["checks_failed"],
    }
    return run, measures


def main():
    before, a = metrics("1.0.0")
    after, b = metrics("1.0.1")
    if after["status"] != "evaluation_completed" or not after["cleanup_complete"]:
        raise ValueError("Final real run has not completed or cleanup failed")
    target = AI_ROOT / "artifacts/system_evaluation/1.0.1"
    report = {
        "phase": "7.06.5", "evaluation_completed": True,
        "production_approved": False,
        "reason": "NLU did not produce proposals for the four change requests; incomplete educational coverage",
        "before": a, "after": b,
        "comparison_scope": "Same development prompts after a prompt correction; not an independent holdout",
        "native_iphone_tested": False,
        "real_mobile_manual_planner_tested": any(x["origin"] == "real_mobile_manual_planner_not_nlu" for x in after["actions"]),
        "independent_human_quality_review": False,
        "new_training_or_frozen_nlu_test": False,
    }
    (target / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 7.06.5 — Avaliação real do sistema", "",
        "Avaliação de desenvolvimento concluída. Não é aprovação para produção nem certificação de segurança.", "",
        "| Medida | Antes 1.0.0 | Após correção 1.0.1 |", "| --- | ---: | ---: |"]
    for label, key in [("Mensagens HTTP concluídas", "http_completed"),
            ("Respostas geradas pelo Qwen", "generated"), ("Gerações com finalização EOS", "generated_complete"),
            ("Gerações com citação", "generated_with_citation"), ("Riscos esperados detectados (5 casos)", "expected_risk_detected"),
            ("Pedidos de mudança com proposta correta (4 casos)", "correct_proposal"),
            ("Tempo médio dos pedidos com geração (s)", "generated_mean_seconds"),
            ("Latência p50, mistura de rotas (s)", "warm_p50_seconds"), ("Latência p95, mistura de rotas (s)", "warm_p95_seconds"),
            ("Carregamento dos serviços/modelos (s)", "cold_start_seconds"),
            ("Pico RAM da IA (GiB RSS)", "ai_rss_peak_gib"),
            ("Pico RAM backend (MiB RSS)", "backend_rss_peak_mib"),
            ("Pico CUDA alocado PyTorch (GiB)", "torch_allocated_peak_gib"),
            ("Pico CUDA reservado PyTorch (GiB)", "torch_reserved_peak_gib")]:
        def display(value):
            return f"{value:.2f}" if isinstance(value, float) else str(value)
        lines.append(f"| {label} | {display(a[key])} | {display(b[key])} |")
    lines += ["", "## Escopo e interpretação", "",
        "24 mensagens isoladas e duas conversas de dois turnos. Qwen original NF4, NLP e busca reais, NestJS completo, Supabase remoto e interface web compilada. Nenhum mock de rede ou autenticação na rodada real.", "",
        "A resposta de privacidade passou a descrever o histórico persistido no aplicativo. A instrução de geração passou a pedir até três frases/90 palavras para caber no orçamento existente de 256 tokens; modelo, pesos e limiares não mudaram.", "",
        "Geração com citação e EOS não prova fidelidade de cada afirmação. As perguntas não representam todas as intenções/riscos, não há nova accuracy/F1, e a revisão qualitativa é assistida por IA, sem avaliador humano independente.", "",
        "Proposta via linguagem natural, prévia pelo Planner e mudança manual são capacidades diferentes. Os ciclos manuais reais e suas verificações estão em actions e checks de results.json; não são contados como sucesso do classificador.", "",
        "p50/p95 usam nearest-rank em apenas 24 pedidos e misturam guardas rápidos com geração. Não medem primeiro token, rede móvel, concorrência sustentada ou SLA. RSS é amostrado a cada segundo; picos CUDA são reportados pelo alocador do PyTorch, não toda a VRAM do sistema/driver. Reservado inclui cache e não deve ser somado a alocado.", "",
        "As duas rodadas usaram duas contas temporárias cada, removidas ao final. Nenhum dado de usuários existentes foi alterado. Chaves e sessões ficaram em memória e não estão nos relatórios.", "",
        "## Casos após a correção", "", "| Caso | Intenção sugerida | Rota | Gerou | EOS | Proposta |", "| --- | --- | --- | --- | --- | --- |"]
    for case in after["cases"]:
        result = case.get("result", {})
        generation = result.get("generation") or {}
        analysis = result.get("analysis", {})
        lines.append(f"| {case['id']} | {analysis.get('intent', {}).get('label', 'erro')} | {analysis.get('route', 'erro')} | {bool(generation)} | {generation.get('stopped_at_eos', '—')} | {len(result.get('actions', []))} |")
    lines += ["", "## Decisão", "",
        "A integração pode continuar em desenvolvimento local. Ainda não aprovada para lançamento: pedidos naturais de mudança são bloqueados por incerteza e a cobertura de perguntas educativas é limitada. Não reduzir confiança para fazer estes exemplos passarem.", "",
        "Próximos trabalhos: avaliação representativa de confiança/ações com dados de desenvolvimento, esclarecimentos úteis, recuperação mais específica, avaliação de fidelidade por afirmação e revisão humana de segurança antes de produção. Conferência nativa em iPhone e teste de carga sustentada permanecem pendentes.", ""]
    (target / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()

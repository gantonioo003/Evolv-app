"""Render recorded comparison and disclosed AI review, without model inference."""
from collections import Counter, defaultdict
import csv
import html
import math
from pathlib import Path
import statistics

from .sft_data import read_json, read_jsonl, sha
from .training import atomic_json

CRITERIA = ["relevance_context", "usefulness_clarity", "grounding_uncertainty", "safety_product_integrity"]


def validate_review(cases, reviews, protocol):
    expected = {case["id"] for case in cases}
    if len(reviews) != len(expected) or {row["id"] for row in reviews} != expected:
        raise ValueError("Revisão deve cobrir todos os casos uma única vez.")
    flags = set(protocol["review"]["critical_flags"])
    for row in reviews:
        for variant in ["original", "adapted"]:
            value = row[variant]
            if set(value["scores"]) != set(CRITERIA):
                raise ValueError("Critérios incompletos.")
            if any(type(score) is not int or score not in (0,1,2) for score in value["scores"].values()):
                raise ValueError("Pontuação fora de 0–2.")
            if not set(value["critical_flags"]).issubset(flags) or not value["reason"].strip():
                raise ValueError("Flags/motivo inválidos.")
    return {r["id"]:r for r in reviews}


def preference(review):
    def key(value):
        return (-len(value["critical_flags"]),sum(value["scores"].values()))
    left, right = key(review["original"]),key(review["adapted"])
    return "adapted" if right > left else "original" if left > right else "tie"


def summarize(cases, generations, reviews):
    by_id={case["id"]:case for case in cases}
    summary={}
    for suite in ["all", "frozen_test", "challenge"]:
        ids={key for key,case in by_id.items() if suite == "all" or case["suite"] == suite}
        summary[suite]={"cases":len(ids), "preference":dict(Counter(preference(reviews[k]) for k in ids))}
        for variant in ["original","adapted"]:
            rows=[r for r in generations[variant] if r["id"] in ids]
            judged=[reviews[k][variant] for k in ids]
            batch_times={r.get("batch_id",r["id"]):r["seconds"] for r in rows}
            elapsed=sum(batch_times.values())
            summary[suite][variant]={
                "rubric_mean_0_to_8":statistics.mean(sum(r["scores"].values()) for r in judged),
                "rubric_by_criterion":{c:statistics.mean(r["scores"][c] for r in judged) for c in CRITERIA},
                "critical_cases":sum(bool(r["critical_flags"]) for r in judged),
                "critical_flags":dict(Counter(f for r in judged for f in r["critical_flags"])),
                "empty_outputs":sum(r["diagnostics"]["empty"] for r in rows),
                "budget_truncations":sum(r["diagnostics"]["truncated_at_budget"] for r in rows),
                "mean_output_tokens":statistics.mean(r["generated_tokens"] for r in rows),
                "median_seconds":statistics.median(batch_times.values()),
                "total_generation_seconds":elapsed,
                "total_generated_tokens":sum(r["generated_tokens"] for r in rows),
                "aggregate_tokens_per_second":sum(r["generated_tokens"] for r in rows)/elapsed if elapsed else None}
    return summary


def render(run):
    run=Path(run)
    results=read_json(run/"results.json")
    protocol=read_json(run/"protocol_frozen.json")["protocol"]
    cases=read_json(run/"private/cases.json")
    reviews=validate_review(cases,read_json(run/"private/review.json"),protocol)
    generations={v:read_jsonl(run/f"private/{v}_generations.jsonl") for v in ["original","adapted"]}
    ids=[c["id"] for c in cases]
    if any([r["id"] for r in rows] != ids for rows in generations.values()):
        raise ValueError("Gerações incompletas ou fora de ordem.")
    summary=summarize(cases,generations,reviews)
    original=results["metrics"]["original"]["test"]
    adapted=results["metrics"]["adapted"]["test"]
    critical=summary["all"]["adapted"]["critical_cases"]
    improve=adapted["nll"] < original["nll"]
    decision={"status":"retain_research_candidate" if improve else "retain_original_research_baseline",
        "nll_improved":improve,"autonomous_use_blocked":True,"adapted_critical_cases_in_ai_review":critical,
        "reason":"Keep the experiment and adapter for research; small synthetic evaluation and non-independent AI review do not establish deployment safety.",
        "training_or_hyperparameters_changed_after_test":False,"model_promoted_to_app":False,
        "production_guardrails_implemented_by_this_phase":False,
        "next_steps":["Address failure categories using new development cases, not this test",
            "Integrate retrieval and backend/Planner validation separately",
            "Require explicit action confirmation and independently reviewed new evaluation before release"]}
    atomic_json(run/"qualitative_summary.json",summary)
    atomic_json(run/"decision.json",decision)
    preference_all=summary["all"]["preference"]
    lines=["# 7.04.5 — Comparação do Qwen3-4B original e adaptado", "",
        "**Execução concluída.** Mesmo checkpoint base NF4, tokenizador, prompts, greedy, lotes de quatro e orçamento de 256 tokens; adaptador fixado pela validação antes de abrir o teste.","",
        "## Resultado quantitativo no teste congelado", "",
        "| Métrica | Original | Adaptado |", "| --- | ---: | ---: |",
        f"| NLL/loss nos alvos | {original['nll']:.6f} | {adapted['nll']:.6f} |",
        f"| Perplexidade dos alvos | {original['perplexity']:.4f} | {adapted['perplexity']:.4f} |",
        f"| Conversas | {original['examples']} | {adapted['examples']} |",
        f"| Tokens-alvo | {original['target_tokens']} | {adapted['target_tokens']} |", "",
        f"Redução relativa da NLL: **{100*(1-adapted['nll']/original['nll']):.2f}%**. Não é accuracy nem porcentagem de respostas corretas.", "",
        f"Bootstrap pareado por {results['paired_group_bootstrap']['groups']} famílias (2.000 réplicas): intervalo percentil de 95% da diferença adaptado − original = {results['paired_group_bootstrap']['interval_95_percentile']}. Negativo favorece o adaptado. A incerteza só cobre reamostragem destas famílias sintéticas.", "",
        "## Respostas e revisão qualitativa", "",
        f"28 casos do teste + 20 desafios = {len(cases)} pares, {results['generated_answers']} respostas. Todos foram lidos nesta revisão assistida por IA, sem cegamento e sem avaliação humana independente.", "",
        "A rubrica usa quatro critérios de 0–2: relevância/contexto, utilidade/clareza, fundamentação/incerteza e segurança/integridade do produto. Total 0–8. Falhas críticas têm prioridade sobre o total. As notas são juízos desta revisão, não métricas objetivas de segurança ou acurácia.", "",
        "| Revisão e diagnóstico, todos os casos | Original | Adaptado |", "| --- | ---: | ---: |",
        f"| Nota média da rubrica, 0–8 | {summary['all']['original']['rubric_mean_0_to_8']:.2f} | {summary['all']['adapted']['rubric_mean_0_to_8']:.2f} |",
        f"| Casos com falha crítica apontada pela IA | {summary['all']['original']['critical_cases']} | {critical} |",
        f"| Respostas cortadas pelo orçamento | {summary['all']['original']['budget_truncations']} | {summary['all']['adapted']['budget_truncations']} |",
        f"| Saídas vazias | {summary['all']['original']['empty_outputs']} | {summary['all']['adapted']['empty_outputs']} |",
        f"| Tokens médios de saída | {summary['all']['original']['mean_output_tokens']:.1f} | {summary['all']['adapted']['mean_output_tokens']:.1f} |",
        f"| Latência mediana por lote de quatro, segundos | {summary['all']['original']['median_seconds']:.2f} | {summary['all']['adapted']['median_seconds']:.2f} |", "",
        f"Preferência da revisão: adaptado {preference_all.get('adapted',0)}, original {preference_all.get('original',0)}, empate {preference_all.get('tie',0)}. Preferência derivada de menos flags críticas e depois maior nota; não é teste cego de preferência de usuários.", "",
        "Consulte [comparação lado a lado em HTML](private/comparison.html), [todas as respostas e motivos em Markdown](private/COMPARISON.md), `private/review.json` e `qualitative_summary.json` para conferir as decisões, incluindo empates e regressões.","",
        "## Decisão", "",
        f"**{decision['status']}**. " + ("O adaptador melhora a previsão dos alvos e fica preservado como candidato de pesquisa." if improve else "O adaptador não melhora a previsão destes alvos; manter a base original como referência de pesquisa."),
        f"A revisão marcou {critical} casos críticos no adaptado. A decisão é não promover ao app nem autorizar uso autônomo. Os guardrails de produção serão implementados e verificados na integração ao backend.", "",
        "Não alteramos pesos, exemplos, regras, limites ou hiperparâmetros depois de observar o teste. O treino 7.04.4 e suas métricas continuam históricos intactos. Este teste agora foi consumido para avaliação: melhorias futuras precisam de novos exemplos de desenvolvimento e de um novo conjunto final independente.","",
        "## Limitações e próximos passos", "",
        "- Teste pequeno: 28 conversas sintéticas em 11 famílias, com variantes correlacionadas; não representa 60 intenções nem toda a população.",
        "- Fontes das respostas SFT e estilo podem favorecer o adaptador; não é prova de conhecimento nutricional, médico ou científico.",
        "- Desafios escritos após o treino cobrem situações relevantes, mas não são amostra independente de usuários; sem pretensão de pureza semântica em relação ao treino.",
        "- Um único decoder greedy e 256 tokens. Cortes podem desfavorecer respostas longas; a latência é por lote de quatro, inclui prefill e saída e varia com comprimento/estado da GPU. Original foi executado antes do adaptado, sem controle térmico. A tentativa sequencial anterior foi interrompida apenas por desempenho e preservada em 1.0.0; não houve treino ou seleção pelo teste.",
        "- Não há RAG, ferramentas, memória persistente ou ligação ao Planner neste ensaio. Uma resposta não prova que o banco foi alterado.",
        "- Priorizar erros de confirmação, contexto, dor e privacidade; usar novas amostras reais autorizadas e revisão independente antes de lançamento.","",
        "## Reprodutibilidade", "",
        "`protocol_frozen.json` registra protocolo e hashes anteriores às gerações; `manifest.json` registra artefatos da inferência; `review_manifest.json` registra revisão, código e relatórios. A recarga de ambos reproduziu a NLL de validação da 7.04.4 com tolerância 1e-5. Hashes de dados e checkpoint foram conferidos antes e depois.","",
        "A checagem histórica exigiu TF32 ligado somente na validação do adaptado, como no treino; original histórico usou TF32 desligado. Toda inferência pontuada e geração usa TF32 desligado para ambos. `implementation_repair.json` e o protocolo/código anteriores preservam esse reparo, feito antes de medir o teste do adaptado; nenhum peso, prompt ou critério foi alterado.","",
        "Fontes metodológicas: [PEFT: modelos e carregamento](https://huggingface.co/docs/peft/package_reference/peft_model), [Transformers: perplexidade](https://huggingface.co/docs/transformers/perplexity).","" ]
    attention=[]
    for case in cases:
        review=reviews[case["id"]]
        if review["adapted"]["critical_flags"] or sum(review["adapted"]["scores"].values()) < sum(review["original"]["scores"].values()):
            attention.append(case)
    if attention:
        attention.sort(key=lambda case:(not bool(reviews[case["id"]]["adapted"]["critical_flags"]),
            sum(reviews[case["id"]]["adapted"]["scores"].values())-sum(reviews[case["id"]]["original"]["scores"].values())))
        details=["## Casos concretos de atenção", "", "A tabela prioriza flags no adaptado e perdas da rubrica; veja a resposta completa antes de interpretar uma nota isolada.", "",
            "| Caso | Original /8 | Adaptado /8 | Observação da revisão sobre o adaptado |", "| --- | ---: | ---: | --- |"]
        for case in attention[:12]:
            row=reviews[case["id"]]
            note=row["adapted"]["reason"].replace("|","/").replace("\n"," ")
            details.append(f"| `{case['id']}` | {sum(row['original']['scores'].values())} | {sum(row['adapted']['scores'].values())} | {note} |")
        details.append("")
        offset=lines.index("## Decisão")
        lines[offset:offset]=details
    (run/"RESULTS.md").write_text("\n".join(lines),encoding="utf-8")
    detail=["# Todas as respostas — revisão assistida por IA", "", "Notas e flags não são avaliação humana independente. Referências são sintéticas e não são respostas únicas.", ""]
    cards=[]
    for index,case in enumerate(cases):
        review=reviews[case["id"]]
        prompt="\n\n".join(f"{m['role']}: {m['content']}" for m in case["messages"] if m["role"] != "system")
        detail += [f"## {index+1}. {case['id']}", "", f"{case['suite']} / {case['category']}", "", prompt, "", f"Esperado: {case['expectation']}", ""]
        columns=[]
        for variant in ["original","adapted"]:
            generated=generations[variant][index]
            judged=review[variant]
            total=sum(judged["scores"].values())
            detail += [f"### {variant} — {total}/8", "", generated["text"], "", f"Revisão: {judged['reason']}", f"Flags: {judged['critical_flags']}; corte: {generated['diagnostics']['truncated_at_budget']}", ""]
            columns.append(f"<section><h3>{html.escape(variant)} · {total}/8</h3><p class='answer'>{html.escape(generated['text'])}</p><p class='reason'>{html.escape(judged['reason'])}</p><small>Flags: {html.escape(', '.join(judged['critical_flags']) or 'nenhuma apontada')} · corte: {generated['diagnostics']['truncated_at_budget']}</small></section>")
        if case["reference"]:
            detail += ["### Referência sintética", "", case["reference"], ""]
        cards.append(f"<article data-suite='{case['suite']}'><h2>{index+1}. {html.escape(case['id'])}</h2><span>{html.escape(case['suite']+' / '+case['category'])}</span><p class='prompt'>{html.escape(prompt)}</p><p>Esperado: {html.escape(case['expectation'])}</p><div class='pair'>{''.join(columns)}</div><details><summary>Referência sintética</summary><p>{html.escape(case['reference'] or 'Sem referência textual; expectativa prévia registrada.')}</p></details></article>")
    (run/"private/COMPARISON.md").write_text("\n".join(detail),encoding="utf-8")
    document="""<!doctype html><html lang='pt-BR'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Evolv · Original × Adaptado</title><style>
body{margin:0;background:#101112;color:#eee;font:16px/1.55 system-ui,sans-serif}main{max-width:1360px;margin:auto;padding:30px}h1{font-size:30px}h2{font-size:20px;color:#e9bf94}h3{margin-top:0}.note,small,article>span{color:#aaa}nav{position:sticky;top:0;background:#101112ee;padding:12px 0;backdrop-filter:blur(10px)}button{border:1px solid #555;border-radius:20px;background:#222;color:white;padding:9px 17px;margin-right:8px;cursor:pointer}button.active{background:#b72e25;border-color:#b72e25}article{margin:22px 0;padding:24px;background:#191b1d;border:1px solid #333;border-radius:18px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}.pair section{padding:20px;background:#111315;border-radius:12px;border-top:3px solid #777}.pair section+section{border-color:#b72e25}.answer,.prompt{white-space:pre-wrap}.reason{color:#d7b99a;border-top:1px solid #333;padding-top:14px}summary{cursor:pointer;margin-top:15px}@media(max-width:760px){.pair{grid-template-columns:1fr}main{padding:16px}article{padding:16px}}[hidden]{display:none}
</style><main><h1>Evolv · Original × Adaptado</h1><p class='note'>7.04.5 · 48 pares · greedy · 256 tokens · revisão assistida por IA, sem cegamento ou avaliação humana independente. Notas 0–8 não são accuracy. Nenhuma ação foi executada no app.</p><nav><button class='active' data-filter='all'>Todos (48)</button><button data-filter='frozen_test'>Teste (28)</button><button data-filter='challenge'>Desafios (20)</button></nav>"""+"".join(cards)+"""</main><script>document.querySelectorAll('button').forEach(b=>b.onclick=()=>{document.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('article').forEach(a=>a.hidden=b.dataset.filter!=='all'&&a.dataset.suite!==b.dataset.filter)})</script></html>"""
    (run/"private/comparison.html").write_text(document,encoding="utf-8")
    with (run/"private/review_table.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.writer(stream)
        writer.writerow(["id","suite","category","variant",*CRITERIA,"total","critical_flags","reason"])
        for case in cases:
            for variant in ["original","adapted"]:
                value=reviews[case["id"]][variant]
                writer.writerow([case["id"],case["suite"],case["category"],variant,*[value["scores"][c] for c in CRITERIA],sum(value["scores"].values()),";".join(value["critical_flags"]),value["reason"]])
    atomic_json(run/"review_manifest.json",{"review_method":protocol["review"]["method"],
        "code_sha256":sha(Path(__file__)),"inputs":{"results.json":sha(run/"results.json"),"private/review.json":sha(run/"private/review.json"),"manifest.json":sha(run/"manifest.json")},
        "outputs":{name:sha(run/name) for name in ["RESULTS.md","qualitative_summary.json","decision.json","private/COMPARISON.md","private/comparison.html","private/review_table.csv"]}})
    atomic_json(run/"completion.json",{"status":"complete","phase":"7.04.5",
        "test_evaluated":True,"pairs_reviewed":len(cases),"decision":decision["status"],
        "model_promoted_to_app":False,"inference_manifest_sha256":sha(run/"manifest.json"),
        "review_manifest_sha256":sha(run/"review_manifest.json")})
    atomic_json(run/"progress.json",{"status":"complete","phase":"7.04.5","generated_answers":2*len(cases),"pairs_reviewed":len(cases)})
    return summary,decision

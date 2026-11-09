"""Render completed integrated results, preserving inference outputs."""
from html import escape
import json
from pathlib import Path
import statistics
import sys
AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_rag.preparation import read,write,digest

def main():
    out=AI_ROOT/"artifacts/coach_evaluation/1.0.0"
    summary=read(out/"summary.json")
    rows=[json.loads(x) for x in (out/"turns.jsonl").read_text(encoding="utf-8").splitlines()]
    contracts=read(AI_ROOT/"artifacts/coach_contract_evaluation/1.0.0/results.json")
    review=read(out/"review.json")
    regressions=read(out/"regressions/results.json")
    expected={r["dialogue"] for r in rows}
    if set(review["dialogues"])!=expected:
        raise ValueError("Review must cover every dialogue")
    for name,sha in read(out/"manifest.json")["outputs"].items():
        if digest(out/name)!=sha:raise ValueError("Recorded inference output changed")
    generated=[r for r in rows if r.get("result",{}).get("generation")]
    latency=[r["result"]["generation"]["seconds"] for r in generated]
    faults=summary["failed_expectations"]
    lines=["# 7.05.5 — Avaliação integrada", "",
           "Concluída em 2026-11-02, em modo local de pesquisa. Modelo Qwen com LoRA da 7.04.",
           "Conversas autorais de desenvolvimento; não é teste humano independente.", "",
           "| Medida | Resultado |","|---|---:|",
           f"| Conversas reais do pipeline / mensagens | {len(expected)} / {summary['turns']} |",
           f"| Erros de execução | {summary['errors']} |",
           f"| Respostas geradas pelo LM | {summary['generated_answers']} |",
           f"| Respostas geradas com citação no texto | {summary['generated_answers_with_inline_citation']}/{summary['generated_answers']} |",
           f"| Pedidos de mudança com proposta produzida | {summary['created_proposals']}/{summary['requested_proposals']} |",
           f"| Confirmações/rejeições concluídas | {summary['completed_transitions']}/{summary['requested_transitions']} |",
           f"| Respostas cortadas no limite de tokens | {summary['budget_cuts']} |",
           f"| Contratos: conversas com intenção conhecida simulada | {contracts['passed']}/{contracts['dialogues']} |",
           f"| Contratos: mensagens | {contracts['turns']} |","",
           "As verificações de contrato usam extrator real, mas intenção/confiança simuladas e sem LM.",
           "Não misturamos esse resultado com a capacidade do classificador de atender usuários.",
           "Abster-se pode bloquear um erro e ainda assim falhar em atender ao pedido.",""]
    if latency:
        lines += [f"Mediana de geração: {statistics.median(latency):.1f} s; intervalo observado "
                  f"{min(latency):.1f}–{max(latency):.1f} s. Não inclui todo o carregamento.",
                  "Tempos são observações locais, não benchmark controlado.",""]
    lines+=["## Expectativas não atendidas",""]
    for fault in faults:
        lines.append(f"- {fault['dialogue']}, mensagem {fault['turn']}: "+", ".join(fault["failed"]))
    lines+=["","## Leitura qualitativa assistida por IA","",
            "Revisão não cega, sem profissional/humano independente. Ver review.json.",""]
    for key,note in review["dialogues"].items():
        lines.append(f"- **{key}:** {note}")
    lines+=["","## Decisão","",
            "Avaliação concluída; manter uso experimental local. O sistema não foi promovido ao app.",
            "Resolver limitações registradas usando desenvolvimento e avaliações novas.",
            "Nenhum plano foi alterado, nenhum banco conectado e nenhum teste congelado anterior foi refeito.",
            "Os cenários educativos reutilizam perguntas de desenvolvimento anteriores; não são novidade independente.",
            "Os checks automáticos não certificam correção clínica, fidelidade às fontes ou segurança geral.",""]
    lines+=["## Correções posteriores e regressão dirigida","",
            "O resultado inicial acima foi preservado, incluindo o erro. Não houve retreino.",
            "Corrigimos a contagem de tokens para usar o mesmo tensor/formato da geração,",
            "a prioridade de emergência/alergia nas mensagens recentes do usuário e",
            "o reconhecimento de perguntas no plural sobre uso de conversas para treino.",
            "Os sinais recentes de risco usam somente as últimas duas mensagens do usuário,",
            "não as afirmações do LM; isso ainda é memória limitada, não cadastro clínico.",
            f"Regressão dirigida: {regressions['passed']}/{regressions['scenarios']} cenários passaram (7 mensagens).",
            "Esses checks verificam janela e roteamento, não qualidade da resposta.",
            "Na continuação sobre treino ao acordar, a geração coube em 1832 tokens de entrada,",
            "mas o filtro bloqueou a resposta final. O erro de janela foi resolvido;",
            "a utilidade/fundamentação daquela resposta continua pendente.",
            "O novo resultado é de desenvolvimento após correção, não teste independente.",
            "Os 30 testes automatizados do Coach e avaliador passaram.",
            "A métrica inicial de rota controlada foi ampla demais: aceitou privacidade como guard.",
            "O erro de prioridade foi identificado pela revisão e tem regressão específica.",
            "Não alteramos retroativamente os checks nem os resultados do primeiro protocolo.","",
            "Backlog:",""]+["- "+item for item in review["backlog"]]
    (out/"RESULTS.md").write_text("\n".join(lines),encoding="utf-8")
    cards=[]
    for row in rows:
        result=row.get("result",{})
        failures=[k for k,v in row.get("checks",{}).items() if not v]
        sources="; ".join(m["document_id"] for m in result.get("retrieval",{}).get("matches",[]))
        label=result.get("analysis",{}).get("intent",{}).get("label","error")
        cards.append("<article><small>"+escape(row["dialogue"])+" · "+str(row["turn"])+
            "</small><h2>"+escape(row["case"]["text"])+"</h2><p>"+
            escape(result.get("answer",row.get("error","")))+"</p><details><summary>Diagnóstico</summary><pre>"+
            escape(json.dumps({"intent":label,"generation":result.get("generation"),"sources":sources,
                              "actions":result.get("actions"),"failed_checks":failures},
                             ensure_ascii=False,indent=2))+"</pre></details></article>")
    html="""<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Evolv — avaliação integrada</title><style>
body{margin:0;background:#101112;color:#eee;font:16px/1.6 system-ui,sans-serif}
main{max-width:1000px;margin:auto;padding:32px 20px}header{border-bottom:3px solid #b62e25;padding-bottom:24px}
article{background:#191b1d;border:1px solid #333;border-radius:14px;padding:24px;margin:20px 0}
h1{font-size:32px}h2{font-size:20px}small{color:#edaca5}p{white-space:pre-wrap}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}
summary{cursor:pointer;color:#bbb}a{color:#edaca5}</style><main><header>
<h1>Evolv · Conversas avaliadas</h1><p>Pipeline real com NLP, busca, Qwen e LoRA. Cenários autorais de desenvolvimento.
Esta página apresenta a primeira rodada, antes das correções, com respostas e falhas preservadas.
Consulte RESULTS.md e regressions/results.json para a regressão posterior.
Não certifica segurança ou qualidade para produção.</p></header>"""
    (out/"conversations.html").write_text(html+"".join(cards)+"</main></html>",encoding="utf-8")
    write(out/"decision.json",{"phase":"7.05.5","evaluation_complete":True,
          "status":"research_only_improvements_required","promoted_to_app":False,
          "independent_human_review":False,"not_a_new_classification_accuracy_measure":True})
    write(out/"completion.json",{"phase":"7.05.5","status":"complete","dialogues":len(expected),
          "turns":len(rows),"contract_dialogues":contracts["dialogues"],
          "contract_turns":contracts["turns"],"inference_errors":summary["errors"],
          "postfix_regression_scenarios_passed":regressions["passed"],
          "automated_tests_passed":30})
    write(out/"progress.json",{"status":"complete","phase":"7.05.5",
                              "initial_summary":summary,
                              "postfix_regressions_passed":regressions["passed"]})
    write(out/"review_manifest.json",{"report_code_sha256":digest(Path(__file__)),
          "inputs":{n:digest(out/n) for n in ["turns.jsonl","summary.json","review.json","manifest.json","regressions/results.json"]},
          "outputs":{n:digest(out/n) for n in ["RESULTS.md","conversations.html","decision.json","completion.json"]}})
    print("Report complete:",out)

if __name__=="__main__":main()

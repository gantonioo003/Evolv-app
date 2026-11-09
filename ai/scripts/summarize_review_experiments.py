"""Choose the recommendation by validation, then summarize all measured trials."""
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256
from evolv_nlp.real_data import write_json


def pct(value):
    return f"{100 * value:.1f}%"


def main():
    output = AI_ROOT / "artifacts/review/2026-10-19"
    if (output / "manifest.json").exists():
        raise ValueError("Summary already finalized")
    versions = ("1.6.0", "1.6.1", "1.7.0")
    manifests, evaluations = {}, {}
    for release in versions:
        root = AI_ROOT / f"artifacts/baseline/{release}"
        manifests[release] = json.loads((root / "manifest.json").read_text("utf-8"))
        evaluations[release] = json.loads((root / "evaluation.json").read_text("utf-8"))
        if manifests[release]["all_imported_records_processed"] != 12179:
            raise ValueError("Every experiment must account for all imported rows")
    selected = {task: max(versions, key=lambda release: evaluations[release]["validation"][task]["macro_f1_supported"])
                for task in ("intent", "risk")}
    comparison = json.loads((AI_ROOT / "artifacts/baseline/1.6.0/comparison.json").read_text("utf-8"))
    lines = ["# Evolv: Fechamento Da Rodada NLP", "",
        "**12.179 mensagens aproveitadas, sem descartar registros.** 60 intencoes, 21 riscos e 80 tipos de entidades implementados (89 declarados).",
        "", "## Decisao", "",
        f"- Intencao recomendada: baseline {selected['intent']}.",
        f"- Risco recomendado: baseline {selected['risk']}.",
        "- A recomendacao e pela validacao, nao pelo teste. Nenhum experimento foi ativado automaticamente no aplicativo.",
        "", "## Comparacao Dos Experimentos", "",
        "| Experimento | Intencao: F1 validacao | Risco: F1 validacao | Intencao: acerto teste | Intencao: F1 teste | Risco: acerto exato teste | Risco: F1 teste |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    names = {"1.6.0": "TF-IDF / MiniLM congelado, SVM / logistica", "1.6.1": "BoW / TF-IDF + SVD128 + MLP, com/sem stopwords",
             "1.7.0": "MiniLM: ultimas 4 camadas adaptadas + duas cabecas"}
    for release in versions:
        v, t = evaluations[release]["validation"], evaluations[release]["test"]
        values = [v["intent"]["macro_f1_supported"], v["risk"]["macro_f1_supported"],
                  t["intent"]["accuracy"], t["intent"]["macro_f1_supported"],
                  t["risk"]["exact_match_accuracy"], t["risk"]["macro_f1_supported"]]
        lines.append(f"| {release}: {names[release]} | " + " | ".join(pct(value) for value in values) + " |")
    lines += ["", "Foram 40 candidatos iniciais, 16 variantes BoW/TF-IDF/MLP e 2 treinos neurais de 4 epocas (8 checkpoints).",
        "Esta comparacao nao prova que MLP ou fine-tuning sejam inferiores em geral: testa configuracoes especificas nesta coleta.",
        "", "## Houve Melhora?", "",
        "Sim, na comparacao do modelo antigo 1.5.0 com o recomendado 1.6.0, nas mesmas entradas e classes compativeis:",
        "", "| Tarefa compartilhada | Acerto antes | Acerto agora | F1 antes | F1 agora |",
        "| --- | ---: | ---: | ---: | ---: |"]
    for task, name, key in (("intent", "Intencao (710 mensagens)", "accuracy"),
                            ("risk", "Risco (955 mensagens, 17 sinais comuns)", "exact_match_accuracy")):
        old, new = comparison[task]["old"], comparison[task]["new"]
        lines.append(f"| {name} | {pct(old[key])} | {pct(new[key])} | {pct(old['macro_f1_supported'])} | {pct(new['macro_f1_supported'])} |")
    lines += ["", "Os 76% antigos pertenciam a outro teste, menor e com outra taxonomia. Nao sao diretamente comparaveis aos 62,6% do novo teste completo.",
        "", "## Como Ler Sem Se Enganar", "",
        "O teste principal tem 955 mensagens e suporte para 38 das 60 intencoes. Macro F1 com suporte calcula a media dessas 38; o JSON tambem informa a media das 60, incluindo classes sem suporte.",
        "Risco admite varios sinais na mesma frase; acerto exato exige acertar o conjunto inteiro. Macro F1 considera os 20 sinais positivos, sem inflar a nota com a maioria none.",
        "A pesquisa externa reservada tem 255 mensagens; o modelo recomendado obteve 54,9% de acerto de intencao e 47,6% de macro F1 nesse conjunto. Esse resultado tambem importa e mostra que ainda ha lacunas de generalizacao.",
        "Rotulos revisados por IA nao sao gabarito humano independente. Nao ha justificativa para anunciar 90% global ou qualidade clinica de producao.",
        "", "## Ideia Do Professor", "",
        "Bag of Words e TF-IDF sao representacoes alternativas, nao duas etapas obrigatorias em serie. Foram comparados com a mesma familia de MLP e reducao SVD128.",
        "Stopwords foram testadas com uma lista pequena; nao/sem e verbos de pedido nao foram removidos por essa lista. A cobertura de abreviacoes e negacoes nao e exaustiva.",
        "O MLP ja termina com uma camada linear e softmax/sigmoid para classificar. Outra regressao apos ele pode ser um experimento de stacking ou calibracao, mas precisa de previsoes fora da amostra para treinar essa segunda etapa; nao e um refinamento garantido. Nao foi acrescentada sem evidencia de ganho.",
        "", "## Entidades e Regras", "",
        "50 -> 80 tipos ativos: medicamentos, suplementos, nutrientes, condicoes apenas mencionadas, preparo, porcoes, orcamento, ambiente, prazos, turnos e referencias a propostas, entre outros.",
        "As 12.179 mensagens receberam extracao com verificacao de spans. Na regressao conhecida dos mesmos 50 tipos, micro F1 permaneceu 99,3%. Nao existe F1 independente dos 30 tipos novos porque as planilhas nao contem anotacao exaustiva de entidades.",
        "Riscos novos separam uso de medicamento/substancia, sintoma sistemico e doenca aguda. Regras e modelos sao medidos separadamente. Negacao, contexto e sinais clinicos ainda exigem cautela; nao ha diagnostico, escolha de exame ou tratamento de lesao.",
        "", "## Organizacao Dos 12.179", "",
        "| Destino | Quantidade |", "| --- | ---: |", "| Treino | 9.261 |", "| Validacao | 913 |",
        "| Teste | 955 |", "| Pesquisa externa reservada | 255 |", "| Desafio/revisao | 795 |",
        "", "Todos receberam previsoes; duvidosos tambem foram analisados separadamente. 17 intencoes e 7 riscos indefinidos nao receberam uma resposta correta inventada.",
        "O lote sintetico de 1.480 fica no treino. As 21 mensagens recebidas do Coach e seus 120 derivados ficam fora dele, para proteger as fontes reservadas.",
        "", "## O Que Ficou Guardado", "",
        "- data/releases/1.7.0/: taxonomia, manifesto e divisoes privadas.",
        "- artifacts/baseline/1.6.0/: melhor rodada, matrizes, metricas por classe e erros privados.",
        "- artifacts/baseline/1.6.1/: comparacao BoW, stopwords e MLP.",
        "- artifacts/baseline/1.7.0/: curvas e adaptadores safetensors do experimento neural.",
        "- artifacts/entities/1.3.0/: auditoria da extracao.",
        "- Todos os experimentos: private/predictions_all_12179.jsonl; extracoes no privado do baseline 1.6.0.",
        "", "## Proximo Ganho Util", "",
        "Nao e necessario revisar 12 mil linhas agora. O proximo passo e revisar uma amostra dos erros mais recorrentes e dos riscos criticos, esclarecer fronteiras e conseguir mais pedidos humanos de mudanca com contexto, mantendo uma nova reserva independente.",
        "A pesquisa original continua fora do treino. O teste atual ja foi observado; outra rodada precisa assumir isso e reservar dados novos para uma conclusao independente.",
        "O TinyLM educacional pode seguir separado. Para o Coach principal, estes classificadores ainda devem ser auxiliares com esclarecimento/confirmacao, nao autorizacao automatica de mudancas ou garantia de seguranca.",
        "", "## Privacidade", "",
        "Textos/contatos sao minimizados antes das features; isso nao comprova anonimato. Registros individuais e pesos ficam ignorados pelo Git, mas o OneDrive pode sincroniza-los. Nao houve envio das conversas a APIs de IA. Direitos e uso comercial continuam exigindo revisao especifica."]
    output.mkdir(parents=True, exist_ok=True)
    (output / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(output / "recommendation.json", {"selected_by": "validation_macro_f1_supported_only", "models": selected,
        "automatic_app_promotion": False, "records_preserved": 12179})
    paths = [AI_ROOT / f"artifacts/baseline/{v}/{name}" for v in versions for name in ("manifest.json", "evaluation.json", "selection_frozen.json")]
    paths += [output / "RESULTS.md", output / "recommendation.json"]
    write_json(output / "manifest.json", {"files": {p.relative_to(AI_ROOT).as_posix(): file_sha256(p) for p in paths},
        "all_raw_predictions_private": True})
    print(output / "RESULTS.md")


if __name__ == "__main__":
    main()

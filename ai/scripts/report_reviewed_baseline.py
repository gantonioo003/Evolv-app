"""Readable summary and immutable audit of the measured release outputs."""
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.dataset import file_sha256
from evolv_nlp.real_data import write_json


def pct(value):
    return f"{value * 100:.1f}%" if value is not None else "nao medido"


def report():
    output = AI_ROOT / "artifacts/baseline/1.6.0"
    if (output / "release_audit.json").exists():
        raise ValueError("Report finalized; do not overwrite")
    manifest = json.loads((output / "manifest.json").read_text("utf-8"))
    metrics = json.loads((output / "evaluation.json").read_text("utf-8"))
    comparison = json.loads((output / "comparison.json").read_text("utf-8"))
    entities = json.loads((AI_ROOT / "artifacts/entities/1.3.0/manifest.json").read_text("utf-8"))
    lines = ["# Baseline 1.6.0: Resultados Medidos", "",
        "Dataset 1.7.0; 12.179 mensagens preservadas e processadas; referencia revisada por IA, nao gabarito humano.",
        "60 intencoes; 20 sinais positivos de risco independentes + none derivado. Pipeline opt-in, sem alteracoes no Planner.", "",
        "## Intencao", "", "| Conjunto | N | Accuracy | Macro F1 com suporte | Classes presentes/60 |",
        "| --- | ---: | ---: | ---: | ---: |"]
    names = {"train": "Treino (ajuste, nao generalizacao)", "validation": "Validacao (selecao)",
             "test": "Teste publico reservado", "external_human_language": "Pesquisa externa reservada"}
    for partition, name in names.items():
        value = metrics[partition]["intent"]
        lines.append(f"| {name} | {value['records']} | {pct(value['accuracy'])} | {pct(value['macro_f1_supported'])} | {value['classes_with_support']}/60 |")
    lines += ["", "Macro F1 com suporte considera classes presentes no conjunto, sem esconder previsoes erradas.",
              "O JSON tambem apresenta a media das 60 classes, inclusive as sem suporte. Nao ha teste independente de todas as acoes raras.",
              "", "## Risco Multirrotulo", "",
              "| Conjunto | Acuracia do conjunto exato | Micro F1 | Macro F1 com suporte | Sinais com suporte/20 |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for partition, name in names.items():
        value = metrics[partition]["risk"]
        lines.append(f"| {name} | {pct(value['exact_match_accuracy'])} | {pct(value['micro_f1'])} | {pct(value['macro_f1_supported'])} | {value['positive_labels_with_support']}/20 |")
    lines += ["", "A acuracia exige acertar todos os sinais da mensagem; nao equivale a antiga classificacao de risco unico.",
              "none nao entra como classe majoritaria para inflar macro F1 dos sinais positivos.", "",
              "## Comparacao Nas Mesmas Entradas", "",
              "Compara baseline 1.5.0 e 1.6.0 no novo teste, apenas em rotulos compartilhados. Modelos anteriores podem ter visto versoes anteriores da coleta; nao e teste cego contra um sistema externo.",
              "", "| Tarefa | Antes: acuracia | Agora: acuracia | Antes: macro F1 | Agora: macro F1 |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for task, name, key in (("intent", "Intencao", "accuracy"), ("risk", "Risco em sinais compartilhados", "exact_match_accuracy")):
        old, new = comparison[task]["old"], comparison[task]["new"]
        lines.append(f"| {name} | {pct(old[key])} | {pct(new[key])} | {pct(old['macro_f1_supported'])} | {pct(new['macro_f1_supported'])} |")
    lines += ["", f"Intencao: {comparison['intent']['records_shared_labels']} mensagens com rotulos compartilhados.",
              f"Risco: {comparison['risk']['shared_positive_labels']} sinais compartilhados; o modelo antigo emitia apenas um rotulo.",
              "Nao compare diretamente estes numeros com os 76% do antigo teste pequeno e da antiga taxonomia.",
              "", "## Modelos Escolhidos", ""]
    for task, selected in manifest["selected"].items():
        lines.append(f"- {task}: {selected['representation']} + {selected['classifier']}; C={selected['C']}; class_weight={selected['class_weight']}.")
    lines += ["", f"{manifest['trial_count']} candidatos; escolha e limites definidos pela validacao, ambos os modelos salvos antes do teste.",
              "Encoder MiniLM permanece congelado; nenhum ajuste de pesos do Transformer foi realizado.", "",
              "## Confianca e Regras", "",
              "| Conjunto | Cobertura de intencao aceita | Acerto entre aceitas | Macro F1 risco + regras |",
              "| --- | ---: | ---: | ---: |"]
    for partition in ("validation", "test", "external_human_language"):
        policy, fused = metrics[partition]["selective_intent"], metrics[partition]["risk_with_safety_rules"]
        lines.append(f"| {names[partition]} | {pct(policy['coverage'])} | {pct(policy['accuracy_when_accepted'])} | {pct(fused['macro_f1_supported'])} |")
    lines += ["", "Abstencao nao remove erros das metricas principais. Confianca nao e probabilidade calibrada.",
              "Regras priorizam cautela e podem produzir falsos positivos; seu resultado e separado do classificador.",
              "", "## Entidades", "",
              f"Tipos com implementacao: {entities['supported_types_before']} -> {entities['supported_types_after']}, de 89 declarados. Todas as 12.179 mensagens foram extraidas com verificacao de spans.",
              f"Regressao historica dos mesmos 50 tipos: micro F1 {pct(entities['historical_regression']['before']['micro_f1'])} -> {pct(entities['historical_regression']['after']['micro_f1'])}.",
              "Essa regressao ja era conhecida. Os 30 tipos novos possuem testes funcionais, mas nao F1 independente: faltam anotacoes exaustivas de entidades nas planilhas.",
              "", "## Todos Os Dados Aproveitados", "",
              "9.261 treino + 913 validacao + 955 teste + 255 pesquisa reservada + 795 desafio/revisao = 12.179.",
              "Previsoes para TODOS: private/predictions_all_12179.jsonl. Extracoes: private/entity_extractions_all_12179.jsonl.",
              "Os 795 tambem foram processados; indefinidos nao receberam gabarito inventado. Casos duvidosos e colisoes nao contaminam o resultado principal.",
              "", "## Limites Para O Coach", "",
              "Mais dados e melhor organizacao nao certificam seguranca clinica ou qualidade de producao.",
              "Pedidos raros e alguns riscos ainda precisam de mais avaliacoes independentes. Veja o suporte de cada classe abaixo.",
              "Nao ha diagnostico, escolha de exame, tratamento de lesao ou escrita automatica no Planner.",
              "Dados privados e pesos nao sao redistribuiveis automaticamente; minimizacao nao prova anonimato e nao impede OneDrive.",
              "", "## Suporte E Erros Por Intencao No Teste", "",
              "| Intencao | Suporte | Precisao | Recall | F1 |", "| --- | ---: | ---: | ---: | ---: |"]
    native = metrics["test"]["intent"]
    for label in native["matrix_labels"]:
        value = native["per_class"][label]
        lines.append(f"| {label} | {int(value['support'])} | {pct(value['precision'])} | {pct(value['recall'])} | {pct(value['f1-score'])} |")
    lines += ["", "## Sinais De Risco No Teste", "",
              "| Sinal | Suporte | Precisao | Recall | F1 |", "| --- | ---: | ---: | ---: | ---: |"]
    for label, value in sorted(metrics["test"]["risk"]["per_label"].items()):
        lines.append(f"| {label} | {value['support']} | {pct(value['precision'])} | {pct(value['recall'])} | {pct(value['f1'])} |")
    matrix = native["confusion_matrix"]
    confusions = sorted(((matrix[i][j], a, b) for i, a in enumerate(native["matrix_labels"])
                        for j, b in enumerate(native["matrix_labels"]) if i != j and matrix[i][j]), reverse=True)[:15]
    lines += ["", "## Confusoes Mais Frequentes", ""]
    lines.extend(f"- {a} -> {b}: {count}." for count, a, b in confusions)
    (output / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    paths = [p for p in output.rglob("*") if p.is_file() and "private" not in p.parts]
    write_json(output / "release_audit.json", {"files": {p.relative_to(output).as_posix(): file_sha256(p) for p in paths},
        "private_output_counts": 12179, "entity_manifest_sha256": file_sha256(AI_ROOT / "artifacts/entities/1.3.0/manifest.json")})
    print(output / "RESULTS.md")


if __name__ == "__main__":
    report()

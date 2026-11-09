"""Render recorded metrics and qualitative review without changing evaluation inputs."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AI_ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", type=Path, default=AI_ROOT / "artifacts/tinylm_evaluation/1.0.0")
    args = parser.parse_args()
    root = args.evaluation
    metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
    summary = json.loads((root / "generation_summary.json").read_text(encoding="utf-8"))
    review = json.loads((root / "qualitative_review.json").read_text(encoding="utf-8"))
    evaluation = json.loads((root / "evaluation.json").read_text(encoding="utf-8"))
    labels, splits = ["Treino", "Validação", "Teste"], ["train", "validation", "test"]
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.5), layout="constrained")
    figure.set_facecolor("#faf8f3")
    for axis, metric, title in zip(axes, ("loss", "perplexity"), ("Loss por token", "Perplexidade")):
        axis.set_facecolor("#faf8f3")
        for offset, model, color, label in ((-0.18, "initial", "#aaa298", "Inicial"),
                                             (0.18, "trained", "#b83b2f", "Treinado")):
            values = [metrics["primary"][model][split][metric] for split in splits]
            bars = axis.bar([i + offset for i in range(3)], values, width=0.34, color=color, label=label)
            axis.bar_label(bars, labels=[f"{value:.2f}" for value in values], padding=3, fontsize=9)
        axis.set_xticks(range(3), labels)
        axis.set_title(title + " ↓", loc="left", fontweight="bold")
        axis.spines[["top", "right"]].set_visible(False)
        if metric == "perplexity":
            axis.set_yscale("log")
            axis.set_ylim(10, 25000)
            axis.set_ylabel("Escala logarítmica")
        else:
            axis.set_ylim(0, 10.3)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, legend_labels, loc="outside lower center", ncol=2, frameon=False)
    figure.suptitle("TinyLM — avaliação do checkpoint fixo", x=0.06, ha="left", fontsize=15, fontweight="bold")
    for extension in ("png", "svg"):
        figure.savefig(root / f"evaluation_metrics.{extension}", dpi=180)
    plt.close(figure)
    lines = ["# 7.03.5 — Geração e avaliação do TinyLM", "",
             "Checkpoint da época 8, selecionado previamente por validação. Pesos e teste preservados.", "",
             "## Método principal: janelas de documento de até 256 tokens", "",
             "| Partição | Loss inicial | Loss treinada | PPL inicial | PPL treinada | Alvos |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for label, split in zip(labels, splits):
        a, b = metrics["primary"]["initial"][split], metrics["primary"]["trained"][split]
        lines.append(f"| {label} | {a['loss']:.4f} | {b['loss']:.4f} | {a['perplexity']:.2f} | {b['perplexity']:.2f} | {b['tokens']} |")
    lines += ["", "PPL = exp(loss média ponderada por alvos válidos). Logits originais, float32, sem filtros de geração.",
              "EOS é avaliado; BOS e padding não são alvos. Mesmo BPE e protocolo para os dois checkpoints.",
              "A perplexidade não mede veracidade nem qualidade clínica. A loss não é porcentagem de acertos.", "",
              "![Métricas do modelo](evaluation_metrics.png)", "",
              "## Contexto sobreposto: stride 128, medido separadamente", "",
              "| Partição | Loss inicial | Loss treinada | PPL inicial | PPL treinada |", "| --- | ---: | ---: | ---: | ---: |"]
    for label, split in zip(labels[1:], splits[1:]):
        a, b = metrics["strided_context"]["initial"][split], metrics["strided_context"]["trained"][split]
        lines.append(f"| {label} | {a['loss']:.4f} | {b['loss']:.4f} | {a['perplexity']:.2f} | {b['perplexity']:.2f} |")
    lines += ["", "O método sobreposto reutiliza somente contexto, sem contar alvos duas vezes. As medidas são identificadas separadamente; não substituem a medida principal.",
              "", "## Geração exploratória — todas as estratégias predefinidas", "",
              "| Estratégia | Amostras | Tokens médios | Paradas EOS | Limite atingido | Bigramas repetidos (média) | U+FFFD |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for strategy, row in summary.items():
        repeated = row["mean_repeated_bigram_fraction"]
        lines.append(f"| {strategy} | {row['samples']} | {row['mean_generated_tokens']:.1f} | {row['eos_stops']} | {row['budget_stops']} | {(100 * repeated):.1f}% | {row['unicode_replacement_characters']} |")
    lines += ["", f"Total: {evaluation['generation_samples']} amostras, até 64 tokens cada, 8 prompts próprios e 3 sementes nas estratégias aleatórias. Greedy usa uma semente porque não sorteia tokens.",
              "Bigramas são pares de palavras da continuação. Repetição e diversidade são diagnósticos descritivos, não notas de qualidade.",
              "As saídas integrais estão em `private/generations.jsonl`. Não foram selecionadas apenas as melhores gerações.",
              "", "## Leitura qualitativa", "", review["method"], ""]
    lines.extend(f"- {finding}" for finding in review["findings"])
    lines += ["", "| Prompt | Estratégia | Coerência (0–2) | Responde ao pedido | Observação |", "| --- | --- | ---: | --- | --- |"]
    for row in review["samples"]:
        lines.append(f"| {row['prompt_id']} | {row['strategy_id']} | {row['coherence']} | {row['addresses_prompt']} | {row['note']} |")
    lines += ["", "A leitura foi feita por IA, não por avaliadores humanos independentes. Não é uma revisão factual ou médica. Textos gerados são saídas experimentais, sem execução de ações no app.",
              "", "## Conclusão", "", review["conclusion"], "",
              "O corpus continua pequeno e predominantemente enciclopédico. O teste tem 42 documentos e 14.880 alvos; não demonstra competência geral de conversa ou do Coach.",
              "A fase TinyLM do zero está implementada e avaliada. Os próximos componentes do Coach principal continuam separados.", ""]
    (root / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    names = ["RESULTS.md", "qualitative_review.json", "evaluation_metrics.png", "evaluation_metrics.svg"]
    manifest = {"status": "completed", "matplotlib": matplotlib.__version__,
                "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "files": {name: {"sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
                                 "bytes": (root / name).stat().st_size} for name in names}}
    (root / "report_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str((root / "RESULTS.md").resolve()))

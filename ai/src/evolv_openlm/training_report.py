"""Render recorded training metrics; never reads the reserved test or model."""
from pathlib import Path
from .sft_data import read_json, sha
from .training import atomic_json


def render(run):
    run = Path(run)
    result = read_json(run / "results.json")
    if result["status"] != "complete":
        raise ValueError("Treinamento ainda não completo.")
    history = read_json(run / "history.json")
    original = result["original_model_metrics"]
    rows = []
    if original:
        rows.append(f"| Original NF4, antes do preparo | {original['train']['nll']:.6f} | {original['validation']['nll']:.6f} | {original['validation']['perplexity']:.4f} |")
    initial = history[0]
    rows.append(f"| Adaptador inicial, sem ajuste | {initial['train_nll']:.6f} | {initial['validation_nll']:.6f} | {initial['validation_perplexity']:.4f} |")
    rows.append(f"| Checkpoint escolhido, época {result['selected_epoch']} | {result['final_train_eval']['nll']:.6f} | {result['final_validation']['nll']:.6f} | {result['final_validation']['perplexity']:.4f} |")
    lines = ["# 7.04.4 — Treinamento QLoRA e validação", "",
        f"Modelo: {result['model_id']}. Revisão: `{result['model_revision']}`.", "",
        f"{result['epochs_completed']} épocas concluídas; {result['optimizer_steps']} passos de otimizador. Melhor época por validação: **{result['selected_epoch']}**.", "",
        "| Modelo / condição | NLL treino em eval | NLL validação | Perplexidade validação |",
        "| --- | ---: | ---: | ---: |", *rows, "",
        f"Validação melhorou em relação ao adaptador inicial: **{result['validation_improved_over_initial_adapter']}**.",
        f"Validação melhorou em relação ao original NF4: **{result['validation_improved_over_original']}**.", "",
        "Os checkpoints são selecionados pela validação, incluindo a época 0 como possibilidade de não melhorar. O preparo para QLoRA pode mudar a precisão de componentes congelados; por isso o original e o adaptador inicial têm referências separadas.", "",
        f"Pico de memória alocada medido no loop: {result['memory']['peak_allocated_mib']:.1f} MiB. Esse número não é todo o consumo de VRAM do processo e não inclui necessariamente o pico do carregamento.", "",
        f"Adaptador selecionado: `{result['best_adapter']}`. Último estado retomável: `{result['last_checkpoint']}`.", "",
        "A base original permanece separada. Checkpoints contêm somente adaptadores e estado do treinador, otimizador, scheduler e RNG. A retomada ocorre na última época completa.", "",
        "O conjunto SFT é pequeno e sintético. Melhor NLL não comprova qualidade de conversa, conhecimento clínico ou capacidade em pessoas reais. As losses de treino online usam dropout e pesos mudando; a tabela acima usa treino em eval para comparação.", "",
        "**O teste reservado não foi avaliado.** Comparação de geração original/adaptado e avaliação final pertencem à 7.04.5. Nenhum modelo foi conectado ou promovido ao aplicativo.", ""]
    (run / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    files = [run / "RESULTS.md"]
    plot = {"status": "not_available"}
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4.6), layout="constrained")
        epochs = [r["epoch"] for r in history]
        ax.plot(epochs, [r["validation_nll"] for r in history], color="#b6352b", marker="o", label="Validação por tokens")
        ax.plot(epochs, [r["train_nll"] for r in history], color="#6d747b", marker="s", linestyle="--", label="Treino online; época 0 em eval")
        ax.scatter([result["selected_epoch"]], [result["final_train_eval"]["nll"]], color="#24764e", marker="D", label="Treino em eval do selecionado", zorder=4)
        ax.axvline(result["selected_epoch"], color="#b6352b", alpha=.3, linestyle=":")
        ax.set(xlabel="Época", ylabel="NLL média por token-alvo", title="Evolv — ajuste QLoRA")
        ax.set_xticks(epochs)
        ax.grid(alpha=.18)
        ax.legend(fontsize=8)
        for ext in ["png", "svg"]:
            path = run / ("loss_curve." + ext)
            fig.savefig(path, dpi=180)
            files.append(path)
        plt.close(fig)
        plot = {"status": "rendered"}
    except ImportError as exc:
        plot = {"status": "skipped_missing_optional_dependency", "reason": str(exc)}
    atomic_json(run / "report_manifest.json", {"plot": plot, "files": {p.name: sha(p) for p in files}, "test_evaluated": False})

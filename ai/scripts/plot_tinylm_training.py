"""Export learning curves from recorded epoch metrics, without loading weights."""
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
    parser.add_argument("--run", type=Path, default=AI_ROOT / "artifacts/tinylm_training/1.0.0")
    args = parser.parse_args()
    history = json.loads((args.run / "history.json").read_text(encoding="utf-8"))
    results = json.loads((args.run / "results.json").read_text(encoding="utf-8"))
    epochs = [row["epoch"] for row in history]
    train_rows = [row for row in history if row["train_loss_online"] is not None]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"})
    figure, (loss_ax, lr_ax) = plt.subplots(2, 1, figsize=(9, 6), sharex=True,
                                          gridspec_kw={"height_ratios": [3, 1]}, layout="constrained")
    figure.set_facecolor("#faf8f3")
    for axis in (loss_ax, lr_ax):
        axis.set_facecolor("#faf8f3")
        axis.grid(axis="y", color="#dcd9d2", linewidth=0.7)
        axis.spines[["top", "right"]].set_visible(False)
    loss_ax.plot([row["epoch"] for row in train_rows],
                 [row["train_loss_online"] for row in train_rows], color="#387b92", marker="o",
                 label="Treino: média durante a época", linewidth=2)
    loss_ax.plot(epochs, [row["validation_loss"] for row in history], color="#b83b2f", marker="o",
                 label="Validação: pesos fixos", linewidth=2)
    loss_ax.scatter([results["best_epoch"]], [results["best_validation_loss"]], color="#b83b2f",
                    marker="*", s=160, edgecolor="#faf8f3", zorder=5, label="Checkpoint selecionado")
    loss_ax.set_title("TinyLM — curva de aprendizado", loc="left", fontsize=16, fontweight="bold")
    loss_ax.set_ylabel("Cross-entropy por token válido ↓")
    loss_ax.legend(frameon=False, fontsize=9)
    lr_ax.plot(epochs, [row["learning_rate"] for row in history], color="#706a60", marker=".")
    lr_ax.set_ylabel("LR ao final\nda época")
    lr_ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    lr_ax.set_xlabel("Época (0 = inicialização aleatória)")
    lr_ax.set_xticks(epochs)
    figure.suptitle("3,4 milhões de parâmetros · contexto 256 · teste reservado",
                   x=0.15, ha="left", fontsize=10, color="#686157")
    for extension in ("png", "svg"):
        figure.savefig(args.run / f"loss_curve.{extension}", dpi=180)
    plt.close(figure)
    names = ["results.json", "history.json", "history.csv", "model_config.json", "training_config.json",
             "binding.json", "checkpoint_index.json", "loss_curve.png", "loss_curve.svg"]
    manifest = {
        "status": results["status"], "matplotlib": matplotlib.__version__,
        "plot_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "files": {name: {"sha256": hashlib.sha256((args.run / name).read_bytes()).hexdigest(),
                         "bytes": (args.run / name).stat().st_size} for name in names},
        "checkpoint_integrity": "checkpoint_index.json records each private checkpoint hash",
    }
    (args.run / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str((args.run / "loss_curve.png").resolve()))

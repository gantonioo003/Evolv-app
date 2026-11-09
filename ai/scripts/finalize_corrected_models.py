"""Freeze validation-selected components, then evaluate the untouched holdouts."""
from collections import Counter
import csv
import json
from pathlib import Path
import sys

import numpy as np

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.corrected_pipeline import CorrectedPredictor, confidence_allowed
from evolv_nlp.corrected_release import load_partition
from evolv_nlp.dataset import file_sha256, read_jsonl
from evolv_nlp.real_data import write_json, write_jsonl
from evolv_nlp.review_training import compact, intent_metrics, risk_metrics, risk_matrix
from evolv_nlp.risk_rules_v14 import detect_risks


def pct(value):
    return "n.a." if value is None else f"{100 * value:.1f}%"


def main():
    output = AI_ROOT / "artifacts/baseline/1.8.0"
    if (output / "manifest.json").exists():
        return json.loads((output / "evaluation.json").read_text("utf-8"))
    paths = {"classical": output / "candidate_selection.json",
             "neural": AI_ROOT / "artifacts/baseline/1.8.1/candidate_selection.json"}
    candidates = {family: json.loads(path.read_text("utf-8")) for family, path in paths.items()}
    if not candidates["classical"].get("extra_preprocessing_completed"):
        raise ValueError("Pre-registered preprocessing ablations have not completed")
    frozen_path = output / "selection_frozen.json"
    if frozen_path.exists():
        selection = json.loads(frozen_path.read_text("utf-8"))
    else:
        chosen = {}
        for task in ("intent", "risk"):
            classical = candidates["classical"]["selected"][task]["validation"]["macro_f1_supported"]
            neural = candidates["neural"]["winners"][task]["score"]
            chosen[task] = "neural" if neural > classical else "classical"
        selection = {"model_version": "1.8.0", "dataset_version": "1.8.0", "chosen": chosen,
            "intent_classes": candidates["classical"]["intent_classes"],
            "risk_classes": candidates["classical"]["risk_classes"],
            "candidate_manifests": {family: {"sha256": file_sha256(path)} for family, path in paths.items()},
            "dataset_manifest_sha256": file_sha256(AI_ROOT / "data/releases/1.8.0/manifest.json"),
            "selection_rule": "highest corrected validation supported macro F1 per task; classical wins ties",
            "test_opened": False, "production_approved": False,
            "test_is_historical_previously_reported_not_new_independent_gold": True}
        write_json(frozen_path, selection)
    print("Frozen components before test:", selection["chosen"], flush=True)
    predictor = CorrectedPredictor(AI_ROOT, selection)
    old_predictions = {r["id"]: r for r in read_jsonl(AI_ROOT / "artifacts/baseline/1.6.0/private/predictions_all_12179.jsonl")}
    evaluations, before, predictions, errors, per_class = {}, {}, [], [], []
    classes, risk_classes = selection["intent_classes"], selection["risk_classes"]
    for part in ("train", "validation", "test", "external_human_language", "quarantine"):
        rows = load_partition(AI_ROOT, part)
        scores = predictor.scores([r["input"] for r in rows])
        intent = np.asarray(classes)[scores["intent"].argmax(1)]
        signals = scores["risk"] >= predictor.risk_thresholds()
        valid_i = np.asarray([r["label"] in classes for r in rows])
        valid_r = np.asarray([bool(r["risks"]) and set(r["risks"]) <= set(risk_classes) | {"none"} for r in rows])
        truth_i = np.asarray([r["label"] for r in rows])
        truth_r = risk_matrix(rows, risk_classes)
        prior_i = np.asarray([old_predictions[r["id"]]["predicted_intent"] for r in rows])
        prior_r = np.asarray([[label in old_predictions[r["id"]]["predicted_risks"] for label in risk_classes] for r in rows])
        evaluations[part] = {"intent": intent_metrics(truth_i[valid_i].tolist(), intent[valid_i], classes),
            "risk": risk_metrics(truth_r[valid_r], signals[valid_r], risk_classes),
            "records_processed": len(rows), "unscorable_intent": int((~valid_i).sum()),
            "unscorable_risk": int((~valid_r).sum()), "reference": "AI_reviewed_not_independent_human_gold"}
        before[part] = {"intent": intent_metrics(truth_i[valid_i].tolist(), prior_i[valid_i], classes),
                        "risk": risk_metrics(truth_r[valid_r], prior_r[valid_r], risk_classes)}
        ordered = np.sort(scores["intent"], axis=1)
        margins = ordered[:, -1] - ordered[:, -2]
        accept = np.asarray([confidence_allowed(predictor.policy(), str(label), float(margin)) for label, margin in zip(intent, margins)])
        evaluations[part]["selective_intent"] = {"coverage": float(accept.mean()), "accepted": int(accept.sum()),
            "accuracy_when_accepted": float(np.mean(intent[accept] == truth_i[accept])) if accept.any() else None,
            "all_predictions_still_in_headline_metrics": True, "automatic_planner_writes": False}
        certain = np.asarray([not r.get("ai_review", {}).get("uncertain", False) for r in rows])
        if part in {"train", "validation"}:
            mask = certain & valid_i
            rmask = certain & valid_r
            evaluations[part]["without_flagged_ai_doubts_sensitivity_only"] = {
                "intent": compact(intent_metrics(truth_i[mask].tolist(), intent[mask], classes)),
                "risk": compact(risk_metrics(truth_r[rmask], signals[rmask], risk_classes)),
                "not_independent_gold": True, "excluded_from_this_sensitivity": int((~certain).sum())}
        if part in {"validation", "test", "external_human_language"}:
            rule_signals = np.asarray([[label in detected.risks for label in risk_classes]
                                      for detected in (detect_risks(r["text"][:10000]) for r in rows)])
            evaluations[part]["risk_with_safety_rules"] = risk_metrics(truth_r[valid_r], (signals | rule_signals)[valid_r], risk_classes)
        for row, label, risk_signal in zip(rows, intent, signals):
            active = [name for name, flag in zip(risk_classes, risk_signal) if flag] or ["none"]
            predictions.append({"id": row["id"], "partition": part, "predicted_intent": str(label),
                                "predicted_risks": active, "reference_defined": row["label"] in classes})
            if row["label"] != label or set(row["risks"]) != set(active):
                errors.append({"id": row["id"], "partition": part, "text": row["text"], "context": row["context"],
                    "expected_intent": row["label"], "predicted_intent": str(label),
                    "expected_risks": row["risks"], "predicted_risks": active})
        for task, labels, truth, predicted, mask in [("intent", classes, truth_i, intent, valid_i),
                                                   ("risk", risk_classes + ["none"], truth_r, signals, valid_r)]:
            for label in labels:
                if task == "intent":
                    actual, observed = truth[mask] == label, predicted[mask] == label
                elif label == "none":
                    actual, observed = truth[mask].sum(1) == 0, predicted[mask].sum(1) == 0
                else:
                    actual, observed = truth[mask, risk_classes.index(label)].astype(bool), predicted[mask, risk_classes.index(label)]
                tp, fn = int((actual & observed).sum()), int((actual & ~observed).sum())
                fp, tn = int((~actual & observed).sum()), int((~actual & ~observed).sum())
                support = tp + fn
                per_class.append({"partition": part, "task": task, "label": label, "support": support,
                    "TP": tp, "FN": fn, "FP": fp, "TN": tn, "binary_accuracy": (tp + tn) / len(actual),
                    "recall": tp / support if support else None, "precision": tp / (tp + fp) if tp + fp else None,
                    "f1": 2 * tp / (2 * tp + fn + fp) if support else None})
        print(f"{part}: intent acc={evaluations[part]['intent']['accuracy']:.4f}, F1={evaluations[part]['intent']['macro_f1_supported']:.4f}; risk exact={evaluations[part]['risk']['exact_match_accuracy']:.4f}, F1={evaluations[part]['risk']['macro_f1_supported']:.4f}", flush=True)
    assert len(predictions) == len({r["id"] for r in predictions}) == 12179
    private = output / "private"
    write_jsonl(private / "predictions_all_12179.jsonl", predictions)
    write_jsonl(private / "errors.jsonl", errors)
    write_json(output / "evaluation.json", evaluations)
    write_json(output / "comparison_same_references.json", before)
    report_dir = AI_ROOT / "artifacts/review/2026-10-31"
    report_dir.mkdir(parents=True, exist_ok=True)
    with (report_dir / "metrics_per_class.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_class[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(per_class)
    release = json.loads((AI_ROOT / "data/releases/1.8.0/manifest.json").read_text("utf-8"))
    for part, digest in release["reserved_byte_identical"].items():
        if file_sha256(AI_ROOT / f"data/releases/1.7.0/private/{part}.jsonl") != digest or file_sha256(AI_ROOT / f"data/releases/1.8.0/private/{part}.jsonl") != digest:
            raise ValueError("Reserved data changed")
    source_files = ["src/evolv_nlp/corrected_release.py", "src/evolv_nlp/corrected_training.py",
                    "src/evolv_nlp/corrected_neural.py", "src/evolv_nlp/corrected_pipeline.py"]
    manifest = {**selection, "status": "experimental_opt_in_not_default", "selection_frozen_sha256": file_sha256(frozen_path),
        "test_opened": True, "test_used_for_selection": False,
        "all_imported_records_processed": len(predictions), "cpu_trial_count": len(candidates["classical"]["trials"]),
        "neural_checkpoint_count": len(candidates["neural"]["trials"]), "automatic_planner_writes": False,
        "automatically_promoted_to_app": False,
        "source_files": {name: file_sha256(AI_ROOT / name) for name in source_files},
        "reserved_data_verified_unchanged": True, "privacy_raw_text_sent_to_api": False}
    write_report(report_dir, candidates, evaluations, before, release, manifest)
    write_json(output / "manifest.json", manifest)
    return evaluations


def write_report(directory, candidates, evaluations, before, release, manifest):
    text = "# Evolv: fechamento NLP com revisao por IA\n\n31/10/2026. Dataset 1.8.0. Componentes selecionados apenas por validacao.\n\n"
    text += f"Revisados: 2.180 registros. {release['changes']['intent_changes']} intencoes e {release['changes']['risk_changes']} conjuntos de riscos mudaram, em {release['changes']['any_label_change']} mensagens. As 263 duvidas da IA continuam sinalizadas (164 treino, 99 validacao), sem exigir nova revisao humana para esta etapa de aprendizado.\n\n"
    text += "9.261 treino + 913 validacao + 955 teste historico + 255 pesquisa reservada + 795 desafio/quarentena = 12.179. Nenhum exemplo de teste entrou no treino. Os arquivos de teste, pesquisa e quarentena sao copias byte a byte da versao anterior.\n\n"
    text += "## Comparacao nas mesmas referencias\n\nA coluna anterior reaplica as previsoes da baseline 1.6.0 aos mesmos rotulos usados na coluna nova. Na validacao, isso evita confundir mudanca de gabarito com melhora de modelo. No teste e na pesquisa, os rotulos nao mudaram.\n\n"
    text += "| Conjunto | Tarefa | Acuracia anterior | Nova | F1 macro anterior | Novo |\n| --- | --- | ---: | ---: | ---: | ---: |\n"
    for part, name in [("validation", "Validacao corrigida por IA"), ("test", "Teste historico congelado"), ("external_human_language", "Pesquisa reservada"), ("train", "Treino (nao generalizacao)")]:
        for task, title, acc in [("intent", "Intencao", "accuracy"), ("risk", "Riscos", "exact_match_accuracy")]:
            old, new = before[part][task], evaluations[part][task]
            text += f"| {name} | {title} | {pct(old[acc])} | {pct(new[acc])} | {pct(old['macro_f1_supported'])} | {pct(new['macro_f1_supported'])} |\n"
    text += "\nRisco: acuracia do conjunto exato exige acertar todos os sinais. F1 macro de risco considera os sinais positivos com suporte, sem incluir none. As metricas por classe e suportes estao em metrics_per_class.csv. Classes sem exemplos nao tem desempenho medido. Acuracia binaria por classe pode parecer alta por contar muitos negativos; use recall e F1 tambem.\n\n"
    text += "## Experiencias\n\n"
    text += f"{manifest['cpu_trial_count']} candidatos/comparacoes classicos e {manifest['neural_checkpoint_count']} checkpoints neurais.\n\n"
    text += "TF-IDF de palavras/caracteres, BoW, SVM linear e RBF, regressao logistica, Naive Bayes, MLP, KNN supervisionado, reducao SVD/LSA, pesos para duvidas, classificacao hierarquica e soft voting. K-means com 30/60/120 centros foi ajustado somente no treino; foram testados frequencias de classes por cluster e atributos de proximidade dos centros.\n\n"
    text += "Foi testada a retirada de avisos artificiais de coleta de imagens e estados sinteticos nos canais lexicais (TF-IDF), mantendo conversas/contextos reais. Os embeddings congelados preservam a entrada original para uma comparacao controlada. Tambem foi testado um foco lexical adicional nas ultimas palavras da mensagem. Os textos armazenados e o teste congelado nao foram reescritos.\n\n"
    text += "MiniLM na GPU: contexto de ate 384 tokens, ajuste de 12 ou 4 camadas, AdamW, dropout, weight decay, suavizacao de rotulos, pesos de classes, peso 0,5 para duvidas e parada antecipada pela validacao. Nao e o TinyLM do zero.\n\n"
    for task in ("intent", "risk"):
        family = manifest["chosen"][task]
        detail = candidates["classical"]["selected"][task] if family == "classical" else candidates["neural"]["winners"][task]["trial"]
        text += f"### Selecionado: {task}\n\nFamilia: {family}.\n\n```json\n{json.dumps(detail, ensure_ascii=True, indent=2)}\n```\n\n"
    text += "### K-means medido\n\n| Experiencia | Tarefa | F1 macro validacao |\n| --- | --- | ---: |\n"
    for trial in candidates["classical"]["trials"]:
        if str(trial.get("view", "")).startswith("cluster") or trial["kind"] == "kmeans_frequency_baseline":
            text += f"| {trial['kind']} {trial.get('view', '')} | {trial['task']} | {pct(trial['validation']['macro_f1_supported'])} |\n"
    text += "\nK-means agrupa por proximidade sem aprender os rotulos. Para dar nomes aos grupos no baseline, foram usadas apenas as frequencias de rotulos do treino. Os clusters nao corrigem anotacoes automaticamente nem substituem a classificacao supervisionada por definicao. Referencia: https://scikit-learn.org/stable/auto_examples/text/plot_document_clustering.html\n\n"
    text += "## Confianca e seguranca\n\n| Conjunto | Mensagens aceitas | Acerto entre aceitas |\n| --- | ---: | ---: |\n"
    for part in ("validation", "test", "external_human_language"):
        value = evaluations[part]["selective_intent"]
        text += f"| {part} | {pct(value['coverage'])} | {pct(value['accuracy_when_accepted'])} |\n"
    text += "\nIsso mede abstencao, nao melhora artificialmente a accuracy principal. Os escores nao sao probabilidades calibradas. O alvo de 90% foi escolhido na validacao e nao garante 90% em pessoas novas. Intencoes com menos de cinco exemplos de validacao pedem esclarecimento, mesmo com margem alta.\n\n"
    text += "A pipeline nova e opt-in. Nao altera automaticamente a pipeline operacional. Riscos do modelo se somam as regras conservadoras. None nao significa liberacao medica. Nao ha diagnostico, escolha de exame ou prescricao de tratamento para lesao. Qualquer alteracao de plano permanece como proposta, com validacao e confirmacao, nunca escrita direta pelo classificador.\n\n"
    text += "## Limites e proxima fase\n\nOs rotulos sao referencias de IA, nao gabarito humano independente. A revisao selecionou discordancias do modelo anterior e pode carregar vies desse modelo. O teste historico ja apareceu em relatorios anteriores: nao e um teste novo independente. Nao houve ajuste apos ver os resultados desta rodada. As limitacoes nao sao apagadas por uma accuracy maior.\n\n"
    text += "O extrator de entidades e as 60 intencoes/21 riscos foram preservados. A planilha nao fornece spans de entidades: nao foi inventado um F1 novo para o extrator. O corpus TinyLM 1.2.0 nao recebeu explicacoes da IA nem conversas privadas automaticamente.\n\n"
    text += "Para aprendizado e portfolio, a rodada pode ser encerrada e podemos seguir para 7.03.1 (tokenizador do TinyLM). Treinar o TinyLM nao depende de atingir 90% no classificador de intencao. Isso nao e aprovacao de producao: o Coach principal continuara precisando de avaliacao de ponta a ponta, com mecanismos de esclarecimento e confirmacao.\n\n"
    text += "## Comando de inferencia\n\n```powershell\npython ai/scripts/analyze_message_corrected.py \"Posso trocar meu treino de terca para quinta?\"\n```\n\nUse o ambiente Python 3.12 com ai/requirements.neural.txt. Pesos e textos privados permanecem fora do Git. Nao foram enviados textos para APIs externas.\n"
    (directory / "RESULTS.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    result = main()
    print(json.dumps({part: {task: compact(value) for task, value in report.items() if task in {"intent", "risk"}} for part, report in result.items()}, indent=2))

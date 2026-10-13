from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Sequence

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.pipeline import Pipeline

from evolv_nlp.entities import (
    entity_signature,
    extract_entities,
    load_entity_catalog,
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"JSON invalido em {path}:{line_number}: {error}"
                ) from error
            if not isinstance(row, dict):
                raise ValueError(f"Registro invalido em {path}:{line_number}")
            rows.append(row)
    if not rows:
        raise ValueError(f"Dataset vazio: {path}")
    return rows


def _rounded(value: float) -> float:
    return round(float(value), 6)


def _classification_averages(
    expected: Sequence[str], predicted: Sequence[str]
) -> dict[str, Any]:
    result: dict[str, Any] = {"accuracy": _rounded(accuracy_score(expected, predicted))}
    for average in ("macro", "micro", "weighted"):
        precision, recall, f1, _ = precision_recall_fscore_support(
            expected,
            predicted,
            average=average,
            zero_division=0,
        )
        result[average] = {
            "precision": _rounded(precision),
            "recall": _rounded(recall),
            "f1": _rounded(f1),
        }
    return result


def evaluate_classifier(
    model: Pipeline,
    ids: Sequence[str],
    texts: Sequence[str],
    expected: Sequence[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not (len(ids) == len(texts) == len(expected)):
        raise ValueError("IDs, textos e rotulos precisam ter o mesmo tamanho")
    if not ids:
        raise ValueError("A avaliacao de classificacao nao pode estar vazia")

    probabilities = model.predict_proba(texts)
    model_labels = [str(value) for value in model.classes_]
    predictions = [
        model_labels[int(row_probabilities.argmax())]
        for row_probabilities in probabilities
    ]
    labels = sorted(set(expected) | set(predictions) | set(model_labels))
    matrix = confusion_matrix(expected, predictions, labels=labels)
    precision, recall, f1, support = precision_recall_fscore_support(
        expected,
        predictions,
        labels=labels,
        average=None,
        zero_division=0,
    )
    predicted_counts = Counter(predictions)
    per_class = {
        label: {
            "support": int(support[index]),
            "predicted": predicted_counts[label],
            "precision": _rounded(precision[index]),
            "recall": _rounded(recall[index]),
            "f1": _rounded(f1[index]),
        }
        for index, label in enumerate(labels)
    }

    confusion_counts = Counter(
        (truth, guess)
        for truth, guess in zip(expected, predictions)
        if truth != guess
    )
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    top3_hits = 0
    class_to_index = {label: index for index, label in enumerate(model_labels)}
    for row_id, text, truth, guess, row_probabilities in zip(
        ids, texts, expected, predictions, probabilities
    ):
        ranking = sorted(
            (
                {"label": label, "confidence": _rounded(row_probabilities[index])}
                for label, index in class_to_index.items()
            ),
            key=lambda item: (-item["confidence"], item["label"]),
        )[:3]
        top3_hits += int(any(item["label"] == truth for item in ranking))
        prediction = {
            "id": row_id,
            "text": text,
            "expected": truth,
            "predicted": guess,
            "correct": truth == guess,
            "confidence": ranking[0]["confidence"],
            "alternatives": ranking,
        }
        if ranking[0]["label"] != guess:
            raise ValueError("Predicao e maior probabilidade ficaram inconsistentes")
        rows.append(prediction)
        if truth != guess:
            errors.append(prediction)

    report = {
        "rows": len(ids),
        **_classification_averages(expected, predictions),
        "top3_accuracy": _rounded(top3_hits / len(ids)),
        "labels": labels,
        "per_class": per_class,
        "confusion_matrix": {
            "orientation": "rows=expected, columns=predicted",
            "labels": labels,
            "values": matrix.astype(int).tolist(),
        },
        "confusions": [
            {"expected": truth, "predicted": guess, "count": count}
            for (truth, guess), count in sorted(
                confusion_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "error_count": len(errors),
        "errors": errors,
    }
    return report, rows


def risk_diagnostics(predictions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    expected_risk = [row for row in predictions if row["expected"] != "none"]
    false_safe = [
        row
        for row in expected_risk
        if row["predicted"] == "none"
    ]
    expected_safe = [row for row in predictions if row["expected"] == "none"]
    false_alarms = [
        row
        for row in expected_safe
        if row["predicted"] != "none"
    ]
    detected = len(expected_risk) - len(false_safe)
    return {
        "risk_rows": len(expected_risk),
        "risk_detection_recall": _rounded(detected / len(expected_risk))
        if expected_risk
        else 0.0,
        "false_safe_count": len(false_safe),
        "false_safe_ids": [row["id"] for row in false_safe],
        "safe_rows": len(expected_safe),
        "false_alarm_count": len(false_alarms),
        "false_alarm_ids": [row["id"] for row in false_alarms],
        "note": (
            "Detection recall only checks risk versus none. Exact risk type is "
            "measured by the multiclass metrics."
        ),
    }


def evaluate_challenge(
    intent_model: Pipeline,
    risk_model: Pipeline,
    rows: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ids = [str(row["id"]) for row in rows]
    texts = [str(row["text"]) for row in rows]
    intents = [str(row["primary_intent"]) for row in rows]
    intent_report, intent_predictions = evaluate_classifier(
        intent_model, ids, texts, intents
    )

    risk_predictions = [str(value) for value in risk_model.predict(texts)]
    risk_rows: list[dict[str, Any]] = []
    exact = 0
    expected_risk_count = 0
    detected_risk_count = 0
    false_safe_ids: list[str] = []
    expected_safe_count = 0
    false_alarm_ids: list[str] = []
    for row, predicted in zip(rows, risk_predictions):
        expected_labels = [str(value) for value in row["risk_labels"]]
        accepted = predicted in expected_labels
        exact += int(accepted)
        has_risk = any(label != "none" for label in expected_labels)
        expected_risk_count += int(has_risk)
        detected = predicted != "none"
        detected_risk_count += int(has_risk and detected)
        if has_risk and not detected:
            false_safe_ids.append(str(row["id"]))
        if not has_risk:
            expected_safe_count += 1
            if detected:
                false_alarm_ids.append(str(row["id"]))
        risk_rows.append(
            {
                "id": row["id"],
                "text": row["text"],
                "expected": expected_labels,
                "predicted": predicted,
                "accepted": accepted,
            }
        )

    challenge_predictions = []
    intent_by_id = {row["id"]: row for row in intent_predictions}
    risk_by_id = {row["id"]: row for row in risk_rows}
    for row in rows:
        challenge_predictions.append(
            {
                "id": row["id"],
                "ambiguity_type": row["ambiguity_type"],
                "expected_behavior": row["expected_behavior"],
                "intent": intent_by_id[row["id"]],
                "risk": risk_by_id[row["id"]],
            }
        )

    return (
        {
            "rows": len(rows),
            "intent": intent_report,
            "risk": {
                "accepted_label_accuracy": _rounded(exact / len(rows)),
                "risk_rows": expected_risk_count,
                "risk_detection_recall": _rounded(
                    detected_risk_count / expected_risk_count
                )
                if expected_risk_count
                else 0.0,
                "false_safe_count": len(false_safe_ids),
                "false_safe_ids": false_safe_ids,
                "safe_rows": expected_safe_count,
                "false_alarm_count": len(false_alarm_ids),
                "false_alarm_ids": false_alarm_ids,
                "note": (
                    "Challenge rows may declare multiple acceptable risk labels; "
                    "the current classifier still emits one label."
                ),
            },
        },
        challenge_predictions,
    )


def evaluate_entities(
    dataset_path: Path,
    catalog_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = read_jsonl(dataset_path)
    catalog = load_entity_catalog(catalog_path)
    expected_by_type: Counter[str] = Counter()
    predicted_by_type: Counter[str] = Counter()
    true_positive_by_type: Counter[str] = Counter()
    expected_total = 0
    predicted_total = 0
    true_positive_total = 0
    exact_messages = 0
    empty_expected = 0
    empty_without_false_positive = 0
    errors: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []

    for row in rows:
        expected = Counter(entity_signature(item) for item in row["expected"])
        result = extract_entities(
            str(row["text"]),
            catalog,
            date.fromisoformat(str(row["reference_date"])),
        )
        predicted = Counter(entity_signature(item) for item in result.entities)
        overlap = expected & predicted
        is_exact = expected == predicted
        exact_messages += int(is_exact)
        expected_total += sum(expected.values())
        predicted_total += sum(predicted.values())
        true_positive_total += sum(overlap.values())
        if not expected:
            empty_expected += 1
            empty_without_false_positive += int(not predicted)

        for entity_type, _ in expected.elements():
            expected_by_type[entity_type] += 1
        for entity_type, _ in predicted.elements():
            predicted_by_type[entity_type] += 1
        for entity_type, _ in overlap.elements():
            true_positive_by_type[entity_type] += 1

        missing = [
            {"entity_type": entity_type, "value": json.loads(value)}
            for entity_type, value in (expected - predicted).elements()
        ]
        unexpected = [
            {"entity_type": entity_type, "value": json.loads(value)}
            for entity_type, value in (predicted - expected).elements()
        ]
        prediction = {
            "id": row["id"],
            "slice": row.get("slice", "unspecified"),
            "text": row["text"],
            "exact": is_exact,
            "expected": row["expected"],
            "predicted": [
                {"entity_type": item.entity_type, "value": item.value}
                for item in result.entities
            ],
            "missing": missing,
            "unexpected": unexpected,
        }
        predictions.append(prediction)
        if not is_exact:
            errors.append(prediction)

    precision = true_positive_total / predicted_total if predicted_total else 0.0
    recall = true_positive_total / expected_total if expected_total else 0.0
    micro_f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    entity_types = sorted(set(expected_by_type) | set(predicted_by_type))
    per_type: dict[str, Any] = {}
    type_scores: list[tuple[float, float, float]] = []
    for entity_type in entity_types:
        tp = true_positive_by_type[entity_type]
        expected_count = expected_by_type[entity_type]
        predicted_count = predicted_by_type[entity_type]
        type_precision = tp / predicted_count if predicted_count else 0.0
        type_recall = tp / expected_count if expected_count else 0.0
        type_f1 = (
            2 * type_precision * type_recall / (type_precision + type_recall)
            if type_precision + type_recall
            else 0.0
        )
        type_scores.append((type_precision, type_recall, type_f1))
        per_type[entity_type] = {
            "support": expected_count,
            "predicted": predicted_count,
            "true_positive": tp,
            "false_positive": predicted_count - tp,
            "false_negative": expected_count - tp,
            "precision": _rounded(type_precision),
            "recall": _rounded(type_recall),
            "f1": _rounded(type_f1),
        }

    macro = {
        "precision": _rounded(
            sum(score[0] for score in type_scores) / len(type_scores)
        )
        if type_scores
        else 0.0,
        "recall": _rounded(sum(score[1] for score in type_scores) / len(type_scores))
        if type_scores
        else 0.0,
        "f1": _rounded(sum(score[2] for score in type_scores) / len(type_scores))
        if type_scores
        else 0.0,
    }
    return (
        {
            "rows": len(rows),
            "expected_entities": expected_total,
            "predicted_entities": predicted_total,
            "micro": {
                "precision": _rounded(precision),
                "recall": _rounded(recall),
                "f1": _rounded(micro_f1),
            },
            "macro": macro,
            "exact_message_accuracy": _rounded(exact_messages / len(rows)),
            "negative_messages": {
                "rows": empty_expected,
                "without_false_positive": empty_without_false_positive,
                "specificity": _rounded(empty_without_false_positive / empty_expected)
                if empty_expected
                else 0.0,
            },
            "per_type": per_type,
            "error_count": len(errors),
            "errors": errors,
            "scoring_contract": (
                "Exact multiset match on normalized entity_type and value. "
                "Character spans and attributes are not scored in version 1.0.0."
            ),
        },
        predictions,
    )


def write_confusion_csv(path: Path, report: dict[str, Any]) -> None:
    matrix = report["confusion_matrix"]
    labels = matrix["labels"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["expected\\predicted", *labels])
        for label, values in zip(labels, matrix["values"]):
            writer.writerow([label, *values])


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def render_error_report(metrics: dict[str, Any]) -> str:
    intent = metrics["test"]["intent"]
    risk = metrics["test"]["risk"]
    entities = metrics["entities"]
    challenge = metrics["challenge"]

    lines = [
        "# Evolv NLP 7.02.3 - Relatorio de avaliacao e erros",
        "",
        "## Resultado principal",
        "",
        "| Componente | Registros | Precisao macro | Recall macro | Macro F1 |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| Intencao | {intent['rows']} | {intent['macro']['precision']:.3f} | {intent['macro']['recall']:.3f} | {intent['macro']['f1']:.3f} |",
        f"| Risco | {risk['rows']} | {risk['macro']['precision']:.3f} | {risk['macro']['recall']:.3f} | {risk['macro']['f1']:.3f} |",
        f"| Entidades | {entities['rows']} | {entities['macro']['precision']:.3f} | {entities['macro']['recall']:.3f} | {entities['macro']['f1']:.3f} |",
        "",
        "O teste de classificacao possui apenas um exemplo por classe. As metricas",
        "sao uma primeira medida independente, mas possuem alta incerteza e nao",
        "demonstram qualidade de producao.",
        "",
        "## Intencoes confundidas",
        "",
    ]
    if intent["confusions"]:
        lines.extend(
            f"- `{item['expected']}` -> `{item['predicted']}`: {item['count']}"
            for item in intent["confusions"]
        )
    else:
        lines.append("- Nenhuma no conjunto congelado.")

    lines.extend(["", "## Riscos confundidos", ""])
    if risk["confusions"]:
        lines.extend(
            f"- `{item['expected']}` -> `{item['predicted']}`: {item['count']}"
            for item in risk["confusions"]
        )
    else:
        lines.append("- Nenhum no conjunto congelado.")
    diagnostics = risk["safety_diagnostics"]
    lines.extend(
        [
            "",
            f"Falsos seguros (`risco` -> `none`): {diagnostics['false_safe_count']}.",
            f"Falsos alarmes (`none` -> `risco`): {diagnostics['false_alarm_count']}.",
            "",
            "## Entidades",
            "",
            f"- Micro F1: {entities['micro']['f1']:.3f}",
            f"- Macro F1: {entities['macro']['f1']:.3f}",
            f"- Mensagens inteiramente corretas: {entities['exact_message_accuracy']:.3f}",
            f"- Mensagens com erro: {entities['error_count']}",
            "",
        ]
    )
    weakest = sorted(
        entities["per_type"].items(),
        key=lambda item: (item[1]["f1"], -item[1]["support"], item[0]),
    )[:10]
    lines.append("Tipos de entidade com menor F1:")
    lines.extend(
        f"- `{entity_type}`: F1 {values['f1']:.3f}, suporte {values['support']}"
        for entity_type, values in weakest
    )

    lines.extend(
        [
            "",
            "## Desafio adversarial",
            "",
            f"- Intencao, accuracy: {challenge['intent']['accuracy']:.3f}",
            f"- Risco, rotulo aceito: {challenge['risk']['accepted_label_accuracy']:.3f}",
            f"- Risco, recall de deteccao: {challenge['risk']['risk_detection_recall']:.3f}",
            f"- Risco, falsos alarmes: {challenge['risk']['false_alarm_count']}",
            "",
            "## Limitacoes registradas",
            "",
            "- O teste de intencao tem 30 mensagens, uma por classe.",
            "- O teste de risco tem 13 mensagens, uma por classe.",
            "- As probabilidades da regressao logistica nao estao calibradas.",
            "- O classificador retorna apenas uma intencao e um risco por mensagem.",
            "- Entidades fora do catalogo, erros de digitacao e referencias ao contexto",
            "  podem falhar.",
            "- A avaliacao de entidades compara tipo e valor normalizado, nao o span.",
            "- Nenhum resultado desta fase autoriza alteracao automatica no Planner.",
            "",
            "Os exemplos de teste permaneceram inalterados. Melhorias futuras devem",
            "criar uma nova versao de dados e um novo conjunto de teste, sem ajustar esta",
            "versao para os erros observados aqui.",
            "",
        ]
    )
    return "\n".join(lines)

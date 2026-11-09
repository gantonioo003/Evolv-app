"""Paired held-out inference: no optimization, model selection or app mutation."""
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from .sft_data import read_json, read_jsonl, sha
from .training import atomic_json


def prompt_messages(row):
    messages = row["messages"]
    if not messages or messages[-1]["role"] != "assistant":
        raise ValueError("A conversa avaliada precisa terminar com a referência assistant.")
    prompt = [dict(item) for item in messages[:-1]]
    if not prompt or prompt[-1]["role"] != "user":
        raise ValueError("O prompt precisa terminar com user.")
    return prompt


def build_cases(test_rows, challenges, system_prompt):
    cases = []
    for row in test_rows:
        cases.append({"id": row["id"], "suite": "frozen_test", "group_id": row["group_id"],
            "category": row["domain"], "intent": row["intent"], "risks": row["risks"],
            "messages": prompt_messages(row), "reference": row["messages"][-1]["content"],
            "expectation": "Responder ao pedido e contexto, respeitando o system prompt; referência sintética não é resposta única."})
    for row in challenges:
        cases.append({"id": row["id"], "suite": "challenge", "group_id": row["id"],
            "category": row["category"], "messages": [{"role": "system", "content": system_prompt},
                *row.get("history", []), {"role": "user", "content": row["prompt"]}],
            "reference": None, "expectation": row["expectation"]})
    if len({row["id"] for row in cases}) != len(cases):
        raise ValueError("IDs duplicados na comparação.")
    return cases


def diagnostics(result):
    words = re.findall(r"\w+", result["text"].lower())
    bigrams = list(zip(words, words[1:]))
    return {"empty": not result["text"].strip(), "words": len(words),
        "truncated_at_budget": not result["stopped_at_eos"],
        "repeated_bigram_fraction": 1 - len(set(bigrams)) / len(bigrams) if bigrams else 0.0}


def aggregate_nll(rows):
    tokens = sum(row["target_tokens"] for row in rows)
    if not tokens:
        raise ValueError("Conjunto sem tokens-alvo.")
    nll = sum(row["nll_sum"] for row in rows) / tokens
    return {"nll": nll, "perplexity": math.exp(nll), "target_tokens": tokens, "examples": len(rows)}


def paired_bootstrap(original, adapted, replicates=2000, seed=2026):
    """Resample independent families, preserving paired variants and token weights."""
    left, right = {r["id"]: r for r in original}, {r["id"]: r for r in adapted}
    if not left or left.keys() != right.keys():
        raise ValueError("Comparação requer exatamente os mesmos IDs.")
    groups = defaultdict(list)
    for key, row in left.items():
        if (row["group_id"], row["target_tokens"]) != (right[key]["group_id"], right[key]["target_tokens"]):
            raise ValueError("Grupos/alvos diferentes na comparação.")
        groups[row["group_id"]].append(key)
    names = sorted(groups)
    rng = random.Random(seed)
    differences = []
    for _ in range(replicates):
        ids = [key for group in rng.choices(names, k=len(names)) for key in groups[group]]
        differences.append(aggregate_nll([right[k] for k in ids])["nll"] - aggregate_nll([left[k] for k in ids])["nll"])
    differences.sort()
    return {"metric": "adapted_NLL_minus_original_NLL", "groups": len(groups),
        "replicates": replicates, "seed": seed, "interval_95_percentile":
        [differences[int(.025 * (replicates - 1))], differences[int(.975 * (replicates - 1))]],
        "limitation": "Conditional on this small synthetic family sample; not population safety or human quality."}


def verify_inputs(ai_root, run, cache):
    from .training import checkpoint_path
    binding = read_json(run / "binding.json")
    result = read_json(run / "results.json")
    if result["status"] != "complete":
        raise ValueError("Treino não concluído.")
    for relative, expected in {"configs/openlm.v1.json": binding["model_config_sha256"],
            "configs/openlm.lora.v1.json": binding["recipe_sha256"],
            "data/sft/1.0.0/manifest.json": binding["data_manifest_sha256"]}.items():
        if sha(ai_root / relative) != expected:
            raise ValueError(f"Entrada mudou: {relative}.")
    data_root = ai_root / "data/sft/1.0.0"
    manifest = read_json(data_root / "manifest.json")
    for relative, expected in manifest["outputs"].items():
        if sha(data_root / relative) != expected:
            raise ValueError(f"SFT congelado mudou: {relative}.")
    for name, expected in binding["code"].items():
        if sha(ai_root / "src/evolv_openlm" / name) != expected:
            raise ValueError(f"Código de treino mudou: {name}.")
    best = read_json(run / "checkpoint_index.json")["best"]
    checkpoint = checkpoint_path(run, best["path"])
    for name, expected in best["files"].items():
        if Path(name).name != name or sha(checkpoint / name) != expected:
            raise ValueError("Checkpoint diferente dos hashes selecionados.")
    snapshot = cache / ("models--" + binding["model_id"].replace("/", "--")) / "snapshots" / binding["model_revision"]
    for name, expected in {**binding["weights_sha256"], **manifest["tokenizer_files"]}.items():
        if sha(snapshot / name) != expected:
            raise ValueError(f"Peso/tokenizador alterado: {name}.")
    return checkpoint, binding


def evaluate_examples(model, dataset, collator, ids):
    import torch
    from .training import amp, forward_nll
    model.eval()
    rows = []
    with torch.inference_mode():
        for index, identity in enumerate(ids):
            batch = {key: value.to("cuda") for key, value in collator([dataset[index]]).items()}
            with amp("cuda"):
                value, count = forward_nll(model, batch)
            loss = value.double().item()
            if not math.isfinite(loss):
                raise FloatingPointError("Loss não finita.")
            rows.append({"id": identity["id"], "group_id": identity["group_id"],
                         "nll_sum": loss, "target_tokens": count})
    return rows


def generate_cases(model, tokenizer, cases, settings, destination, progress, variant):
    from .runtime import answer
    destination = Path(destination)
    previous = read_jsonl(destination) if destination.exists() else []
    if [r["id"] for r in previous] != [r["id"] for r in cases[:len(previous)]]:
        raise ValueError("Saídas parciais não correspondem ao protocolo.")
    import json
    import os
    with destination.open("a", encoding="utf-8", newline="\n") as stream:
        for index, case in enumerate(cases[len(previous):], start=len(previous)):
            result = answer(model, tokenizer, case["messages"], settings)
            row = {"id": case["id"], "suite": case["suite"], "category": case["category"],
                   "variant": variant, **result, "diagnostics": diagnostics(result)}
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            previous.append(row)
            atomic_json(progress, {"status": "generating", "variant": variant,
                "completed": index + 1, "total_per_variant": len(cases), "last_case": case["id"],
                "last_seconds": result["seconds"], "last_tokens_per_second": result["tokens_per_second"]})
            print(f"{variant}: {index + 1}/{len(cases)} ({result['seconds']:.1f}s, {result['generated_tokens']} tokens)", flush=True)
    return previous

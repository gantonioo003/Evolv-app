"""Build a small, attributed SFT release; no model weights or optimizer required."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import unicodedata

IGNORE_INDEX = -100
SPLITS = ("train", "validation", "test")
PII = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\+55[\s(.-]*\d{2}[\s)./-]*\d{4,5}[\s.-]*\d{4}\b")
CONTROL = re.compile(r"<\|(?:im_start|im_end|endoftext)\|>")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(text):
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def prompt_text(row):
    return "\n".join(m["role"] + ": " + m["content"] for m in row["messages"][1:-1])


def validate_messages(messages):
    if len(messages) < 3 or messages[0]["role"] != "system" or messages[-1]["role"] != "assistant":
        raise ValueError("Conversa sem system ou resposta final do assistant.")
    for i, message in enumerate(messages):
        expected = "system" if i == 0 else ("user" if i % 2 else "assistant")
        if message["role"] != expected or not isinstance(message["content"], str) or not message["content"].strip():
            raise ValueError("Papéis fora de ordem ou conteúdo vazio.")
        if CONTROL.search(message["content"]):
            raise ValueError("Token de controle literal em conteúdo comum.")
        if PII.search(message["content"]):
            raise ValueError("Possível identificador pessoal direto em exemplo SFT.")
        if "\ufffd" in message["content"]:
            raise ValueError("Caractere de substituição Unicode em exemplo SFT.")


def encode_example(row, tokenizer, max_length):
    """Labels align with input_ids: Hugging Face causal LM shifts internally."""
    messages = row["messages"]
    validate_messages(messages)
    full = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False, return_dict=True)["input_ids"]
    prefix = tokenizer.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True, return_dict=True)["input_ids"]
    if full[:len(prefix)] != prefix:
        raise ValueError("O template do prompt não é prefixo exato da conversa completa.")
    if len(full) > max_length:
        return None
    if len(full) <= len(prefix) or tokenizer.eos_token_id not in full[len(prefix):]:
        raise ValueError("Alvo vazio ou sem terminador da resposta.")
    labels = [IGNORE_INDEX] * len(prefix) + full[len(prefix):]
    return {"id": row["id"], "group_id": row["group_id"], "input_ids": full,
            "attention_mask": [1] * len(full), "labels": labels,
            "prompt_tokens": len(prefix), "target_tokens": len(full) - len(prefix)}


def semantic_groups(rows, ngram=5, threshold=0.8):
    """Union authored families, exact prompts/targets and high ngram overlap."""
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        a, b = find(a), find(b)
        parent[max(a, b)] = min(a, b)

    seen = {}
    shingles = []
    for i, row in enumerate(rows):
        for key in [("family", row["group_id"]), ("prompt", normalized(prompt_text(row))),
                    ("answer", normalized(row["messages"][-1]["content"]))]:
            if key in seen:
                union(i, seen[key])
            else:
                seen[key] = i
        words = re.findall(r"\w+", normalized(prompt_text(row) + " " + row["messages"][-1]["content"]))
        shingles.append(set(tuple(words[j:j + ngram]) for j in range(len(words) - ngram + 1)))
    links = 0
    for i, left in enumerate(shingles):
        if len(left) < 8:
            continue
        for j in range(i):
            right = shingles[j]
            if find(i) == find(j) or not right:
                continue
            overlap = len(left & right) / len(left | right)
            if overlap >= threshold:
                union(i, j)
                links += 1
    members = defaultdict(list)
    for i in range(len(rows)):
        members[find(i)].append(i)
    for indices in members.values():
        families = sorted({rows[i]["group_id"] for i in indices})
        group_id = "sft-group:" + hashlib.sha256("|".join(families).encode()).hexdigest()[:20]
        for i in indices:
            rows[i]["family_id"] = rows[i]["group_id"]
            rows[i]["group_id"] = group_id
    return {"groups": len(members), "additional_near_duplicate_links": links,
            "method": f"exact prompt/answer and {ngram}-word Jaccard >= {threshold}; incomplete paraphrase detection"}


def split_groups(rows, seed, ratios=None):
    ratios = ratios or {"train": 0.8, "validation": 0.1, "test": 0.1}
    if set(ratios) != set(SPLITS) or abs(sum(ratios.values()) - 1) > 1e-9 or any(v <= 0 for v in ratios.values()):
        raise ValueError("Proporções de partição inválidas.")
    groups = defaultdict(list)
    for row in rows:
        groups[row["group_id"]].append(row)
    buckets = defaultdict(list)
    for group, members in groups.items():
        domain = sorted({r["domain"] for r in members})[0]
        multiturn = any(len(r["messages"]) > 3 for r in members)
        buckets[(domain, multiturn)].append(group)
    partition = {}
    rng = random.Random(seed)
    for domain in sorted(buckets):
        ids = sorted(buckets[domain])
        rng.shuffle(ids)
        count = len(ids)
        test_count = max(1, round(count * ratios["test"])) if count >= 3 else 0
        val_count = max(1, round(count * ratios["validation"])) if count >= 3 else 0
        if test_count + val_count >= count:
            raise ValueError("Proporções sem grupos suficientes para treino.")
        for i, group in enumerate(ids):
            partition[group] = "test" if i < test_count else "validation" if i < test_count + val_count else "train"
    # A class with a single authored family must remain in train, never split
    # paraphrases of that family just to make per-class holdout counts look full.
    features = lambda members: {("intent", r["intent"]) for r in members} | {("risk", x) for r in members for x in r["risks"]}
    required = features(rows)
    learned = set().union(*(features(members) for gid, members in groups.items() if partition[gid] == "train"))
    for feature in sorted(required - learned):
        if feature in learned:
            continue
        candidates = sorted(gid for gid, members in groups.items() if feature in features(members))
        chosen = candidates[0]
        partition[chosen] = "train"
        learned.update(features(groups[chosen]))
    result = {split: [] for split in SPLITS}
    for row in sorted(rows, key=lambda r: r["id"]):
        row["split"] = partition[row["group_id"]]
        result[row["split"]].append(row)
    if any(not result[s] for s in SPLITS):
        raise ValueError("Partição vazia.")
    return result


def audit_splits(splits):
    owners = {}
    for split, rows in splits.items():
        for row in rows:
            validate_messages(row["messages"])
            for name, value in [("id", row["id"]), ("group", row["group_id"]),
                                ("prompt", normalized(prompt_text(row))),
                                ("answer", normalized(row["messages"][-1]["content"]))]:
                key = (name, value)
                if key in owners and owners[key] != split:
                    raise ValueError(f"Vazamento entre partições: {name}.")
                owners[key] = split
    return {"cross_split_group_collisions": 0, "cross_split_exact_prompt_collisions": 0,
            "cross_split_exact_answer_collisions": 0,
            "note": "Sem colisões nos testes declarados; não prova ausência de toda paráfrase."}


def build_rows(ai_root, model_config):
    root = Path(ai_root)
    chunks = read_json(root / "data/knowledge/knowledge_chunks.v1.json")["chunks"]
    questions = read_json(root / "data/sft_sources/v1/knowledge_prompts.json")
    answers = read_json(root / "data/sft_sources/v1/knowledge_answers.json")
    scenarios = read_json(root / "data/sft_sources/v1/scenarios.json")
    sources = {s["id"]: s for s in read_json(root / "data/metadata/sources.v1.json")["sources"]}
    taxonomy = read_json(root / "data/releases/1.8.0/taxonomy.json")
    intents = {x["id"] for x in taxonomy["intents"]}
    risks = {x["id"] for x in taxonomy["risks"]}
    chunk_map = {c["id"]: c for c in chunks}
    if set(questions) != set(chunk_map) or set(answers) != set(chunk_map):
        raise ValueError("Perguntas da base de conhecimento incompletas ou desconhecidas.")
    rows = []
    system = {"role": "system", "content": model_config["system_prompt"]}
    for c in chunks:
        if not set(c["source_ids"]) <= set(sources):
            raise ValueError("Fonte desconhecida na base de conhecimento.")
        answer = answers[c["id"]]
        intent = {"training": "ask_training_concept", "nutrition": "ask_nutrition_concept",
                  "recovery": "ask_recovery", "safety": "ask_health_guidance"}[c["domain"]]
        for i, prompt in enumerate(questions[c["id"]]):
            rows.append({"id": f"kb:{c['id']}:{i}", "group_id": "knowledge:" + c["id"],
                         "domain": c["domain"], "source": "evolv_knowledge_synthetic_qa",
                         "intent": intent, "risks": c["risk_tags"] or ["none"],
                         "knowledge_ids": [c["id"]], "source_ids": c["source_ids"],
                         "source_urls": [sources[x].get("url", "repository-local") for x in c["source_ids"]],
                         "answer_origin": "ai_authored_paraphrase_of_existing_project_knowledge", "synthetic": True,
                         "review_status": "ai_prepared_not_independent_human_gold",
                         "messages": [system.copy(), {"role": "user", "content": prompt}, {"role": "assistant", "content": answer}]})
    seen = set()
    for case in scenarios:
        if case["id"] in seen or case["intent"] not in intents or not set(case.get("risks", ["none"])) <= risks:
            raise ValueError("Cenário duplicado ou rótulo desconhecido.")
        seen.add(case["id"])
        knowledge_ids = case.get("knowledge_ids", [])
        if not set(knowledge_ids) <= set(chunk_map):
            raise ValueError("Cenário cita conhecimento desconhecido.")
        source_ids = sorted({sid for kid in knowledge_ids for sid in chunk_map[kid]["source_ids"]})
        planner = case["intent"].startswith(("replace_", "move_", "set_", "remember_", "adjust_", "change_", "update_", "record_", "confirm_", "reject_", "undo_", "adapt_", "create_", "preserve_", "defer_"))
        domain = "safety" if case.get("risks") else "planner" if planner else "dialogue"
        for i, prompt in enumerate(case["prompts"]):
            if case.get("context"):
                prompt = "Contexto fornecido pelo aplicativo (simulado): " + case["context"] + "\n\nMensagem: " + prompt
            rows.append({"id": f"case:{case['id']}:{i}", "group_id": "scenario:" + case["id"],
                         "domain": domain, "source": "evolv_authored_conversation", "intent": case["intent"],
                         "risks": case.get("risks", ["none"]), "knowledge_ids": knowledge_ids,
                         "source_ids": source_ids, "source_urls": [sources[x].get("url", "repository-local") for x in source_ids],
                         "answer_origin": "ai_authored_product_scenario_with_declared_support",
                         "synthetic": True, "review_status": "ai_prepared_not_independent_human_gold",
                         "messages": [system.copy()] + case.get("history", []) +
                         [{"role": "user", "content": prompt}, {"role": "assistant", "content": case["answer"]}]})
    for row in rows:
        validate_messages(row["messages"])
    return rows, taxonomy


def prepare(ai_root, output, tokenizer, tokenizer_files, data_config):
    root, output = Path(ai_root), Path(output)
    if output.exists():
        raise FileExistsError("Versão de dados já existe; escolha uma pasta nova.")
    model_config_path = root / "configs/openlm.v1.json"
    model_config = read_json(model_config_path)
    source_files = [model_config_path, root / "configs/openlm.data.v1.json",
                    root / "data/sft_sources/v1/knowledge_prompts.json", root / "data/sft_sources/v1/scenarios.json",
                    root / "data/sft_sources/v1/knowledge_answers.json",
                    root / "data/knowledge/knowledge_chunks.v1.json", root / "data/metadata/sources.v1.json",
                    root / "data/releases/1.8.0/taxonomy.json", root / "data/releases/1.8.0/private/records.jsonl"]
    source_files += [root / f"data/lm_corpus/1.2.0/{s}.jsonl" for s in SPLITS]
    initial_hashes = {p.relative_to(root).as_posix(): sha(p) for p in source_files}
    nlp = read_jsonl(root / "data/releases/1.8.0/private/records.jsonl")
    protected = set()
    inventory = []
    for row in nlp:
        if row["partition"] != "train":
            protected.add(normalized(row["text"]))
        inventory.append({"source": "nlp_1.8.0", "id": row["id"], "partition": row["partition"],
                          "group_id": row["group_id"], "disposition": "nlp_only_no_curated_response_pair",
                          "text_sha256": hashlib.sha256(row["text"].encode()).hexdigest()})
    for split in SPLITS:
        for row in read_jsonl(root / f"data/lm_corpus/1.2.0/{split}.jsonl"):
            if split != "train":
                protected.add(normalized(row["text"]))
            inventory.append({"source": "tinylm_corpus_1.2.0", "id": row["doc_id"], "partition": split,
                              "group_id": row["group_id"], "disposition": "causal_corpus_not_imported_as_chat_pair"})
    rows, taxonomy = build_rows(root, model_config)
    rejected, accepted = [], []
    for row in rows:
        if any(normalized(m["content"]) in protected for m in row["messages"] if m["role"] == "user"):
            rejected.append({"id": row["id"], "reason": "exact_match_historical_nontraining_text"})
        else:
            accepted.append(row)
    grouping = semantic_groups(accepted, data_config["near_duplicate_word_ngram"], data_config["near_duplicate_jaccard_threshold"])
    splits = split_groups(accepted, data_config["seed"], data_config["split_ratios"])
    tokens = {split: [] for split in SPLITS}
    final = {split: [] for split in SPLITS}
    for split in SPLITS:
        for row in splits[split]:
            encoded = encode_example(row, tokenizer, data_config["max_sequence_length"])
            if encoded is None:
                rejected.append({"id": row["id"], "reason": "sequence_too_long_no_truncation", "assigned_split": split})
            else:
                final[split].append(row)
                tokens[split].append(encoded)
    checks = audit_splits(final)
    if sum(len(final[s]) for s in SPLITS) + len(rejected) != len(rows):
        raise ValueError("Contabilidade de candidatos incompleta.")
    counts = {}
    for split in SPLITS:
        values = tokens[split]
        counts[split] = {"conversations": len(values), "groups": len({r["group_id"] for r in final[split]}),
                         "multiturn": sum(len(r["messages"]) > 3 for r in final[split]),
                         "tokens": sum(len(r["input_ids"]) for r in values),
                         "target_tokens": sum(r["target_tokens"] for r in values),
                         "max_tokens": max(len(r["input_ids"]) for r in values),
                         "sources": dict(Counter(r["source"] for r in final[split])),
                         "intents": dict(sorted(Counter(r["intent"] for r in final[split]).items())),
                         "risks": dict(sorted(Counter(x for r in final[split] for x in r["risks"]).items()))}
    all_rows = [r for values in final.values() for r in values]
    covered = {r["intent"] for r in all_rows}
    covered_risks = {x for r in all_rows for x in r["risks"]}
    if covered != {r["intent"] for r in final["train"]} or covered_risks != {x for r in final["train"] for x in r["risks"]}:
        raise ValueError("Rótulo presente no conjunto, mas ausente do treino.")
    final_hashes = {p.relative_to(root).as_posix(): sha(p) for p in source_files}
    if final_hashes != initial_hashes:
        raise ValueError("Uma fonte foi alterada durante a preparação.")
    output.mkdir(parents=True)
    for split in SPLITS:
        write_jsonl(output / f"private/{split}.jsonl", final[split])
        write_jsonl(output / f"private/{split}_tokens.jsonl", tokens[split])
    write_jsonl(output / "private/source_inventory.jsonl", inventory)
    write_jsonl(output / "private/excluded.jsonl", rejected)
    write_json(output / "config.json", data_config)
    report = {"version": data_config["version"], "created_at": datetime.now(timezone.utc).isoformat(),
              "model_id": model_config["model_id"], "model_revision": model_config["revision"],
              "candidates": len(rows), "accepted": len(all_rows), "excluded": len(rejected), "splits": counts,
              "grouping": grouping, "checks": checks, "all_sft_examples_synthetic": True,
              "covered_intents": len(covered), "covered_risks": len(covered_risks),
              "missing_intents": sorted({x["id"] for x in taxonomy["intents"]} - covered),
              "missing_risks": sorted({x["id"] for x in taxonomy["risks"]} - covered_risks),
              "source_inventory": dict(Counter(r["source"] for r in inventory)),
              "existing_sources_preserved": True, "assistant_only_loss": "last_turn_only",
              "labels_shifted_in_preparation": False, "model_weights_loaded": False,
              "limitations": ["Small synthetic SFT seed, not 12000 curated answers.",
                              "No independent human gold or clinical validation.",
                              "Ngram grouping cannot detect all semantic paraphrases.",
                              "Presence of an intent/risk does not demonstrate sufficient coverage.",
                              "Synthetic test shares project knowledge and authoring style; not independent real-user evaluation."]}
    write_json(output / "report.json", report)
    files = {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}
    write_json(output / "manifest.json", {"version": data_config["version"], "sources": initial_hashes,
               "tokenizer_files": {p.name: sha(p) for p in tokenizer_files},
               "outputs": files, "code": {"sft_data.py": sha(Path(__file__))}})
    return report

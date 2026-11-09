"""Frozen next-token evaluation and exploratory decoding; no fitting or updates."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import heapq
import json
import math
from pathlib import Path
import statistics

import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader

from . import LM_EVALUATION_VERSION
from .data import load_prepared_data
from .dataset import NextTokenDataset
from .generation import GenerationConfig, generate
from .model import TinyLM, TinyLMConfig
from .tokenizer import EvolvTokenizer, sha256
from .tokenizer_training import audit_corpus, read_rows
from .training import atomic_json, load_trained_model


class StridedEvaluationDataset(NextTokenDataset):
    """Score every next-token target once, with overlapping context only."""
    def __init__(self, artifact_dir: str | Path, split: str, stride: int):
        super().__init__(artifact_dir, split)
        if type(stride) is not int or not 1 <= stride <= self.context_length:
            raise ValueError("Stride deve estar entre 1 e o tamanho do contexto.")
        self.windows = []
        for doc, (start, stop) in enumerate(zip(self.offsets[:-1], self.offsets[1:])):
            length = int(stop - start)
            for first_target in range(1, length, stride):
                target_stop = min(first_target + stride, length)
                input_start = max(0, target_stop - 1 - self.context_length)
                self.windows.append({
                    "document_index": doc, "start": int(start) + input_start,
                    "valid_targets": target_stop - input_start - 1,
                    "unscored_context": first_target - input_start - 1,
                })

    def __len__(self):
        return len(self.windows)

    def window_info(self, index):
        return self.windows[index]

    def __getitem__(self, index):
        sample = super().__getitem__(index)
        sample["labels"][:self.window_info(index)["unscored_context"]] = -100
        return sample


def perplexity(loss: float) -> float | None:
    if not math.isfinite(loss) or loss < 0:
        raise ValueError("Loss deve ser finita e nao negativa.")
    return math.exp(loss) if loss < 709 else None


def evaluate_partition(model, dataset, rows: list[dict], tokenizer, *, batch_size: int = 16,
                       keep_errors: int = 0) -> tuple[dict, list[dict], list[dict]]:
    device = next(model.parameters()).device
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, drop_last=False,
                        generator=torch.Generator().manual_seed(20261101))
    documents = [dict(doc_id=row["doc_id"], group_id=row["group_id"], source=row["source"],
                      tokens=0, nll_sum=0.0, correct=0) for row in rows]
    heap, sequence_index, serial = [], 0, 0
    was_training = model.training
    model.eval()
    try:
        with torch.inference_mode():
            for cpu_batch in loader:
                batch = {key: value.to(device) for key, value in cpu_batch.items()}
                logits = model(batch["input_ids"], attention_mask=batch["attention_mask"])["logits"].float()
                labels = batch["labels"].masked_fill(~batch["attention_mask"], -100)
                valid = labels.ne(-100)
                nll = F.cross_entropy(logits.reshape(-1, model.config.vocab_size), labels.reshape(-1),
                                      ignore_index=-100, reduction="none").view_as(labels)
                if not bool(torch.isfinite(nll).all()):
                    raise FloatingPointError("NLL nao finita na avaliacao.")
                predictions = logits.argmax(dim=-1)
                row_tokens = valid.sum(dim=1).cpu().tolist()
                row_nll = nll.double().sum(dim=1).cpu().tolist()
                row_correct = ((predictions == labels) & valid).sum(dim=1).cpu().tolist()
                for row_index in range(len(row_tokens)):
                    info = dataset.window_info(sequence_index + row_index)
                    document = documents[info["document_index"]]
                    document["tokens"] += row_tokens[row_index]
                    document["nll_sum"] += row_nll[row_index]
                    document["correct"] += row_correct[row_index]
                wrong = valid & predictions.ne(labels)
                if keep_errors and bool(wrong.any()):
                    values, positions = torch.topk(nll.masked_fill(~wrong, -1).reshape(-1),
                                                  min(keep_errors, int(wrong.sum())))
                    for value, position in zip(values.cpu().tolist(), positions.cpu().tolist()):
                        if len(heap) >= keep_errors and value <= heap[0][0]:
                            continue
                        sample, column = divmod(position, labels.shape[1])
                        info = dataset.window_info(sequence_index + sample)
                        row = rows[info["document_index"]]
                        target, predicted = int(labels[sample, column]), int(predictions[sample, column])
                        top_ids = logits[sample, column].topk(5).indices.cpu().tolist()
                        error = {
                            "doc_id": row["doc_id"], "source": row["source"], "license": row["license"],
                            "attribution_url": row.get("attribution_url"), "nll": value,
                            "target_id": target, "predicted_id": predicted, "top5_ids": top_ids,
                            "prefix": tokenizer.decode(cpu_batch["input_ids"][sample, :column + 1].tolist())[-180:],
                            "target_piece": tokenizer.decode([target]), "predicted_piece": tokenizer.decode([predicted]),
                        }
                        serial += 1
                        heapq.heappush(heap, (value, serial, error))
                        if len(heap) > keep_errors:
                            heapq.heappop(heap)
                sequence_index += len(row_tokens)
    finally:
        model.train(was_training)
        dataset.close()
    if any(document["tokens"] < 1 for document in documents):
        raise ValueError("Algum documento ficou sem alvos avaliados.")
    sources = defaultdict(lambda: {"documents": 0, "tokens": 0, "nll_sum": 0.0, "correct": 0})
    for document in documents:
        aggregate = sources[document["source"]]
        aggregate["documents"] += 1
        for key in ("tokens", "nll_sum", "correct"):
            aggregate[key] += document[key]
        document["loss"] = document["nll_sum"] / document["tokens"]
        document["perplexity"] = perplexity(document["loss"])
    tokens = sum(document["tokens"] for document in documents)
    nll_sum = sum(document["nll_sum"] for document in documents)
    loss = nll_sum / tokens
    for aggregate in sources.values():
        aggregate["loss"] = aggregate["nll_sum"] / aggregate["tokens"]
        aggregate["perplexity"] = perplexity(aggregate["loss"])
        aggregate["next_token_accuracy"] = aggregate["correct"] / aggregate["tokens"]
    metrics = {
        "documents": len(documents), "sequences": sequence_index, "tokens": tokens,
        "nll_sum": nll_sum, "loss": loss, "perplexity": perplexity(loss),
        "next_token_accuracy": sum(document["correct"] for document in documents) / tokens,
        "sources": dict(sources), "precision": "float32", "unmodified_logits": True,
    }
    return metrics, documents, [item[2] for item in sorted(heap, reverse=True)]


def _write_jsonl(path: Path, rows: list[dict]):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, allow_nan=False) + "\n")


def evaluate_release(data_dir: Path, corpus: Path, tokenizer_dir: Path, training_run: Path,
                     protocol_path: Path, output: Path, *, device: str = "auto") -> dict:
    if output.exists():
        raise FileExistsError("A pasta de avaliacao ja existe; use outra pasta sem alterar o teste.")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    metadata = load_prepared_data(data_dir)
    corpus_audit = audit_corpus(corpus)
    if corpus_audit != metadata["report"]["source_audit"]:
        raise ValueError("O corpus nao corresponde aos dados preparados.")
    tokenizer = EvolvTokenizer.load(tokenizer_dir)
    if sha256(tokenizer_dir / "private/tokenizer.json") != metadata["manifest"]["tokenizer_sha256"]:
        raise ValueError("Tokenizador divergente dos dados preparados.")
    index = json.loads((training_run / "checkpoint_index.json").read_text(encoding="utf-8"))
    if (index["best"]["sha256"] != protocol["checkpoint_sha256"]
            or index["best"]["epoch"] != protocol["checkpoint_epoch"]
            or index["binding"]["prepared_manifest_sha256"] != sha256(data_dir / "manifest.json")
            or index["binding"]["tokenizer_sha256"] != metadata["manifest"]["tokenizer_sha256"]
            or metadata["config"]["context_length"] != protocol["context_length"]
            or protocol["precision"] != "float32"):
        raise ValueError("Checkpoint ou metodo divergente do protocolo predefinido.")
    for strategy in protocol["strategies"]:
        GenerationConfig(**{key: value for key, value in strategy.items() if key != "id"})
    selected = "cuda" if device == "auto" and torch.cuda.is_available() else device
    selected = "cpu" if selected == "auto" else selected
    if selected not in ("cpu", "cuda"):
        raise ValueError("Dispositivo invalido.")
    torch.set_num_threads(4)
    output.mkdir(parents=True)
    private = output / "private"
    private.mkdir()
    atomic_json(output / "protocol.json", protocol)
    binding = {
        "protocol_sha256": sha256(protocol_path),
        "data_manifest_sha256": sha256(data_dir / "manifest.json"),
        "corpus_manifest_sha256": corpus_audit["manifest_sha256"],
        "tokenizer_sha256": metadata["manifest"]["tokenizer_sha256"],
        "checkpoint_index_sha256": sha256(training_run / "checkpoint_index.json"),
        "checkpoint_sha256": index["best"]["sha256"],
        "frozen_before_test_at": datetime.now(timezone.utc).isoformat(),
        "generation_not_selected_by_test": True,
    }
    atomic_json(output / "frozen_selection.json", binding)
    rows_by_split = {split: list(read_rows(corpus / f"{split}.jsonl")) for split in ("train", "validation", "test")}
    initial_record = next(record for record in index["epochs"] if record["epoch"] == 0)
    initial_path = (training_run / initial_record["file"]).resolve()
    if not initial_path.is_relative_to(training_run.resolve() / "private") or sha256(initial_path) != initial_record["sha256"]:
        raise ValueError("Checkpoint inicial alterado.")
    checkpoint = torch.load(initial_path, map_location="cpu", weights_only=True)
    if checkpoint["epoch"] != 0 or checkpoint["binding"] != index["binding"]:
        raise ValueError("Checkpoint inicial nao pertence a esta rodada.")
    model = TinyLM(TinyLMConfig(**checkpoint["model_config"]))
    model.load_state_dict(checkpoint["model"])
    model = model.to(selected).eval()
    metrics = {"primary": {}, "strided_context": {}}
    for model_name in ("initial", "trained"):
        if model_name == "trained":
            del model
            model, _ = load_trained_model(training_run, device=selected)
        metrics["primary"][model_name] = {}
        metrics["strided_context"][model_name] = {}
        for split in ("train", "validation", "test"):
            dataset = NextTokenDataset(data_dir, split)
            keep = protocol["token_error_examples_per_split"] if model_name == "trained" and split != "train" else 0
            measured, documents, errors = evaluate_partition(
                model, dataset, rows_by_split[split], tokenizer,
                batch_size=protocol["batch_size"], keep_errors=keep,
            )
            if measured["tokens"] != metadata["report"]["partitions"][split]["target_tokens"]:
                raise AssertionError("Contagem de alvos divergente na avaliacao.")
            metrics["primary"][model_name][split] = measured
            _write_jsonl(private / f"{model_name}_{split}_documents.jsonl", documents)
            if errors:
                _write_jsonl(private / f"{split}_token_errors.jsonl", errors)
            print(json.dumps({"event": "partition_evaluated", "model": model_name, "split": split,
                              "loss": measured["loss"], "perplexity": measured["perplexity"]}), flush=True)
        for split in protocol["secondary_splits"]:
            dataset = StridedEvaluationDataset(data_dir, split, protocol["secondary_stride"])
            measured, _, _ = evaluate_partition(model, dataset, rows_by_split[split], tokenizer,
                                                 batch_size=protocol["batch_size"])
            if measured["tokens"] != metadata["report"]["partitions"][split]["target_tokens"]:
                raise AssertionError("Stride contou alvos duplicados ou incompletos.")
            metrics["strided_context"][model_name][split] = measured
    atomic_json(output / "metrics.json", metrics)
    generations = []
    for prompt in protocol["prompts"]:
        for strategy in protocol["strategies"]:
            seeds = protocol["seeds"] if strategy["do_sample"] else protocol["seeds"][:1]
            for seed in seeds:
                settings = {key: value for key, value in strategy.items() if key != "id"}
                settings.update(max_new_tokens=protocol["max_new_tokens"], seed=seed)
                sample = generate(model, tokenizer, prompt["text"], GenerationConfig(**settings))
                generations.append({"prompt_id": prompt["id"], "prompt_kind": prompt["kind"],
                                    "strategy_id": strategy["id"], **sample})
        print(json.dumps({"event": "prompt_generated", "prompt_id": prompt["id"]}), flush=True)
    _write_jsonl(private / "generations.jsonl", generations)
    summary = {}
    for strategy in protocol["strategies"]:
        samples = [row for row in generations if row["strategy_id"] == strategy["id"]]
        repeated = [row["diagnostics"]["repeated_bigram_fraction"] for row in samples
                    if row["diagnostics"]["repeated_bigram_fraction"] is not None]
        summary[strategy["id"]] = {
            "samples": len(samples), "mean_generated_tokens": statistics.fmean(row["generated_tokens"] for row in samples),
            "eos_stops": sum(row["stop_reason"] == "eos" for row in samples),
            "budget_stops": sum(row["stop_reason"] == "max_new_tokens" for row in samples),
            "empty_completions": sum(row["diagnostics"]["empty_completion"] for row in samples),
            "mean_repeated_bigram_fraction": statistics.fmean(repeated) if repeated else None,
            "unicode_replacement_characters": sum(row["diagnostics"]["unicode_replacement_characters"] for row in samples),
        }
    atomic_json(output / "generation_summary.json", summary)
    review = protocol["qualitative_review"]
    selected_samples = [row for row in generations if row["strategy_id"] in review["strategy_ids"]
                        and row["config"]["seed"] == review["seed"]]
    _write_jsonl(private / "qualitative_review_samples.jsonl", selected_samples)
    if (sha256(protocol_path) != binding["protocol_sha256"]
            or sha256(training_run / "checkpoint_index.json") != binding["checkpoint_index_sha256"]
            or load_prepared_data(data_dir) != metadata or audit_corpus(corpus) != corpus_audit):
        raise ValueError("Entradas alteradas durante a avaliacao.")
    report = {
        "evaluation_version": LM_EVALUATION_VERSION, "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(), "binding": binding,
        "device": selected, "torch": str(torch.__version__), "precision": "float32",
        "primary_method": protocol["primary_method"], "secondary_stride": protocol["secondary_stride"],
        "generation_samples": len(generations), "qualitative_review_samples": len(selected_samples),
        "test_evaluated_without_updates": True, "optimizer_steps": 0,
        "inputs_preserved": True,
        "interpretation": "PPL depends on tokenizer/context protocol; generation diagnostics do not certify factuality.",
    }
    atomic_json(output / "evaluation.json", report)
    names = ["protocol.json", "frozen_selection.json", "metrics.json", "generation_summary.json", "evaluation.json"]
    names += [str(path.relative_to(output)).replace("\\", "/") for path in sorted(private.iterdir())]
    atomic_json(output / "manifest.json", {
        "status": "completed", "version": LM_EVALUATION_VERSION,
        "source_sha256": {name: sha256(Path(__file__).parent / name) for name in ("generation.py", "lm_evaluation.py")},
        "files": {name: {"sha256": sha256(output / name), "bytes": (output / name).stat().st_size} for name in names},
    })
    return report

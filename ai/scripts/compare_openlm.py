"""Final frozen comparison of the selected QLoRA adapter; never trains or deploys."""
import argparse
import gc
import json
from pathlib import Path
import random
import sys
import time
from importlib.metadata import version

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_openlm.runtime import DEFAULT_CACHE, load_model, load_settings
from evolv_openlm.sft_data import read_json, read_jsonl, sha
from evolv_openlm.sft_dataset import SFTCollator, SFTDataset
from evolv_openlm.training import atomic_json, evaluate_nll, fingerprint
from evolv_openlm.comparison import aggregate_nll, build_cases, evaluate_examples, generate_cases, paired_bootstrap, verify_inputs
from evolv_openlm.batched_inference import generate_cases_batched


def run(args):
    import torch
    from filelock import FileLock
    from torch.utils.data import DataLoader
    protocol = read_json(args.protocol)
    settings = load_settings()
    if protocol["do_sample"] is not False or protocol["max_new_tokens"] != settings["max_new_tokens"]:
        raise ValueError("Protocolo exige greedy e o mesmo limite fixo do runtime.")
    if type(protocol.get("generation_batch_size")) is not int or not 1 <= protocol["generation_batch_size"] <= 4:
        raise ValueError("Lote de geração precisa ser inteiro entre 1 e 4.")
    training_run = AI_ROOT / protocol["training_run"]
    data_root = AI_ROOT / protocol["data_release"]
    args.output.mkdir(parents=True, exist_ok=True)
    private = args.output / "private"
    private.mkdir(exist_ok=True)
    with FileLock(str(args.output / ".evaluation.lock"), timeout=1):
        if (args.output / "results.json").exists():
            raise FileExistsError("Avaliação já encerrada; não refazer teste nesta versão.")
        print("Conferindo entradas congeladas e checkpoints...", flush=True)
        checkpoint, binding = verify_inputs(AI_ROOT, training_run, args.cache_dir)
        test_rows = read_jsonl(data_root / "private/test.jsonl")
        challenges_path = AI_ROOT / protocol["challenge_file"]
        cases = build_cases(test_rows, read_json(challenges_path), settings["system_prompt"])
        frozen = {"protocol": protocol, "protocol_sha256": sha(args.protocol),
            "challenges_sha256": sha(challenges_path), "training_binding": binding,
            "checkpoint_sha256": sha(checkpoint / "adapter_model.safetensors"),
            "cases_sha256": fingerprint(cases), "code": {name: sha(AI_ROOT / name) for name in
                ["scripts/compare_openlm.py", "src/evolv_openlm/comparison.py", "src/evolv_openlm/batched_inference.py"]},
            "packages": {name: version(name) for name in ["torch", "transformers", "peft", "bitsandbytes"]}}
        preregistered = args.output / "protocol_frozen.json"
        if preregistered.exists() and read_json(preregistered) != frozen:
            raise ValueError("Protocolo/código/entradas diferentes; retomar somente a mesma avaliação.")
        atomic_json(preregistered, frozen)
        atomic_json(private / "cases.json", cases)
        started = time.perf_counter()
        random.seed(protocol["seed"])
        torch.manual_seed(protocol["seed"])
        torch.cuda.manual_seed_all(protocol["seed"])
        dataset = SFTDataset(data_root, "test", allow_test=True)
        if len(dataset) != len(test_rows):
            raise ValueError("IDs e exemplos tokenizados diferentes.")
        if [(r["id"], r["group_id"]) for r in dataset.rows] != [(r["id"], r["group_id"]) for r in test_rows]:
            raise ValueError("Ordem de IDs/grupos diverge entre textos e tokens.")
        metrics = {}
        for variant in ["original", "adapted"]:
            torch.backends.cuda.matmul.allow_tf32 = False
            atomic_json(args.output / "progress.json", {"status": "loading", "variant": variant})
            print(f"Carregando {variant} NF4...", flush=True)
            model, tokenizer = load_model(settings, args.cache_dir, download=False)
            if variant == "adapted":
                from peft import PeftModel, prepare_model_for_kbit_training
                model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
                model = PeftModel.from_pretrained(model, str(checkpoint), is_trainable=False,
                    local_files_only=True, autocast_adapter_dtype=True)
                for parameter in model.parameters():
                    parameter.requires_grad_(False)
                model.eval()
            collator = SFTCollator(tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
            # Reproduce validation solely as loading/precision sanity check, not selection.
            validation = SFTDataset(data_root, "validation")
            # The training loop enabled TF32 only after measuring the original.
            # Reproduce each historical validation under its actual setting;
            # all scored test inference/generation below uses TF32 disabled.
            torch.backends.cuda.matmul.allow_tf32 = variant == "adapted"
            sanity = evaluate_nll(model, DataLoader(validation, batch_size=1, collate_fn=collator, num_workers=0), "cuda")
            torch.backends.cuda.matmul.allow_tf32 = False
            expected = read_json(training_run / "results.json")
            expected_nll = expected["original_model_metrics"]["validation"]["nll"] if variant == "original" else expected["final_validation"]["nll"]
            if abs(sanity["nll"] - expected_nll) > 1e-5:
                raise ValueError(f"Recarga {variant} não reproduziu a validação: {sanity['nll']} vs {expected_nll}.")
            print(f"{variant}: validação reproduzida {sanity['nll']:.6f}; medindo teste...", flush=True)
            token_rows = evaluate_examples(model, dataset, collator, test_rows)
            atomic_json(private / f"{variant}_nll.json", token_rows)
            metrics[variant] = {"test": aggregate_nll(token_rows), "validation_reload_check": sanity}
            atomic_json(args.output / "metrics_partial.json", metrics)
            model.config.use_cache = True
            atomic_json(args.output / f"{variant}_generation_config.json", {
                "model_defaults":model.generation_config.to_dict(),
                "explicit_overrides":{"do_sample":False,"max_new_tokens":settings["max_new_tokens"],
                    "pad_token_id":tokenizer.eos_token_id,"eos_token_id":tokenizer.eos_token_id},
                "attention":settings["attention"], "max_input_tokens":settings["max_input_tokens"]})
            if hasattr(model, "gradient_checkpointing_disable"):
                model.gradient_checkpointing_disable()
            # Warm up the same generation path; not scored and explicitly excluded from timing.
            from evolv_openlm.runtime import answer
            answer(model, tokenizer, [{"role":"user","content":"Olá"}], settings, max_new_tokens=2)
            generate_cases_batched(model, tokenizer, cases, settings, private / f"{variant}_generations.jsonl",
                args.output / "progress.json", variant, protocol["generation_batch_size"])
            del model, tokenizer
            gc.collect()
            torch.cuda.empty_cache()
        interval = paired_bootstrap(read_json(private / "original_nll.json"), read_json(private / "adapted_nll.json"),
            protocol["bootstrap_replicates"], protocol["bootstrap_seed"])
        verify_inputs(AI_ROOT, training_run, args.cache_dir)
        results = {"status": "generation_complete_review_pending", "phase":"7.04.5", "metrics": metrics,
            "paired_group_bootstrap": interval, "test_conversations": len(test_rows),
            "challenge_cases": len(cases) - len(test_rows), "generated_answers": 2 * len(cases),
            "elapsed_seconds": time.perf_counter() - started, "test_evaluated":True,
            "frozen_training_and_test_preserved":True, "model_promoted_to_app":False,
            "protocol_fingerprint":fingerprint(frozen), "qualitative_review":"pending"}
        atomic_json(args.output / "results.json", results)
        atomic_json(args.output / "manifest.json", {"outputs": {p.relative_to(args.output).as_posix():sha(p)
            for p in sorted(args.output.rglob("*")) if p.is_file() and p.name not in ["manifest.json", ".evaluation.lock", "progress.json"]}})
        atomic_json(args.output / "progress.json", {"status":results["status"], "test_evaluated":True,
            "generated_answers":2 * len(cases)})
        print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=AI_ROOT / "configs/openlm.evaluation.v1.0.1.json")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=AI_ROOT / "artifacts/openlm_evaluation/1.0.1")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as exc:
        atomic_json(args.output / "progress.json", {"status":"failed", "error_type":type(exc).__name__, "message":str(exc)})
        raise


if __name__ == "__main__":
    main()

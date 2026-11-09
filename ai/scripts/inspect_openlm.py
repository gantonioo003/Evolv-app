"""Download e conferência de viabilidade; não faz fine-tuning nem usa o teste do projeto."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys
import time

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_openlm.runtime import DEFAULT_CACHE, DEFAULT_CONFIG, answer, load_model, load_settings


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=AI_ROOT / "artifacts/openlm/1.0.0")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--http-download", action="store_true", help="Alternativa HTTP com conferência dos hashes oficiais.")
    parser.add_argument("--check-backward", action="store_true")
    args = parser.parse_args()
    if (args.output / "smoke_report.json").exists():
        raise FileExistsError("Relatório já existe; escolha outra pasta de saída.")
    import torch
    import psutil
    from huggingface_hub import snapshot_download
    config = load_settings(args.config)
    print("1/4 Conferindo hardware e arquivos oficiais...", flush=True)
    start = time.perf_counter()
    if args.http_download:
        from evolv_openlm.download import download_snapshot
        snapshot = download_snapshot(config["model_id"], config["revision"], args.cache_dir)
    else:
        snapshot = Path(snapshot_download(
            config["model_id"], revision=config["revision"], cache_dir=str(args.cache_dir),
            local_files_only=not args.download, token=False, max_workers=2,
            allow_patterns=["*.safetensors", "*.json", "*.jinja", "*.txt", "LICENSE*", "README.md"],
        ))
    files = []
    for path in sorted(snapshot.iterdir()):
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as file:
                for block in iter(lambda: file.read(8 * 1024 * 1024), b""):
                    digest.update(block)
            files.append({"name": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    save(args.output / "download_manifest.json", {
        "model_id": config["model_id"], "revision": config["revision"], "files": files,
    })
    print("2/4 Carregando NF4 na GPU...", flush=True)
    torch.cuda.reset_peak_memory_stats()
    model, tokenizer = load_model(config, args.cache_dir, download=False)
    loaded = torch.cuda.memory_allocated()
    probes = [
        ("pt_concept", "Qual a diferença entre séries e repetições? Responda em duas frases."),
        ("pt_informal", "so consigo treinar 2x na semana, ainda vale a pena? responde curto"),
        ("pt_action", "Posso trocar meu treino de terça para quinta? Você não conhece minha agenda."),
        ("pt_pain", "Meu joelho começou a incomodar no vôlei. Isso prova que preciso treinar mais explosão? Responda brevemente."),
        ("en", "Explain sets and repetitions in two short sentences in English."),
        ("es", "Explica series y repeticiones en dos frases cortas en español."),
    ]
    samples = []
    print("3/4 Gerando respostas em português, inglês e espanhol...", flush=True)
    for name, prompt in probes:
        messages = [{"role": "system", "content": config["system_prompt"]}, {"role": "user", "content": prompt}]
        if name == "en":
            messages[0]["content"] = "You are a helpful fitness assistant. Reply in the language requested by the user."
        elif name == "es":
            messages[0]["content"] = "Responde en el idioma solicitado por el usuario."
        result = answer(model, tokenizer, messages, config, max_new_tokens=160)
        if not result["text"].strip():
            raise RuntimeError("Geração vazia.")
        samples.append({"name": name, "messages": messages, **result})
        print(name, f"{result['tokens_per_second']:.1f} tokens/s", flush=True)
    generation_peak = torch.cuda.max_memory_allocated()
    backward = None
    if args.check_backward:
        print("4/4 Conferindo backward LoRA (sem atualizar pesos)...", flush=True)
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        model.config.use_cache = False
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
        model = get_peft_model(model, LoraConfig(
            r=8, lora_alpha=16, lora_dropout=0.05, target_modules="all-linear",
            bias="none", task_type="CAUSAL_LM",
        ))
        model.train()
        trainable = [p for p in model.parameters() if p.requires_grad]
        before = [p.detach().clone() for p in trainable]
        # Repetição artificial serve apenas para medir memória; não é dataset.
        ids = tokenizer("Treino e recuperação devem respeitar o contexto e os limites da pessoa. " * 160,
                        return_tensors="pt", truncation=True, max_length=1024).to("cuda")
        labels = ids["input_ids"].clone()
        torch.cuda.reset_peak_memory_stats()
        with torch.autocast("cuda", dtype=torch.bfloat16):
            loss = model(**ids, labels=labels).loss
        loss.backward()
        finite = all(p.grad is not None and torch.isfinite(p.grad).all().item() for p in trainable)
        nonzero = any(p.grad.abs().sum().item() > 0 for p in trainable if p.grad is not None)
        unchanged = all(torch.equal(p.detach(), old) for p, old in zip(trainable, before))
        if not (finite and nonzero and unchanged):
            raise RuntimeError("Falha nos gradientes ou pesos alterados durante o diagnóstico.")
        backward = {
            "sequence_length": ids["input_ids"].shape[-1], "batch_size": 1,
            "lora_rank": 8, "target_modules": "all-linear", "gradient_checkpointing": True,
            "trainable_parameters": sum(p.numel() for p in trainable),
            "loss": loss.item(), "finite_gradients": finite, "nonzero_gradients": nonzero,
            "weights_unchanged": unchanged, "optimizer_steps": 0,
            "peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20,
            "peak_reserved_mib": torch.cuda.max_memory_reserved() / 2**20,
            "note": "Teste de viabilidade; não define a configuração final de LoRA nem mede qualidade.",
        }
        model.zero_grad(set_to_none=True)
    private = args.output / "private"
    save(private / "samples.json", samples)
    save(private / "local_paths.json", {"cache_dir": str(args.cache_dir), "snapshot": str(snapshot)})
    props = torch.cuda.get_device_properties(0)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(), "phase": "7.04.1",
        "model_id": config["model_id"], "revision": config["revision"],
        "python": platform.python_version(), "os": platform.platform(),
        "packages": {name: version(name) for name in ["torch", "transformers", "tokenizers", "peft", "accelerate", "bitsandbytes", "huggingface-hub", "safetensors"]},
        "hardware": {"gpu": props.name, "vram_mib": props.total_memory / 2**20,
                     "ram_gib": psutil.virtual_memory().total / 2**30,
                     "cpu": platform.processor(), "bf16_supported": torch.cuda.is_bf16_supported()},
        "quantization": "NF4 double quantization; compute BF16", "device_map": str(model.hf_device_map),
        "loaded_allocated_mib": loaded / 2**20, "generation_peak_allocated_mib": generation_peak / 2**20,
        "probes": [{k: s[k] for k in ["name", "input_tokens", "generated_tokens", "seconds", "tokens_per_second", "stopped_at_eos"]} for s in samples],
        "backward_feasibility": backward, "optimizer_steps": 0,
        "dataset_partitions_read": [], "quality_benchmark": False,
        "total_seconds": time.perf_counter() - start,
    }
    save(args.output / "smoke_report.json", report)
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()

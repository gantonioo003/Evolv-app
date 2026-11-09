"""Disposable tiny-Qwen GPU check; never loads or trains the 4B checkpoint."""
import gc
from pathlib import Path
import tempfile


def tiny_quantized_check(settings):
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, Qwen3Config
    from .lora import attach_lora, make_optimizer

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("O ensaio requer CUDA e BF16.")
    torch.set_num_threads(4)
    with torch.random.fork_rng(devices=[0]), tempfile.TemporaryDirectory(prefix="evolv-lora-toy-") as tmp:
        torch.manual_seed(42)
        config = Qwen3Config(vocab_size=128, hidden_size=64, intermediate_size=128,
            num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
            head_dim=16, max_position_embeddings=128, tie_word_embeddings=True,
            bos_token_id=1, eos_token_id=2, pad_token_id=0, use_cache=False)
        base = AutoModelForCausalLM.from_config(config).to(torch.bfloat16)
        base.save_pretrained(tmp, safe_serialization=True)
        del base
        gc.collect()
        model = AutoModelForCausalLM.from_pretrained(
            tmp, dtype=torch.bfloat16, device_map={"": 0}, attn_implementation="sdpa",
            local_files_only=True, trust_remote_code=False,
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16))
        model, trainability = attach_lora(model, settings)
        if not model.is_gradient_checkpointing:
            raise RuntimeError("Gradient checkpointing não foi ativado.")
        ids = torch.arange(1, 33, device="cuda").reshape(2, 16)
        ids[1, -4:] = 0
        mask = (ids != 0).long()
        labels = ids.clone()
        labels[:, :8] = -100
        labels[mask == 0] = -100
        model.eval()
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            with_adapter = model(input_ids=ids, attention_mask=mask).logits
            with model.disable_adapter():
                without_adapter = model(input_ids=ids, attention_mask=mask).logits
        delta = (with_adapter.float() - without_adapter.float()).abs().max().item()
        if not torch.allclose(with_adapter, without_adapter, atol=1e-6, rtol=1e-5):
            raise RuntimeError("LoRA inicial alterou a função do modelo.")
        frozen = {n: p.detach().cpu().clone() for n, p in model.named_parameters() if not p.requires_grad}
        before = {n: p.detach().cpu().clone() for n, p in model.named_parameters() if p.requires_grad}
        model.train()
        optimizer = make_optimizer(model, settings)
        optimizer.zero_grad(set_to_none=True)
        torch.cuda.reset_peak_memory_stats()
        with torch.autocast("cuda", dtype=torch.bfloat16):
            loss = model(input_ids=ids, attention_mask=mask, labels=labels).loss
        if not torch.isfinite(loss).item():
            raise RuntimeError("Loss não finita no modelo descartável.")
        loss.backward()
        params = [p for p in model.parameters() if p.requires_grad]
        if any(p.grad is None or not torch.isfinite(p.grad).all().item() for p in params):
            raise RuntimeError("Gradientes inválidos nos adaptadores.")
        grad_norm = torch.nn.utils.clip_grad_norm_(params, settings["training"]["max_grad_norm"])
        if not torch.isfinite(grad_norm).item() or grad_norm.item() <= 0:
            raise RuntimeError("Não houve gradiente finito e não nulo.")
        optimizer.step()
        changed = []
        for name, param in model.named_parameters():
            value = param.detach().cpu()
            if name in frozen and not torch.equal(value, frozen[name]):
                raise RuntimeError("Peso base alterado pelo otimizador.")
            if name in before and not torch.equal(value, before[name]):
                changed.append(name)
        if not changed:
            raise RuntimeError("Nenhum adaptador mudou no ensaio descartável.")
        torch.cuda.synchronize()
        result = {"model": "random tiny Qwen3, 2 layers, hidden size 64, vocab 128",
                  "device": torch.cuda.get_device_name(0), "quantization": "NF4 double quant + BF16 compute",
                  **trainability, "initial_identity_max_delta": delta,
                  "gradient_checkpointing": True, "finite_gradients": True,
                  "frozen_base_unchanged_after_step": True, "changed_adapter_tensors": len(changed),
                  "toy_optimizer_steps": 1, "real_model_optimizer_steps": 0,
                  "toy_loss_not_a_quality_metric": loss.item(),
                  "toy_peak_allocated_mib_not_4B_memory": torch.cuda.max_memory_allocated() / 2**20,
                  "adapter_weights_saved": False, "dataset_examples_used": 0}
        optimizer.zero_grad(set_to_none=True)
        del model, optimizer, loss, params, param, with_adapter, without_adapter
        gc.collect()
        torch.cuda.empty_cache()
    return result

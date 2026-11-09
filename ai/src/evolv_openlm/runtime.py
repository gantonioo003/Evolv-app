"""Pinned official checkpoint, its original tokenizer and bounded local inference."""
import json
import os
from pathlib import Path
import time

AI_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = AI_ROOT / "configs/openlm.v1.json"
DEFAULT_CACHE = Path.home() / "Documents/Codex/models/evolv-openlm"


def load_settings(path=DEFAULT_CONFIG):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if len(config["revision"]) != 40:
        raise ValueError("Use uma revisão fixa do modelo.")
    return config


def load_model(config, cache_dir=None, download=False):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    if not torch.cuda.is_available():
        raise RuntimeError("Esta configuração NF4 exige GPU CUDA. Confira o ambiente Python.")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("A GPU não oferece o bfloat16 exigido pela configuração.")
    torch.set_num_threads(4)
    cache = Path(cache_dir or os.environ.get("EVOLV_MODEL_CACHE", DEFAULT_CACHE))
    kwargs = dict(revision=config["revision"], cache_dir=str(cache),
                  local_files_only=not download, trust_remote_code=False, token=False)
    tokenizer = AutoTokenizer.from_pretrained(config["model_id"], **kwargs)
    model = AutoModelForCausalLM.from_pretrained(
        config["model_id"], **kwargs, dtype=torch.bfloat16,
        device_map={"": 0}, attn_implementation=config["attention"],
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=config["load_in_4bit"],
            bnb_4bit_quant_type=config["quant_type"],
            bnb_4bit_use_double_quant=config["double_quant"],
            bnb_4bit_compute_dtype=torch.bfloat16,
        ),
    )
    model.eval()
    return model, tokenizer


def answer(model, tokenizer, messages, config, max_new_tokens=None):
    import torch
    budget = config["max_new_tokens"] if max_new_tokens is None else max_new_tokens
    if not 1 <= budget <= config["max_new_tokens"]:
        raise ValueError("Limite de saída fora da configuração.")
    inputs = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True,
        return_tensors="pt", return_dict=True,
    ).to("cuda")
    length = inputs["input_ids"].shape[-1]
    if length > config["max_input_tokens"]:
        raise ValueError("Conversa excedeu o limite local. Inicie outra conversa com /limpar.")
    torch.cuda.synchronize()
    start = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(
            **inputs, max_new_tokens=budget, do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    ids = output[0, length:].tolist()
    return {
        "text": tokenizer.decode(ids, skip_special_tokens=True),
        "input_tokens": length, "generated_tokens": len(ids),
        "seconds": elapsed, "tokens_per_second": len(ids) / max(elapsed, 1e-9),
        "stopped_at_eos": bool(ids and ids[-1] == tokenizer.eos_token_id),
    }

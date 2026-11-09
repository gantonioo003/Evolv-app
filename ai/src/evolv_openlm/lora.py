"""Versioned QLoRA recipe and trainability checks; no training loop."""
import math
from pathlib import Path

from .runtime import AI_ROOT, load_settings
from .sft_data import read_json

DEFAULT_LORA_CONFIG = AI_ROOT / "configs/openlm.lora.v1.json"
TARGETS = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}


def load_lora_settings(path=DEFAULT_LORA_CONFIG):
    settings = read_json(path)
    adapter, training = settings["adapter"], settings["training"]
    if settings["method"] != "QLoRA" or adapter["task_type"] != "CAUSAL_LM":
        raise ValueError("Receita deve ser QLoRA causal.")
    if type(adapter["r"]) is not int or adapter["r"] < 1:
        raise ValueError("Rank deve ser um inteiro positivo.")
    if not math.isfinite(adapter["lora_alpha"]) or adapter["lora_alpha"] <= 0:
        raise ValueError("Alpha inválido.")
    if not 0 <= adapter["lora_dropout"] < 1:
        raise ValueError("Dropout inválido.")
    if set(adapter["target_modules"]) != TARGETS or len(adapter["target_modules"]) != len(TARGETS):
        raise ValueError("A receita deve adaptar exatamente as sete projeções previstas.")
    if adapter["bias"] != "none" or adapter["init_lora_weights"] is not True:
        raise ValueError("Bias deve permanecer congelado e LoRA deve iniciar como identidade.")
    if adapter["use_dora"] or adapter["use_rslora"]:
        raise ValueError("Esta versão usa LoRA padrão.")
    for key in ["per_device_train_batch_size", "per_device_eval_batch_size", "gradient_accumulation_steps", "num_train_epochs"]:
        if type(training[key]) is not int or training[key] < 1:
            raise ValueError(f"Valor inválido: {key}.")
    if not math.isfinite(training["learning_rate"]) or training["learning_rate"] <= 0:
        raise ValueError("Learning rate inválido.")
    if not 0 <= training["warmup_ratio"] < 1 or training["max_grad_norm"] <= 0:
        raise ValueError("Warmup ou clipping inválido.")
    if not training["bf16"] or training["fp16"] or training["optim"] != "adamw_torch":
        raise ValueError("Esta versão usa BF16 e AdamW do PyTorch.")
    if not training["gradient_checkpointing"] or training["gradient_checkpointing_kwargs"] != {"use_reentrant": False}:
        raise ValueError("Checkpointing não reentrante é necessário nesta receita.")
    if training["eval_strategy"] != "epoch" or training["save_strategy"] != "epoch":
        raise ValueError("Avaliar e salvar por época.")
    if training["metric_for_best_model"] != "eval_token_nll" or training["greater_is_better"]:
        raise ValueError("Seleção deve usar NLL de validação ponderada por tokens.")
    if training["report_to"] != "none":
        raise ValueError("Telemetria externa não faz parte desta configuração.")
    if Path(settings["data_release"]).is_absolute() or ".." in Path(settings["data_release"]).parts:
        raise ValueError("Versão de dados deve estar dentro da pasta ai.")
    return settings


def make_peft_config(settings):
    from peft import LoraConfig
    return LoraConfig(**settings["adapter"], inference_mode=False,
                      base_model_name_or_path=settings["model_id"], revision=settings["model_revision"])


def target_geometry(model, settings):
    targets = set(settings["adapter"]["target_modules"])
    found = []
    for name, module in model.named_modules():
        if name.rsplit(".", 1)[-1] in targets:
            if not hasattr(module, "in_features") or not hasattr(module, "out_features"):
                raise ValueError(f"Alvo não é uma projeção linear: {name}.")
            found.append({"name": name, "input": module.in_features, "output": module.out_features,
                          "lora_parameters": settings["adapter"]["r"] * (module.in_features + module.out_features)})
    expected = model.config.num_hidden_layers * len(targets)
    if len(found) != expected or {x["name"].rsplit(".", 1)[-1] for x in found} != targets:
        raise ValueError("Quantidade de projeções diferente da arquitetura prevista.")
    return found


def trainability_report(model):
    trainable = {name: p for name, p in model.named_parameters() if p.requires_grad}
    if not trainable or any(not (".lora_A." in n or ".lora_B." in n) for n in trainable):
        raise ValueError("Parâmetros fora dos adaptadores estão treináveis.")
    count = sum(p.numel() for p in trainable.values())
    # Count frozen parameters separately; Params4bit.numel() may reflect packed
    # storage, so do not present that value as the original model parameter count.
    return {"trainable_parameters": count, "trainable_tensors": len(trainable),
            "only_lora_trainable": True, "trainable_dtypes": sorted({str(p.dtype) for p in trainable.values()})}


def attach_lora(model, settings, require_quantized=True):
    from peft import get_peft_model, prepare_model_for_kbit_training
    if require_quantized and not getattr(model, "is_loaded_in_4bit", False):
        raise ValueError("O modelo real precisa ser carregado em 4 bits antes do QLoRA.")
    geometry = target_geometry(model, settings)
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=settings["training"]["gradient_checkpointing"],
        gradient_checkpointing_kwargs=settings["training"]["gradient_checkpointing_kwargs"],
    )
    model = get_peft_model(model, make_peft_config(settings))
    report = trainability_report(model)
    if report["trainable_parameters"] != sum(x["lora_parameters"] for x in geometry):
        raise ValueError("Contagem dos adaptadores não corresponde à geometria.")
    model.train()
    return model, report


def make_training_arguments(settings, output_dir, num_training_examples):
    from transformers import TrainingArguments
    training = dict(settings["training"])
    training.pop("warmup_ratio")
    training["warmup_steps"] = training_plan(num_training_examples, settings)["warmup_steps"]
    return TrainingArguments(output_dir=str(output_dir), **training)


def make_callbacks(settings):
    from transformers import EarlyStoppingCallback
    config = settings["early_stopping"]
    return [EarlyStoppingCallback(early_stopping_patience=config["patience"], early_stopping_threshold=config["threshold"])]


def make_optimizer(model, settings):
    import torch
    trainability_report(model)
    config = settings["training"]
    return torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=config["learning_rate"], weight_decay=config["weight_decay"],
                            betas=(config["adam_beta1"], config["adam_beta2"]),
                            eps=config["adam_epsilon"], foreach=False)


def training_plan(train_rows, settings, world_size=1):
    if train_rows < 1 or world_size != 1:
        raise ValueError("Esta receita é para treino não vazio em uma única GPU.")
    config = settings["training"]
    micro = config["per_device_train_batch_size"]
    accumulation = config["gradient_accumulation_steps"]
    batches = math.ceil(train_rows / micro)
    updates = math.ceil(batches / accumulation)
    total = updates * config["num_train_epochs"]
    return {"train_conversations": train_rows, "world_size": world_size,
            "microbatches_per_epoch": batches, "effective_batch_size_max": micro * accumulation,
            "optimizer_steps_per_epoch": updates, "planned_optimizer_steps_max": total,
            "warmup_steps": math.ceil(total * config["warmup_ratio"]),
            "last_accumulation_microbatches": batches % accumulation or accumulation,
            "epochs_max": config["num_train_epochs"], "last_partial_batch_kept": True}


def structural_report(settings, cache_dir):
    import torch
    from accelerate import init_empty_weights
    from transformers import AutoConfig, AutoModelForCausalLM
    from peft import get_peft_model
    model_config = load_settings()
    if settings["model_id"] != model_config["model_id"] or settings["model_revision"] != model_config["revision"]:
        raise ValueError("Configuração LoRA aponta para outro modelo/revisão.")
    config = AutoConfig.from_pretrained(model_config["model_id"], revision=model_config["revision"],
        cache_dir=str(cache_dir), local_files_only=True, trust_remote_code=False, token=False)
    with init_empty_weights():
        model = AutoModelForCausalLM.from_config(config, dtype=torch.bfloat16, trust_remote_code=False)
    model.tie_weights()
    geometry = target_geometry(model, settings)
    base_parameters = sum(p.numel() for p in model.parameters())
    # Attach on meta only: no 4B tensor allocation, pretrained load or forward.
    model = get_peft_model(model, make_peft_config(settings))
    trainable = trainability_report(model)
    expected = sum(x["lora_parameters"] for x in geometry)
    if trainable["trainable_parameters"] != expected or any(p.device.type != "meta" for p in model.parameters()):
        raise ValueError("Inspeção estrutural divergente ou alocação inesperada de pesos.")
    count = trainable["trainable_parameters"]
    return {"base_parameters_architecture": base_parameters, "layers": config.num_hidden_layers,
            "targeted_projections": len(geometry), "geometry": geometry, **trainable,
            "trainable_percent_of_base": 100 * count / base_parameters,
            "adapter_weights_float32_mib": count * 4 / 2**20,
            "adamw_two_float32_moments_mib": count * 8 / 2**20,
            "pretrained_weights_loaded": False, "all_parameters_on_meta": True}

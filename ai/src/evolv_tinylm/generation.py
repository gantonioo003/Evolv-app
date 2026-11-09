"""Autoregressive generation with local RNG, explicit context limits and sampling."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re

import torch

from .tokenizer import SPECIAL_IDS


@dataclass(frozen=True)
class GenerationConfig:
    max_new_tokens: int = 64
    do_sample: bool = True
    temperature: float = 1.0
    top_k: int = 0
    top_p: float = 0.9
    seed: int = 42

    def __post_init__(self):
        for name in ("max_new_tokens", "top_k", "seed"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"{name} deve ser um inteiro nao negativo.")
        if self.seed >= 2**63 or type(self.do_sample) is not bool:
            raise ValueError("Semente ou modo de amostragem invalido.")
        for name in ("temperature", "top_p"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} deve ser finito.")
        if self.temperature <= 0 or not 0 < self.top_p <= 1:
            raise ValueError("Use temperatura positiva e 0 < top_p <= 1; greedy usa do_sample=False.")


def filter_logits(logits: torch.Tensor, *, top_k: int = 0, top_p: float = 1.0) -> torch.Tensor:
    """Filter a single vocabulary vector; keep the token crossing nucleus mass."""
    if logits.ndim != 1 or type(top_k) is not int or top_k < 0 or not 0 < top_p <= 1:
        raise ValueError("Vetor ou parametros de filtragem invalidos.")
    scores = logits.float().clone()
    if bool(torch.isnan(scores).any() | torch.isposinf(scores).any()) or not bool(torch.isfinite(scores).any()):
        raise ValueError("Scores sem distribuicao valida.")
    if top_k:
        indices = torch.topk(scores, min(top_k, scores.numel())).indices
        keep = torch.zeros_like(scores, dtype=torch.bool).scatter_(0, indices, True)
        scores.masked_fill_(~keep, float("-inf"))
    if top_p < 1:
        ordered, indices = torch.sort(scores, descending=True)
        probabilities = torch.softmax(ordered, dim=-1)
        remove = probabilities.cumsum(dim=-1) - probabilities >= top_p
        remove[0] = False
        scores[indices[remove]] = float("-inf")
    return scores


def text_diagnostics(text: str, generated_ids: list[int]) -> dict:
    words = re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
    bigrams = list(zip(words, words[1:]))
    content = [index for index in generated_ids if index != SPECIAL_IDS["<|eos|>"]]
    return {
        "words": len(words), "content_tokens": len(content),
        "distinct_1": len(set(words)) / len(words) if words else None,
        "distinct_2": len(set(bigrams)) / len(bigrams) if bigrams else None,
        "repeated_bigram_fraction": 1 - len(set(bigrams)) / len(bigrams) if bigrams else None,
        "unicode_replacement_characters": text.count("\ufffd"),
        "empty_completion": not text.strip(),
    }


def generate(model, tokenizer, prompt: str, config: GenerationConfig | None = None) -> dict:
    config = config or GenerationConfig()
    if model.config.vocab_size != tokenizer.vocab_size:
        raise ValueError("Vocabulario da rede e do tokenizador divergem.")
    device = next(model.parameters()).device
    generator = torch.Generator(device=device).manual_seed(config.seed)
    prompt_ids = [SPECIAL_IDS["<|bos|>"]] + tokenizer.encode(prompt)
    all_ids, generated = list(prompt_ids), []
    banned = [index for token, index in SPECIAL_IDS.items() if token != "<|eos|>"]
    was_training = model.training
    model.eval()
    context_crops = 0
    stop_reason = "max_new_tokens"
    try:
        with torch.inference_mode():
            for _ in range(config.max_new_tokens):
                if len(all_ids) > model.config.context_length:
                    context_crops += 1
                context = all_ids[-model.config.context_length:]
                input_ids = torch.tensor([context], dtype=torch.long, device=device)
                mask = torch.ones_like(input_ids, dtype=torch.bool)
                scores = model(input_ids, attention_mask=mask)["logits"][0, -1].float().clone()
                if not bool(torch.isfinite(scores).all()):
                    raise FloatingPointError("Scores nao finitos durante a geracao.")
                scores[banned] = float("-inf")
                if config.do_sample:
                    scores = filter_logits(scores / config.temperature, top_k=config.top_k, top_p=config.top_p)
                    token = int(torch.multinomial(torch.softmax(scores, dim=-1), 1, generator=generator))
                else:
                    token = int(scores.argmax())
                generated.append(token)
                all_ids.append(token)
                if token == SPECIAL_IDS["<|eos|>"]:
                    stop_reason = "eos"
                    break
    finally:
        model.train(was_training)
    continuation = tokenizer.decode(generated)
    return {
        "prompt": prompt, "continuation": continuation, "full_text": tokenizer.decode(all_ids),
        "generated_ids": generated, "generated_tokens": len(generated), "stop_reason": stop_reason,
        "prompt_tokens_including_bos": len(prompt_ids),
        "prompt_tokens_outside_first_window": max(0, len(prompt_ids) - model.config.context_length),
        "steps_with_context_cropping": context_crops, "context_length": model.config.context_length,
        "config": asdict(config), "diagnostics": text_diagnostics(continuation, generated),
    }

"""Coach language runtime backed by the local llama.cpp process."""
import json
from time import perf_counter
from urllib.request import Request, urlopen

from .runtime import DEFAULT_CACHE, load_settings


class GgufLM:
    def __init__(self, model):
        from transformers import AutoTokenizer

        if model not in {"qwen3-8b", "ministral-3-8b"}:
            raise ValueError("Modelo GGUF local desconhecido.")
        self.variant = self.model = model
        self.settings = load_settings()
        self.context_router_enabled = False
        models = self._request("/v1/models", timeout=5)["data"]
        if not any(candidate["id"] == model for candidate in models):
            raise ValueError("O servidor local está com outro modelo carregado.")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.settings["model_id"], revision=self.settings["revision"],
            cache_dir=str(DEFAULT_CACHE), local_files_only=True, trust_remote_code=False, token=False,
        )
        self.generate([
            {"role": "system", "content": "Responda em português brasileiro em uma frase curta."},
            {"role": "user", "content": "Oi, tudo bem?"},
        ], limit=24)

    def count(self, messages):
        return len(self.tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_dict=False,
        ))

    @staticmethod
    def _request(path, data=None, *, timeout=45):
        body = None if data is None else json.dumps(data, ensure_ascii=False).encode()
        request = Request("http://127.0.0.1:11437" + path, data=body,
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def generate(self, messages, limit=24):
        start = perf_counter()
        result = self._request("/v1/chat/completions", {
            "model": self.model, "messages": messages, "stream": False, "temperature": 0,
            "seed": 42, "max_tokens": limit, "chat_template_kwargs": {"enable_thinking": False},
        })
        usage = result.get("usage", {})
        choice = result["choices"][0]
        elapsed = perf_counter() - start
        generated = usage.get("completion_tokens") or 0
        return {
            "text": choice["message"]["content"] or "",
            "input_tokens": usage.get("prompt_tokens") or 0,
            "generated_tokens": generated,
            "seconds": elapsed,
            "tokens_per_second": generated / max(elapsed, 1e-9),
            "stopped_at_eos": choice.get("finish_reason") == "stop",
        }

    def interpret(self, messages):
        return self.generate(messages, 144)["text"]

    def write(self, messages):
        return self.generate(messages, self.settings["max_new_tokens"])

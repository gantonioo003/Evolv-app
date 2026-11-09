"""Small decoder-only Transformer, implemented with PyTorch primitives."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F


@dataclass(frozen=True)
class TinyLMConfig:
    vocab_size: int = 8192
    context_length: int = 256
    d_model: int = 192
    num_layers: int = 4
    num_heads: int = 6
    ffn_dim: int = 768
    dropout: float = 0.1
    layer_norm_eps: float = 1e-5
    tie_embeddings: bool = True
    pad_token_id: int = 0
    ignore_index: int = -100

    def __post_init__(self):
        for name in ("vocab_size", "context_length", "d_model", "num_layers", "num_heads", "ffn_dim"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} deve ser um inteiro positivo.")
        if self.d_model % self.num_heads:
            raise ValueError("d_model deve ser divisivel pelo numero de cabecas.")
        if (isinstance(self.dropout, bool) or not isinstance(self.dropout, (int, float))
                or not math.isfinite(self.dropout) or not 0 <= self.dropout < 1):
            raise ValueError("dropout deve estar entre 0 (inclusivo) e 1 (exclusivo).")
        if (isinstance(self.layer_norm_eps, bool) or not isinstance(self.layer_norm_eps, (int, float))
                or not math.isfinite(self.layer_norm_eps) or self.layer_norm_eps <= 0):
            raise ValueError("layer_norm_eps deve ser positivo e finito.")
        if type(self.tie_embeddings) is not bool:
            raise ValueError("tie_embeddings deve ser booleano.")
        if type(self.pad_token_id) is not int or not 0 <= self.pad_token_id < self.vocab_size:
            raise ValueError("ID de padding invalido.")
        if type(self.ignore_index) is not int or self.ignore_index >= 0:
            raise ValueError("ignore_index deve ser um inteiro negativo, fora do vocabulario.")

    @classmethod
    def load(cls, path: str | Path) -> "TinyLMConfig":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict:
        return asdict(self)

    def validate_data_config(self, config: dict) -> None:
        if (config["vocab_size"] != self.vocab_size
                or config["context_length"] != self.context_length
                or config["special_token_ids"]["<|pad|>"] != self.pad_token_id
                or config["ignore_index"] != self.ignore_index
                or config["target_shift"] != 1 or not config["right_padding"]):
            raise ValueError("Configuracao do modelo incompativel com os dados preparados.")


class CausalSelfAttention(nn.Module):
    def __init__(self, config: TinyLMConfig):
        super().__init__()
        self.num_heads = config.num_heads
        self.head_dim = config.d_model // config.num_heads
        self.dropout = config.dropout
        self.qkv = nn.Linear(config.d_model, 3 * config.d_model)
        self.projection = nn.Linear(config.d_model, config.d_model)
        self.output_dropout = nn.Dropout(config.dropout)
        self.register_buffer(
            "causal_mask", torch.ones(config.context_length, config.context_length,
                                      dtype=torch.bool).tril(), persistent=False,
        )

    def forward(self, x: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        batch, length, width = x.shape
        q, k, v = self.qkv(x).chunk(3, dim=-1)
        q, k, v = (tensor.view(batch, length, self.num_heads, self.head_dim).transpose(1, 2)
                   for tensor in (q, k, v))
        # SDPA: True means ALLOWED, unlike MultiheadAttention.key_padding_mask.
        # Combine causal and padding restrictions instead of passing is_causal=True too.
        allowed = (self.causal_mask[:length, :length][None, None, :, :]
                   & attention_mask[:, None, None, :])
        attended = F.scaled_dot_product_attention(
            q, k, v, attn_mask=allowed,
            dropout_p=self.dropout if self.training else 0.0,
        )
        attended = attended.transpose(1, 2).contiguous().view(batch, length, width)
        output = self.output_dropout(self.projection(attended))
        return output * attention_mask.unsqueeze(-1)


class DecoderBlock(nn.Module):
    def __init__(self, config: TinyLMConfig):
        super().__init__()
        self.attention_norm = nn.LayerNorm(config.d_model, eps=config.layer_norm_eps)
        self.attention = CausalSelfAttention(config)
        self.mlp_norm = nn.LayerNorm(config.d_model, eps=config.layer_norm_eps)
        self.mlp = nn.Sequential(
            nn.Linear(config.d_model, config.ffn_dim), nn.GELU(),
            nn.Linear(config.ffn_dim, config.d_model), nn.Dropout(config.dropout),
        )

    def forward(self, x: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        # Pre-LayerNorm and two residual paths, with padding activations cleared.
        x = x + self.attention(self.attention_norm(x), attention_mask)
        x = x + self.mlp(self.mlp_norm(x))
        return x * attention_mask.unsqueeze(-1)


class TinyLM(nn.Module):
    def __init__(self, config: TinyLMConfig):
        super().__init__()
        self.config = config
        # No padding_idx: this table can share weights with the output head.
        # Padding INPUT activations are explicitly masked, including after blocks.
        self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
        self.position_embedding = nn.Embedding(config.context_length, config.d_model)
        self.embedding_dropout = nn.Dropout(config.dropout)
        self.blocks = nn.ModuleList(DecoderBlock(config) for _ in range(config.num_layers))
        self.final_norm = nn.LayerNorm(config.d_model, eps=config.layer_norm_eps)
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
        self.apply(self._initialize)
        for block in self.blocks:
            for projection in (block.attention.projection, block.mlp[2]):
                nn.init.normal_(projection.weight, mean=0.0,
                                std=0.02 / math.sqrt(2 * config.num_layers))
        if config.tie_embeddings:
            self.lm_head.weight = self.token_embedding.weight

    @staticmethod
    def _initialize(module: nn.Module) -> None:
        if isinstance(module, (nn.Linear, nn.Embedding)):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if isinstance(module, nn.Linear) and module.bias is not None:
                nn.init.zeros_(module.bias)

    def parameter_summary(self) -> dict:
        groups = {}
        for name, parameter in self.named_parameters():
            group = name.split(".")[0]
            groups[group] = groups.get(group, 0) + parameter.numel()
        return {
            "total": sum(parameter.numel() for parameter in self.parameters()),
            "trainable": sum(parameter.numel() for parameter in self.parameters() if parameter.requires_grad),
            "by_component_unique_parameters": groups,
            "output_head_shares_token_embedding": self.lm_head.weight is self.token_embedding.weight,
        }

    def _validate_inputs(self, input_ids: torch.Tensor,
                         attention_mask: torch.Tensor | None) -> torch.Tensor:
        if input_ids.ndim != 2 or input_ids.dtype != torch.long:
            raise ValueError("input_ids deve ser int64 com formato [lote, sequencia].")
        batch, length = input_ids.shape
        if batch < 1 or not 1 <= length <= self.config.context_length:
            raise ValueError("Lote vazio ou sequencia fora do limite de contexto.")
        if attention_mask is None:
            attention_mask = input_ids.ne(self.config.pad_token_id)
        if (attention_mask.shape != input_ids.shape or attention_mask.dtype != torch.bool
                or attention_mask.device != input_ids.device):
            raise ValueError("attention_mask deve ser bool, com o mesmo formato e dispositivo da entrada.")
        invalid = ((input_ids < 0).any() | (input_ids >= self.config.vocab_size).any()
                   | (~attention_mask[:, 0]).any()
                   | (attention_mask[:, 1:] & ~attention_mask[:, :-1]).any())
        if bool(invalid):
            raise ValueError("IDs invalidos ou mascara sem prefixo real e padding apenas a direita.")
        return attention_mask

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor | None = None,
                labels: torch.Tensor | None = None) -> dict[str, torch.Tensor | None]:
        mask = self._validate_inputs(input_ids, attention_mask)
        positions = torch.arange(input_ids.shape[1], device=input_ids.device)
        x = self.token_embedding(input_ids) + self.position_embedding(positions)[None, :, :]
        x = self.embedding_dropout(x) * mask.unsqueeze(-1)
        for block in self.blocks:
            x = block(x, mask)
        x = self.final_norm(x) * mask.unsqueeze(-1)
        logits = self.lm_head(x)  # Raw scores [B, T, V]; no softmax before cross-entropy.
        loss = loss_sum = valid_tokens = None
        if labels is not None:
            if (labels.shape != input_ids.shape or labels.dtype != torch.long
                    or labels.device != input_ids.device):
                raise ValueError("labels deve ser int64, com o mesmo formato e dispositivo da entrada.")
            targets = labels.masked_fill(~mask, self.config.ignore_index)
            valid = targets.ne(self.config.ignore_index)
            if bool((((targets < 0) | (targets >= self.config.vocab_size)) & valid).any()):
                raise ValueError("Alvo fora do vocabulario.")
            # The dataset has ALREADY shifted targets by one; do not shift again.
            loss_sum = F.cross_entropy(
                logits.reshape(-1, self.config.vocab_size), targets.reshape(-1),
                ignore_index=self.config.ignore_index, reduction="sum",
            )
            valid_tokens = valid.sum()
            # All-ignored labels give a differentiable zero, never NaN.
            loss = loss_sum / valid_tokens.clamp_min(1)
        return {"logits": logits, "loss": loss, "loss_sum": loss_sum, "valid_tokens": valid_tokens}

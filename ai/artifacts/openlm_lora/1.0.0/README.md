# QLoRA 1.0.0 — configuração 7.04.3

Modelo: Qwen3-4B-Instruct-2507 na revisão fixa já selecionada.

- Rank 8, alpha 16, dropout 0,05.
- Sete projeções por bloco: q/k/v/o e gate/up/down.
- 36 blocos, 252 projeções, 16.515.072 parâmetros LoRA (0,41057% da base).
- Base em NF4; cálculo BF16; apenas LoRA treinável.
- Lote 1, acumulação 16, até 3 épocas, learning rate 1e-4, AdamW.
- 335 exemplos: até 21 updates/época, 63 no total; warmup 7.
- Seleção por `eval_token_nll`, que o loop da 7.04.4 precisa calcular por tokens.

Estrutura conferida em meta. Ensaio NF4/BF16 com Qwen minúsculo na RTX 5050
aprovado: identidade inicial, gradientes finitos, um update apenas nos adaptadores
e base preservada. Quatorze testes da configuração passaram.

**Não houve carregamento, geração ou treino do checkpoint de 4B.** Os pesos
completos ainda precisam terminar de baixar, e sua memória de treino real não
foi medida. Este diretório contém configurações, não um adaptador treinado.

Detalhes: `docs/33-openlm-lora-configuration.md`, na raiz do projeto.

# 7.04.1 — Seleção técnica

Selecionado **Qwen3-4B-Instruct-2507**, oficial, revisão fixa
`cdbee75f17c01a7cc42f958dc650907174af0554`.

Estratégia: NF4 de 4 bits, cálculo BF16 e futura adaptação por QLoRA.
Computador observado: RTX 5050 Laptop com 8 GB de VRAM e aproximadamente 16 GB de RAM.

**A escolha está registrada; a viabilidade prática ainda não foi demonstrada.**
Os pesos oficiais somam 8,04 GB decimais. Na transferência observada, 4 MiB levaram
17,13 segundos; o download completo levaria horas. Foi interrompido com os
parciais preservados. Não há respostas geradas, velocidade de geração, pico de
VRAM ou resultado de backward atribuídos ao modelo nesta etapa.

Dependências instaladas sem substituir PyTorch ou Transformers existentes.
`pip check` não encontrou dependências quebradas. Três testes locais do downloader
passaram: reutilização de arquivo íntegro, rejeição de hash incorreto e rejeição
de retomada com faixa inconsistente. São verificações do download, não do modelo.

Código de chat e diagnóstico está preparado. Completar o cache e executar o
diagnóstico são condições anteriores ao treino real na 7.04.4. O preparo dos
dados na 7.04.2 pode avançar enquanto isso.

Decisão completa: `docs/31-openlm-base-selection.md`, a partir da raiz do projeto.
Registro estruturado: `selection.json`, nesta pasta.

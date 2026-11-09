# 7.04.4 — Treinamento QLoRA e validação

Modelo: Qwen/Qwen3-4B-Instruct-2507. Revisão: `cdbee75f17c01a7cc42f958dc650907174af0554`.

3 épocas concluídas; 63 passos de otimizador. Melhor época por validação: **3**.

| Modelo / condição | NLL treino em eval | NLL validação | Perplexidade validação |
| --- | ---: | ---: | ---: |
| Original NF4, antes do preparo | 4.149058 | 4.039655 | 56.8067 |
| Adaptador inicial, sem ajuste | 4.143333 | 4.033484 | 56.4573 |
| Checkpoint escolhido, época 3 | 1.583131 | 1.884680 | 6.5842 |

Validação melhorou em relação ao adaptador inicial: **True**.
Validação melhorou em relação ao original NF4: **True**.

Os checkpoints são selecionados pela validação, incluindo a época 0 como possibilidade de não melhorar. O preparo para QLoRA pode mudar a precisão de componentes congelados; por isso o original e o adaptador inicial têm referências separadas.

Pico de memória alocada medido no loop: 4545.7 MiB. Esse número não é todo o consumo de VRAM do processo e não inclui necessariamente o pico do carregamento.

Adaptador selecionado: `private/checkpoints/epoch_0003`. Último estado retomável: `private/checkpoints/epoch_0003`.

A base original permanece separada. Checkpoints contêm somente adaptadores e estado do treinador, otimizador, scheduler e RNG. A retomada ocorre na última época completa.

O conjunto SFT é pequeno e sintético. Melhor NLL não comprova qualidade de conversa, conhecimento clínico ou capacidade em pessoas reais. As losses de treino online usam dropout e pesos mudando; a tabela acima usa treino em eval para comparação.

**O teste reservado não foi avaliado.** Comparação de geração original/adaptado e avaliação final pertencem à 7.04.5. Nenhum modelo foi conectado ou promovido ao aplicativo.

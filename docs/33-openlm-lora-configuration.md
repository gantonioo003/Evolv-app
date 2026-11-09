# 7.04.3 — Configuração LoRA/PEFT

## Decisão

Receita **QLoRA 1.0.0** para `Qwen/Qwen3-4B-Instruct-2507`, revisão
`cdbee75f17c01a7cc42f958dc650907174af0554`.

O modelo base será carregado em **NF4 de 4 bits**, com quantização dupla e cálculo
em BF16, conforme a seleção da 7.04.1. Os pesos base ficam congelados. Apenas os
adaptadores LoRA serão treinados na 7.04.4.

A etapa concluiu a configuração, a conferência estrutural e um ensaio técnico
com um modelo minúsculo descartável na GPU. **Não carregou nem treinou o modelo
de 4B**; os arquivos completos de pesos ainda não foram baixados. Não há métricas
de qualidade, melhoria do Coach ou medição de VRAM real desse modelo nesta fase.

## Onde entram os adaptadores

```text
Modelo base congelado em 4 bits
  └─ cada um dos 36 blocos
       ├─ atenção: q_proj, k_proj, v_proj, o_proj
       └─ rede densa: gate_proj, up_proj, down_proj
            └─ cada projeção recebe matrizes LoRA A e B
```

São **252 projeções**, cada uma com duas matrizes adicionais. Embeddings, cabeça
de saída e normalizações não recebem adaptadores nesta receita. Bias também fica
congelado. Não adicionamos tokens ao vocabulário.

| Parâmetro dos adaptadores | Valor | Motivo |
| --- | --- | --- |
| Rank `r` | 8 | Começo contido para o pequeno dataset e a GPU disponível. |
| `lora_alpha` | 16 | Escala padrão alpha/r = 2 nesta receita. |
| Dropout | 0,05 | Regularização dos adaptadores. |
| Inicialização | A aleatória, B zerada | O adaptador inicia sem alterar a função. |
| Bias | `none` | Evita treinar bias do modelo base. |
| Tipo de tarefa | `CAUSAL_LM` | Ajuste de um gerador causal de texto. |
| Variantes | LoRA padrão | Sem DoRA ou rsLoRA neste primeiro experimento. |

Os valores são um ponto inicial de engenharia; não foram escolhidos por busca
de hiperparâmetros nem comprovados como melhores pelos dados de teste.

## Tamanho conferido

Criamos a arquitetura oficial em **meta**, isto é, apenas formatos e contagens,
sem alocar os bilhões de valores dos pesos. PEFT encontrou os alvos e inseriu os
adaptadores nessa estrutura:

- Modelo base: **4.022.468.096 parâmetros** pela arquitetura.
- Adaptadores: **16.515.072 parâmetros treináveis**, em 504 tensores.
- Fração treinável relativa ao modelo base: **0,41057%**.
- Apenas nomes `lora_A` e `lora_B` ficaram treináveis.

Os adaptadores em float32 representam aproximadamente **63 MiB de pesos** e
**126 MiB para os dois momentos do AdamW**, além de gradientes e outros custos.
Essas contas não são o consumo total de GPU. O preparo de QLoRA também pode
converter componentes congelados para float32 por estabilidade, aumentando a
memória; estar congelado não significa necessariamente ocupar 4 bits em tudo.

## Parâmetros previstos para o ajuste

| Opção | Configuração inicial |
| --- | --- |
| Dataset | SFT 1.0.0: 335 treino e 28 validação |
| Teste | 28 conversas reservadas, não carregadas nesta etapa |
| Épocas | No máximo 3 |
| Conversas por lote na GPU | 1 |
| Acumulação de gradientes | Até 16 lotes por atualização |
| Learning rate | 0,0001 |
| Otimizador | AdamW do PyTorch, apenas parâmetros LoRA |
| Betas / epsilon | 0,9 / 0,999; 1e-8 |
| Weight decay | 0,01 |
| Clipping | Norma máxima 1,0 |
| Scheduler | Decaimento linear após warmup |
| Warmup | 10% do plano: 7 atualizações |
| Precisão | BF16 no cálculo; adaptadores float32 conforme PEFT |
| Gradient checkpointing | Ligado, não reentrante |
| Cache KV no treino | Desligado |
| Sequência | Limite de 1.024 tokens; padding dinâmico |
| Trabalhadores do DataLoader | 0, para simplificar execução no Windows |
| Avaliação e salvamento | Ao final de cada época |
| Checkpoints mantidos | Até 2, segundo a estratégia do Trainer |
| Early stopping | Paciência 2, sem melhora mínima adicional |
| Critério de seleção | Menor NLL de validação ponderada por tokens-alvo |
| Telemetria externa / compilação | Desligadas |

Com 335 exemplos, lote 1 e acumulação 16, são **21 atualizações por época**:
20 grupos completos e um último grupo de 15 lotes. O máximo planejado é
**63 atualizações** em três épocas. O grupo parcial não deve ser descartado.
Early stopping ou falha pode reduzir o total realizado.

A receita registra `warmup_ratio=0.1`, mas a versão instalada do Transformers
recebe `warmup_steps`. O helper converte a proporção em 7 passos absolutos usando
o tamanho do treino; não ignora silenciosamente a opção.

## Como a loss será usada

Os dados da 7.04.2 já contêm labels -100 no contexto e labels válidos apenas na
última resposta e no encerramento do template. Não há deslocamento manual novo:
o modelo causal do Transformers desloca os alvos internamente.

Na 7.04.4, a avaliação precisa acumular a soma das perdas e dividir pelo número
de tokens-alvo, publicando a métrica **`eval_token_nll`**. Esse é o nome configurado
para escolher checkpoints e para o callback de early stopping. A receita não
implementa esse loop: usar uma média arbitrária de losses de lotes como se fosse
a métrica ponderada daria uma comparação diferente.

O modelo original também precisa de uma referência antes do ajuste. A decisão
final de usar o adaptado depende da comparação da 7.04.5; menor loss em poucos
exemplos sintéticos, sozinha, não demonstra melhor conversa ou segurança.

## Conferência prática feita nesta fase

Um **Qwen3 aleatório de dois blocos**, dimensão 64 e vocabulário 128, foi salvo
temporariamente, carregado em NF4 na RTX 5050 e preparado com a mesma receita
de adaptadores. O teste usou IDs artificiais, sem exemplos do dataset.

Verificações aprovadas:

1. LoRA inicial e adaptador desativado produziram os mesmos scores: delta máximo 0.
2. Apenas os adaptadores ficaram treináveis; checkpointing estava ligado.
3. Forward e backward em BF16/NF4 geraram loss e gradientes finitos.
4. Um passo descartável de AdamW alterou adaptadores.
5. Nenhum parâmetro base mudou após esse passo.
6. Nenhum peso treinado foi salvo ou promovido como modelo do Evolv.

Esse ensaio verifica a integração das bibliotecas e o congelamento. Sua loss
não mede qualidade e sua memória não estima o tamanho necessário para o modelo
de 4B. O relatório separa explicitamente `toy_optimizer_steps=1` de
`real_model_optimizer_steps=0`.

Quatorze testes adicionais passaram para limites da receita, alvos, rank,
inicialização, learning rate, critério de seleção, atualização parcial,
congelamento, hashes e integridade dos relatórios. Não repetem o treino de GPU.

## Arquivos

| Caminho relativo à raiz do projeto | Função |
| --- | --- |
| `ai/configs/openlm.lora.v1.json` | Receita autoritativa dos adaptadores e parâmetros de ajuste. |
| `ai/src/evolv_openlm/lora.py` | Validação, construção PEFT, congelamento, otimizador e plano de updates. |
| `ai/src/evolv_openlm/lora_checks.py` | Ensaio descartável com Qwen minúsculo. |
| `ai/scripts/configure_openlm_lora.py` | Confere arquitetura, dados e opções aceitas pelas bibliotecas. |
| `ai/artifacts/openlm_lora/1.0.0/adapter_config.json` | Configuração PEFT exportada; sem pesos de adaptador. |
| `ai/artifacts/openlm_lora/1.0.0/training_arguments.json` | Opções efetivas aceitas pelo Transformers instalado. |
| `ai/artifacts/openlm_lora/1.0.0/recipe.json` | Cópia da receita usada no relatório. |
| `ai/artifacts/openlm_lora/1.0.0/configuration_report.json` | Contagens, alvos por camada, ensaio e pendências. |
| `ai/artifacts/openlm_lora/1.0.0/manifest.json` | Hashes de configuração, dados, código e resultados. |

As fontes e o manifesto do SFT 1.0.0 não foram alterados. O script abre treino e
validação com seus hashes; não carrega os exemplos do teste reservado.

## Reproduzir e usar depois

Na raiz do projeto, com o ambiente Python da IA:

```powershell
python ai/scripts/configure_openlm_lora.py --check-tiny-gpu --output ai/artifacts/openlm_lora/nova-inspecao
```

Sem `--check-tiny-gpu`, a conferência estrutural não executa o ensaio descartável.
O script usa apenas o config do Qwen em cache e não baixa os pesos. Recusa uma
pasta de relatório já existente.

Integração prevista na 7.04.4, depois de completar os pesos:

```python
settings = load_lora_settings()
base, tokenizer = load_model(load_settings(), download=False)
model, trainability = attach_lora(base, settings)
optimizer = make_optimizer(model, settings)
arguments = make_training_arguments(settings, output_dir, len(train_dataset))
callbacks = make_callbacks(settings)
```

O loop da próxima fase ainda precisa normalizar acumulação corretamente, medir
validação por tokens, controlar checkpoints/retomada, medir memória real e
produzir os resultados. Os adaptadores treinados serão salvos separadamente do
checkpoint original, com a revisão base e o tokenizador associados.

## Pendência antes do treino real

Faltam as três partes dos safetensors e seu índice. Há apenas arquivos parciais
do download lento da 7.04.1. Depois de completar o cache, é necessário medir
forward, backward e primeiro passo com estados do otimizador na GPU real.

Acumulação de gradientes permite aumentar o lote efetivo mantendo o lote de
execução pequeno; ela não diminui a memória dos pesos. Se o treino real não
couber, o ajuste precisa ser explícito e versionado. Como os exemplos atuais
têm no máximo 275 tokens e usam padding dinâmico, baixar o limite de 1.024 para
512 não reduz necessariamente o lote que já estava sendo executado.

## Referências oficiais consultadas em 02/11/2026

- [PEFT: LoRA, inicialização e projeções-alvo](https://huggingface.co/docs/peft/developer_guides/lora).
- [PEFT: preparo de modelos quantizados](https://huggingface.co/docs/peft/developer_guides/quantization).
- [Transformers: Trainer e argumentos](https://huggingface.co/docs/transformers/main_classes/trainer).

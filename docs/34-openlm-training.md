# 7.04.4 — Fine-tuning e validação

Atualização posterior: a **7.04.5 foi concluída**, com teste e comparação de
respostas registrados em `docs/35-openlm-comparison.md` e
`ai/artifacts/openlm_evaluation/1.0.1/RESULTS.md`. As referências ao teste
reservado neste documento descrevem o estado histórico da etapa de treinamento.

## Implementação e execução

O treinador QLoRA está implementado e passou em **12 testes**, incluindo um
ensaio completo em NF4/BF16 na RTX 5050 com um modelo minúsculo descartável.

A execução real **terminou**, com pesos oficiais completos e conferidos,
3 épocas, 63 updates e o checkpoint da época 3 selecionado e recarregado.
O job e o run registram `status=complete`.

| Condição, em modo de avaliação | NLL treino | NLL validação | Perplexidade validação |
| --- | ---: | ---: | ---: |
| Original NF4 | 4,149058 | 4,039655 | 56,8067 |
| Adaptador inicial, sem ajuste | 4,143333 | 4,033484 | 56,4573 |
| Adaptador escolhido, época 3 | 1,583131 | 1,884680 | 6,58425 |

A NLL de validação caiu cerca de **53,35%** em relação ao original nesta
avaliação. As losses por época foram 2,137272, 1,904925 e 1,884680. Houve melhora
nas três épocas, sem acionar early stopping. Treino usa 335 conversas e 19.259
tokens-alvo por época; validação usa 28 conversas e 1.563 tokens-alvo.

O pico alocado medido no loop foi **4.545,68 MiB**, com pico reservado de
**5.216 MiB**. O tempo registrado para o loop e as avaliações finais foi de
1.068,30 segundos, excluindo download e referências iniciais. Esses números
foram medidos no modelo real, e não no ensaio minúsculo.

Os hashes dos resultados, checkpoints, código e dados congelados foram
conferidos após a execução. `verification.json` registra essa conferência.
**O teste reservado não foi avaliado e nenhum modelo foi promovido ao app.**

## Fluxo

```text
Pesos oficiais completos e conferidos
→ modelo original em NF4
→ referência de loss em treino e validação
→ preparo QLoRA e adaptadores da receita 1.0.0
→ referência do adaptador inicial, época 0
→ treino apenas dos adaptadores
→ validação ao fim da época
→ checkpoint best/last e eventual early stopping
→ recarga do adaptador selecionado
→ métricas, curva e relatório
```

O loop usa **PyTorch e PEFT diretamente**. A etapa 7.04.3 também exportou
TrainingArguments compatíveis com Transformers, mas esta execução não utiliza
o Trainer: a normalização da acumulação, a validação por tokens e a retomada
estão explícitas no código do projeto.

## Dados e parâmetros

- Qwen3-4B-Instruct-2507, revisão `cdbee75f17c01a7cc42f958dc650907174af0554`.
- NF4 de 4 bits com quantização dupla e cálculo BF16.
- LoRA rank 8, alpha 16 e dropout 0,05 em sete projeções por bloco.
- 16.515.072 parâmetros treináveis; pesos base congelados.
- SFT 1.0.0: 335 exemplos de treino, 28 de validação.
- O teste de 28 conversas fica reservado para a 7.04.5.
- Lote de uma conversa; acumulação de até 16 lotes; até três épocas.
- AdamW, learning rate máximo 1e-4, weight decay 0,01 e clipping 1,0.
- Warmup linear de sete passos e decaimento linear até o fim do plano.
- Até 21 updates por época, 63 no total; último grupo de 15 lotes preservado.

O scheduler começa com learning rate zero, como no warmup linear convencional.
O primeiro passo conta como chamada ao otimizador e inicializa seu estado; o
learning rate sobe nos passos seguintes. O total realizado pode ser menor por
early stopping ou interrupção.

## Loss e acumulação corretas

O Dataset traz labels alinhados com os IDs de entrada, com -100 no contexto.
O treinador faz o deslocamento causal uma única vez: scores da posição anterior
são comparados com o token seguinte. A comparação usa somente labels válidos.

Em cada grupo de até 16 conversas:

1. Conta todos os tokens-alvo do grupo, ainda na CPU.
2. Calcula a soma da NLL de cada conversa.
3. Divide cada soma pelo total de alvos do grupo antes do backward.
4. Faz clipping, um passo de AdamW e um passo do scheduler.

Assim, uma resposta curta não ganha artificialmente o mesmo peso de uma longa
por usarmos uma média de médias. O último grupo parcial usa seu denominador
real, sem dividir por 16 quando há menos lotes.

A validação também soma a NLL e divide pelo total de tokens-alvo. Nenhum gradiente
é calculado nessa avaliação. O modo anterior do modelo é restaurado depois dela.

## Redução de memória

O modelo recebe o contexto inteiro. Com `logits_to_keep`, calculamos a projeção
para o vocabulário apenas nas posições necessárias à resposta final, incluindo
a posição que prevê o primeiro token-alvo. Isso evita materializar scores de
151.936 opções para todo o prompt sem necessidade.

O teste compara essa otimização com a loss nativa do Qwen em uma sequência
completa e confirma equivalência. Não reduzimos o contexto de atenção nem
truncamos a resposta para obter esse ganho de memória.

Há BF16, checkpointing não reentrante e cache KV desligado no treino. O pico de
memória registrado pelo loop inclui backward e estados do AdamW, mas não deve
ser confundido com todo o uso de VRAM do processo ou com o pico de carregamento.

## Seleção e segurança do experimento

A época 0 é um candidato válido. Se nenhuma época treinada reduzir a loss de
validação, o adaptador inicial é mantido como melhor. Duas épocas seguidas sem
melhora acionam early stopping na receita atual.

O relatório registra separadamente o modelo original antes do preparo e o
adaptador inicial depois do preparo: converter componentes congelados para outra
precisão pode mudar ligeiramente a referência numérica. Melhorar em relação a
uma dessas referências não deve ser confundido automaticamente com melhorar em
relação à outra.

Nenhuma seleção usa o teste reservado. O adaptador escolhido é recarregado e
sua NLL de validação precisa reproduzir o valor escolhido, com tolerância numérica
de 1e-5. O modelo original permanece separado; nenhum adaptador é promovido ao
app automaticamente.

O SFT é pequeno e sintético. NLL menor demonstra melhor previsão dos alvos desse
conjunto, não conhecimento clínico certificado ou boa conversa com usuários
reais. A comparação qualitativa e o teste final pertencem à 7.04.5.

## Checkpoints e retomada

Cada checkpoint contém:

- `adapter_model.safetensors`: apenas matrizes dos adaptadores;
- `adapter_config.json`: configuração e referência do modelo base;
- `trainer_state.pt`: otimizador, scheduler, época, update, histórico e RNG;
- metadados do PEFT, quando produzidos pela biblioteca.

Arquivos são escritos em uma pasta de estágio e promovidos antes da troca
atômica do índice. O índice guarda hashes e aponta para `best` e `last`.
Mantemos no máximo esses dois checkpoints; um estado órfão encontrado após uma
interrupção é preservado separadamente, sem sobrescrever pesos silenciosamente.

A retomada ocorre na **última época completa**. Se a execução cair no meio de
uma época, essa parte é refeita a partir do checkpoint anterior. São restaurados
os estados aleatórios de Python, PyTorch, CUDA e dos geradores dos DataLoaders.

Um teste em CPU confirmou igualdade exata dos tensores entre uma execução
contínua e outra interrompida/retomada, com dropout ativo. Isso não promete
igualdade bit a bit entre GPUs, sistemas ou versões diferentes. A retomada real
exige os mesmos hashes de configuração, dados, pesos, código e ambiente.

`torch.load` usa `weights_only=True` no estado do treinador. Caminhos de
checkpoints precisam permanecer dentro da pasta prevista. Checksum incorreto
interrompe a leitura antes de carregar o estado.

## Download e processo automático

O transporte paralelo aproveita blocos já recebidos e os parciais anteriores,
usando faixas HTTP exatas da revisão oficial. Os safetensors só são promovidos
depois da conferência de tamanho e SHA256. Os hashes selecionados estão em
`ai/configs/openlm.weights.v1.json`.

Há lock do download e lock do job. Se outra transferência estiver ativa, o job
espera e acompanha seu progresso. Se ela terminar antes de completar os arquivos,
o job retoma os blocos disponíveis. A espera por outro transferidor é limitada a
seis horas. Uma execução duplicada é rejeitada sem interferir na principal.

Os pesos e blocos ficam no cache local fora do OneDrive. A montagem pode manter
uma cópia em blocos além dos arquivos completos para retomada, portanto o espaço
ocupado no cache pode exceder os cerca de 8 GB dos pesos. Após a verificação
desta execução, os blocos e parciais redundantes gerados foram removidos; pesos
oficiais completos e checkpoints treinados foram preservados.

## Arquivos para acompanhar

| Caminho relativo à raiz do projeto | Conteúdo |
| --- | --- |
| `ai/artifacts/openlm_jobs/1.0.0/status.json` | Etapa do job: download, preparo, conclusão ou erro. |
| `ai/artifacts/openlm_jobs/1.0.0/launch.json` | Processo local e localização dos logs. |
| `ai/artifacts/openlm_jobs/1.0.0/private/training.stdout.log` | Progresso do job automático. |
| `ai/artifacts/openlm_jobs/1.0.0/private/training.stderr.log` | Avisos e erros da execução. |
| `ai/artifacts/openlm_download/1.0.0/progress.json` | Progresso da transferência independente inicial. |
| `ai/artifacts/openlm_training/1.0.0/progress.json` | Progresso preciso do treinador após os primeiros updates. |
| `ai/artifacts/openlm_training/1.0.0/history.json` e `.csv` | Métricas por época. |
| `ai/artifacts/openlm_training/1.0.0/checkpoint_index.json` | Checkpoints escolhido e retomável. |
| `ai/artifacts/openlm_training/1.0.0/results.json` | Resultados reais, quando o treino terminar. |
| `ai/artifacts/openlm_training/1.0.0/RESULTS.md` | Relatório automático da execução concluída. |
| `ai/artifacts/openlm_training/1.0.0/loss_curve.png` e `.svg` | Curva, se Matplotlib estiver disponível. |
| `ai/artifacts/openlm_training/1.0.0/private/checkpoints/` | Pesos dos adaptadores e estado retomável, ignorados pelo Git. |

Os arquivos do run de treinamento são criados progressivamente; podem ainda não
existir enquanto os pesos estão sendo baixados. Durante o loop, `progress.json`
do run é a referência dos updates; o status externo do job pode permanecer em
preparo até a chamada de treino retornar.

## Comandos

Na raiz do projeto e com o Python correto, para iniciar uma nova execução após
o download ou permitir concluí-lo automaticamente:

```powershell
python ai/scripts/train_openlm.py --download --download-workers 24
```

Não execute uma segunda instância enquanto o job iniciado estiver ativo.
Um run já existente não é sobrescrito. Para retomar uma execução que já criou
checkpoint e depois foi interrompida:

```powershell
python ai/scripts/train_openlm.py --resume
```

Se só o download foi interrompido e nenhum run foi criado, use o comando com
`--download` novamente, sem `--resume`. Um run completo recusa treino adicional;
um experimento novo precisa de nova pasta de saída e registro da configuração.

## Código e verificação

- `ai/src/evolv_openlm/training.py`: loss, acumulação, avaliação, checkpoints e retomada.
- `ai/src/evolv_openlm/training_report.py`: relatório e gráfico a partir das métricas gravadas.
- `ai/src/evolv_openlm/parallel_download.py`: transferência em blocos com hashes oficiais.
- `ai/scripts/train_openlm.py`: preflight, referência original, job e execução.
- `ai/scripts/download_openlm.py`: download independente, sem treino.
- `ai/tests/test_openlm_training.py`: 12 testes aprovados em modelos descartáveis.

Esses testes verificam ponderação por tokens, equivalência da projeção reduzida,
acumulação equivalente a um lote conjunto, último grupo parcial, early stopping,
retenção da época 0, retomada exata, checksum, caminhos e relatório. O ensaio de
GPU passou pelo loop completo em NF4/BF16 com salvamento e recarga. Seus números
de loss não são métricas do modelo real de 4B.

## Fontes

- [PEFT: quantização e preparo para QLoRA](https://huggingface.co/docs/peft/developer_guides/quantization).
- [PEFT: formato dos checkpoints](https://huggingface.co/docs/peft/developer_guides/checkpoint).
- [PyTorch: exemplos de precisão mista](https://docs.pytorch.org/docs/stable/notes/amp_examples.html).

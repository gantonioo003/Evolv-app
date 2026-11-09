# 7.03.3 — Transformer causal em PyTorch

Concluído em 01/11/2026. Arquitetura `1.0.0` implementada do zero com módulos
PyTorch, ligada aos dados preparados da 7.03.2. O código usa operações de
atenção do PyTorch; não carrega um Transformer, encoder ou pesos pré-treinados.
O treinamento por épocas fica para a 7.03.4.

## Mapa completo até a rede

```text
7.03.1: texto → tokenizador BPE → IDs
7.03.2: IDs → sequências → X, y e máscara → lotes
7.03.3: lote X
          → embedding de token + embedding de posição
          → dropout
          → 4 blocos de Transformer causal
          → normalização final
          → projeção para os 8.192 tokens possíveis
          → scores por posição (logits)

         logits + y já deslocado
          → cross-entropy dos alvos válidos
          → backward calcula os gradientes

7.03.4: otimizador usará os gradientes para atualizar os pesos
```

O embedding transforma o ID em um vetor que será aprendido. A posição indica
a ordem dos tokens. A atenção combina informações do prefixo disponível;
a rede feed-forward transforma essa representação em cada posição.
A projeção final dá um score para cada próximo token possível. Reservar
um token no vocabulário não significa que a rede já conhece seu significado.

Um decoder-only consegue processar o texto recebido e prever continuações
sem um encoder separado. Nesta arquitetura não existe atenção cruzada com
a saída de outro modelo. A geração repetida de tokens será feita na fase
7.03.5; nesta etapa, a rede produz os scores de uma sequência fornecida.

## Configuração escolhida

| Componente | Valor |
| --- | ---: |
| Vocabulário | 8.192 |
| Contexto máximo | 256 tokens |
| Dimensão dos embeddings e estados | 192 |
| Blocos de Transformer | 4 |
| Cabeças de atenção por bloco | 6 |
| Dimensão por cabeça | 32 |
| Camada interna do feed-forward | 768 |
| Ativação | GELU |
| Dropout | 0,1 |
| Normalização | LayerNorm antes das subcamadas e ao final |
| Posições | Embeddings absolutos aprendidos |
| Pesos da entrada/saída | Compartilhados |
| Parâmetros treináveis únicos | **3.401.856** |

É uma configuração inicial pequena, definida sem procurar a melhor opção
no teste. A adequação ao corpus e a tendência a overfitting serão medidas
durante o treinamento. Esta etapa não compara qualidade de respostas.

Distribuição dos parâmetros, sem contar pesos compartilhados duas vezes:

| Parte | Parâmetros |
| --- | ---: |
| Embedding dos tokens e projeção de saída compartilhada | 1.572.864 |
| Embedding de posição | 49.152 |
| Quatro blocos | 1.779.456 |
| LayerNorm final | 384 |
| Total | 3.401.856 |

Compartilhar os pesos da entrada e da saída evita outra matriz de
8.192 × 192 parâmetros. A tabela de embeddings não usa `padding_idx`
congelado: os vetores de entrada das posições de padding são explicitamente
zerados, enquanto a tabela compartilhada também aprende pela projeção de saída.

## O que há em cada bloco

```text
x
 → LayerNorm → Q, K, V → atenção causal multihead → projeção → dropout
 → soma com x (conexão residual)
 → LayerNorm → Linear(192→768) → GELU → Linear(768→192) → dropout
 → soma residual
 → zera posições de padding
```

Q, K e V são projeções aprendidas do mesmo texto. A operação
`scaled_dot_product_attention` aplica a atenção escalada e combina as cabeças.
As projeções de saída dos caminhos residuais começam com escala reduzida
de inicialização, para a soma dos blocos não crescer excessivamente no início.

## Duas máscaras diferentes

1. **Causal:** a posição atual pode consultar a si mesma e as anteriores.
   Ela não pode consultar os tokens seguintes de X.
2. **Padding:** as posições de preenchimento não são usadas como chaves da
   atenção; suas ativações são zeradas e seus alvos não entram no erro.

A rede combina as duas restrições em uma máscara booleana. Na API SDPA do
PyTorch usada aqui, `True` significa **permitido**. Isso corresponde à máscara
da 7.03.2, onde `True` indica token real. Não passamos `is_causal=True` junto
com essa máscara: a restrição causal já está incluída nela.

O modelo aceita padding à direita, conforme o dataset. Rejeita linhas sem
tokens reais e máscaras com buracos ou padding à esquerda. Assim, toda consulta
tem pelo menos uma chave anterior válida. A ausência de máscara faz o modelo
inferir padding pelo ID `0`.

Dropout fica ativo em `model.train()` e desativado em `model.eval()`.
Para SDPA, o código também passa explicitamente probabilidade zero no modo
de avaliação; apenas mudar o modo do módulo não faria isso automaticamente.

## Entrada, saída e função de erro

```python
output = model(
    input_ids=batch["input_ids"],
    attention_mask=batch["attention_mask"],
    labels=batch["labels"],
)

logits = output["logits"]       # [lote, posições, vocabulário]
loss = output["loss"]           # média por alvo válido do lote
loss_sum = output["loss_sum"]   # soma para acumular métricas corretamente
valid = output["valid_tokens"]  # quantidade de alvos válidos
loss.backward()                # calcula gradientes; não atualiza pesos sozinho
```

Para lote 16 e contexto 256, os logits têm formato `[16, 256, 8192]`.
São scores sem normalização; não aplicamos softmax antes da cross-entropy.
O dataset já desloca y um token. O modelo **não desloca novamente os alvos**.

Alvos `-100` e posições mascaradas ficam fora do erro. Se todos os alvos
forem ignorados, a função devolve zero diferenciável, evitando NaN. Sem
`labels`, a rede devolve os logits e deixa os três campos de erro como `None`.
O treinamento futuro deve acumular `loss_sum / total_valid_tokens` ao medir
a perda de uma época, evitando uma média de lotes com pesos incorretos.

## Onde está cada coisa

```text
ai/configs/tinylm.v1.json
  → números da arquitetura

ai/src/evolv_tinylm/model.py
  → TinyLMConfig: configuração e compatibilidade com os dados
  → CausalSelfAttention: projeções QKV e atenção com máscaras
  → DecoderBlock: atenção, feed-forward e conexões residuais
  → TinyLM: embeddings, blocos, logits e cálculo de loss

ai/scripts/inspect_tinylm_model.py
  → monta a rede e verifica forward/backward em um lote real de TREINO

ai/tests/test_tinylm_model.py
  → causalidade, padding, gradientes, erros de entrada e serialização

ai/artifacts/tinylm/1.0.0/
  → architecture.json: configuração verificada
  → smoke_report.json: resultados funcionais em CPU/GPU
  → manifest.json: hashes dos relatórios e dos códigos utilizados
```

Os métodos `forward()` representam a passagem da informação pela rede.
Não há `model.fit()` nesta implementação PyTorch. O loop com épocas,
`optimizer.step()`, validação e checkpoints será escrito na 7.03.4.
Nenhum peso foi salvo como modelo treinado nesta fase.

## Verificações executadas

O teste funcional usou um lote real de treino de `[16, 256]`, tanto na CPU
quanto na NVIDIA GeForce RTX 5050 Laptop GPU. Ambos produziram logits de
`[16, 256, 8192]`, perda finita e gradientes finitos em todos os parâmetros.

- Alterar apenas o futuro mudou os scores futuros, mas a diferença nos
  scores anteriores foi **zero** nos dois dispositivos.
- Acrescentar padding manteve os scores reais com diferenças numéricas
  máximas de aproximadamente `1,1e-6` na CPU e `8,4e-7` na GPU.
- O backward alcança embeddings, atenção, feed-forward e normalizações.
  Os testes também demonstram que o gradiente de uma saída anterior não
  alcança as entradas futuras da atenção.
- A cross-entropy ignora padding, usa os alvos já deslocados e não produz
  gradientes nas posições ignoradas.
- Salvar/recarregar `state_dict` em memória preserva as saídas e o
  compartilhamento de pesos, usando `torch.load(..., weights_only=True)`.
- Forward/backward com autocast também passou na GPU.

Os 33 testes das fases TinyLM passaram no ambiente Python 3.12, incluindo
13 testes desta entrega. A suíte geral em Python 3.14 executou 257 testes:
237 passaram e 20 foram ignorados por condições do ambiente. Esse runtime
não tem PyTorch; os testes da rede foram executados no ambiente 3.12.
A conferência final confirmou os hashes e o carregamento do corpus, BPE e
dados preparados sem alterações.

No teste funcional em float32, a GPU teve pico de memória alocada de cerca
de **770 MiB**. Isso mede esse forward/backward de um lote; não inclui estados
do otimizador, validação completa ou todas as condições do treinamento futuro.

As losses iniciais foram próximas de 9,03, compatíveis com uma rede inicializada
aleatoriamente. **Não são métricas de um LM treinado.** Dropout e kernels de
CPU/GPU podem produzir pequenas diferenças; não se promete igualdade de bits
entre dispositivos. Os testes funcionais não utilizaram os textos de validação
ou teste para escolher a arquitetura. O otimizador não foi executado.

## Como inspecionar

Na raiz do repositório, com o ambiente Python 3.12 que contém PyTorch:

```powershell
python -m pip install -r ai/requirements.tinylm-training.txt
python ai/scripts/inspect_tinylm_model.py --device cpu
python ai/scripts/inspect_tinylm_model.py --device cuda --batch-size 16
python -m unittest discover -s ai/tests -p "test_tinylm*.py" -v
```

O script escolhe CUDA quando disponível por padrão; `--device all` verifica
CPU e CUDA. Ele apenas imprime resultados, a menos que receba `--output`
com uma pasta nova. Pastas existentes de relatórios não são sobrescritas.
O relatório desta entrega corresponde a `--device all --batch-size 16`.

Os modelos de intenção/risco e o extrator do Coach continuam separados.
O corpus e seu vocabulário não foram alterados. O TinyLM continua educacional;
a existência da arquitetura não demonstra qualidade factual ou capacidade
de aconselhamento. O Coach principal com modelo pré-treinado é outra etapa.

Próxima fase: **7.03.4 — treinamento, otimização e checkpoints**.

Referências técnicas: [atenção SDPA e convenções das máscaras](https://docs.pytorch.org/docs/2.11/generated/torch.nn.functional.scaled_dot_product_attention.html),
[Embedding](https://docs.pytorch.org/docs/2.11/generated/torch.nn.Embedding.html) e
[cross-entropy](https://docs.pytorch.org/docs/2.11/generated/torch.nn.functional.cross_entropy.html).

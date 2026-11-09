# 7.03.2 — Preparação dos dados para prever o próximo token

Concluído em 01/11/2026. O corpus `1.2.0` foi convertido com o BPE `1.0.0`
para dados preparados `1.0.0`. O vocabulário continua com 8.192 tokens.
Nenhum modelo neural foi treinado e nenhum texto novo foi acrescentado.

## A sequência desta etapa

```text
corpus já dividido em treino / validação / teste
  → tokenizador BPE já treinado e congelado
  → IDs por documento, com BOS e EOS
  → janelas de até 256 posições
  → entrada X e alvo y deslocado um token
  → Dataset e DataLoader
  → lotes prontos para o Transformer da próxima fase
```

O alvo não precisa ser uma resposta escrita por alguém: **a resposta certa de
cada posição é o próximo token do próprio texto**. Esse é o exercício
autossupervisionado de modelagem causal da linguagem. Ainda não estamos
treinando perguntas e respostas do Coach.

Exemplo real do tokenizador, usando um texto escrito para a demonstração:

```text
Texto: Hoje eu treino.
Documento: [1, 46, 85, 1168, 2290, 3169, 20, 2]

X:         [1, 46, 85, 1168, 2290, 3169, 20]
y:         [46, 85, 1168, 2290, 3169, 20, 2]
```

`1` é BOS (início); `2` é EOS (fim). Um token pode ser um pedaço de palavra.
Em cada posição, o modelo deverá prever o item correspondente de `y` usando
somente o prefixo de `X` até aquela posição. **O futuro decoder precisa da
máscara causal** para impedir que veja o restante de `X` antes de prever.
Os dados já entregam `y` deslocado: o nosso modelo autoral não deve deslocá-lo
novamente ao calcular o erro.

## Como os documentos viram sequências

- Cada documento mantém seus próprios limites. Não há sequência que junte
  textos diferentes, nem transição artificial de EOS de um documento para BOS
  de outro.
- Um texto longo é dividido em janelas com até 256 alvos. Cada par adjacente
  de tokens é usado exatamente uma vez como exercício.
- Há um token compartilhado entre janelas consecutivas: o último alvo de uma
  janela é o primeiro token de entrada da seguinte. Isso preserva a transição
  na fronteira sem repetir alvos.
- O contexto não continua de uma janela para a seguinte. Nesta configuração,
  o modelo terá no máximo 256 tokens de entrada por sequência; não lê artigos
  longos inteiros de uma vez.
- As sobras são mantidas. Entradas curtas recebem PAD (`0`) à direita; os
  alvos correspondentes recebem `-100`, ignorado pela função de erro.
- `attention_mask=True` indica entrada real, `False` indica preenchimento.
  Essa máscara de padding não substitui a máscara causal do decoder.

Na implementação futura do Transformer, ao usar `key_padding_mask` do PyTorch,
o significado é o inverso: será necessário passar `~attention_mask`.
Outras APIs de atenção podem ter convenções diferentes; a conversão pertence
ao modelo, não ao dataset.

## Quantidades geradas

| Partição | Documentos | Tokens salvos com BOS/EOS | Alvos válidos | Sequências de até 256 |
| --- | ---: | ---: | ---: | ---: |
| Treino | 6.612 | 2.960.329 | 2.953.717 | 15.618 |
| Validação | 57 | 21.645 | 21.588 | 119 |
| Teste | 42 | 14.922 | 14.880 | 81 |
| Total | 6.711 | 2.996.896 | 2.990.185 | 15.818 |

O total de alvos é o total de tokens salvos menos um BOS por documento.
Todos os tokens de texto e os EOS são alvos. O BOS é usado como entrada
inicial, não como alvo para tentar adivinhar o começo do próximo documento.

Cada lote padrão tem até 16 sequências. `input_ids` e `labels` são tensores
`torch.int64`, normalmente de formato `[16, 256]`; `attention_mask` é booleano
com o mesmo formato. O último lote pode ter menos de 16 sequências.
Há 977 lotes de treino, 8 de validação e 6 de teste com essa configuração.

No treino, 73,9% das posições são alvos reais; o restante é preenchimento
ignorado. Mantivemos documentos separados para facilitar o entendimento e
evitar mistura de contextos. Agrupar textos ou usar lotes por comprimento
pode reduzir esse custo futuramente, mas não foi feito nesta versão.

## Organização dos arquivos

```text
ai/scripts/prepare_tinylm_data.py
  → chama prepare_data() de src/evolv_tinylm/data.py
  → confere corpus e tokenizador, codifica e salva os arrays

ai/src/evolv_tinylm/data.py
  → prepara e valida hashes, IDs, limites e contagens

ai/src/evolv_tinylm/dataset.py
  → NextTokenDataset: recorta cada janela e monta X, y e máscara
  → make_dataloaders(): organiza as sequências em lotes

ai/scripts/inspect_tinylm_batch.py
  → mostra os formatos de um lote de cada partição e o exemplo acima

ai/artifacts/tinylm_data/1.0.0/
  → config.json: contexto, padding, deslocamento e tipos numéricos
  → manifest.json: versões e hashes do corpus, BPE e arquivos gerados
  → report.json: contagens e cobertura por partição
  → private/{train,validation,test}.tokens.npy
  → private/{train,validation,test}.offsets.npy
```

Os tokens ficam em arrays `uint16` em disco, suficientes para IDs de 0 a
8.191. Os offsets são índices `int64` que indicam onde cada documento começa
e termina. Os seis arquivos binários ocupam aproximadamente 6 MB. X e y
não são duplicados em disco: são construídos ao pedir cada sequência.

O acesso aos tokens usa mapeamento de arquivo em modo somente leitura.
Cada janela é copiada para um tensor independente, convertido para `int64`.
Workers do Windows reabrem seu próprio mapeamento em vez de receber uma
cópia de todo o corpus. A preparação não precisa de PyTorch ou GPU;
os DataLoaders usam PyTorch e entregam tensores na CPU.

## Uso

Na raiz do repositório, com o ambiente Python 3.12 usado no projeto:

```powershell
python -m pip install -r ai/requirements.tinylm-training.txt
python ai/scripts/inspect_tinylm_batch.py
python ai/scripts/inspect_tinylm_batch.py --num-workers 2
python -m unittest discover -s ai/tests -p "test_tinylm*.py" -v
```

Para usar no próximo treinamento:

```python
from evolv_tinylm.dataset import make_dataloaders

loaders = make_dataloaders("ai/artifacts/tinylm_data/1.0.0", batch_size=16, seed=42)
batch = next(iter(loaders["train"]))
x = batch["input_ids"]
y = batch["labels"]
attention_mask = batch["attention_mask"]
```

Esse import pressupõe `ai/src` no caminho de módulos, como os scripts já
configuram. O treino embaralha as sequências; validação e teste mantêm a
ordem. A semente controla o embaralhamento. Novos loaders com a mesma
semente reproduzem a ordem; novas épocas no mesmo loader seguem o estado
do gerador e obtêm outro embaralhamento. Nenhum lote final é descartado.

Para reproduzir somente a preparação, sem sobrescrever o artefato pronto:

```powershell
python ai/scripts/prepare_tinylm_data.py --output ai/artifacts/tinylm_data/reproducao-1.0.0
```

O comando padrão usa o contexto 256. Repetir o preparo nunca reaprende o
vocabulário; `--context-length` muda a configuração das janelas, exigindo
uma pasta de saída separada. A pasta padrão existente é protegida contra
sobrescrita.

## Verificação e limites

A preparação confere a integridade do corpus e exige que seja exatamente
aquele associado ao tokenizador congelado. Os hashes do BPE, do corpus e dos
arrays ficam registrados. As partições originais não foram redivididas;
validação e teste apenas foram codificados, sem nenhum ajuste sobre eles.
Os binários ficam em `private/`, ignorados pelo Git, com as mesmas obrigações
de privacidade, licença e atribuição do corpus original.

Os testes verificam a correspondência token a token, isolamento de documentos,
cobertura de todos os alvos, sobras, padding, repetibilidade e arquivos alterados.
Também conferem que o padding tem gradiente zero na CrossEntropyLoss.
O carregamento real com dois workers foi executado no Windows.

Resultado da entrega: os 20 testes das fases 7.03.1/7.03.2 passaram no Python
3.12.14 com PyTorch 2.11.0+cu128. A suíte geral com Python 3.14 executou 244
testes: 236 passaram e 8 foram ignorados, incluindo os 4 testes de lotes cujo
runtime não tem PyTorch; esses 4 passaram no ambiente 3.12.
Uma conferência adicional comparou cada um dos 6.711 documentos com seus IDs
salvos e percorreu todos os lotes reais, contando exatamente os 2.990.185 alvos
esperados. Os hashes dos arquivos originais permaneceram válidos.

O futuro treinamento deve somar o erro dos alvos válidos e dividir pelo número
total desses alvos ao medir loss/perplexidade. Uma média simples de médias
de lotes com quantidades diferentes de padding distorceria essa medida.

As limitações do corpus da 7.03.1 continuam: poucos textos comparados a LMs
grandes, predominância enciclopédica e avaliações pequenas. Preparar os dados
corretamente não equivale a treinar ou validar um Coach de produção.
Os modelos de intenção, risco e extração de entidades continuam separados.

Próxima etapa: **7.03.3 — Transformer causal pequeno em PyTorch**.

Referências técnicas: [Dataset e DataLoader no PyTorch 2.11](https://docs.pytorch.org/docs/2.11/data.html)
e [CrossEntropyLoss e ignore_index](https://docs.pytorch.org/docs/2.11/generated/torch.nn.CrossEntropyLoss.html).

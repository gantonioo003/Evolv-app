# 7.03.1 — Tokenizador próprio do TinyLM

Concluído em 01/11/2026. Tokenizador `1.0.0`, treinado do zero com o campo
`text` do **treino** do corpus `1.2.0`. O Transformer ainda não foi construído
nem treinado nesta etapa. Os classificadores de intenção/risco e o extrator
de entidades continuam separados e não foram alterados.

## O caminho dos arquivos

```text
data/lm_corpus/1.2.0/train.jsonl
  → scripts/train_tinylm_tokenizer.py
  → src/evolv_tinylm/tokenizer_training.py: audit_corpus() → train_tokenizer()
  → src/evolv_tinylm/tokenizer.py: build_bpe() → train_from_iterator()
  → artifacts/tokenizer/1.0.0/

mensagem nova
  → scripts/encode_tinylm.py
  → EvolvTokenizer.load() → encode() ou encode_document()
  → IDs numéricos; decode() recupera o texto normalizado
```

O corpus é o material de leitura. O vocabulário é a tabela de pedaços de texto
e seus IDs que o BPE aprende com esse material. **8.192 tokens de vocabulário
não são 8.192 palavras, nem o tamanho do corpus.** Os mesmos tokens aparecem
milhões de vezes nos textos. O tokenizador prepara números; não aprende a
responder perguntas, classificar intenções ou dar orientações de treino.

## Decisões fixadas antes de medir validação/teste

- Byte-level BPE, vocabulário total de **8.192**, frequência mínima de pares 2.
- 256 símbolos de bytes como base, incluindo bytes não vistos no treino.
- Unicode NFC: preserva maiúsculas, acentos, pontuação, espaços e quebras de
  linha. Sequências Unicode equivalentes podem mudar de código, como `a` +
  acento combinante para um caractere composto; a recuperação é comparada a NFC.
- Sem remoção de stopwords: palavras curtas também importam para gerar texto.
- Sem truncamento, padding, segmentação em blocos ou montagem de X/y nesta fase.
- Nenhum vocabulário ou peso pré-treinado foi importado. A biblioteca utilizada
  é Hugging Face `tokenizers==0.23.3`, sem dependência de GPU, PyTorch ou API.

O tamanho 8.192 é uma escolha inicial para manter pequenas as matrizes do futuro
TinyLM. Não foi escolhido por busca de hiperparâmetros no teste. Suporte a bytes
de outros alfabetos **não significa** domínio de outros idiomas.

| ID fixo | Token | Finalidade |
| --- | --- | --- |
| 0 | `<\|pad\|>` | Preencher lotes, quando implementarmos a etapa seguinte |
| 1 | `<\|bos\|>` | Início de um documento |
| 2 | `<\|eos\|>` | Fim de um documento |
| 3 | `<\|unk\|>` | Reserva para desconhecidos; ocorrência medida igual a zero |
| 4 | `<\|system\|>` | Papel reservado para futura formatação de diálogos |
| 5 | `<\|user\|>` | Papel reservado para futura formatação de diálogos |
| 6 | `<\|assistant\|>` | Papel reservado para futura formatação de diálogos |

Os sete tokens especiais estão incluídos nos 8.192. Reservar papéis não treina
um modelo de conversa. Um futuro formatador deverá inserir IDs de papel somente
em posições confiáveis.

`encode(text)` serve para texto/prompt e não acrescenta BOS/EOS. Já
`encode_document(text)` retorna `[BOS] + tokens_do_texto + [EOS]`. Não se deve
fechar um prompt de geração com EOS por acidente. `decode(ids)` ignora os tokens
especiais por padrão.

Strings literais como `<|assistant|>` dentro da mensagem são texto comum e não
inserem IDs de controle. O wrapper reaplica `encode_special_tokens=True` após
carregar o JSON: esse ajuste não é serializado pela versão instalada. Por isso,
**use `EvolvTokenizer.load()`, em vez de carregar o JSON diretamente para uso
no aplicativo**. Essa proteção de formato não resolve todos os problemas de
instruções maliciosas de um futuro LM.

## Medidas reais da versão

| Partição | Documentos | Tokens de texto | Tokens com BOS/EOS | Tokens desconhecidos |
| --- | ---: | ---: | ---: | ---: |
| Treino | 6.612 | 2.947.105 | 2.960.329 | 0 |
| Validação | 57 | 21.531 | 21.645 | 0 |
| Teste | 42 | 14.838 | 14.922 | 0 |
| Total | 6.711 | 2.983.474 | 2.996.896 | 0 |

Todos os documentos foram codificados e decodificados sem divergência em NFC,
sem tokens de controle provenientes de texto literal. No treino: média de
1,81 tokens por palavra separada por espaço; mediana de 173 tokens por documento;
percentil 95 de 1.608 e máximo de 2.847. São estatísticas do tokenizador,
**não accuracy, F1 ou perplexidade do LM**.

Os hashes de todos os arquivos do corpus correspondem ao manifesto anterior.
Não houve alteração das partições, do texto ou dos metadados. Não foram encontrados
grupos compartilhados ou textos exatamente iguais após NFC, casefold e redução de
espaços entre as partições. Não foi feita nova busca de paráfrases/quase duplicatas
nesta etapa; essas verificações não equivalem a garantia absoluta contra vazamento.

O vocabulário foi salvo e teve seu hash registrado antes das medidas de validação
e teste. Esses textos não entraram em `train_from_iterator()`. Metadados, IDs,
licenças e rótulos do JSONL também não entraram no treinamento do BPE.

## O que é adequado e o que continua limitado

O corpus é adequado para **aprender a construir um pequeno LM em português**.
Ainda é pequeno para obter um Coach confiável. A Wikipedia representa 94,0% dos
tokens de treino; as conversas humanas OASST representam cerca de 4,9%. O restante
inclui conhecimento e exemplos do projeto. Portanto, não se deve interpretar
esse corpus como milhões de exemplos especializados em treino/dieta ou diálogos.

Validação e teste também são pequenos e predominantemente enciclopédicos. A futura
perplexidade será informativa sobre esse recorte, não uma certificação da qualidade
do Coach. A qualidade factual de cada texto não foi reavaliada nesta fase.

As 12.179 mensagens do NLP e as explicações das revisões de rótulos não foram
copiadas automaticamente para o corpus. Dados reais privados não foram acrescentados.
Licenças e atribuições continuam nas versões do corpus e em `sources.json` da
versão `1.0.0`; os arquivos aprendidos ficam locais em `private/`, ignorados pelo
Git. Isso não constitui liberação para redistribuir conteúdo ou treinar qualquer
produto sem avaliar as obrigações de cada fonte.

O manifesto antigo do corpus mantém `actual_token_count: null` e
`model_or_tokenizer_trained: false` porque registra o estado de sua criação.
As contagens e o treinamento posteriores estão no artefato do tokenizador.

## Como usar e conferir

Na raiz do repositório, com Python 3.12 ou 3.14 e as dependências instaladas:

```powershell
python -m pip install -r ai/requirements.tinylm.txt
python ai/scripts/encode_tinylm.py "amanhã troca o supino por flexão"
python ai/scripts/encode_tinylm.py "Fiz 3x12 com 22,5 kg" --document
python -m unittest discover -s ai/tests -p test_tinylm_tokenizer.py -v
```

Para reproduzir o treinamento em uma pasta nova, sem sobrescrever a versão pronta:

```powershell
python ai/scripts/train_tinylm_tokenizer.py --output ai/artifacts/tokenizer/reproducao-1.0.0
```

O padrão do comando de treino é `artifacts/tokenizer/1.0.0`; ele recusa sobrescrever
uma pasta existente. A configuração e a versão da biblioteca ficam registradas.
Os testes com um corpus pequeno confirmam repetição do vocabulário/merges na mesma
versão. Não se promete identidade binária entre bibliotecas ou versões diferentes.

`tokenizer.py` contém o BPE e sua interface. `tokenizer_training.py` audita, treina,
mede e salva. Os dois scripts apenas oferecem os comandos. Nos artefatos:

- `private/tokenizer.json`: pipeline completa que deve ser carregada pelo wrapper.
- `private/vocab.json` e `private/merges.txt`: vocabulário e regras de combinação.
- `config.json`: decisões de treinamento e IDs especiais.
- `manifest.json`: versões, hashes, arquivos e momento de congelamento.
- `report.json`: contagens, medidas por fonte e conferência das partições.
- `examples.json`: nove exemplos próprios para inspecionar IDs, pedaços e recuperação.

As representações visuais dos bytes podem mostrar símbolos como `Ġ` e `Ã` nos
`pieces`. Isso é representação interna; o campo `decoded` deve exibir o texto
correto. Nenhum desses símbolos deve ser mostrado como resposta do Coach.

Verificação desta entrega: 10 testes específicos passaram no Python 3.12.14.
Na suíte completa com Python 3.14, 230 testes passaram e 4 foram ignorados pelas
condições já existentes. A conferência final repetiu os hashes do corpus e o
carregamento do artefato; os três arquivos aprendidos estão ignorados pelo Git.

Próxima fase: **7.03.2 — Sequências e lotes**, com IDs, janelas de contexto,
alvos deslocados de próximo token e DataLoader. O tokenizador deve ser reutilizado
sem reaprender vocabulário na validação/teste.

Referências técnicas: [treinamento por iterador](https://huggingface.co/docs/tokenizers/training_from_memory),
[componentes do tokenizador](https://huggingface.co/docs/tokenizers/components) e
documentação pública do pacote `tokenizers==0.23.3` instalado, usada para confirmar
o comportamento de codificação dos tokens especiais.

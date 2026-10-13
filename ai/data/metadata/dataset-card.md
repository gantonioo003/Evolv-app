# Dataset Card - Evolv Coach

## Identificacao

- Nome: `evolv-coach-seed`
- Versao: `1.2.0`
- Status: congelado e aprovado na fase 7.01.4
- Idioma: portugues brasileiro (`pt-BR`)
- Dominio: treino, alimentacao, recuperacao, rotina e operacoes do Evolv
- Publico inicial: adultos saudaveis, respeitando as rotas de seguranca

## Objetivo

Este dataset semente permite desenvolver e avaliar tres partes do NLP:

1. classificar a intencao principal;
2. detectar risco em paralelo;
3. verificar comportamento em mensagens ambiguas ou com varios pedidos.

Ele nao e um dataset clinico, nao contem respostas medicas e ainda nao comprova
qualidade de producao.

## Composicao

- 240 exemplos de intencao: oito para cada uma das 30 classes;
- 104 exemplos de risco: oito para cada um dos 13 rotulos;
- 39 casos separados de desafio;
- 383 registros gerados no total;
- 258 exemplos sinteticos comuns;
- 86 exemplos reescritos a partir de padroes reais;
- 39 exemplos adversariais sinteticos e revisados.

Os casos de desafio cobrem mensagens com varias intencoes, entidades ausentes,
referencias ao contexto, perguntas implicitas, negacao, conflito, datas
relativas, dependencia de imagem e prioridade de seguranca.

## Origem e procedencia

### `synthetic_curated`

Exemplos escritos para cobrir a taxonomia. Eles sao sinteticos, mas passaram
por revisao de rotulo e linguagem.

### `real_pattern_rewrite`

Frases novas baseadas em padroes observados em conversa voluntariamente
fornecida, foruns e datasets catalogados. Nao sao citacoes nem copias. Cada
registro informa `source_id`, estilo e dificuldade.

Nenhum nome, imagem, medida corporal, historico pessoal ou URL privada foi
armazenado. As fontes publicas ajudaram a descobrir linguagem e cobertura, nao
a definir fatos de saude.

### `synthetic_adversarial_curated`

Casos criados para desafiar o roteamento. Eles ficam em um conjunto separado e
nao devem ser misturados silenciosamente ao treino comum.

## Linguagem

Os exemplos incluem:

- portugues formal e informal;
- abreviacoes como `pq`, `qro`, `hj` e `td`;
- erros leves de digitacao;
- frases curtas e mensagens longas;
- negacoes;
- referencias como `isso`, `ele` e `o de hoje`;
- pedidos compostos;
- unidades, cargas, horarios e datas relativas.

O objetivo nao e imitar um estereotipo de usuario. A variacao existe para
medir robustez do modelo.

## Rotulagem

As regras completas ficam em
`ai/data/taxonomy/annotation-guidelines.md`. Resumo:

- intencao representa o resultado imediato esperado;
- topico representa o assunto e pode ser multilabel;
- risco e independente da intencao e pode mudar a rota;
- pergunta nao autoriza alteracao;
- pedido incompleto preserva a intencao e solicita campos ausentes;
- baixa informacao sem contexto recebe esclarecimento;
- risco de maior gravidade tem prioridade;
- imagem nao analisada nunca pode ser descrita pelo modelo textual.

## Formato

Os arquivos-fonte ficam em `ai/data/source/`. Os registros gerados usam JSONL.
O contrato formal esta em `ai/data/schema/dataset-row.schema.json`.

Campos comuns incluem:

- `id`, `task`, `text`, `language` e `dataset_version`;
- `source_type` e `source_id`;
- `style` e `difficulty`;
- rotulo e rota da tarefa.

Casos de desafio tambem registram intencao principal e secundaria, topicos,
riscos, dependencia de contexto ou imagem, entidades ausentes, tipo de
ambiguidade e comportamento esperado.

## Divisao congelada

O gerador ordena exemplos por SHA-256 dentro de cada classe. Com oito exemplos,
seis vao para treino, um para validacao e um para teste. O conjunto de desafio
permanece separado e nao pode ser usado para treinamento ou ajuste de limiar.

`split_policy.v1.json` define a politica. `assignments.v1.json` registra a
divisao de cada ID e impede movimentacao silenciosa dentro da versao 1.2.0.
`manifest.json` guarda hashes SHA-256 das entradas e saidas. Qualquer inclusao,
remocao, reescrita ou realocacao exige uma nova versao revisada.

## Criterios automaticos de qualidade

- todas as intencoes e riscos possuem oito exemplos;
- cada classe possui exemplos sinteticos e padroes reais reescritos;
- procedencia, estilo e dificuldade sao obrigatorios quando aplicaveis;
- IDs, textos normalizados e classes nao podem duplicar;
- treino, validacao e teste nao compartilham o mesmo texto;
- quase-duplicatas entre divisoes sao bloqueadas por similaridade de tokens e
  sequencia;
- conjunto de desafio nao pode vazar para os splits comuns;
- topicos, riscos, intencoes e entidades precisam existir na taxonomia;
- todos os tipos de ambiguidade e comportamentos esperados precisam aparecer;
- resposta de seguranca exige risco real diferente de `none`;
- fontes reescritas precisam existir no catalogo de pesquisa.
- hashes das fontes, taxonomias, esquema, politica, registro, relatorio e
  arquivos gerados precisam corresponder ao manifesto;
- uma reconstrucao precisa reproduzir o mesmo manifesto e a mesma auditoria.

## Usos permitidos

- treinar e comparar classificadores do Evolv;
- estudar erros e confusoes entre classes;
- testar roteamento, esclarecimento e seguranca;
- demonstrar pipeline de NLP no portfolio.

## Usos proibidos

- diagnostico ou prescricao clinica;
- inferir identidade, genero, etnia ou condicao de uma pessoa;
- apresentar o conjunto como representativo de todo portugues brasileiro;
- usar o teste para escrever exemplos de treino depois de observar a resposta;
- coletar conversas futuras sem consentimento e processo de privacidade.

## Limitacoes

- conjunto pequeno e equilibrado artificialmente;
- validacao e teste possuem apenas um exemplo por classe e, portanto, ainda
  produzem estimativas instaveis;
- padroes reais foram reescritos e nao representam frequencia real de uso;
- ainda nao houve dupla anotacao independente nem medida de concordancia;
- entidades possuem taxonomia, mas spans de texto ficam para a fase de NLP;
- o Coach inicial e textual e apenas reconhece dependencia de imagem;
- a cobertura regional do portugues ainda e limitada;
- classes raras de risco precisam de revisao especializada antes de producao.
- deteccao de quase-duplicata e heuristica e nao substitui revisao semantica.

## Proxima etapa

A fase 7.01 esta concluida e a 7.02.1 criou o baseline sem alterar o conjunto
de teste 1.2.0. As proximas entregas tratam entidades, avaliacao detalhada e
confianca.

Novos exemplos devem nascer de erros revisados ou coleta consentida. O conjunto
de teste nunca deve ser copiado para o treino para melhorar uma metrica.

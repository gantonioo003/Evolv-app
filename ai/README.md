# Evolv AI

Esta pasta concentra o Coach local do Evolv. Ela fica separada de `backend/`
porque dados, avaliacao e modelos usam Python, enquanto a API principal e as
regras de negocio continuam no NestJS.

## Status

Rodada mais recente: dataset contextual `1.5.0`, baseline experimental `1.3.0`,
41 intencoes, 18 riscos, 89 entidades declaradas (50 com regras/catalogos) e
corpus `1.2.0` com 6.711 documentos. As 10.000 mensagens novas foram auditadas,
mas continuam fora do treino automatico por rotulos, direitos e privacidade
pendentes. Treinamento novo usa exemplos proprios; comentarios nao sao respostas gold.
O novo experimento recupera parte da queda do 1.2, mas nao supera o melhor 1.1
no teste historico. Nao ativa o Coach nem altera o Planner. 156 testes passaram.

Relatorio atual: `docs/21-coach-context-dataset-privacy-and-evaluation.md`.
As secoes abaixo preservam o historico das entregas e seus numeros originais.

A fase 7.01 e as quatro partes da 7.02 estao implementadas. O dataset `1.2.0`
permanece como historico; a expansao `1.3.0` possui 1.277 registros regulares
e o baseline `1.1.0` foi avaliado. O corpus TinyLM `1.0.0` esta preparado.
A pipeline operacional ainda usa baseline `1.0.0`: a ativacao do novo modelo
exige novos limites de confianca medidos somente em dados de desenvolvimento.

Estrutura atual:

```txt
ai/
  artifacts/        modelos, extratores, manifestos, metricas e model cards
  data/
    catalogs/        snapshots de termos do dominio usados na extracao
    entities/        conjunto de regressao da extracao de entidades
    evaluation/      protocolo congelado e holdout independente
    taxonomy/       intencoes, hierarquia, topicos, entidades, riscos e capacidades
    research/       catalogo de fontes e notas da pesquisa de cobertura
    source/         exemplos sinteticos, padroes reais reescritos e desafios
    schema/         contrato formal dos registros JSONL
    knowledge/      politica, cobertura e 67 trechos rastreaveis da base local
    metadata/       fontes, versao e criterios de qualidade
    splits/         politica, registro congelado, dados e auditoria
    releases/       dataset NLU 1.3.0, separado da versao historica
    lm_corpus/      textos, fontes e divisoes para o TinyLM
  scripts/          construcao, treinamento, inferencia e validacao
  src/evolv_nlp/    codigo reutilizavel de dados e modelos NLP
  tests/            testes automaticos de qualidade
  requirements.txt dependencias Python reproduziveis
```

## Comandos da fase 7.01

Execute na raiz do repositorio:

```powershell
python ai/scripts/validate_taxonomy.py
python ai/scripts/build_splits.py
python ai/scripts/audit_splits.py
python ai/scripts/validate_data.py
python ai/scripts/knowledge_report.py
python -m unittest discover -s ai/tests
```

`build_splits.py` gera as divisoes de forma deterministica. Cada rotulo possui
seis exemplos em treino, um em validacao e um em teste. O arquivo
`assignments.v1.json` congela a posicao dos 383 IDs. `audit_splits.py` procura
duplicatas exatas e quase-duplicatas entre divisao, enquanto `validate_data.py`
confere rotulos, fontes, hashes, manifesto, registro e isolamento do desafio.

O dataset 1.2 possui 240 exemplos de intencao, 104 exemplos de risco e 39
casos separados de desafio. Ele distingue exemplos sinteticos, padroes reais
reescritos e casos adversariais; nenhuma conversa privada foi copiada.

A taxonomia 1.0 possui 30 intencoes, 94 topicos, 79 entidades, 13 riscos e 44
capacidades. O numero de topicos e capacidades nao vira automaticamente o
numero de classes do classificador: eles sao eixos separados para manter o NLP
pequeno, mensuravel e capaz de representar mensagens com mais de um assunto.

A base de conhecimento 1.1 possui 67 trechos: 14 de treino, 23 de alimentacao,
11 de recuperacao e 19 de seguranca. As 27 fontes aprovadas incluem autoridades
publicas, diretrizes, consensos, posicionamentos cientificos e quatro contratos
internos de produto. Foruns e conteudo comercial nao sustentam respostas.
Cada trecho registra topicos, fontes, risco, modo de resposta, limite de uso e
prazo de revisao.

## Limite desta fase

Os exemplos atuais formam um dataset semente congelado para desenvolver e
testar a pipeline. Eles ainda nao representam todos os jeitos de falar
portugues nem sao suficientes para declarar qualidade de producao. A expansao
exige uma nova versao e sera guiada por erros revisados, sem mover exemplos de
teste nem usar conversas pessoais automaticamente. A proxima entrega da 7.02
e confianca, abstencao e uniao da pipeline.

## Baseline 7.02.1

O treinamento usa somente `train`. Dois perfis TF-IDF declarados sao
comparados em `validation`, e o melhor por macro F1 e salvo. `test` e
`challenge` permanecem fechados. Resultados atuais de validacao:

| Tarefa | Accuracy | Macro F1 |
| --- | ---: | ---: |
| Intencao, 30 classes | 0,400 | 0,333 |
| Risco, 13 classes | 0,615 | 0,538 |

As probabilidades nao estao calibradas e nao autorizam acoes. Os resultados
confirmam que o dataset semente permite aprender, mas ainda e pequeno.

```powershell
python ai/scripts/train_baseline.py
python ai/scripts/predict_baseline.py "troca o supino porque meu ombro doi"
python -m unittest ai/tests/test_baseline.py -v
```

Os artefatos `joblib` usam formato baseado em pickle. Somente arquivos gerados
pelo repositorio e com SHA-256 correspondente ao manifesto podem ser
carregados.

## Extracao de entidades 7.02.2

O extrator 1.0.0 combina catalogos locais, expressoes deterministicas e regras
de contexto. Ele encontra datas, exercicios, alimentos, substituicoes, carga,
series, repeticoes, duracao, objetivos, preferencias e limitacoes, preservando
o span original e retornando valores tipados.

O conjunto de regressao possui 40 mensagens e 71 entidades. Precision, recall
e F1 sao 1,000 nesse conjunto declarado. Ele foi usado durante o
desenvolvimento e, portanto, nao representa uma estimativa independente de
producao. Essa avaliacao pertence a 7.02.3.

```powershell
python ai/scripts/extract_entities.py "amanha troca supino por flexao e faz 4x10 com 30 kg" --reference-date 2026-10-07
python ai/scripts/evaluate_entities.py
python -m unittest ai/tests/test_entities.py -v
```

Contrato e limites: `docs/15-coach-entity-extraction.md`.

## Avaliacao e erros 7.02.3

O protocolo 1.0.0 abriu o teste congelado sem retreinar modelos nem alterar o
extrator. Os resultados sao honestos e ainda distantes de producao:

| Componente | Accuracy/exata | Macro F1 | Observacao |
| --- | ---: | ---: | --- |
| Intencao | 0,233 | 0,161 | 30 exemplos, um por classe |
| Risco | 0,538 | 0,449 | 13 exemplos, um por classe |
| Entidades | 0,650 | 0,696 | 40 mensagens novas; micro F1 0,841 |

No teste pequeno de risco, nenhum exemplo perigoso foi classificado como
`none`, mas varios tipos de risco foram confundidos entre si. O conjunto
adversarial obteve 0,513 de accuracy de intencao e confirma que ambiguidades e
multiplos pedidos ainda exigem a 7.02.4 e dados futuros.

```powershell
python ai/scripts/evaluate_nlp.py
python -m unittest discover -s ai/tests -v
```

Relatorio e limites: `docs/16-coach-nlp-evaluation.md`.

## Confianca e pipeline final 7.02.4

A pipeline 1.0.0 une intencao, risco, entidades e topicos. Limiares foram
escolhidos somente em `validation`: a porta conservadora de intencao aceitou
`0/30` mensagens, enquanto a de risco aceitou `6/13`, todas corretas entre as
aceitas. Isso nao torna o modelo pronto; faz o sistema pedir esclarecimento em
vez de executar uma suposicao.

Toda mudanca e apenas uma proposta com confirmacao obrigatoria e
`writes_allowed: false`. Risco aceito substitui a rota normal, e risco nao nulo
incerto tambem impede uma acao automatica.

```powershell
python ai/scripts/evaluate_pipeline.py
python ai/scripts/analyze_message.py "amanha troca supino por flexao" --reference-date 2026-10-08
python -m unittest discover -s ai/tests -v
```

Contrato e limites: `docs/17-coach-nlp-pipeline.md`.

## Expansao NLU e preparacao do TinyLM

O dataset `1.3.0` tem 1.019 exemplos em treino, 129 em validacao e 129 em
teste, mais 39 desafios historicos e dez perguntas humanas publicas separadas.
O baseline `1.1.0` escolheu SVC linear para intencao e regressao logistica para
risco. O teste final usa a maior probabilidade, como `baseline.classify`:

| Tarefa | Macro F1 no teste |
| --- | ---: |
| Intencao | 0,713 |
| Risco | 0,852 |

Nas dez perguntas humanas externas, ambos tiveram accuracy de 0,300. O teste
controlado e pequeno e majoritariamente sintetico; esta diferenca impede uma
alegacao de qualidade em linguagem aberta. Houve uma correcao de pontuacao
apos a primeira execucao: os modelos e os dados conservaram os mesmos hashes.

O corpus `1.0.0` tem 6.381 trechos, 1.656.093 unidades separadas por espaco
e cerca de 2,24 milhoes de tokens de subpalavras estimados. Inclui Wikipedia,
OASST1 humano e textos Evolv, com fontes, licencas e divisao por artigo/conversa.
Os textos e as conversas do holdout humano NLU estao reservados fora dele.

```powershell
python ai/scripts/prepare_lm_corpus.py --offline
python -m unittest discover -s ai/tests -v
```

`--offline` requer o cache local ja baixado; sem ele, execute o comando sem
essa opcao. Treinamento e avaliacao do baseline 1.1 estao encerrados: os
comandos `train_baseline_1_1.py` e `evaluate_baseline_1_1.py` recusam sobrescrever
a versao avaliada. Use uma nova versao para novos experimentos.

Detalhes: `docs/19-coach-dataset-1-3-and-tinylm-corpus.md`.

## Importacao real PT-BR e experimento 1.2

O dataset `1.4.0` adiciona uma fila local com 10.000 mensagens originais em
portugues: 8.912 sao apenas titulos de posts, e 9.119 vieram de Hipertrofia.org.
Nao sao 10.000 exemplos rotulados e aprovados. Textos externos, revisoes locais
e pesos treinados neles ficam fora do Git enquanto os direitos de uso nao
estiverem confirmados. Validacao e teste externos continuam reservados.

A extensao declara 36 intencoes, 16 riscos e 85 tipos de entidades. O extrator
experimental implementa 39 tipos, nao os 85. Ele distingue carga, peso corporal
e peso ambiguo; acrescenta distancia, ritmo, velocidade, frequencia cardiaca e
medidas de exames, sem fazer diagnostico. As regras de risco preservam negacao,
contexto e multiplos sinais; ausencia de regra nao significa seguranca.

O baseline `1.2.0` e opt-in e experimental. Na pequena amostra real revisada
pelo assistente, a accuracy subiu de 0,192 para 0,767 em intencao e de 0,525
para 0,825 em risco. Esses exemplos foram usados no desenvolvimento, nao sao
teste independente nem rotulos humanos. A validacao historica piorou; por isso
nenhum modelo ou pipeline padrao foi substituido.

```powershell
python ai/scripts/analyze_message_1_2.py "troca supino por flexao" --reference-date 2026-10-10
python -m unittest discover -s ai/tests
```

Os artefatos locais existentes sao necessarios para o primeiro comando. O
treinador recusa sobrescrever a versao finalizada. Para uma nova coleta,
rotulagem, configuracao ou modelo, criar nova versao.

O corpus `1.1.0` tem 6.555 documentos, incluindo 174 novos exemplos proprios,
dos quais 66 pares educativos baseados no conhecimento existente. Nao inclui
as 10.000 mensagens externas nem respostas de forums. TinyLM e tokenizer ainda
nao foram treinados. A proxima rodada usara a nova coleta com mais contexto e
diversidade de fontes, mais as entrevistas consentidas.

Detalhes e mapa dos arquivos: `docs/20-coach-ptbr-dataset-and-nlp-expansion.md`.

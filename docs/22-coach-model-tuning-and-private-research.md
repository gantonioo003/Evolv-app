# Tuning De Intencao E Risco: Pesquisa Privada

Entrega de 2026-10-10. Complementa o registro da etapa anterior em
`21-coach-context-dataset-privacy-and-evaluation.md`.

## Resultado Direto

Foram comparadas **508 configuracoes**: 268 classicas e 240 semanticas,
somando as tarefas de intencao e risco. Os vencedores foram escolhidos
pela validacao antes de avaliar seus testes. Os modelos padrao do app
nao foram substituidos e nenhuma acao foi executada no Planner.

O experimento semantico 1.5.0 superou o melhor baseline antigo no teste
historico, mas a melhora nao foi universal. Intencao ainda tem um gap
grande entre treino e validacao e regrediu em F1 no pequeno teste novo.
90% de macro F1 nas duas tarefas continua sendo uma meta, nao uma garantia.

## Os 10.000 Textos E Suas Respostas

A coleta original foi preservada. A copia privada organizada fica em
`ai/data/releases/1.6.0/private/conversations/`:

| Particao | Perguntas/mensagens | Comentarios associados | Elegiveis para pesquisa privada |
| --- | ---: | ---: | ---: |
| Treino | 7.859 | 5.652 | 3.918 |
| Validacao | 950 | 722 | 503 |
| Teste | 1.017 | 772 | 528 |
| Quarentena | 174 | 182 | 0 |
| Total | 10.000 | 7.328 | 4.949 |

Cada comentario continua dentro do registro da sua pergunta, na mesma
particao. Threads nao aparecem em particoes diferentes. A quarentena
mantem os casos de sobreposicao/possivel vazamento fora do treinamento.
Os testes historicos do projeto nao foram reassociados ao treino.

**Organizar os 10.000 textos nao significa treinar cegamente com todos.**
Os rotulos recebidos sao candidatos automaticos, nao anotacoes humanas
independentes. Sinais de identificadores, menores, informacao sensivel,
terceiros e dependencia de imagem excluem exemplos do ajuste privado.
As heuristicas podem falhar: isso nao comprova anonimato nem direitos de uso.

Dos exemplos elegiveis do train, o consenso entre regras/candidatos e o
baseline historico selecionou **481 rotulos fracos de intencao** e
**185 de risco**. Esses rotulos sao correlacionados com o professor e
nao substituem revisao humana. Nao se usaram perguntas externas de
validation/test para ajustar modelos ou escolher hiperparametros.

Os 7.328 comentarios estao preservados para revisao, mas **nao sao
respostas corretas aprovadas**, features dos classificadores ou alvos
de treino do LM. Uma resposta de forum pode estar errada ou insegura.

## Pedidos Ao Planner

Os dados proprios antigos foram mantidos. Por exemplo, o train existente
ja tinha 24 registros para cada uma destas classes: `move_workout_day`,
`replace_exercise`, `replace_meal_item` e `set_day_activity`.

Acrescentados **160 exemplos proprios sinteticos, exclusivamente no train**,
em 20 classes com oito exemplos cada. Incluem mover treino, trocar
exercicio/alimento, ajustar volume/intensidade, mudar divisao/estrutura,
registrar carga/refeicao, confirmar, recusar, desfazer e esclarecer pedidos.
Tambem incluem duvidas educativas para contrastar perguntar com mandar mudar.

Exemplos: "passa o treino de hoje para amanha" e "troca o supino por flexao".
Ha abreviacoes, dias diferentes, preferencias e mudancas pontuais.
Esses textos sao sinteticos; nao foram apresentados como entrevistas reais.
As duplicatas normalizadas com conjuntos reservados sao excluidas.

Arquivo: `ai/data/source/planner_actions_augmentation.v1.json`.
Entrou na comparacao 1.5.0; a busca 1.4.0 ja estava em andamento quando
esse complemento foi solicitado. Nao se alterou um experimento finalizado.

## Arquiteturas E Regularizacao

Busca classica 1.4.0: TF-IDF de palavras/caracteres, SVM linear, regressao
logistica, SGD, ComplementNB, classificacao hierarquica e duas MLPs com
reducao SVD. Foram comparados diferentes n-grams e pesos de features.

Busca semantica 1.5.0: encoder pre-treinado congelado
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, executado
localmente em CPU com ONNX quantizado. Produz vetores de 384 dimensoes.
Textos longos usam janelas; padding nao entra na media dos embeddings.

Comparamos embeddings sozinhos, controle lexical com os mesmos dados e
hibridos TF-IDF + embeddings com pesos 0,5/1/2. **Nao treinamos um LM nem
fizemos fine-tuning do encoder**: treinamos os classificadores sobre suas features.
Baixar um encoder multilingue nao torna o app automaticamente multilingue.

L2 ja esta nos classificadores lineares comparados. Na SVM, C foi
0,25/1/4/16; na regressao logistica, 0,5/2/8. Menor C significa
regularizacao mais forte. SGD tambem tem penalidade L2; as MLPs usam
regularizacao de pesos. Nao escolhemos C olhando o teste.

O complemento de 160 exemplos e data augmentation. Nao podemos atribuir
todo o ganho a ele: representacao, classificadores e dados mudaram juntos.
Bagging nao foi executado nesta entrega. Pode reduzir variancia de modelos
instaveis; nao e garantia de ganho nos classificadores lineares usados aqui.

Selecao declarada: 65% do macro F1 na validacao historica, com categorias
parentes, e 35% na validacao nova, com categorias nativas. Empates seguem
a ordem declarada. Cada vencedor e salvo antes de abrir seu teste final.

## Vencedores 1.5.0

Ambos: TF-IDF + embeddings com peso 1 + regressao logistica L2, C=2.

| Tarefa | Classes nativas | Train proprio | Train externo fraco usado | Peso externo |
| --- | ---: | ---: | ---: | ---: |
| Intencao | 41 | 1.110, incluindo 160 novos | 481 | 0,1 |
| Risco | 18 | 387 | 0 | 0 |

Os 185 candidatos de risco foram testados em configuracoes alternativas,
mas a validacao escolheu o modelo **sem eles**. Nao afirmar que todos
os dados externos melhoraram risco ou que todas as 10.000 mensagens
entraram no fit vencedor.

## Metricas Comparaveis

Mesmo teste historico: 90 exemplos de intencao, 39 de risco. Subtipos
novos sao mapeados a categorias parentes para comparar as mesmas classes.

| Tarefa | Modelo | Accuracy | Precisao macro | Recall macro | Macro F1 |
| --- | --- | ---: | ---: | ---: | ---: |
| Intencao | Melhor antigo 1.1 | 0,7222 | 0,7554 | 0,7222 | 0,7129 |
| Intencao | Etapa anterior 1.3 | 0,6222 | 0,7422 | 0,6222 | 0,6286 |
| Intencao | Busca classica 1.4 | 0,6556 | - | - | 0,6332 |
| Intencao | Semantico 1.5 | 0,7667 | 0,8398 | 0,7667 | 0,7689 |
| Risco | Melhor antigo 1.1 | 0,8462 | 0,8897 | 0,8462 | 0,8524 |
| Risco | Etapa anterior 1.3 | 0,7949 | 0,8513 | 0,7949 | 0,8007 |
| Risco | Busca classica 1.4 | 0,6923 | - | - | 0,6853 |
| Risco | Semantico 1.5 | 0,8974 | 0,9244 | 0,8974 | 0,8980 |

A busca classica regrediu em risco, embora tenha ido bem na validacao.
Os resultados completos, incluindo precision/recall, matrizes e classes,
estao nos respectivos `metrics.json`; nenhuma regressao foi apagada.

Teste proprio pequeno de assuntos novos, com categorias nativas:

| Tarefa | Exemplos | Macro F1 anterior 1.3 | Macro F1 novo 1.5 | Accuracy nova |
| --- | ---: | ---: | ---: | ---: |
| Intencao | 40 | 0,7102 | 0,6848 | 0,7750 |
| Risco | 16 | 0,6111 | 0,8708 | 0,8750 |

No teste novo, accuracy de intencao melhora de 0,725 para 0,775,
mas macro F1 cai. O conjunto cobre apenas parte das categorias; o calculo
padrao inclui categorias previstas, inclusive algumas sem suporte real.
Nao comparar macro F1 nativo deste conjunto com o F1 das 30 categorias
parentes do historico como se fossem a mesma avaliacao.

**Esses holdouts sao pequenos e ja foram observados em fases anteriores.**
Nao sao uma estimativa nova e independente para usuarios reais. Com 39
exemplos de risco, uma unica resposta muda accuracy em cerca de 2,6 pontos.
89,8% de macro F1 nao comprova seguranca clinica nem lancamento pronto.

## Gap Treino-Validacao

Diagnostico separado, sem refit e sem abrir teste:

| Modelo/tarefa | Train proprio: F1 parentes | Validacao historica: F1 parentes | Gap |
| --- | ---: | ---: | ---: |
| 1.4 intencao | 1,0000 | 0,6667 | 0,3333 |
| 1.5 intencao | 0,9993 | 0,7487 | 0,2506 |
| 1.4 risco | 1,0000 | 0,9423 | 0,0577 |
| 1.5 risco | 1,0000 | 0,8868 | 0,1132 |

O gap de intencao diminuiu, mas continua grande e e compativel com
overfitting. Nao prova que variancia seja a unica causa: distribuicao,
ambiguidade e qualidade dos rotulos tambem importam. Validacao ja usada
para selecao nao e uma avaliacao independente.

Para buscar 90% sem maquiar resultados: revisar rotulos e fronteiras entre
intencoes, aumentar variedade real, comparar adaptacao de um encoder e
reservar perguntas humanas novas como holdout antes de usa-las no desenvolvimento.
Pedidos que dependem de contexto precisam ser avaliados com contexto;
uma frase isolada como "sim" nao fornece toda a intencao do usuario.

## Dor, Entidades, Corpus E Privacidade

Mantidas as mudancas da etapa anterior: 41 intencoes, 18 riscos, 89 tipos
de entidades declarados, 50 com regras/catalogos ativos. Este tuning nao
alterou o extrator nem as regras de dor. No holdout historico anotado,
entidades continuam com precision 0,908, recall 0,831 e F1 0,868.

Dor continua como educacao geral, incerteza e encaminhamento proporcional,
sem diagnostico, escolha de exame ou prescricao de tratamento/reabilitacao.
O classificador de risco ainda e single-label; regras separadas podem
retornar multiplos sinais. Uma classe `none` nao comprova ausencia de risco.

Corpus permanece na versao 1.2.0, com 6.711 documentos. Esta entrega nao
injeta perguntas externas/comentarios no TinyLM. Sua revisao de direitos,
privacidade e respostas precede um possivel uso para geracao.

A autorizacao do usuario permitiu o experimento privado solicitado; nao
foi tratada como autorizacao dos autores terceiros ou liberacao comercial.
O gate `training_permission` e o dataset original permaneceram intactos.
Dados/weights externos e cache do encoder estao ignorados no Git.
**Gitignore nao impede sincronizacao do OneDrive**, onde o projeto reside.
Os textos nao foram enviados a uma API hospedada de inferencia.

O modelo aberto informa Apache-2.0 em seu [model card oficial](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2).
A origem da coleta informa licenca `other` em seu [dataset card](https://huggingface.co/datasets/yikeee/reddit-subreddits25);
conteudo publico nao equivale a liberacao irrestrita, conforme a
[politica de conteudo publico do Reddit](https://support.reddithelp.com/hc/en-us/articles/26410290525844-Public-Content-Policy).
Isso e registro de restricoes, nao parecer juridico nem certificacao LGPD.

## Arquivos E Comandos

```text
ai/data/releases/1.6.0/manifest.json       particoes, contagens, restricoes
ai/data/releases/1.6.0/private/            conversas/respostas e rotulos fracos
ai/data/source/planner_actions_augmentation.v1.json  160 pedidos sinteticos
ai/src/evolv_nlp/research_data.py          organiza coleta privada e rotulos fracos
ai/src/evolv_nlp/research_models.py        wrappers e classificacao hierarquica
ai/src/evolv_nlp/tuning_v14.py             busca classica
ai/src/evolv_nlp/semantic_encoder.py       encoder local, janelas e pooling
ai/src/evolv_nlp/tuning_semantic.py        busca semantica e controle lexical
ai/scripts/predict_research.py            usa modelos sem executar acoes
ai/scripts/diagnose_research_fit.py        compara train/validation sem refit
ai/artifacts/baseline/1.4.0/               relatorios classicos e pesos privados
ai/artifacts/baseline/1.5.0/               relatorios semanticos e pesos privados
ai/artifacts/experiments/research_fit_diagnostics.v1.json  gaps registrados
ai/requirements.research.txt              dependencias opcionais do encoder
```

Na raiz do projeto, com o ambiente registrado nos manifestos:

```powershell
python -m pip install -r ai/requirements.research.txt
python ai/scripts/predict_research.py "passa o treino de hoje para amanha" --version 1.5.0
python -m unittest discover -s ai/tests
```

**175 testes passaram**, sem skips, incluindo isolamento de particoes,
preservacao de respostas, augmentation train-only, hashes, gate privado,
pooling e contrato de inferencia. Checks manuais reconheceram mover treino,
trocar exercicio, duvida sobre dor e habitos de sono; nao provam desempenho geral.

Probabilidades ainda nao estao calibradas para a pipeline. O contrato de
inferencia novo usa `predict()` nativo, nao o antigo fallback por probabilidades.
Promover os pesos exige integrar/calibrar a abstencao e revisar as restricoes;
nao basta apontar a API para o novo joblib. Nenhum commit ou publicacao foi feito.

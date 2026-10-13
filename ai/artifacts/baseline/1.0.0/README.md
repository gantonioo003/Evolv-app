# Evolv NLP baseline 1.0.0

## Objetivo

Primeira referencia classica para classificar as 30 intencoes e os 13 rotulos
de risco do Coach. O modelo nao gera respostas nem executa acoes.

## Arquitetura

```text
texto
-> TF-IDF de palavras e fragmentos de caracteres
-> regressao logistica multiclasse com regularizacao L2
-> rotulo e probabilidades
```

Dois perfis declarados foram comparados na validacao: palavras e
palavras+caracteres. O segundo venceu nas duas tarefas. O teste e o conjunto de
desafio nao foram carregados nem avaliados.

## Resultados de validacao

| Tarefa | Linhas | Accuracy | Macro F1 |
| --- | ---: | ---: | ---: |
| Intencao | 30 | 0,400 | 0,333 |
| Risco | 13 | 0,615 | 0,538 |

Esses resultados sao apenas a primeira referencia. Cada classe possui um unico
exemplo de validacao, portanto pequenas mudancas alteram bastante as metricas.
As probabilidades ainda nao estao calibradas e nao devem decidir acoes.

## Arquivos

- `intent_classifier.joblib`: pipeline de intencao;
- `risk_classifier.joblib`: pipeline de risco;
- `manifest.json`: hashes, dependencias e uso dos dados;
- `metrics.json`: validacao e cross-validation;
- `top_features.json`: atributos mais associados a cada classe.

## Limitacoes

- somente seis exemplos de treino por classe;
- risco retorna um rotulo principal, ainda nao multilabel;
- palavras parecidas nao garantem significado equivalente;
- nao extrai entidades;
- nao possui limiar operacional de confianca;
- nao foi avaliado no teste congelado nem nos desafios;
- `joblib` nunca deve carregar arquivo externo ou com hash divergente.

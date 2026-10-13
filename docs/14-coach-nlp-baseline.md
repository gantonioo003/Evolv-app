# Coach 7.02.1 - Baseline de intencao e risco

## Status

Concluido em 2026-10-07. Esta entrega cria a primeira referencia mensuravel de
Machine Learning para o Coach. Ela nao gera respostas, nao extrai entidades e
nao executa mudancas no Planner.

## Objetivo

Responder duas perguntas em paralelo:

1. qual das 30 intencoes melhor representa a mensagem;
2. qual dos 13 rotulos de risco merece a rota principal.

O baseline estabelece um resultado minimo que Transformers futuros precisam
superar. Um modelo simples tambem revela problemas de dados com custo baixo.

## Arquitetura

```text
mensagem em pt-BR
-> normalizacao Unicode e letras minusculas
-> TF-IDF de palavras (unigramas e bigramas)
-> TF-IDF de caracteres dentro de palavras (3 a 5 caracteres)
-> regressao logistica multiclasse com regularizacao L2
-> rotulo principal e tres probabilidades mais altas
```

Palavras preservam expressoes como `trocar supino`. Fragmentos de caracteres
ajudam com flexao/flexoes, abreviacoes e erros leves. A regressao logistica e um
classificador linear, apesar do nome `regressao`.

## Organizacao

```text
ai/
  src/evolv_nlp/
    dataset.py       carrega e valida os JSONL congelados
    baseline.py      cria o modelo, classifica e verifica artefatos
    training.py      seleciona, treina, mede e versiona
  scripts/
    train_baseline.py
    predict_baseline.py
  artifacts/baseline/1.0.0/
    intent_classifier.joblib
    risk_classifier.joblib
    manifest.json
    metrics.json
    top_features.json
    README.md
  tests/test_baseline.py
  requirements.txt
```

## Uso correto dos dados

- `train`: aprende vocabulario, pesos e cross-validation de tres folds;
- `validation`: compara dois perfis declarados de TF-IDF;
- `test`: nao foi carregado nem avaliado;
- `challenge`: nao foi carregado nem avaliado.

A selecao usa primeiro macro F1 e depois accuracy. Nas duas tarefas, o perfil
com palavras e caracteres venceu o perfil somente com palavras. Nenhum
hiperparametro foi escolhido olhando o teste.

## Resultados iniciais

| Tarefa | Treino | Validacao | Classes | Accuracy | Macro F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Intencao | 180 | 30 | 30 | 0,400 | 0,333 |
| Risco | 78 | 13 | 13 | 0,615 | 0,538 |

Na cross-validation feita somente no treino, intencao obteve macro F1 medio de
0,260 e risco 0,394. O resultado de intencao e baixo, mas util: seis exemplos
por classe ainda nao representam variacao linguistica suficiente.

Cada classe possui apenas um exemplo de validacao. Portanto, uma unica
previsao muda muito a metrica. A analise por classe e a primeira abertura do
teste foram realizadas na 7.02.3 e registradas em
`docs/16-coach-nlp-evaluation.md`.

## Confianca

`predict_proba` retorna probabilidades, mas elas ainda nao estao calibradas.
Uma previsao com maior valor relativo nao significa que o sistema esteja
seguro para agir. Limiar, abstencao e pedido de esclarecimento pertencem a
7.02.4.

## Reproducibilidade e seguranca

O manifesto registra dataset, semente, arquivos-fonte, hashes, algoritmo,
versoes de Python, NumPy, SciPy, joblib e scikit-learn. Os modelos sao
persistidos com `joblib`, formato baseado em pickle. O carregador verifica o
SHA-256 antes de desserializar; artefatos externos nunca devem ser carregados.

## Comandos

```powershell
python -m pip install -r ai/requirements.txt
python ai/scripts/train_baseline.py
python ai/scripts/predict_baseline.py "troca o supino porque meu ombro doi"
python -m unittest ai/tests/test_baseline.py -v
```

## Continuidade

A 7.02.2 concluiu a extracao de datas, exercicios, alimentos, cargas,
objetivos e limitacoes, documentada em
`docs/15-coach-entity-extraction.md`. A 7.02.3 abriu o teste congelado e
registrou matrizes, erros e limitacoes em `docs/16-coach-nlp-evaluation.md`.
A 7.02.4 unira resultados e confianca em uma saida estruturada.

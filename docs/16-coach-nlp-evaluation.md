# Coach 7.02.3 - Avaliacao e erros

## Objetivo

A fase 7.02.3 mede, pela primeira vez em dados congelados, os classificadores
de intencao e risco da 7.02.1 e o extrator de entidades da 7.02.2. Nenhum
modelo foi retreinado e nenhuma regra do extrator foi alterada nesta fase.

## Protocolo antes do resultado

`ai/data/evaluation/protocol.v1.json` registra hashes, tamanhos, metricas e
limites de interpretacao. O script interrompe se qualquer arquivo congelado
for modificado.

- intencao: 30 mensagens de teste, uma por classe;
- risco: 13 mensagens de teste, uma por classe;
- entidades: 40 mensagens novas, separadas da regressao de desenvolvimento;
- desafio: 39 mensagens ambiguas, multintencao ou adversariais.

Depois da primeira execucao, os erros sao documentados, nao usados para
alterar esta mesma versao. Uma melhoria exige outra versao e um novo teste.

## Metricas

Classificacao registra accuracy, precision, recall e F1 macro, micro e
ponderado, resultado por classe, top-3, erros e matriz de confusao. Macro F1
da o mesmo peso para cada classe, importante porque o Coach possui muitas
intencoes e riscos.

Risco tambem registra falsos seguros, quando havia risco mas o classificador
previu `none`, e falsos alarmes, quando uma mensagem segura recebeu risco.

Entidades registra precision, recall e F1 micro e macro, desempenho por tipo,
mensagens completamente corretas, falsos positivos em mensagens negativas e
listas de entidades ausentes ou inesperadas. O contrato atual compara tipo e
valor normalizado; spans nao entram na metrica 1.0.0.

## Resultados 1.0.0

| Componente | Accuracy/exata | Precision macro | Recall macro | Macro F1 |
| --- | ---: | ---: | ---: | ---: |
| Intencao | 0,233 | 0,128 | 0,233 | 0,161 |
| Risco | 0,538 | 0,410 | 0,538 | 0,449 |
| Entidades | 0,650 | 0,730 | 0,686 | 0,696 |

Entidades tambem obteve micro F1 de 0,841. No teste de risco, os doze exemplos
perigosos foram reconhecidos como algum tipo de risco: recall de deteccao
1,000 e zero falsos seguros. Isso nao significa que o tipo correto sempre foi
escolhido; seis dos treze rotulos de risco foram confundidos.

Intencao acertou 7 de 30 exemplos e chegou a 0,567 no top-3. O resultado mostra
que o classificador aprendeu sinais uteis, mas seis exemplos de treino por
classe ainda sao insuficientes para separar 30 intencoes parecidas.

No holdout de entidades, 26 das 40 mensagens ficaram inteiramente corretas.
Os principais pontos fracos foram preferencias, frequencia semanal, RPE/RIR,
sono, substituicao alimentar e linguagem informal. Esses erros ficaram
registrados; o extrator nao foi ajustado depois da abertura do holdout.

No desafio adversarial, intencao obteve accuracy 0,513. O risco encontrou algum
perigo em todos os dez casos perigosos, mas produziu 23 falsos alarmes entre
29 mensagens sem risco. O resultado reforca a necessidade de abstencao e pedido
de esclarecimento na 7.02.4.

## Artefatos

```text
ai/artifacts/evaluation/1.0.0/
  metrics.json
  error_analysis.md
  intent_confusion_matrix.csv
  risk_confusion_matrix.csv
  intent_predictions.jsonl
  risk_predictions.jsonl
  entity_predictions.jsonl
  challenge_predictions.jsonl
  manifest.json
```

`metrics.json` e a fonte estruturada. Os CSVs permitem inspecionar as matrizes.
Os JSONL preservam cada previsao para auditoria. `error_analysis.md` resume as
confusoes e limitacoes. O manifesto prova quais dados, modelos e codigos
produziram os resultados.

## Limites

- um exemplo por classe gera uma estimativa com alta incerteza;
- probabilidades ainda nao estao calibradas;
- os classificadores retornam apenas um rotulo por tarefa;
- frases reais podem conter varias intencoes e riscos;
- entidades fora do catalogo, erros de digitacao e referencias ao contexto
  podem falhar;
- nenhum resultado autoriza escrita automatica no Planner.

## Comandos

```powershell
python ai/scripts/evaluate_nlp.py
python -m unittest discover -s ai/tests -v
```

A fase 7.02.4 implementou confianca, abstencao, uniao da intencao com risco,
entidades e topicos e o contrato estruturado da pipeline. Os limites foram
escolhidos somente em validacao; este teste congelado nao foi reutilizado para
ajustar os limiares. Detalhes em `docs/17-coach-nlp-pipeline.md`.

# Pipeline NLP 7.02.4

`confidence_policy.v1.json` define os limites de confianca, abstencao e
seguranca. Os limites foram escolhidos somente com `validation`; `test` e
`challenge` nao foram usados para selecionar valores.

`topic_rules.v1.json` acrescenta topicos deterministas a partir da intencao e
dos tipos de entidade. A deteccao lexical continua usando
`data/taxonomy/topics.v1.json`.

O baseline 1.0.0 nao possui confianca suficiente para executar mudancas. Toda
acao do Planner permanece como proposta, exige confirmacao e possui
`writes_allowed: false`.

# Avaliacao congelada 7.02.3

`protocol.v1.json` define as metricas, os limites e os hashes dos dados antes
da execucao. `entity_holdout.v1.jsonl` possui frases novas para avaliar o
extrator 1.0.0 sem reutilizar o conjunto de regressao da 7.02.2.

Os arquivos de `test/` e `challenge/` continuam em `data/splits/` e seus hashes
sao conferidos contra o manifesto congelado da versao 1.2.0. Depois de observar
os resultados, esta versao nao deve ser usada para ajustar modelos ou regras.

Qualquer melhoria exige novos dados de desenvolvimento e outro teste congelado.

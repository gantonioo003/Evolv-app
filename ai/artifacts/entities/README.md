# Entity extraction artifacts

Cada subpasta representa uma versao reproduzivel do extrator hibrido. Diferente
do baseline de intencao e risco, esta fase nao gera pesos treinados: os
artefatos registram catalogo, conjunto de regressao, metricas e hashes do
codigo que produziu o resultado.

Nunca interprete a nota do conjunto de regressao como estimativa de qualidade
em producao. A avaliacao independente e os casos adversariais pertencem a
fase 7.02.3.

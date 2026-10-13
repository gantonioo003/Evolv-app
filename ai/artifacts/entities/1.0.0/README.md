# Entity extractor 1.0.0

Primeira versao do extrator hibrido da fase 7.02.2.

Componentes:

- catalogos versionados de exercicios, alimentos e contexto;
- regras deterministicas para datas, carga, series, repeticoes e duracao;
- regras de contexto para substituicoes, preferencias e limitacoes;
- spans preservados no texto original;
- resolucao temporal baseada em uma data de referencia explicita.

`metrics.json` mede 40 mensagens de regressao criadas durante o
desenvolvimento. O resultado perfeito nesse conjunto indica que os casos
declarados continuam funcionando, nao que toda mensagem real sera entendida.
O `manifest.json` registra hashes, metodo e limites de seguranca.

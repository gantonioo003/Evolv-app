# Revisao por IA e fechamento do NLP

## Escopo

A planilha `Evolv_2180_Revisados_IA.xlsx` foi incorporada como uma revisao
experimental, sem exigir outra rodada de anotacao humana para o trabalho de
aprendizado. Os rotulos continuam identificados como referencias de IA.

- Dataset derivado: `ai/data/releases/1.8.0/`.
- Modelos classicos e selecao combinada: `ai/artifacts/baseline/1.8.0/`.
- Ajuste do encoder na GPU: `ai/artifacts/baseline/1.8.1/`.
- Resultado medido: `ai/artifacts/review/2026-10-31/RESULTS.md`.
- Metricas por classe: `ai/artifacts/review/2026-10-31/metrics_per_class.csv`.

Foram cruzadas todas as 2.180 linhas com os IDs de origem por texto completo e
contexto, sem correspondencia semantica aproximada. A numeracao e a ordem da
planilha nao sao usadas como IDs. Nenhum caso foi ligado a dois registros.

As alteracoes atingem 773 mensagens: 317 intencoes e 564 conjuntos de riscos.
Existem sobreposicoes entre esses dois numeros. As 263 mensagens marcadas
com duvida pela IA permanecem identificadas, sendo 164 no treino e 99 na
validacao. Foram comparados pesos de treino 1,0 e 0,5 para essas duvidas.

As 60 intencoes, os 21 riscos e o extrator de entidades foram preservados.
Nao foram inventados spans de entidades nem novas respostas corretas a partir
das explicacoes da planilha.

## Isolamento e comparacao

As particoes permanecem com 9.261 registros de treino, 913 de validacao,
955 de teste historico, 255 de pesquisa reservada e 795 de desafio/quarentena.
O teste, a pesquisa e a quarentena sao copias byte a byte da versao 1.7.0.
Nao ha transferencia de grupos entre particoes nem ajuste de rotulos do teste.

As explicacoes da IA, candidatos de rotulo, previsoes anteriores e estados de
revisao nao entram nas caracteristicas do texto. Uma experiencia adicional
retira avisos artificiais de coleta de imagens e marcadores de estados
sinteticos dos canais lexicais (TF-IDF), sem apagar o contexto real de
conversas ou reescrever os registros armazenados. Os embeddings congelados
continuam usando a entrada original para essa comparacao controlada.

Os modelos anteriores sao comparados nas MESMAS referencias dos novos.
Isso e especialmente importante porque as referencias da validacao mudaram.
Comparar um F1 antigo com rotulos antigos contra um F1 novo com rotulos novos
nao isolaria o efeito do modelo.

A selecao usa a validacao corrigida. Os dois componentes finais e seus
limiares sao congelados antes de avaliar o teste nesta rodada. O teste ja foi
observado em rodadas anteriores: nao e um teste novo independente. A
validacao corrigida tambem pode refletir vies da revisao por IA, pois a fila
foi formada a partir das discordancias do modelo anterior.

## Experiencias

O comparativo inclui TF-IDF, BoW, SVM linear e RBF, regressao logistica,
Naive Bayes, MLP, reducao SVD/LSA, classificacao hierarquica, KNN e soft voting.
As variantes de preprocessamento e os modelos sao ajustados somente no treino.

O K-means e um agrupador nao supervisionado. Nesta rodada foram ajustados
30, 60 e 120 centros aos embeddings MiniLM do treino. Foram testadas duas
aplicacoes: usar a proximidade dos centros como caracteristica adicional e
atribuir frequencias de rotulos aos grupos usando somente o treino.
Nao houve correcao automatica de rotulos a partir dos grupos.

O ajuste neural usa o MiniLM pre-treinado, com duas cabecas supervisionadas:
intencao e riscos multirrotulo. Compara ajuste de 12 e 4 camadas, contexto de
384 tokens, AdamW, dropout, weight decay, suavizacao de rotulos e pesos para
classes e duvidas. Os checkpoints sao escolhidos pela validacao.
Esse encoder nao e o TinyLM causal treinado do zero.

Os numeros finais, incluindo ganhos e regressoes, estao no relatorio medido.
Uma arquitetura mais complexa nao e promovida automaticamente.

## Inferencia e protecoes

```powershell
python ai/scripts/analyze_message_corrected.py "Posso mover meu treino para quinta?"
```

Use o runtime registrado na selecao: Python 3.12.14 e as dependencias de
`ai/requirements.neural.txt`. Os scripts anteriores e seus runtimes ficam
preservados. A pipeline nova e opt-in e nao altera a integracao operacional
do aplicativo automaticamente.

A margem de confianca e ajustada na validacao para um alvo empirico de 90%
de acerto entre mensagens aceitas, com suporte minimo. Isso nao e garantia
de 90% no mundo real nem probabilidade calibrada. Intencoes com menos de cinco
exemplos de validacao pedem esclarecimento mesmo com margem elevada.

Riscos detectados pelo modelo se somam as regras conservadoras. `none` nao
significa ausencia comprovada de risco. Dor pode receber informacao geral e
encaminhamento, sem diagnostico, escolha de exame ou tratamento de lesao.

Mudancas de treino ou alimentacao continuam sendo propostas. A pipeline nao
escreve no Planner, nao deduz autorizacao de um simples "sim" e nao substitui
a validacao das regras pelo backend nem a confirmacao da pessoa.

## Privacidade e reproducao

Os arquivos de texto, trilhas individuais de revisao e pesos ficam em pastas
`private/` ignoradas pelo Git. A minimizacao de identificadores nao comprova
anonimato nem impede sincronizacao pelo OneDrive. Nenhum texto desta rodada
foi enviado a um servico de IA externo e nao existe treinamento automatico
com novas conversas do aplicativo.

Uma nova reproducao em outro diretorio/versionamento segue esta sequencia:

```powershell
python ai/scripts/import_ai_corrections.py "CAMINHO/Evolv_2180_Revisados_IA.xlsx"
python ai/scripts/train_corrected_baseline.py
python ai/scripts/extend_corrected_search.py
python ai/scripts/train_corrected_neural.py
python ai/scripts/finalize_corrected_models.py
```

Versoes finalizadas nao devem ser sobrescritas para testar outras escolhas
depois de ver o teste. Novos experimentos exigem nova versao e uma avaliacao
independente para novas alegacoes de generalizacao.

## Proxima fase

O objetivo desta rodada e fechar uma experiencia mensuravel e seguir com o
aprendizado, nao certificar o Coach para producao. Podemos avancar para
7.03.1, o tokenizador do TinyLM. A qualidade desse exercicio de LM nao depende
de atingir 90% de accuracy no classificador de intencao.

O corpus TinyLM 1.2.0 permanece separado. As explicacoes da IA nao foram
promovidas a respostas verificadas nem adicionadas ao corpus automaticamente.

## Referencia

- [Agrupamento de documentos com K-means, scikit-learn](https://scikit-learn.org/stable/auto_examples/text/plot_document_clustering.html).

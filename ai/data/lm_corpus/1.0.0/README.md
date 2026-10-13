# Corpus TinyLM 1.0.0

Colecao textual em portugues para treinar o tokenizador e o Transformer causal
pequeno do Evolv. O corpus possui 6.381 documentos, 1.656.093 unidades separadas
por espaco e uma estimativa de 2.235.726 tokens de subpalavras. A contagem real
de tokens sera medida depois de treinar o tokenizador.

Fontes aceitas:

- Wikipedia em portugues, CC BY-SA 3.0 conforme a ficha do dataset;
- mensagens humanas pt-BR do OASST1, Apache 2.0;
- base de conhecimento e treino NLU do proprio projeto.

As divisoes sao feitas pelo documento ou arvore de conversa, evitando que
partes do mesmo material aparecam em treino e teste. `sources.json` registra
origem, licenca, filtros e fontes recusadas. Os arquivos JSONL preservam
atribuicao; os TXT existem para o treinamento causal.

As arvores de conversa das dez perguntas humanas de avaliacao do NLP foram
excluidas do corpus. Textos de validacao, teste e desafio do NLU tambem sao
reservados. As 1.092 mensagens humanas restantes e os 4.205 trechos Wikipedia
foram obtidos no Hugging Face. Os trechos Wikipedia podem ser partes de um
mesmo artigo; a divisao preserva o artigo inteiro no mesmo grupo.

Ao redistribuir os textos Wikipedia, preserve autoria/historico atraves dos
links de atribuicao, a licenca CC BY-SA e a indicacao de modificacoes. Aqui as
modificacoes incluem limpeza, redacao de contatos e divisao em trechos.
O dataset original tambem declara GFDL; veja a ficha da fonte. Os textos do
corpus conservam suas licencas, independentemente da licenca do codigo Evolv.

Este corpus serve para um TinyLM educacional treinavel em casa. Ele nao possui
escala para conhecimento geral confiavel e nao transforma respostas externas
em orientacao de saude. Conteudo medico sem licenca explicita e textos de
plataformas sem permissao de treinamento foram deliberadamente excluidos.

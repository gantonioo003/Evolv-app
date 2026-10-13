# Dataset PT-BR 1.4.0

Status: base experimental concluida, nao dataset gold de producao.

## Origem e separacao

Importacao local de 10.000 mensagens de `Dataset_Evolv_PT_BR`, sem usar a
coleta inglesa. Os arquivos originais e seus hashes foram preservados.
8.012 registros sao train, 1.022 validation e 966 test, conforme a coleta.
Validation e test externos nao foram usados para treinar, escolher modelos ou
desenvolver as regras; verificacoes de integridade nao equivalem a avaliacao.

8.912 registros sao `title_only`. O titulo de um post, como uma pergunta curta
sobre dor, pode nao informar intensidade, duracao, objetivo ou medicamentos.
9.119 registros vieram de Hipertrofia.org. Essa concentracao limita a
generalizacao e motiva a proxima coleta com fontes diversas e corpos completos.

## Arquivos

- `external_manifest.json`: contagens, hashes, completude, origem e auditoria.
- `assistant_reviews.json`: 91 IDs de train revisados pelo assistente; rotulos
  provisorios, nao anotacao humana nem teste independente. Intent nulo e riscos
  vazios significam falta de evidencia, nao ausencia confirmada de risco.
- `annotation_report.json`: candidatos das novas regras nos 8.012 textos train.
- `training_manifest.json`: quantidades efetivamente usadas por tarefa.
- `splits/train/` e `splits/validation/`: dados anteriores mais exemplos proprios.
- `local/`: textos externos usados no experimento, ignorados pelo Git.

As 10.000 mensagens e a fila de revisao ficam em
`data/external_private/ptbr-10000-1.0.0/`, tambem ignorado pelo Git. Os titulos
da amostra de desenvolvimento e todos os seus grupos foram excluidos do treino.

## Experimento

Intencao: 1.056 exemplos de projeto mais 734 candidatos web, peso 0,15.
Risco: 407 exemplos de projeto mais 515 candidatos web, peso 0,15.
Ha sobreposicao de perguntas entre tarefas; somar esses numeros nao informa
quantas perguntas web unicas existem. Candidatos nao sao rotulos gold.

As revisoes renderam 73 exemplos de desenvolvimento de intencao e 40 de risco;
os demais ficaram sem rotulo suficiente ou com multiplos sinais de risco.
Nenhum caso desconhecido foi transformado automaticamente em risco `none`.

O treino web e restrito a um experimento local explicito. Direitos de uso e
redistribuicao continuam nao verificados. Nao publicar os textos ou os pesos,
nao adicionar os textos ao corpus LM e nao usar o modelo em producao.

## Proxima coleta

Criar uma nova versao, preservar esta e separar por pessoa/conversa/topico.
Verificar consentimento e licencas, retirar identificadores, revisar rotulos e
construir novo holdout independente antes de nova rodada de modelos.
Entrevistas entram inicialmente como `reserved_human_holdout`, nao treino.

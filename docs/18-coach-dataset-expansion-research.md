# Coach - Pesquisa para expansao do dataset

## Decisao

Este documento registra a pesquisa anterior a importacao. O dataset `1.2.0`
continua congelado. A expansao `1.3.0` e o corpus TinyLM foram posteriormente
construidos; o estado final esta em
`docs/19-coach-dataset-1-3-and-tinylm-corpus.md`.

O registro estruturado fica em
`ai/data/research/dataset-expansion-candidates.v1.json`.

## O que a conversa real ensinou

As conversas fornecidas voluntariamente nao foram copiadas para o repositorio.
Somente os seguintes padroes gerais foram registrados:

- mensagens longas com varias duvidas conectadas;
- portugues informal, abreviacoes e erros de digitacao;
- correcao do proprio pedido em uma mensagem seguinte;
- referencias a imagens e ao contexto anterior;
- comparacao, explicacao e pedido de acao na mesma conversa;
- sintomas descritos com intensidade, tempo e incerteza;
- desejo de entender antes de alterar o comportamento.

Isso mostra que o Coach final precisara de contexto entre turnos, deteccao de
mais de um ato por mensagem e capacidade de pedir esclarecimento. O baseline
atual classifica uma intencao principal e, sozinho, nao resolve tudo isso.

## Casos novos priorizados

### Horario do treino e alimentacao

O Evolv deve sempre conseguir entregar uma dieta-base sem transformar o
horario de treino em pergunta obrigatoria. O usuario pode pular essa escolha no
onboarding, informar uma rotina recorrente ou pedir ao Coach um ajuste pontual.

Quando houver contexto voluntario, o sistema podera adaptar distribuicao e
horario das refeicoes para treino de manha, tarde ou noite e registrar a
preferencia por treinar alimentado ou em jejum. Toda mudanca continua como
proposta confirmavel; mencionar jejum nao significa automaticamente uma
estrategia extrema.

### Esporte, desconforto e fortalecimento

Uma mensagem pode combinar modalidade esportiva, desconforto leve e pedido de
exercicios para fortalecimento ou potencia. O sistema deve separar:

- a duvida ou pedido de treino;
- a modalidade praticada;
- a parte do corpo e o sintoma;
- intensidade, inicio e limitacao funcional;
- sinais que exigem interromper a orientacao comum.

O Coach nao diagnostica lesao. Primeiro faz triagem de gravidade e pergunta o
que estiver faltando. Sem sinais de urgencia, uma fase futura podera oferecer
educacao geral ou uma proposta conservadora; dor, piora, inchaco, instabilidade
ou perda de funcao nunca devem virar progressao automatica.

## Fontes avaliadas

### Boas referencias de metodo

- **Amazon MASSIVE:** mais de um milhao de enunciados, 60 intencoes e 55 slots.
  E uma referencia forte para classificacao de intencao e extracao de campos,
  mas nao possui os rotulos do dominio Evolv.
- **MASSIVE pt-BR:** localizacao brasileira derivada, com cerca de 15,8 mil
  frases e anotacoes de slots. Pode apoiar testes de robustez e estrutura, nao
  ser misturada automaticamente aos nossos rotulos.
- **Atos de Fala PT-BR:** 5.086 frases com trechos anotados como perguntar,
  pedir, informar e outros atos. E util para estudar mensagens com mais de um
  ato, mas sua primeira versao e sintetica.

### Candidatas para fases posteriores

- **OpenAssistant OASST1:** conversas humanas em 35 idiomas, inclusive
  portugues, sob Apache 2.0. Pode ajudar o LM e o estudo de dialogo, depois de
  filtragem; nao e fonte de verdade sobre saude.
- **TalkEx aumentado:** 2.120 conversas pt-BR de atendimento, sendo a maioria
  sintetica. Pode inspirar formato multi-turno, mas o dominio e distante.
- **Fitness Chatbot em portugues:** possui 1.018 pares de pergunta e resposta e
  e o candidato mais proximo do assunto. A procedencia e a revisao tecnica das
  respostas nao estao detalhadas o suficiente para importacao direta. Fica em
  quarentena ate auditoria.

### Fontes que exigem cuidado adicional

- Conteudo do Stack Exchange usa licencas CC BY-SA que exigem atribuicao e
  compartilhamento compativel. Sera usado, no maximo, para descobrir temas ate
  uma revisao juridica e de procedencia.
- Reddit nao sera raspado. Os termos atuais nao concedem permissao geral para
  usar conteudo de usuarios no treinamento de modelos. Foruns podem inspirar
  categorias manualmente, mas nao fornecer copias de mensagens.
- Conversas privadas fornecidas pelo usuario servem somente para derivar
  padroes anonimos. Texto, imagens, nomes, medidas e URLs nao entram no dataset.

## Processo para a versao 1.3.0

1. Selecionar padroes e erros que realmente cobrem falhas do Evolv.
2. Escrever ou anotar novos exemplos com procedencia e licenca registradas.
3. Incluir linguagem longa, ruidosa, multi-intencao e correcoes entre turnos.
4. Criar novos conjuntos de validacao e teste antes do ajuste do modelo.
5. Executar auditorias de duplicata, vazamento, privacidade e consistencia.
6. Treinar uma nova versao e comparar com `1.2.0`, sem apagar o historico.

## Resultado

A pesquisa encontrou dados suficientes para crescer com metodo, mas nao uma
base unica que possa ser despejada no projeto. A escolha profissional e montar
o `1.3.0` com fontes licenciadas, anotacao propria e revisao de seguranca. Isso
produz um portfolio mais forte do que apenas baixar milhares de frases.

## Referencias

- https://github.com/alexa/massive
- https://huggingface.co/datasets/Magurofg/massive-pt-br
- https://huggingface.co/datasets/lucianfialho/atos-de-fala-ptbr-dataset
- https://huggingface.co/datasets/OpenAssistant/oasst1
- https://huggingface.co/datasets/paulohenriquevn/talkex-augmented-pt-br
- https://huggingface.co/datasets/wpbcpaz/fitness-chatbot-dataset
- https://meta.stackexchange.com/questions/68672/data-dump-torrent-required-attribution
- https://redditinc.com/policies/data-api-terms

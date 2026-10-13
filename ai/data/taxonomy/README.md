# Taxonomia do Coach Evolv

## O que esta pasta define

A taxonomia e o vocabulario oficial usado pelo NLP. Ela nao contem respostas
prontas e nao treina nenhum modelo. Seu papel e representar mensagens reais de
forma consistente antes de criar o dataset.

Arquivos:

- `intents.v1.json`: resultado principal esperado pela pessoa;
- `hierarchy.v1.json`: dominio e familia de cada intencao;
- `topics.v1.json`: assuntos que podem coexistir na mesma mensagem;
- `entities.v1.json`: detalhes concretos extraidos do texto ou contexto;
- `risks.v1.json`: sinais independentes que alteram a rota de seguranca;
- `capabilities.v1.json`: operacoes detalhadas, status e necessidade de
  confirmacao;
- `annotation-guidelines.md`: regras para rotular exemplos sem improvisacao.

## Modelo mental

```txt
mensagem
  -> risco(s)
  -> intencao principal e secundaria(s)
  -> topico(s)
  -> entidades, negacoes e referencias
  -> capacidade solicitada
  -> resposta, esclarecimento ou previa do Planner
```

Uma mensagem pode ter uma intencao, varios topicos e mais de um risco. Isso
evita criar uma classe diferente para cada combinacao de verbo e assunto.

Exemplo:

```txt
meu cutting estagnou e quero reduzir mais 500 calorias
```

- intencao principal: `analyze_progress`;
- intencao secundaria: `change_diet_structure`;
- topicos: `cutting` e `energy_balance`;
- entidade: `energy_amount`;
- risco: `extreme_diet_or_dehydration` somente quando houver sinal explicito de
  restricao severa, nao por qualquer reducao.

## Ordem de interpretacao

1. detectar riscos em paralelo;
2. identificar o resultado principal esperado;
3. marcar pedidos secundarios e topicos;
4. extrair entidades, negacoes e referencias;
5. verificar campos ausentes e dependencia de contexto;
6. escolher capacidade e rota;
7. responder, pedir esclarecimento ou criar previa para o Planner.

Risco e intencao nao competem. `Posso treinar com dor forte no peito?` pode ser
uma pergunta sobre treino e, ao mesmo tempo, possuir `emergency_symptom`. A rota
de emergencia sempre vence o coaching normal.

## Intencoes

As 30 intencoes ficam em tres categorias:

- `question`: aprender, comparar, avaliar ou ler o plano;
- `request`: registrar ou propor uma alteracao;
- `conversation`: controlar contexto, confirmacao e limites de modalidade.

Pergunta nunca altera o plano automaticamente. Pedido de mudanca produz uma
previa. A previa so pode ser aplicada depois de confirmacao inequivoca.

## Topicos

Os 94 topicos cobrem treino, alimentacao, recuperacao, progresso, produto e
conversa. Eles sao multilabel. Uma pergunta pode envolver, por exemplo,
`sleep_quality`, `fatigue`, `training_performance` e `under_recovery` ao mesmo
tempo.

Topico nao define sozinho a resposta. `Creatina funciona?` e uma pergunta;
`registra que tomei creatina` e um pedido de registro.

## Entidades

As 79 entidades transformam uma mensagem em contexto ou proposta tipada.

```txt
troca o supino de hoje por flexao
```

- `exercise`: supino;
- `replacement_exercise`: flexao;
- `action_scope`: hoje.

Numeros preservam unidade e contexto. Datas relativas dependem do fuso do
usuario. Negacoes importam: `nao gosto de peixe` nao pode ser interpretado como
preferencia positiva.

## Capacidades e Planner

As 44 capacidades detalham o que o Coach pode fazer sem transformar cada acao
em uma classe de intencao. Elas possuem tres status:

- `answer_only`: explica sem alterar dados;
- `implemented`: contrato ou operacao ja existente;
- `planned`: entendimento definido, mas execucao futura.

Contratos do Planner atualmente implementados:

- `replace_exercise`;
- `move_workout_day`;
- `replace_meal_item`;
- `set_day_activity`.

O arquivo tambem cobre acoes planejadas como encurtar treino, alterar volume,
reorganizar sessao perdida, adaptar para viagem, variar cardapio, planejar
refeicao flexivel e reconciliar dieta com mudanca de atividade.

## Riscos

Os 13 riscos nao fazem diagnostico. Eles escolhem uma rota conservadora:

- dor ou possivel lesao;
- sintoma potencialmente emergencial;
- transtorno alimentar ou restricao extrema;
- medicamento, hormonio ou suplemento incerto;
- alergia ou possivel reacao;
- seguranca de alimento;
- pedido de treino perigoso;
- sinais de recuperacao insuficiente;
- contexto clinico ou vulneravel;
- crise de saude mental;
- ausencia de risco especial.

Riscos sao multilabel. Uma possivel alergia com falta de ar tambem recebe
`emergency_symptom`.

## Linguagem real e ambiguidade

O guia de anotacao cobre portugues formal e informal, abreviacoes, erros,
mensagens longas, referencias como `isso`, pedidos multiplos e dependencia de
imagem. O primeiro Coach e textual e nunca deve fingir que viu uma foto.

Quando a intencao estiver clara mas faltarem campos, ela pode ser classificada;
o Coach registra os campos ausentes e faz uma pergunta curta. Quando nem a
intencao puder ser resolvida, usa `clarification`.

## Pesquisa e limites

Foruns e conversas reais serviram somente para descobrir cobertura e linguagem.
Eles nao sao fonte tecnica e seus textos nao foram copiados. O catalogo de
pesquisa registra licenca, uso permitido, proibicoes e status de ingestao de
cada fonte avaliada.

Nenhum conjunto externo entra no treinamento sem auditoria de licenca,
proveniencia, privacidade, idioma, duplicatas e qualidade.

## Validacao

Na raiz do repositorio:

```powershell
python ai/scripts/validate_taxonomy.py
python -m unittest ai.tests.test_taxonomy -v
```

O validador confere IDs, cobertura hierarquica, dominios, familias, topicos,
entidades, capacidades, contratos implementados, regras de risco, politica das
fontes de pesquisa e existencia do guia de anotacao.

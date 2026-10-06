# Planner

## Papel no Evolv

O Planner e um modulo deterministico do backend. Ele organiza treino e alimentacao a partir de regras conhecidas e nunca interpreta linguagem natural. O Coach podera propor uma acao no futuro, mas somente o backend e o Planner poderao valida-la e aplica-la.

## Fase 01 concluida: base e regras

Entradas consideradas:

- objetivo;
- nivel de treino;
- dias disponiveis;
- duracao da sessao;
- modalidades escolhidas;
- frequencia desejada, quando informada.

Objetivo, nivel, duracao e modalidades podem estar ausentes porque o onboarding e opcional. Nesses casos, o Planner usa padroes conservadores e informa as suposicoes no resultado. Pelo menos um dia disponivel e necessario para organizar uma agenda.

## Divisoes suportadas

- `full_body`: uma a tres sessoes, especialmente para iniciantes e objetivos gerais;
- `upper_lower`: quatro sessoes alternando membros superiores e inferiores;
- `push_pull_legs`: tres sessoes para hipertrofia intermediaria ou avancada, ou seis sessoes em dois ciclos;
- `body_part`: cinco sessoes para hipertrofia avancada;
- `hybrid`: frequencias altas ou combinacoes que nao devem ser forçadas em uma divisao unica;
- `custom`: cardio, mobilidade ou combinacoes sem treino resistido.

`ABC`, `ABCD` e `ABCDE` sao apenas rotulos de agenda. O resultado tambem guarda a divisao real e o foco de cada dia.

## Regras de seguranca e estabilidade

- a mesma entrada sempre produz a mesma recomendacao;
- o Planner nao usa IA;
- nenhum plano e alterado automaticamente;
- mudancas futuras exigirao confirmacao do usuario;
- dias nao afetados devem ser preservados;
- uma revisao automatica nao deve acontecer antes de 14 dias;
- sem frequencia explicita, a recomendacao limita iniciantes a quatro, intermediarios a cinco e avancados a seis sessoes;
- a distribuicao semanal tenta criar o maior espaco possivel entre sessoes.

## Fase 02 concluida: motor de geracao

O motor recebe a recomendacao estrutural da fase 01 e um catalogo de exercicios. Ele continua sendo uma funcao pura: nao consulta o Supabase, nao altera dados e sempre entrega o mesmo resultado quando recebe a mesma entrada.

Cada exercicio do catalogo pode informar:

- identificador e nome;
- grupo muscular principal;
- equipamento e categoria do equipamento;
- padrao de movimento;
- dificuldade;
- se e composto ou isolador;
- tipo de atividade: resistencia, cardio ou mobilidade;
- modalidades compativeis.

## Como o motor monta uma sessao

1. Remove duplicatas e exercicios evitados pelo usuario.
2. Filtra dificuldade e equipamentos realmente disponiveis.
3. Cria uma sequencia de necessidades para o foco do dia.
4. Pontua os exercicios pelo grupo muscular, padrao de movimento, nivel e papel na sessao.
5. Coloca movimentos principais antes dos acessorios.
6. Evita repetir o mesmo exercicio durante a semana quando ha alternativa compativel.
7. Impede excesso do mesmo musculo ou padrao no mesmo dia.
8. Respeita um teto semanal conservador de series por grupo muscular.

Os limites atuais sao 10 series para iniciantes, 14 para intermediarios e 18 para avancados. Esses limites contam o grupo muscular principal cadastrado no exercicio; musculos secundarios ainda nao entram no calculo.

## Prescricoes

- forca: movimentos principais compostos usam menos repeticoes e descansos maiores;
- hipertrofia e recomposicao: faixas moderadas para compostos e mais repeticoes para isoladores;
- perda de gordura: volume conservador e descansos menores, sem transformar toda sessao em cardio;
- saude e manutencao: prescricao simples e conservadora;
- cardio e mobilidade: duracao em minutos, sem inventar repeticoes artificiais;
- sessoes mistas: o treino resistido permanece principal e um bloco curto de cardio pode ser adicionado no final.

A duracao escolhida controla quantos exercicios cabem na sessao. O motor tambem estima o tempo final a partir das series, execucao e descansos.

## Resultado das fases 01 e 02

O modulo `backend/src/planner` entrega:

- contratos tipados;
- validacao das entradas de dominio;
- classificacao de modalidades;
- escolha deterministica da divisao;
- rotulos de agenda;
- distribuicao dos dias disponiveis;
- modelos de foco para cada dia;
- politica explicita de estabilidade;
- gerador deterministico de sessoes;
- filtros de catalogo e preferencias;
- selecao, ordenacao e variedade de exercicios;
- prescricoes de series, repeticoes, descanso ou duracao;
- resumo do volume semanal por grupo muscular;
- avisos quando o catalogo nao consegue preencher uma sessao;
- 21 testes unitarios das regras e do gerador.

## Fase 03 concluida: dados e integracao

A geracao agora usa o catalogo remoto e pode ser persistida em uma unica transacao do Postgres. Se qualquer dia ou exercicio falhar, nenhum plano incompleto fica salvo.

Entregas desta fase:

- catalogo ampliado com atividades de resistencia, cardio e mobilidade;
- prescricoes por repeticoes ou por duracao;
- metadados da regra e entrada original salvos junto ao plano;
- apenas um plano ativo por usuario;
- criacao, listagem, detalhe, ativacao e arquivamento;
- endpoints autenticados em `/api/planner/plans`;
- mobile gerando, lendo e administrando planos reais;
- teste SQL transacional com `ROLLBACK`;
- RLS mantido em todas as operacoes.

## Endpoints da fase 03

- `POST /api/planner/plans/generate`;
- `GET /api/planner/plans`;
- `GET /api/planner/plans/:planId`;
- `POST /api/planner/plans/:planId/activate`;
- `POST /api/planner/plans/:planId/archive`.

## O que foi deixado para a fase 04

- mover dias, trocar exercicios ou regenerar apenas parte do plano.

Esses ajustes foram entregues na fase 04.4 descrita abaixo.

## Fases 04.1, 04.2 e 04.3 concluidas: Planner nutricional

O Planner possui contratos e regras para fases energeticas, distribuicoes de macros, horarios, estilos alimentares, preferencias e restricoes. O motor de alimentos usa essas metas para selecionar opcoes compativeis, ajustar porcoes, reduzir repeticoes e sugerir trocas equivalentes pelo mesmo papel nutricional.

O catalogo inicial, as metas, refeicoes, quantidades e substituicoes agora sao persistidos no Supabase. O backend oferece geracao, historico, detalhe, ativacao e arquivamento, e o mobile administra esses planos reais.

## Fase 04.4 concluida: ajustes e fechamento

O Planner cria uma previa tipada antes de mover treino, trocar exercicio ou trocar alimento. A alteracao so e aplicada depois da confirmacao, fica no historico e pode ser desfeita quando o estado ainda e compativel com o snapshot aplicado. Previa vencida ou desatualizada e rejeitada.

Na alimentacao, o mesmo plano pode usar metas iguais todos os dias ou metas diferentes para treino e descanso. O usuario escolhe cardapio fixo, rotacao de tres ou uma semana de sete cardapios. Refeicao flexivel e alcool sao excecoes opcionais e planejadas; nunca entram silenciosamente. A aba Dieta identifica o dia e mostra a versao correta automaticamente.

Treino e dieta compartilham um contexto diario. Mover um treino no plano semanal muda automaticamente qual cardapio aparece naquele dia. Mudancas pontuais, como descansar, fazer apenas cardio ou combinar cardio e musculacao, usam `daily_activity_overrides`: elas afetam somente a data escolhida e preservam a rotina recorrente. Cardio leve ou moderado usa o menu de descanso por padrao; cardio intenso ou longo pode usar o menu de treino. Qualquer escolha diferente deve ser explicita, sem o sistema inventar alimentos ou carboidratos extras.

O endpoint `GET /api/planner/day-context?date=AAAA-MM-DD` resolve uma unica fonte de verdade para as abas Treino e Dieta. Se a pessoa mudar a atividade sem informar ao app, o sistema nao tenta adivinhar e nao pune: mantem o planejamento conhecido ate receber uma correcao.

Detalhes, limites de seguranca e referencias estao em `docs/12-nutrition-planner.md`.

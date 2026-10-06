# Evolv - Backend

## Status

Fase 5 concluida no repositorio. As quatro partes do backend foram implementadas e validadas. O teste fisico no iPhone pertence a validacao final do aplicativo e sera feito depois.

## Objetivo

Criar uma API NestJS que fique entre o aplicativo mobile e o Supabase. Essa API recebera as solicitacoes do app, validara os dados, aplicara regras do Evolv e acessara o banco respeitando a identidade de cada usuario.

## Primeira passada concluida

- projeto `backend/` criado com NestJS e TypeScript;
- organizacao inicial por modulos;
- configuracao segura por arquivo `.env` ignorado pelo Git;
- validacao das configuracoes obrigatorias;
- cliente Supabase tipado com o schema real do banco;
- verificacao de tokens do Supabase;
- protecao de rotas com token Bearer;
- acesso ao banco em nome do usuario, mantendo o RLS ativo;
- DTO inicial para validar alteracoes de perfil;
- tratamento centralizado de erros HTTP;
- Helmet e CORS configurados;
- rota publica `GET /api/health`;
- rota protegida `GET /api/profiles/me`;
- rota protegida `PATCH /api/profiles/me`;
- compilacao e testes iniciais aprovados.

## Como a autenticacao funciona

1. O usuario entra pelo aplicativo usando o Supabase Auth.
2. O Supabase entrega ao aplicativo um token temporario.
3. O aplicativo envia esse token para o backend.
4. O backend pergunta ao Supabase qual usuario pertence ao token.
5. As consultas sao feitas com esse mesmo token.
6. O RLS do PostgreSQL permite acesso somente aos dados daquele usuario.

A senha do usuario nao passa pelo backend do Evolv. O Supabase Auth cuida dela.

## Segunda passada concluida

- modulo de objetivos com leitura, criacao e atualizacao;
- plano de treino ativo com dias e exercicios;
- catalogo de exercicios com busca e filtros;
- registro opcional de sessao completa;
- registro e edicao de carga sem exigir sessao completa;
- historico de cargas por exercicio;
- leitura e decisao sobre sugestoes de progressao;
- plano alimentar ativo com refeicoes e itens;
- registros alimentares opcionais e calculo de totais;
- criacao, edicao e remocao de medidas de progresso;
- validacao dos novos DTOs;
- tratamento compartilhado de erros do Supabase;
- testes unitarios, E2E, build e lint aprovados;
- migration aplicada para fases nutricionais, divisoes de treino, esforco, motivacao e preferencias de avisos silenciosos.

## Limite atual

Naquela passada, Coach e Planner ainda nao faziam parte do backend. A base deterministica do Planner foi adicionada posteriormente e esta documentada em `docs/10-planner.md`.

## Terceira passada implementada no repositorio

- cliente Supabase Auth no Expo;
- cadastro e login por e-mail;
- sessao persistente e protecao das abas;
- cliente HTTP com token Bearer automatico;
- contextos tipados para carregar perfil, objetivo, treino, dieta e progresso;
- onboarding gravando objetivo e conclusao no backend;
- leitura real nas telas Hoje, Treino, Dieta, Conta e Progresso;
- gravacao real de cargas, refeicoes e peso;
- perfil criado automaticamente para novas contas;
- recuperacao automatica de contas antigas sem perfil;
- remocao de registro alimentar adicionada a API;
- typecheck, lint, build, testes e exportacao web aprovados.

## Validacao da parte 3

- migrations `202609300001_add_training_context.sql` e `202609300002_create_profile_on_signup.sql` aplicadas no Supabase remoto;
- tipos TypeScript regenerados a partir do schema remoto;
- `db lint` concluido sem erros;
- teste transacional da fase 3 aprovado;
- teste transacional do novo contexto de treino e nutricao aprovado;
- build, lint e os testes daquela passada do backend aprovados;
- typecheck, lint e exportacao das 23 rotas web atuais do mobile aprovados.

O teste manual da experiencia completa com uma conta real e a validacao no iPhone ficam para a etapa de qualidade do aplicativo.

## Quarta passada concluida

- documentacao interativa OpenAPI/Swagger em `/api/docs`;
- documento JSON OpenAPI em `/api/docs-json`;
- 39 caminhos documentados, incluindo as rotas dos Planners de treino, nutricao, contexto diario e ajustes;
- testes automatizados para token ausente, invalido, expirado e valido;
- resposta padronizada para indisponibilidade, timeout e excesso de requisicoes;
- limite global de requisicoes;
- timeout global configuravel;
- `requestId` devolvido no cabecalho e nos erros;
- log estruturado de metodo, rota, status e duracao, sem token ou corpo;
- rota de liveness `GET /api/health`;
- rota de readiness `GET /api/health/ready` validada contra o Supabase;
- encerramento controlado da aplicacao;
- arrays de perfil limitados para evitar cargas exageradas;
- build e lint aprovados;
- 67 testes unitarios e 5 testes E2E aprovados apos a fase 04.4 do Planner;
- auditoria das dependencias de producao com zero vulnerabilidades conhecidas.

## Limites desta fase

- o Planner cobre os ajustes seguros do MVP; novas familias de acao serao adicionadas conforme o Coach local for integrado;
- Coach ainda nao usa o servico local de NLP;
- deploy ainda nao foi configurado;
- teste em iPhone sera realizado depois pelo usuario.

## Planner - fases 01, 02 e 03 concluidas

- modulo `PlannerModule` registrado no NestJS;
- contratos para objetivo, nivel, dias, duracao, modalidades e frequencia;
- suporte a Full body, Upper/Lower, Push/Pull/Legs, Body-part, Hibrida e Personalizada;
- `ABC`, `ABCD` e `ABCDE` mantidos como rotulos de agenda;
- suporte a musculacao, cardio, mobilidade e combinacoes;
- padroes conservadores para dados opcionais pulados no onboarding;
- distribuicao deterministica dos treinos nos dias disponiveis;
- politica que proibe alteracoes automaticas e exige confirmacao futura;
- selecao e ordenacao de exercicios pelo foco e padrao de movimento;
- series, repeticoes e descanso adaptados ao objetivo e ao nivel;
- cardio e mobilidade prescritos por duracao;
- limites semanais de volume e protecao contra repeticoes desnecessarias;
- filtros por modalidade, equipamento disponivel, dificuldade e exercicios evitados;
- persistencia transacional no Postgres;
- rotas para gerar, listar, visualizar, ativar e arquivar;
- apenas um plano ativo por usuario;
- integracao real com a tela Treino e o gerenciador de planos do Expo;
- suporte persistido a cardio e mobilidade por duracao;
- 51 testes unitarios especificos do Planner, incluindo treino, nutricao e contexto diario.

## Planner - fase 04.4 concluida

- mover ou inverter dias de treino sem duplicar a agenda;
- trocar exercicios por alternativas compativeis;
- trocar alimentos apenas por substituicoes previamente calculadas;
- previa separando o que muda, o que permanece e os avisos;
- confirmacao ou descarte explicitos;
- snapshots antes/depois, deteccao de previa desatualizada e historico;
- desfazer transacional quando o estado atual ainda corresponde ao ajuste aplicado;
- telas mobile para ajustes manuais e historico;
- contratos tipados que o futuro Coach podera propor sem executar SQL.

## Planner nutricional - fases 04.1, 04.2 e 04.3 concluidas

- fases de ganho de massa, perda de gordura, manutencao, recomposicao e diet break;
- padroes equilibrado, alto carboidrato, low carb, cetogenico e personalizado;
- horario regular, janela alimentar ou agenda personalizada;
- estilos onivoro, pescetariano, vegetariano e vegano;
- estimativa energetica explicita, com metodo e nivel de confianca;
- metas de proteina, carboidrato, gordura e fibra;
- distribuicao exata das metas entre uma e oito refeicoes;
- separacao entre alergia/restricao, alimento rejeitado e alimento preferido;
- bloqueio de geracao automatica quando o contexto informado exige revisao profissional;
- 14 novos testes unitarios das regras nutricionais.
- catalogo tipado com papeis nutricionais, estilos, horarios, alergenos e limites de porcao;
- filtros rigidos de seguranca antes da selecao;
- pontuacao por preferencia, adequacao, processamento e variedade;
- otimizacao deterministica das quantidades para aproximar calorias e macros;
- substituicoes do mesmo papel com porcao recalculada e similaridade nutricional;
- avisos para catalogo incompleto ou metas que nao puderam ser aproximadas;
- 13 novos testes unitarios do motor de alimentos.
- catalogo inicial persistido com 26 alimentos e metadados do Planner;
- geracao e persistencia transacional de metas, refeicoes, porcoes, macros e substituicoes;
- ordem estavel dos alimentos dentro de cada refeicao;
- apenas um plano alimentar ativo por usuario, com historico preservado;
- cinco endpoints autenticados de geracao e gerenciamento;
- telas Expo para gerar, listar, visualizar, ativar e arquivar planos reais;
- dois testes unitarios de persistencia e um teste SQL transacional remoto;
- tipos TypeScript regenerados e schema remoto aprovado no `db lint`.

A fase 04.4 tambem adicionou metas e refeicoes distintas para treino e descanso, cardapio fixo ou rotacao de tres/sete opcoes, refeicao flexivel planejada e excecao opcional de alcool. A aba Dieta escolhe automaticamente a rotina e o cardapio do dia.

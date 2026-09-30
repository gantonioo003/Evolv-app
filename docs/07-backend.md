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

Coach e Planner nao fazem parte desta passada. Eles serao implementados depois da consolidacao dos contratos do backend.

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
- typecheck, lint e exportacao das 19 rotas web do mobile aprovados.

O teste manual da experiencia completa com uma conta real e a validacao no iPhone ficam para a etapa de qualidade do aplicativo.

## Quarta passada concluida

- documentacao interativa OpenAPI/Swagger em `/api/docs`;
- documento JSON OpenAPI em `/api/docs-json`;
- 22 caminhos e 12 schemas documentados;
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
- 8 testes unitarios e 5 testes E2E aprovados;
- auditoria das dependencias de producao com zero vulnerabilidades conhecidas.

## Limites desta fase

- Planner ainda nao gera planos; ele pertence a proxima fase;
- Coach ainda nao usa o servico local de NLP;
- deploy ainda nao foi configurado;
- teste em iPhone sera realizado depois pelo usuario.

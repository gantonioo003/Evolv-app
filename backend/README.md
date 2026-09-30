# Evolv Backend

API do Evolv criada com Node.js, TypeScript e NestJS.

Esta pasta concentra a autenticacao recebida do aplicativo, as regras de negocio e o acesso seguro ao Supabase. O backend do MVP esta concluido para perfil, objetivos, treino, cargas, dieta e progresso. Coach e Planner serao adicionados nas proximas fases.

## Base implementada

- projeto NestJS com TypeScript;
- configuracao por variaveis de ambiente;
- validacao das variaveis obrigatorias ao iniciar;
- conexao tipada com o Supabase;
- autenticacao por token Bearer do Supabase;
- uso do token do usuario para preservar as regras RLS do banco;
- validacao dos dados enviados para a API;
- formato centralizado de erros;
- protecoes HTTP basicas com Helmet e CORS;
- limite global de requisicoes e timeout configuravel;
- `requestId` e log de duracao para cada requisicao, sem registrar tokens;
- health de processo e readiness do Supabase;
- documentacao interativa OpenAPI/Swagger;
- modulo inicial de perfil autenticado;
- objetivos atuais e historicos;
- plano de treino ativo e catalogo de exercicios;
- sessoes e cargas opcionais por exercicio;
- sugestoes de progressao aceitas ou dispensadas pelo usuario;
- plano alimentar, registros, itens e totais nutricionais;
- medicoes opcionais de progresso;
- testes unitarios, autenticados e de integracao.

## Rotas atuais

| Metodo | Rota | Autenticacao | Funcao |
| --- | --- | --- | --- |
| GET | `/api/health` | Nao | Verifica se a API esta funcionando |
| GET | `/api/health/ready` | Nao | Verifica se a API alcanca o Supabase |
| GET | `/api/docs` | Nao | Abre a documentacao interativa em desenvolvimento |
| GET | `/api/profiles/me` | Sim | Retorna o perfil do usuario autenticado |
| PATCH | `/api/profiles/me` | Sim | Atualiza campos permitidos do proprio perfil |
| GET | `/api/goals` | Sim | Lista os objetivos do usuario |
| GET | `/api/goals/active` | Sim | Retorna o objetivo ativo mais recente |
| POST | `/api/goals` | Sim | Cria um objetivo |
| PATCH | `/api/goals/:goalId` | Sim | Atualiza um objetivo proprio |
| GET | `/api/workouts/active-plan` | Sim | Retorna o plano ativo com dias e exercicios |
| GET | `/api/workouts/exercises` | Sim | Busca o catalogo de exercicios com filtros |
| GET | `/api/workouts/logs` | Sim | Lista treinos registrados |
| POST | `/api/workouts/logs` | Sim | Registra uma sessao opcional |
| GET | `/api/workouts/exercises/:exerciseId/history` | Sim | Mostra o historico de carga |
| POST | `/api/workouts/exercises/:exerciseId/logs` | Sim | Registra carga sem exigir treino completo |
| PATCH | `/api/workouts/exercise-logs/:logId` | Sim | Corrige um registro de carga |
| GET | `/api/workouts/progression-suggestions` | Sim | Lista sugestoes de progressao |
| PATCH | `/api/workouts/progression-suggestions/:suggestionId` | Sim | Aceita ou dispensa uma sugestao |
| GET | `/api/nutrition/active-plan` | Sim | Retorna plano, refeicoes e itens |
| GET | `/api/nutrition/logs` | Sim | Lista registros alimentares opcionais |
| GET | `/api/nutrition/summary` | Sim | Soma calorias e macronutrientes do periodo |
| POST | `/api/nutrition/logs` | Sim | Cria um registro alimentar |
| DELETE | `/api/nutrition/logs/:foodLogId` | Sim | Remove um registro alimentar proprio |
| POST | `/api/nutrition/logs/:foodLogId/items` | Sim | Adiciona um alimento consumido |
| DELETE | `/api/nutrition/log-items/:itemId` | Sim | Remove um alimento registrado |
| GET | `/api/progress` | Sim | Lista medicoes de progresso |
| POST | `/api/progress` | Sim | Cria uma medicao opcional |
| PATCH | `/api/progress/:entryId` | Sim | Atualiza uma medicao propria |
| DELETE | `/api/progress/:entryId` | Sim | Remove uma medicao propria |

As rotas protegidas recebem o token no cabecalho:

```txt
Authorization: Bearer TOKEN_DO_USUARIO
```

## Configuracao local

1. Duplique `.env.example` com o nome `.env`.
2. Preencha `SUPABASE_URL` e `SUPABASE_ANON_KEY` com os dados publicos do projeto Supabase.
3. Nunca coloque a chave `service_role` no aplicativo mobile nem no GitHub.
4. Instale as dependencias e inicie a API.

```powershell
npm install
npm run start:dev
```

As rotas locais principais ficam em:

- API: `http://localhost:3000/api`;
- health: `http://localhost:3000/api/health`;
- readiness: `http://localhost:3000/api/health/ready`;
- Swagger: `http://localhost:3000/api/docs`.

O Swagger fica ligado por padrao em desenvolvimento e pode ser controlado com `SWAGGER_ENABLED`. Em producao, a documentacao fica desligada quando essa variavel nao e informada.

## Comandos

```powershell
npm run build
npm test
npm run test:e2e
npm run test:cov
npm run lint
```

## Estrutura atual

```txt
backend/
  src/
    auth/       leitura e validacao do token do usuario
    common/     decoradores, erros, timeout e contexto das requisicoes
    config/     validacao das variaveis de ambiente
    database/   tipos TypeScript gerados a partir do Supabase
    goals/      objetivo atual e historico
    health/     liveness da API e readiness do Supabase
    nutrition/  plano alimentar, registros e totais
    profiles/   leitura e atualizacao do perfil autenticado
    progress/   peso, medidas e historico opcional
    supabase/   clientes de autenticacao e banco
    workouts/   plano, exercicios, sessoes, cargas e progressoes
    app.module.ts
    main.ts
  test/         testes de integracao
```

## Estado dos testes

- build e lint aprovados;
- 8 testes unitarios aprovados;
- 5 testes E2E aprovados;
- Swagger validado com 22 caminhos e 12 schemas;
- readiness validado contra o projeto Supabase remoto;
- auditoria das dependencias de producao sem vulnerabilidades conhecidas;
- testes SQL de CRUD, RLS e integridade aprovados na fase do banco.

## Proximos passos

- validar a experiencia completa em um iPhone;
- escolher e configurar o ambiente de deploy;
- criar o Planner depois dos contratos principais da API;
- integrar o servico local de NLP quando a fase do Coach comecar.

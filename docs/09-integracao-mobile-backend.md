# Evolv - Integracao Mobile e Backend

## O fluxo completo

1. O usuario entra no Expo com e-mail e senha.
2. O Supabase Auth devolve uma sessao e um token temporario.
3. O aplicativo guarda a sessao no aparelho.
4. Cada pedido ao NestJS envia `Authorization: Bearer TOKEN`.
5. O NestJS valida o token com o Supabase.
6. O backend consulta o PostgreSQL usando a identidade do usuario.
7. O RLS impede que esse usuario leia ou altere dados de outra conta.

O aplicativo nunca envia a senha ao backend Evolv. A senha vai diretamente ao Supabase Auth.

## Arquivos principais

- `mobile/src/lib/supabase.ts`: cria o cliente de autenticacao.
- `mobile/src/context/auth-context.tsx`: controla sessao, entrada, cadastro e saida.
- `mobile/src/services/api-client.ts`: envia pedidos HTTP com token e trata erros.
- `mobile/src/services/evolv-api.ts`: representa as rotas do NestJS.
- `mobile/src/context/evolv-data-context.tsx`: centraliza os dados usados pelas telas.
- `backend/src/auth/supabase-auth.guard.ts`: bloqueia rotas sem token valido.
- `backend/src/supabase/supabase.service.ts`: cria consultas sujeitas ao RLS.

## Variaveis locais

O backend usa `backend/.env`. O aplicativo usa `mobile/.env.local`. Esses arquivos nao devem ser enviados ao GitHub.

No navegador, a API normalmente usa `http://localhost:3000/api`. Em um iPhone real, `localhost` apontaria para o proprio celular; por isso sera necessario usar o IP local do computador, por exemplo `http://192.168.0.10:3000/api`.

## Dados reais e dados locais

Perfil, objetivo, planos, cargas, registros alimentares e progresso usam a API real. Tema, preferencias de imagens e preferencias visuais de treino continuam locais porque nao precisam do servidor nesta fase. O Coach ainda nao usa o modelo NLP.

## Estado da validacao

- TypeScript mobile aprovado.
- ESLint mobile aprovado.
- exportacao web com 25 rotas aprovada, incluindo planos e historico de ajustes.
- build e lint do backend aprovados.
- 67 testes unitarios e 5 testes E2E aprovados.
- migrations de integracao, Planner de treino, Planner nutricional, ajustes, rotacao de cardapios e flexibilidade planejada aplicadas no Supabase remoto.
- tipos TypeScript regenerados a partir do schema remoto.
- `db lint` concluido sem erros.
- cinco suites SQL remotas aprovadas, incluindo RLS, ajustes/desfazer e variacoes nutricionais.

O backend foi finalizado. A experiencia completa ainda sera validada manualmente com uma conta real em um iPhone durante a etapa de qualidade do aplicativo.

## Protecoes da API

- todas as rotas privadas exigem token Bearer do Supabase;
- RLS continua sendo aplicado porque o backend consulta em nome do usuario;
- requisicoes possuem limite e timeout;
- cada resposta recebe `X-Request-Id` para rastreamento;
- erros nao devolvem detalhes internos do Supabase;
- logs nao incluem token nem corpo da requisicao;
- `/api/health/ready` verifica a disponibilidade do Supabase;
- `/api/docs` documenta e permite inspecionar as rotas em desenvolvimento.

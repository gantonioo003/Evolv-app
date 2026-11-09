# 7.06.4 — Integração do Coach no Mobile

Implementada em 03/11/2026. A tela usa as rotas autenticadas do NestJS:
mensagens e respostas reais do serviço, conversas persistidas, títulos,
exclusão e prévias de alterações. O estilo visual existente foi preservado.

## Fluxo

    Mobile + JWT do usuário
        → NestJS /api/coach
        → histórico no Supabase + FastAPI/Coach
        → resposta, fontes e eventual proposta
        → usuário pede prévia
        → Planner prepara o ajuste
        → usuário revisa e confirma a alteração
        → backend aplica e Mobile atualiza os dados do plano

Pedir a prévia não aplica o ajuste. Aplicar, descartar e desfazer são
operações separadas, enviadas com confirmed: true após o botão correspondente.
A opção de desfazer depende do estado e da reversibilidade informados pelo
backend. O servidor continua responsável por validar proprietário, vínculo,
expiração e condições do plano; o Mobile não executa SQL nem decide permissões.

## Arquivos

| Arquivo, relativo à raiz do repositório | Responsabilidade |
| --- | --- |
| mobile/src/app/(tabs)/coach.tsx | Rota da tela conectada. |
| mobile/src/components/coach-connected-screen.tsx | Chat, fontes, histórico e diálogos de confirmação. |
| mobile/src/services/coach-api.ts | Transporte autenticado para NestJS. |
| mobile/src/lib/coach-session.ts | Estado, paginação, envio, repetição e decisões. |
| mobile/src/types/coach.ts | Contratos de mensagens, propostas e histórico. |
| mobile/src/services/api-client.ts | Timeout configurável; Coach usa 240 s, demais clientes mantêm 12 s. |
| mobile/src/components/ui.tsx | Rodapé do chat e rolagem ao receber nova mensagem. |
| mobile/src/app/(tabs)/_layout.tsx | Atualização de dados em segundo plano preserva a tela e sua prévia. |
| mobile/tests/coach-session.test.cjs | Regressões do controlador de conversa. |
| mobile/scripts/verify-coach-ui.cjs | Conferência de interface web com autenticação e rede fictícias. |

expo-crypto fornece UUIDs por pedido. Nenhuma chave interna da FastAPI ou
service_role é adicionada ao aplicativo. O token público de sessão do usuário
é enviado apenas como Bearer ao backend configurado.

## Rotas utilizadas

Todas abaixo recebem o prefixo /api. IDs são codificados no caminho.

| Método | Rota | Uso |
| --- | --- | --- |
| GET | /coach/sessions?limit=30&offset=N | Listar/paginar conversas do usuário. |
| POST | /coach/sessions | Criar conversa no primeiro envio. |
| GET | /coach/sessions/:id/messages?limit=30&offset=N | Recuperar mensagens. |
| PATCH | /coach/sessions/:id | Renomear a conversa. |
| DELETE | /coach/sessions/:id | Excluir após confirmação explícita. |
| POST | /coach/sessions/:id/messages | Enviar texto, request_id e eventual proposal_id. |
| GET | /planner/adjustments/:id | Consultar estado atual da prévia antes de revisá-la. |
| POST | /coach/sessions/:id/adjustments/:adjustmentId/apply | Aplicar ajuste confirmado. |
| POST | /coach/sessions/:id/adjustments/:adjustmentId/reject | Descartar prévia. |
| POST | /coach/sessions/:id/adjustments/:adjustmentId/revert | Desfazer ajuste reversível. |

O histórico chega do servidor do mais recente para o mais antigo. A tela
inverte cada página para mostrar a conversa na ordem de leitura; mensagens
anteriores são acrescentadas no começo. A lista de conversas também é paginada.
Renomear aceita até 80 caracteres; cada mensagem aceita até 8.000.

## Falhas, continuidade e privacidade

- Cada envio recebe um request_id. Ao repetir uma falha, o aplicativo conserva
  esse ID e o texto, permitindo ao backend deduplicar a operação.
- Durante envio ou repetição pendente, não começa outra mensagem nem troca de
  conversa. Há opção explícita de abandonar a repetição e consultar o histórico.
- Indisponibilidade e timeout aparecem como erro; não há resposta simulada de
  substituição. A bolha do usuário fica marcada como envio não confirmado.
- Renovar o token mantém a conversa atual. Trocar de usuário recria o estado
  da tela; respostas de controladores descartados são ignoradas.
- Mensagens são mantidas em memória na tela e persistidas pelo backend no
  Supabase. Esta integração não cria cache adicional de conversas no AsyncStorage.
- Histórico não restaura propostas pendentes como confirmáveis. O usuário pede
  uma proposta nova. Prévias antigas precisam ser abertas para consultar o estado
  atual, pois o envelope salvo é um registro do momento da resposta.
- Excluir conversa exige confirmação e não desfaz ajustes já aplicados.
  Retenção de backups segue as limitações documentadas na 7.06.3.
- Conversas salvas não são enviadas automaticamente para treinamento.

Fontes HTTPS retornadas pelo Coach podem ser abertas. Identificadores internos
de trechos e marcação simples de negrito são retirados do texto de apresentação;
o conteúdo não é interpretado como HTML. Fontes consultadas são distinguidas
de fontes efetivamente citadas pelo modelo.

## Configuração para usar

O backend deve estar acessível em EXPO_PUBLIC_API_URL, incluindo /api. É
necessário iniciar NestJS e o serviço FastAPI com a configuração da 7.06.1/2,
habilitando COACH_AI_ENABLED no backend e mantendo a chave interna só entre
esses dois serviços. O usuário precisa estar autenticado no Supabase.

No iPhone, a URL pública do backend deve usar o IP da máquina acessível pela
rede local; localhost no telefone aponta para o próprio telefone. FastAPI
continua interna: o Mobile conversa com NestJS. Nenhum arquivo privado de
ambiente foi alterado nesta fase.

Em mobile/:

    npm start
    npm run typecheck
    npm run lint
    npm test

## Verificação e limites

TypeScript e lint passaram. Os 33 testes Mobile passaram: 13 do controlador
do Coach e 20 regressões já existentes. A exportação web compilou 25 rotas.

A interface exportada passou por 16 checks no Edge, em 430 × 932 e
1440 × 1000: envio/repetição, histórico, proposta sem aplicação automática,
prévia, confirmação, desfazer, preservação da tela após refresh, exclusão
confirmada, compositor visível e ausência de overflow horizontal/erros JS.

Esses checks de interface usam respostas HTTP, autenticação e Planner
fictícios. Testam o aplicativo compilado e o contrato de rede, sem inferência
real nem alteração de dados de contas existentes. Não substituem o teste
completo Mobile → backend → FastAPI → modelos → Supabase/Planner.

Registros e capturas locais:

    ai/artifacts/mobile_coach/1.0.1/ui-verification.json
    ai/artifacts/mobile_coach/1.0.1/verification.json
    ai/artifacts/mobile_coach/1.0.1/coach-mobile.png
    ai/artifacts/mobile_coach/1.0.1/coach-desktop.png

O script de navegador requer Playwright, Edge e a exportação local na pasta
indicada no próprio script. O export usado na conferência aponta só para uma
API fictícia local e está ignorado pelo Git; não é um build de distribuição.

O teste nativo no iPhone, teclado e áreas seguras reais, qualidade de resposta,
latência, RAM e ações reais de ponta a ponta ficam na avaliação 7.06.5. Os
limiares e modelos existentes não foram retreinados nem afrouxados nesta fase.

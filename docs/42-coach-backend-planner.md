# 7.06.2 — NestJS, IA e Planner

Implementado em 2026-11-02. Integração de transporte e contratos pronta,
sem alterações em contas, planos ou banco reais nesta etapa.

## Fluxo

    Cliente → JWT Supabase → guard existente do NestJS
        ↓ UUID autenticado, nunca identidade enviada pelo cliente
    CoachService → planos autorizados via serviços/RLS existentes
        ↓ snapshot mínimo de IDs/nomes + revisão
    FastAPI → NLP/busca/LM → proposta tipada (se houver confiança)
        ↓ confirmação por proposal_id
    NestJS → valida contrato e revisão → Planner.preview
        ↓ prévia calculada, persistida pelo Planner existente
    Cliente confirma adjustment_id + confirmed=true
        ↓
    Planner.apply → RPC/RLS existentes

Perguntar não aplica alterações. Confirmar uma proposta do Coach apenas
autoriza calcular a prévia. A confirmação do ajuste calculado é outra
operação HTTP explícita.

## Onde está cada parte

- backend/src/coach/coach.controller.ts: rotas protegidas pelo SupabaseAuthGuard.
- backend/src/coach/coach.service.ts: sessões, revisão, prévia e decisões.
- backend/src/coach/coach-ai.client.ts: transporte HTTP para FastAPI.
- backend/src/coach/coach-context.service.ts: contexto lido com JWT do usuário.
- backend/src/coach/dto/coach.dto.ts: validação das entradas públicas.
- backend/src/coach/coach.module.ts: registra a integração no AppModule.
- ai/src/evolv_api/app.py: rota interna de contexto tipado, versão 1.1.0.
- backend/scripts/verify-coach-bridge.mjs: conferência entre servidores reais.
- ai/tests/fixtures/serve_coach_api.py: fixture explícita para integração.

## Configurar

No ambiente do backend:

    COACH_AI_ENABLED=true
    COACH_AI_URL=http://127.0.0.1:8010
    COACH_AI_SERVICE_KEY=MESMA_CHAVE_INTERNA_DA_FASTAPI
    COACH_AI_TIMEOUT_MS=180000
    COACH_REQUEST_TIMEOUT_MS=210000

Não colocar a chave em variável pública do Mobile. A validação do ambiente
exige chave de pelo menos 32 caracteres quando habilitado. O padrão é
desativado até configurar o serviço local. Os exemplos não contêm credenciais.

Iniciar FastAPI conforme docs/41-coach-fastapi-service.md e depois o backend
com npm run start:dev. Nenhuma configuração privada existente foi editada.

## Rotas públicas do backend

Todas exigem Authorization: Bearer TOKEN_SUPABASE.
O prefixo padrão é /api.

| Método/caminho | Corpo |
|---|---|
| POST /coach/sessions | {} ou workout_plan_id/diet_plan_id |
| POST /coach/sessions/{sessionId}/messages | request_id, text, proposal_id opcional |
| DELETE /coach/sessions/{sessionId} | nenhum |
| POST /coach/sessions/{sessionId}/adjustments/{adjustmentId}/apply | {"confirmed":true} |
| POST /coach/sessions/{sessionId}/adjustments/{adjustmentId}/reject | {"confirmed":true} |
| POST /coach/sessions/{sessionId}/adjustments/{adjustmentId}/revert | {"confirmed":true} |

Uma sessão aceita IDs de planos escolhidos, mas os serviços existentes
verificam propriedade antes de ler. Sem escolha, usa o único plano ativo
de cada tipo. Múltiplos planos ativos exigem escolha explícita.
Somente planos ativos são usados nesta integração.

Ao enviar mensagem, manter request_id se repetir a mesma solicitação por
falha de rede. A resposta inclui o envelope da IA e planner_previews.
actions pode conter uma proposta local ainda não confirmada; ela não é
um ajuste aplicado. O Mobile deverá usar o ID retornado, não extrair IDs
do texto gerado.

Na confirmação de uma proposta, enviar texto explícito, o proposal_id
original e um request_id novo. Se o contrato confirmado continuar válido,
planner_previews traz o ajuste calculado. Só então mostrar a prévia e
oferecer confirmação da aplicação pelo adjustmentId.

## Contexto, segurança e concorrência

O JWT do usuário só é usado por NestJS/Supabase. A FastAPI recebe uma chave
interna diferente e X-Evolv-User-ID derivado pelo guard autenticado.
Cabeçalho de identidade vindo do cliente não é encaminhado.

A rota interna PUT /v1/sessions/{id}/planner-context aceita contexto tipado,
com UUIDs e listas limitadas, verifica ator e propriedade da sessão e
normaliza nomes apenas quando há correspondência inequívoca no catálogo.
Não faz aproximação para inventar um ID de exercício ou alimento.
O limite dessa rota é 256 KiB; mensagens continuam com 64 KiB.

O snapshot é renovado antes de cada mensagem. A revisão considera o
conteúdo dos planos e catálogos; a FastAPI retorna seu fingerprint.
Antes de pedir prévia, o NestJS exige que a proposta confirmada tenha
o mesmo fingerprint atual e ainda não tenha vencido. Isso também impede
usar uma resposta cacheada com um contexto de plano que mudou.

Os catálogos são lidos com o cliente RLS do usuário, somente id/nome.
Uma consulta chegando ao limite de 1000 itens é rejeitada em vez de usar
catálogo silenciosamente incompleto; paginação maior é trabalho futuro.
As leituras do plano usam os serviços existentes com filtro de proprietário.
Os dados pessoais completos usados para calcular a revisão não são
enviados ao LM nem incluídos no snapshot HTTP.

O NestJS aceita as quatro ações conhecidas com os campos exatos:
mover treino, substituir exercício, substituir alimento e atividade do dia.
Valida UUIDs, enumerações, campos necessários, source=coach e rejeita
SQL/chaves extras. Texto de resposta nunca é executado.

Cada sessão tem operação serializada. A associação proposta → ajuste fica
em memória e impede duplicar a prévia ao repetir a mesma confirmação.
O usuário só pode aplicar/rejeitar/reverter ajustes associados à própria
sessão, e o Planner ainda verifica propriedade, estado, conflitos e
validade por suas rotas/RPCs existentes.

Sessões e associações são temporárias: limite de 32 sessões e validade
ociosa de 30 minutos. Reiniciar o NestJS perde as associações. Uma falha
após gravar uma prévia mas antes de receber seu ID pode deixar uma prévia
pendente duplicada numa repetição; não há garantia durável exatamente uma
vez nesta fase. Não há aplicação automática dessa prévia. Histórico e
idempotência persistente devem ser tratados na 7.06.3.

O timeout maior é restrito ao Coach; os outros endpoints mantêm o padrão.
O timeout HTTP não garante cancelamento da geração nem prova que uma
operação no servidor falhou. O cliente deve recuperar estado antes de
repetir uma aplicação. Não há repetição automática de chamadas pela ponte.

## Verificação realizada

- Build TypeScript passou.
- Lint dos arquivos novos e do timeout/config passou sem avisos.
- 22 testes do backend passaram, cobrindo ponte, contexto, timeout e
  regressões do Planner.
- 14 testes HTTP da FastAPI passaram, incluindo ator/contexto inválidos.
- 14 checks entre NestJS e FastAPI reais passaram em loopback.

Registro final: ai/artifacts/backend_coach/1.0.2/.
Os registros 1.0.0 e 1.0.1 são conferências intermediárias anteriores à
formatação e aos ajustes finais.

A conferência HTTP executou o guard real do NestJS, porém a validação
Supabase de token e o Planner/banco foram substituídos por fixtures.
A fixture Python usa entidades reais e intenção conhecida simulada,
sem Qwen. Portanto, comprova integração HTTP, validação e encaminhamento
de prévia/aplicação; não mede qualidade do NLP ou executa escrita real
no Supabase. Os servidores temporários foram encerrados.

O Qwen por HTTP já foi conferido na 7.06.1. A baixa confiança observada
na 7.05 continua podendo impedir propostas no modelo real: não alteramos
pesos ou limiares para fazer os testes passarem.

## Próximas fases

7.06.3: persistir conversas e associações no Supabase, com RLS.
7.06.4: conectar o Mobile às rotas, prévias e confirmações.
7.06.5: avaliar a cadeia completa com a infraestrutura e ações reais
em ambiente de teste apropriado.

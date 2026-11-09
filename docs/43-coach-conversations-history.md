# 7.06.3 — Conversas e histórico no Supabase

Implementado e verificado em 2026-11-02, inclusive no Supabase remoto.
Usamos as tabelas existentes coach_conversations e coach_messages.
Não foi necessária migration nem alteração dos tipos gerados do banco.

## Mapa

    JWT do usuário → NestJS → Supabase com RLS
                       ↓
    conversa permanente + mensagens + respostas por request_id
                       ↓ ao retomar
    sessão temporária nova na FastAPI + quatro pares recentes
                       ↓
    contexto do plano atualizado + Coach

- backend/src/coach/coach-history.service.ts: persistência, consulta e vínculos.
- backend/src/coach/coach.service.ts: usa IDs permanentes e retoma o runtime.
- backend/src/coach/coach.controller.ts: listagem, histórico, título e exclusão.
- ai/src/evolv_api/app.py: restauração interna de histórico, versão 1.2.0.
- backend/test/fixtures/coach-postgres.ts: PostgreSQL embarcado dos testes.
- backend/scripts/verify-coach-history.mjs: integração HTTP e reinício.
- backend/scripts/verify-coach-history-remote.mjs: conferência remota com contas temporárias.

## IDs e recuperação

O session_id público agora é o ID permanente de coach_conversations,
também retornado como conversation_id. O ID efêmero da FastAPI fica no
backend. Reiniciar ou expirar o runtime não apaga a conversa no Supabase.

Ao retomar, o backend verifica o proprietário, cria outra sessão de IA e
restaura até quatro pares completos recentes de usuário/assistente. Depois
renova o snapshot do plano. IDs/configurações da conversa ficam em uma
mensagem system de metadata conhecida; não são usados como instruções do LM.
O histórico público exclui esse registro de configuração.

A FastAPI aceita somente pares completos user/assistant, até oito mensagens.
Não aceita system. Também minimiza identificadores reconhecidos e limpa
propostas e autorizações antigas ao restaurar. O limite bruto dessa rota
interna é 256 KiB, mantendo o limite de 64 KiB das mensagens novas.

Propostas pendentes antigas podem continuar visíveis no histórico como
registro, mas não são reativadas no runtime. É necessário solicitar uma
proposta nova quando a anterior não existir mais na sessão da IA.
Isso evita transformar uma conversa salva em autorização de execução.

## Rotas

JWT Supabase obrigatório em todas as rotas. Prefixo padrão: /api.

| Rota | Função |
|---|---|
| POST /coach/sessions | cria conversa permanente, mesmo sem carregar o LM |
| GET /coach/sessions?limit=30&offset=0 | lista conversas do usuário |
| GET /coach/sessions/{id}/messages?limit=30&offset=0 | consulta mensagens |
| PATCH /coach/sessions/{id} | renomeia, corpo {"title":"Meu treino"} |
| DELETE /coach/sessions/{id} | exclui a conversa e mensagens |
| POST /coach/sessions/{id}/messages | envia mensagem, persiste o par e resposta |

Paginação: limit de 1 a 100 e offset de 0 a 100000. Listas são ordenadas
da mais recente para a mais antiga, com ID como critério de desempate.
O Mobile deverá ordenar para apresentação da conversa. Paginação por
offset pode deslocar itens se novas mensagens forem inseridas entre páginas.

DELETE agora exclui histórico persistente: não é apenas fechar uma janela
ou limpar memória. O Mobile deve apresentar essa intenção com clareza.
As mensagens são removidas em cascata pelo FK existente. Perfil, planos,
memórias/preferências independentes e ajustes do Planner não são apagados.
Os ajustes mantêm seu histórico próprio; o FK remove a associação à conversa.
O backend tenta limpar também o runtime conhecido, sem impedir a exclusão
do banco se a IA estiver indisponível.

## Gravação e repetição

O backend grava o texto minimizado do usuário e a resposta como um único
INSERT/upsert de duas linhas no PostgREST, transacional. Não fica um par
pela metade por erro numa das linhas da operação.

IDs de mensagem são derivados de usuário, conversa, request_id e papel.
Repetir o mesmo request_id não cria outras linhas. O hash da entrada
detecta reutilização do mesmo ID com texto/proposta diferentes e retorna
conflito. A resposta salva permite repetir uma chamada após reiniciar o
NestJS sem gerar novamente nem aplicar uma ação.

Metadata guarda o request_id, hash e envelope da resposta para recuperação.
Esse conteúdo é privado ao usuário, pode conter informações sensíveis e
não constitui dado anônimo. O processo não escreve JWTs, chaves de serviço
ou credenciais nos registros. O texto novo passa por minimização de
e-mail, CPF, telefone e links; isso não reconhece todos os dados pessoais.

A confirmação de uma proposta continua separada da aplicação do ajuste.
A associação de proposta a prévia usa conversation_id e metadata do
requested_change do Planner. Assim, um reinício do backend não precisa
da associação só em memória para verificar propriedade de um ajuste.

Ainda não há transação única entre gerar, criar prévia, vincular e salvar
mensagens. Uma falha após inserir prévia e antes de vinculá-la pode deixar
prévia órfã; concorrência entre múltiplas instâncias também pode criar
prévias duplicadas. Duplicidade detectada bloqueia a recuperação automática.
Isso não autoriza aplicação sem confirmação. A implantação atual deve
manter um processo de backend; garantias distribuídas exigem reforço futuro.

## Acesso e uso dos dados

Todas as operações da aplicação usam forUser(accessToken), UUID derivado
do guard autenticado e filtros explícitos de proprietário, além do RLS
existente. O backend nunca usa service_role para atender conversas.
O trigger existente também impede que uma mensagem do usuário B aponte
para uma conversa do usuário A.

Salvar para continuidade do serviço não autoriza treinamento. Nenhum
dataset, corpus, peso ou rotina de treinamento foi conectado às conversas.
Não há exportação automática para treino.

Exclusão funcional não representa promessa de apagamento imediato de
backups ou de todas as cópias em memória de processos indisponíveis.
Essas políticas de produção precisam ser definidas antes do lançamento.

## Verificações

- Build TypeScript passou.
- Lint dos arquivos do Coach e fixture PostgreSQL passou sem avisos.
- 29 testes backend passaram, incluindo PostgreSQL/RLS e Planner.
- 16 testes HTTP FastAPI passaram, incluindo restauração sem system/propostas.
- 20 checks HTTP integrados passaram com NestJS, FastAPI e PostgreSQL embarcado.
- Oito checks passaram no Supabase remoto com dois usuários temporários.

A conferência remota testou criação/configuração, par de mensagens,
deduplicação, isolamento entre usuários, referência de proprietário
incorreto, retomada por outra instância do repositório, título e exclusão
em cascata. As duas contas e seus dados de teste foram removidos.
Nenhum dado de usuários existentes foi alterado.

Na integração local, intenção/confiança são explícitas de teste e o
Planner de domínio é simulado, mas as operações do repositório executam
SQL e as políticas RLS originais em PostgreSQL. O reinício testado recria
a aplicação NestJS mantendo o banco; o novo runtime recebe o histórico.
Esses checks não medem accuracy do NLP ou qualidade de geração.

Registros:

    ai/artifacts/coach_history/1.0.1/
    ai/artifacts/coach_history/remote-verification.json
    ai/artifacts/coach_history/remote_probe.json

A primeira tentativa de consultar o SQL remoto pela CLI falhou ao criar
login role administrativo. Como não houve migration, a validação foi
concluída pela Data API autenticada. As contas temporárias foram criadas
e removidas por uma chave administrativa capturada só em memória pelo
verificador. Essa chave não foi salva nem usada pelo backend da aplicação.

O registro 1.0.0 é uma conferência intermediária.
Para rodar testes a partir de backend/:

    npm test -- src/coach src/common/interceptors/request-timeout.interceptor.spec.ts src/planner/planner-adjustments.service.spec.ts

Os conjuntos totalizam 45 testes automatizados (29 backend + 16 FastAPI), além dos checks
integrados e remotos. Eles não devem ser apresentados como uma medida
única de qualidade do Coach.

O Mobile foi conectado na 7.06.4 (docs/44-coach-mobile-integration.md). Os limites de confiança,
recuperação e qualidade identificados na 7.05 permanecem.

Referência das políticas de acesso:
https://supabase.com/docs/guides/database/postgres/row-level-security

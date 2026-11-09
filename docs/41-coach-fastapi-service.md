# 7.06.1 — Serviço de IA pela FastAPI

Implementado e conferido em 2026-11-02. O Coach agora pode ser chamado por
HTTP local. O teste usou Uvicorn real, NLP, busca e Qwen original, sem
conectar ao NestJS, Mobile, Supabase ou Planner.

## Mapa dos arquivos

- ai/src/evolv_api/app.py: rotas, autenticação interna, sessões e recursos.
- ai/scripts/serve_coach.py: inicia em 127.0.0.1:8010, com um worker.
- ai/requirements.api.txt: versões das dependências HTTP.
- ai/tests/test_coach_api.py: 12 testes HTTP com componentes controlados.
- ai/scripts/verify_coach_api.py: conferência real temporária em loopback.
- ai/artifacts/coach_api/1.0.0/: resultado real e hashes.

    Backend autenticado (integração na 7.06.2)
       ↓ Bearer interno + UUID do usuário derivado do JWT pelo backend
    FastAPI → sessão isolada → Coach/NLP → busca → Qwen
       ↓
    resposta estruturada, fontes, diagnósticos e propostas quando disponíveis

## Executar

No PowerShell, usando o ambiente que já executou os modelos:

    cd "C:\Users\ganto\OneDrive\Área de Trabalho\Evolv-app"
    & "C:\Users\ganto\Documents\Codex\2026-09-09\to\.venv-evolv-review\Scripts\python.exe" -m pip install -r ai/requirements.api.txt
    $env:EVOLV_AI_SERVICE_KEY = & "C:\Users\ganto\Documents\Codex\2026-09-09\to\.venv-evolv-review\Scripts\python.exe" -c "import secrets; print(secrets.token_urlsafe(32))"
    & "C:\Users\ganto\Documents\Codex\2026-09-09\to\.venv-evolv-review\Scripts\python.exe" ai/scripts/serve_coach.py

A chave fica na variável de ambiente dessa sessão. Na próxima fase o NestJS
usará a mesma chave no lado servidor. Não colocar a chave no Mobile,
variável pública de frontend, repositório ou mensagens do Coach.

Padrão: EVOLV_AI_VARIANT=original e EVOLV_AI_MODE=generate.
Para experimento explícito com o LoRA, definir EVOLV_AI_VARIANT=adapted
antes de iniciar. EVOLV_AI_MODE=analyze carrega NLP e busca sem Qwen.
Não há download de modelos. Geração exige o ambiente CUDA existente.

O carregamento ocorre no lifespan da aplicação, uma vez por processo.
O Uvicorn só atende depois da etapa de inicialização. Caso o carregamento
falhe, a aplicação permanece com readiness 503 e precisa ser reiniciada
após corrigir o ambiente. Importar o módulo não carrega modelos.

Documentação de rotas: http://127.0.0.1:8010/docs

## Rotas

| Método e caminho | Finalidade |
|---|---|
| GET /health/live | Processo HTTP responde; não certifica modelos |
| GET /health/ready | Modelos disponíveis; exige chave de serviço |
| POST /v1/sessions | Cria sessão; corpo {} |
| POST /v1/sessions/{id}/messages | Envia mensagem e, opcionalmente, ID da proposta |
| DELETE /v1/sessions/{id} | Descarta histórico, pendência e cache da sessão |

Nas rotas de sessão, enviar:

    Authorization: Bearer CHAVE_INTERNA
    X-Evolv-User-ID: UUID_DO_USUARIO

O serviço confia nesse cabeçalho somente porque exige a credencial interna.
Ele não verifica o JWT do Supabase nesta fase. O próximo backend deve
verificar o JWT, derivar o UUID autenticado e substituir qualquer identidade
recebida do cliente. A posse da chave interna concede autoridade de serviço.
O serviço está restrito ao loopback no inicializador fornecido.

Exemplo de corpo de mensagem:

    {
      "request_id": "b9493062-826c-478b-84a4-7408e2b4f48f",
      "text": "Quanto tempo um adulto deve dormir?"
    }

request_id é um UUID novo por mensagem lógica; reutilizar o mesmo UUID
ao repetir a mesma mensagem por falha de rede. proposal_id é opcional e
é um UUID de proposta pendente, não texto extraído de uma resposta.
Campos extras, como user_id, SQL, system_prompt ou planner_snapshot,
são rejeitados. A API atual não recebe contexto de plano; a 7.06.2
precisará obtê-lo de forma autenticada. Não inventamos IDs para permitir ações.

A resposta contém session_id, request_id e result. result preserva
answer, analysis, retrieval, generation, citations, safety, actions e planner.
Uma chamada HTTP bem-sucedida não significa que o modelo deu resposta
correta ou concluiu um pedido de alteração. Os gargalos da 7.05 continuam.

## Recursos, isolamento e privacidade

Modelos são compartilhados por todas as sessões do processo. Histórico,
propostas e cache de requisições pertencem a cada sessão e usuário.
Tentativas de acessar uma sessão de outro usuário recebem o mesmo 404
de uma sessão inexistente.

Uma operação por vez acessa os componentes compartilhados, inclusive a
GPU. Uma chamada concorrente recebe 429/service_busy com Retry-After,
sem criar fila de gerações. Chamadas de saúde continuam leves.
Usar apenas um worker e sem reload; múltiplos workers duplicariam pesos
e separariam a memória das sessões.

Limites: 32 sessões globais, oito por usuário, 8000 caracteres por mensagem
e 65536 bytes no corpo HTTP, inclusive upload em partes. O texto não pode
ser vazio ou só espaços. Erros de validação não repetem a entrada recebida.

A sessão expira logicamente após 30 minutos sem uso. A remoção física
é preguiçosa, na próxima operação de sessão, ou no desligamento; não
prometemos apagar bytes exatamente no instante do vencimento. DELETE
limpa o estado imediatamente quando não há operação em curso.

O cache em memória guarda as últimas oito respostas por sessão. Mesmo
request_id e mesmo conteúdo devolvem a resposta já calculada, sem novo
turno ou geração. Mesmo ID com conteúdo diferente retorna 409. Após
expiração/remoção do cache, não há garantia de deduplicação durável.
Isso será responsabilidade do backend para operações persistentes.

Falhas de processamento restauram histórico e pendência ao estado anterior
do turno e devolvem erro genérico. Não retornamos traceback, caminhos
locais, credenciais nem mensagens internas de exceção. O inicializador
desliga access logs. Não há gravação automática de conversas ou autorização
automática para treinamento.

Não há cancelamento forçado da thread de geração ao desconectar o cliente.
Uma geração em andamento pode terminar e manter seu resultado na sessão.
O consumidor deve reutilizar request_id ao tentar novamente.

## Validação

12 testes HTTP passaram usando TestClient e componentes controlados:
saúde, chave, carregamento único, propriedade, isolamento, validação,
limite de corpo, duplicatas/conflitos, ocupação, expiração/exclusão,
capacidade, rollback e indisponibilidade dos modelos.

A conferência real iniciou um Uvicorn temporário, carregou os modelos,
criou sessão, gerou uma resposta, conferiu a repetição idempotente,
bloqueou outro UUID e excluiu a sessão. O servidor foi encerrado.
A chave temporária não foi gravada no relatório.

A resposta do Qwen original chegou ao limite de 256 tokens e ficou
incompleta; o diagnóstico stopped_at_eos=false foi preservado. A verificação
aprova funcionamento HTTP, não qualidade dessa resposta ou produção.
Os tempos observados estão em artifacts/coach_api/1.0.0/verification.json.

Para rodar os testes, a partir de ai/:

    python -m unittest discover -s tests -p test_coach_api.py -v

Para nova conferência real, usar uma nova versão/pasta no script de
verificação; o registro atual é preservado e não pode ser sobrescrito.

O NestJS ainda não chama este serviço. Seu timeout atual de 15 segundos
deve ser revisto na 7.06.2 conforme as latências locais, sem fingir que
uma geração terminou só porque uma chamada HTTP excedeu o prazo.
Histórico durável e RLS continuam na 7.06.3.

## Referência técnica

O uso de lifespan para compartilhar modelos entre requisições segue a
documentação oficial: https://fastapi.tiangolo.com/advanced/events/

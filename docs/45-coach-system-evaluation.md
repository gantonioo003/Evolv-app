# 7.06.5 — Avaliação do sistema integrado

Avaliação de desenvolvimento em 03/11/2026. A integração foi exercitada com
serviços, modelos e banco reais. Isso não aprova o Coach para lançamento:
a principal limitação encontrada é a capacidade de entender/concluir pedidos.

## O que foi executado

    Interface Expo web autenticada
        → NestJS completo
        → Supabase remoto, RLS e histórico
        → FastAPI, NLP congelado, extrator e busca semântica
        → Qwen original NF4 na RTX 5050 Laptop de 8 GB

Dois conjuntos completos usaram 24 mensagens isoladas e duas conversas de dois
turnos cada: perguntas educativas, cinco riscos, privacidade, duas tentativas
de injeção, quatro pedidos de mudança, pedidos negados/hipotéticos e ambiguidade.
Uma regressão posterior focou autenticação, link direto e confirmação na web.

Nenhuma mensagem de usuário existente foi utilizada. Cada execução criou duas
contas temporárias, com um plano de treino próprio. Tokens e chave interna
ficaram em memória. Não houve treino novo ou mudança dos limiares do NLP.

## Resultados das rodadas completas

| Medida | Antes | Após instrução mais curta |
| --- | ---: | ---: |
| Mensagens isoladas com HTTP concluído | 24/24 | 24/24 |
| Perguntas educativas que chegaram à geração | 4/8 | 4/8 |
| Gerações que terminaram antes do limite | 0/4 | 4/4 |
| Gerações com citação | 3/4 | 4/4 |
| Riscos esperados identificados, nos cinco casos | 5/5 | 5/5 |
| Pedidos de mudança com proposta correta | 0/4 | 0/4 |
| Tempo médio dos pedidos com geração | 29,46 s | 14,49 s |
| p50, mistura de rotas | 4,11 s | 3,23 s |
| p95, mistura de rotas | 29,79 s | 15,24 s |
| Pico RAM IA, RSS | 3,26 GiB | 3,26 GiB |
| Pico RAM NestJS, RSS | 124,60 MiB | 129,24 MiB |
| Pico CUDA alocado pelo PyTorch | 4,03 GiB | 4,03 GiB |
| Pico CUDA reservado pelo PyTorch | 5,48 GiB | 4,65 GiB |

A instrução de geração passou a pedir até três frases/90 palavras, mantendo
o orçamento de 256 tokens. Não é um novo modelo. O carregamento observado foi
51,88 s e 29,95 s, com diferenças de cache/estado da máquina entre rodadas;
não se deve atribuir essa diferença de startup à instrução textual.

As latências incluem HTTP local, NestJS, acesso remoto ao banco e processamento.
p95 usa nearest-rank em somente 24 mensagens, misturando guardas rápidos e
geração. Não mede primeiro token, rede móvel, múltiplos usuários ou SLA.
RAM foi amostrada a cada segundo; os picos CUDA são do alocador PyTorch, sem
certificar consumo total de driver/outros processos. Memória reservada inclui
cache e não deve ser somada à alocada.

## Ações reais: distinção importante

O classificador não autorizou proposta em nenhum dos quatro pedidos naturais.
O sistema pediu esclarecimento e não alterou o plano. Isso evita execução
incerta, mas é falha em concluir a tarefa solicitada, não sucesso do Coach.

Separadamente, o Planner real foi testado:

- criar prévia de descanso sem alterar a atividade;
- aplicar a atividade no Supabase e desfazer, verificando o estado original;
- criar prévia de mudança de terça para quinta no plano temporário;
- abrir a prévia na interface web, clicar em Confirmar e conferir a mudança
  no banco; clicar em Desfazer e conferir o retorno ao estado original.

Esses ciclos verificam o caminho Mobile → backend → Planner → banco.
Não são contados como propostas bem-sucedidas produzidas pelo NLP. O fluxo
Coach → proposta → aplicação continua coberto por testes de contrato com
intenção conhecida e não teve conclusão positiva nos pedidos naturais desta
avaliação. Não baixamos a confiança para fazer o teste passar.

## Segurança e privacidade observadas

Chamadas sem login foram recusadas; o cliente não conseguiu informar outro
proprietário; outro usuário não leu mensagens pela API ou diretamente pela
Data API do Supabase; a API interna exigiu chave e respeitou propriedade.
O mesmo request_id recuperou a resposta persistida, e o mesmo ID com texto
diferente foi recusado. Pedir exclusão no chat não apagou dados.

Nos cinco exemplos de risco, não houve geração nem proposta: emergência,
alergia, dor, desidratação extrema e hormônios. O seguimento sobre alergia
preservou o sinal anterior. Pedidos negados, hipotéticos e os dois exemplos
de injeção não criaram ação. Isso não constitui teste de penetração, auditoria
LGPD ou garantia sobre toda formulação possível.

A resposta de privacidade do backend foi corrigida para explicar que o
histórico fica salvo na conta. O envelope agora informa persistência no
Supabase e Planner conectado, sem conceder permissão de escrita ao modelo.
O chat não registra consentimento de treino nem exporta conversas para datasets.

## Correções encontradas pela avaliação

1. Texto de privacidade ainda descrevia o protótipo somente em memória:
   corrigido na fronteira autenticada do NestJS, com teste de regressão.
2. As quatro gerações eram cortadas: instrução de concisão reduziu os textos
   para uma média de 94,75 tokens, com quatro finalizações EOS observadas.
3. A abertura direta de uma prévia iniciava consulta antes de restaurar a
   sessão, deixando um aviso de login antigo. A tela agora aguarda a sessão
   e limpa o erro quando carrega a prévia com sucesso.
4. O servidor estático do avaliador usava index.html em uma rota dinâmica:
   passou a usar o HTML exportado da própria rota de ajuste. O erro de
   JavaScript registrado na rodada 1.0.1 permanece preservado; o novo teste
   de navegador verifica a correção sem apagar o resultado anterior.

## Qualidade: o que ainda falta

Revisão qualitativa assistida por IA, sem avaliador humano independente:

- Quatro de oito perguntas educativas receberam esclarecimento genérico,
  incluindo sobrecarga progressiva, séries/repetições, substituição e deload.
- O seguimento sobre aumentar carga também não foi resolvido; histórico
  persistido não garante entendimento de contexto.
- A resposta sobre proteína acompanha o trecho recuperado, e a de horário
  de refeição usa o contexto correspondente. Ambas ficaram mais curtas.
- A resposta sobre sono ainda afirma reparação/regeneração antes de admitir
  que faltam evidências de mecanismo. Esses mecanismos não aparecem nos
  dois trechos entregues. A fundamentação dessa afirmação não foi aprovada.
- A comparação entre cardio e musculação recuperou um trecho amplo de saúde
  e apresentou diferenças mais específicas. Citar um ID válido não prova
  que o trecho sustenta cada afirmação.

Os próximos ganhos devem vir de cobertura/roteamento, esclarecimentos úteis,
recuperação mais específica e avaliação de fidelidade, sem maquiar o resultado
nem reduzir os bloqueios de ação. Não foi calculada nova accuracy/F1 de NLU;
os testes congelados e pesos das fases anteriores foram preservados.

## Arquivos e reprodução

| Caminho relativo à raiz | Função |
| --- | --- |
| ai/data/evaluation/coach_system.v1.json | Protocolo de desenvolvimento. |
| backend/scripts/evaluate-coach-system.mjs | Orquestra serviços, contas temporárias, HTTP e navegador reais. |
| ai/scripts/serve_coach_evaluation.py | Inicializa o Coach real e mede RSS/CUDA. |
| ai/scripts/report_coach_system.py | Compara as duas rodadas completas. |
| backend/src/coach/coach.service.ts | Descreve a persistência e privacidade reais do aplicativo. |
| mobile/src/app/adjustments/[adjustmentId].tsx | Aguarda restauração da autenticação ao abrir uma prévia. |
| ai/artifacts/system_evaluation/1.0.0/ | Primeira observação, preservada. |
| ai/artifacts/system_evaluation/1.0.1/ | Rodada completa após concisão; comparação e resultados. |
| ai/artifacts/system_evaluation/1.0.2/ | Regressão dirigida do link/confirmar/desfazer. |

O avaliador requer o ambiente Python existente, Supabase CLI autenticada,
Playwright/Edge, backend compilado e export web local apontando para a porta
3199. EVOLV_TEST_PYTHON, EVOLV_SUPABASE_CLI e NODE_PATH indicam os executáveis;
EVOLV_EVALUATION_VERSION seleciona uma pasta nova. Ele recusa sobrescrever
uma execução registrada. EVOLV_EVALUATION_CASE_IDS permite regressão dirigida,
e EVOLV_EVALUATION_WEB seleciona o export. Não salvar credenciais nesses valores.

O export é apenas uma ferramenta local de avaliação, ignorada pelo Git.
Nenhum arquivo privado de ambiente foi alterado nem aplicativo publicado.

## Limites de encerramento

A avaliação do sistema foi executada e os gargalos estão documentados. Isso
fecha o experimento de integração, mantendo o produto em desenvolvimento.
Não houve teste nativo em iPhone físico, teclado/áreas seguras reais, carga
sustentada, falhas de rede móvel, auditoria profissional de saúde ou aprovação
para comercialização. Essas verificações não podem ser substituídas por uma
janela de navegador com tamanho de celular.

Os registros finais de limpeza, testes e hashes ficam em
ai/artifacts/system_evaluation/completion.json.

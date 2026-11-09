# 7.07.5 — Validação de mudanças pelo Coach

Data: 03/11/2026. Escopo: pedidos naturais, proposta, prévia, confirmação,
aplicação e desfazer. A avaliação usa serviços e banco reais, exclusivamente
com planos de duas contas temporárias. Não acessa planos de usuários existentes.

## Configuração e reprodução

O serviço aceita `EVOLV_AI_NLP_VERSION=1.9.0` para selecionar explicitamente
o reconhecimento desenvolvido na 7.07.3. Sem a variável, continua em 1.8.0.
Uma versão desconhecida falha na inicialização; não existe fallback silencioso.
`GET /health/ready`, autenticado pela chave interna, informa a versão selecionada.
Não se alteraram pesos, limiares de confiança ou regras para aprovar estes casos.

O teste usa `EVOLV_AI_MODE=analyze`: os classificadores, o extrator, as regras,
o carregamento do RAG, a FastAPI, o NestJS, o histórico e o Planner são reais.
A geração do Qwen está desativada porque este roteiro verifica alterações de
plano e respostas determinísticas de confirmação. Não é avaliação de qualidade
de respostas geradas, nem comparação de modelos, nem nova medição de F1.

Execução a partir de `backend/`, após `npm run build`:

```powershell
$env:EVOLV_TEST_PYTHON = '<python do ambiente de IA>'
$env:EVOLV_SUPABASE_CLI = '<supabase.exe autenticado neste projeto>'
$env:NODE_PATH = '<node_modules que contém playwright>'
$env:EVOLV_ACTION_FLOW_VERSION = '<versão nova, por exemplo 1.0.3>'
node scripts/evaluate-coach-action-flow.mjs
```

O roteiro usa `.env` do backend em memória, nunca imprime credenciais, cria
usuários com credenciais aleatórias e os exclui em `finally`. A administração
somente cria/remove contas temporárias; chamadas do aplicativo usam o token
do usuário. Chave interna aleatória, portas locais e subprocessos são isolados.
Nenhuma configuração privada de execução foi editada.

O navegador usa a exportação existente de Mobile em
`ai/artifacts/system_evaluation/1.0.2/web`, com API local na porta 3199.
Não há interceptação de rede, troca de rótulos por fixture ou prévia manual
na conferência da tela do Coach. A sessão autenticada é a de uma conta real
temporária. A exportação é anterior a esta etapa; não houve mudança visual.

## Casos e verificações

O roteiro declara os casos antes de consultar o modelo. Testa seis pedidos
completos: duas formas de mover terça para quinta, descanso, cardio, troca
de exercício e troca de alimento. Os nomes das duas trocas vêm dos planos
gerados: primeiro exercício substituto compatível e não usado naquele dia;
primeiro alimento único com substituição previamente calculada. A seleção
não consulta as previsões para procurar uma frase que passe.

Também testa seis bloqueios: destino ausente, exercício substituto ausente,
data ausente, negação, hipótese e relato urgente. Há conversas adicionais para
recusa, identificador incorreto e proposta invalidada por modificação do plano.
São casos de desenvolvimento, alguns já usados no diagnóstico; não constituem
amostra independente nem estimativa de desempenho populacional.

Para cada proposta correta, a versão final verifica:

1. O plano permanece igual após mensagem e prévia.
2. O payload corresponde ao pedido e usa os IDs do plano autenticado.
3. `confirmed:false` e aplicação por outra conta são recusados.
4. Confirmar explicitamente muda o estado real para o dia/atividade solicitados.
5. Repetir a aplicação é recusado e não modifica novamente o estado.
6. Desfazer restaura o estado anterior.
7. Mensagens e respostas ficam no histórico da conta temporária.

Na tela do Coach, o navegador envia a frase natural e aciona **Ver prévia →
Revisar ajuste → Confirmar alteração → Desfazer alteração**. O teste consulta
o plano no backend entre os cliques, além de capturar quatro imagens.

O teste de plano desatualizado faz uma alteração manual controlada somente
para provocar a divergência do snapshot. Essa operação é desfeita em `finally`
e não conta como sucesso de reconhecimento do Coach.

## Rodadas e resultados

Os artefatos ficam em `ai/artifacts/coach_action_flow/`, sem sobrescrever rodadas.

- **1.0.0:** impedimento de execução do CLI no sandbox; nenhum usuário criado.
- **1.0.1:** os 12 casos e o ciclo pelo navegador executaram. Três pedidos
  produziram propostas e completaram aplicação/desfazer. Seis verificações
  falharam por dois erros do roteiro repetidos em três ciclos: campo `kind`
  em vez de `adjustment_kind`; HTTP 409 esperado exclusivamente, embora
  o contrato existente use HTTP 400 para reaplicar um ajuste já resolvido.
  As falhas originais foram preservadas. Duas contas criadas e excluídas.
- **1.0.2:** rodada final com esses contratos corrigidos, verificação do payload
  e estado exatos, além de hashes dos datasets/classificadores antes e depois.
  **92 verificações aprovadas, zero falhas; 12 casos processados e três ciclos
  reais de aplicação/desfazer.** O navegador também completou o ciclo pelo Coach
  sem erros JavaScript. Duas contas criadas e excluídas. O resultado definitivo
  está em `1.0.2/results.json`; o histórico das falhas anteriores foi mantido.

| Pedido | Resultado observado |
| --- | --- |
| Mover treino usando datas explícitas | Proposta, prévia, aplicação e desfazer |
| Mover treino usando terça/quinta | Proposta, prévia, aplicação e desfazer |
| Definir dia de descanso | Proposta, prévia, aplicação e desfazer |
| Definir cardio | Esclarecimento por confiança insuficiente |
| Trocar Afundo por Agachamento bulgaro | Intenção correta, confiança insuficiente |
| Trocar Ovo por Tofu | Classificou update_goal sem confiança; pediu esclarecimento |

Os bloqueios não foram contados como sucesso de alteração. O fluxo de mudança
está demonstrado para remarcação e descanso; a cobertura natural das trocas e
de cardio ainda precisa melhorar. Não baixamos a confiança para ocultar isso.

## Limites e próximos trabalhos

- Nenhuma promoção automática do reconhecimento 1.9.0 ao aplicativo padrão.
  Para experimentar a nova versão na FastAPI, é necessário o opt-in acima.
- Não há retreino, nova accuracy/F1 ou abertura do teste congelado nesta etapa.
- A verificação conserva datasets, pesos e políticas por hashes; não revisa
  os rótulos das mensagens usadas nos testes de classificação.
- Testar via navegador em 430 × 932 não substitui o iPhone físico, deixado
  para a última etapa conforme combinado.
- Esclarecimentos ainda não acumulam campos persistentes de respostas curtas.
- Faltam as próximas etapas de conhecimento, busca, respostas fundamentadas,
  contexto conversacional e avaliação final. Esta validação não certifica
  qualidade geral nem prontidão para lançamento.
- A resposta determinística de proposta ainda exibe o nome técnico da ação;
  melhorar sua redação é trabalho de apresentação, não autorização do Planner.

Validação local: 72 testes de Coach/FastAPI (incluindo três novos testes de
seleção de versão) aprovados; backend compilado; JavaScript do roteiro válido.
As duas incompatibilidades históricas descritas na 7.07.4 não foram modificadas
nem reinterpretadas como testes aprovados nesta etapa.

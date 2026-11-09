# 7.07.11 — Avaliação final do Coach no computador

08/11/2026

A versão web atual foi exportada e testada no Edge com uma janela de
1366 × 900. A avaliação conectou Expo Web, NestJS, FastAPI e Supabase.
O Coach usou NLP 1.9.0 selecionado explicitamente, busca 1.1.1 e Qwen
original em NF4. Usamos contas, mensagens e planos temporários. Os critérios
do roteiro foram registrados antes da execução. Alguns exemplos vêm das
etapas de desenvolvimento anteriores.

## Conclusão de tarefas

| Tarefa | Resultado da rodada completa |
| --- | --- |
| Processar mensagens | 33/33 mensagens isoladas e 13/13 turnos em seis conversas. |
| Responder perguntas educativas | 8/12 tiveram conteúdo que responde ao pedido. Uma dessas oito incluiu aviso de lacuna indevido. |
| Alterar o plano | 3/4 pedidos completaram proposta, prévia, confirmação, aplicação e desfazer. Foram duas remarcações e um descanso. Cardio ficou em esclarecimento. |
| Proteger ações | Nos três ciclos o estado ficou igual até aplicar. Outra conta, confirmação falsa e reaplicação foram recusadas. Desfazer restaurou o estado original. |
| Segurança, privacidade e injeção | 7/7 riscos isolados encaminhados sem geração. Os quatro pedidos de privacidade receberam a explicação do histórico. Pedidos negados, ambíguos e tentativas de injeção ficaram sem proposta. |
| Usar histórico | Alimentação noturna e mudança explícita para séries funcionaram. Alergia e urgência foram preservadas no seguimento. A referência de exercício pediu o nome. Preferência de horário e continuação sobre progressão ficaram sem solução. |
| Interface no Edge | Envio autenticado, histórico reaberto e fonte exibida. A prévia aberta por link no navegador completou aplicar e desfazer. |

Passaram **50 verificações operacionais**, incluindo isolamento de histórico
no NestJS e na Data API do Supabase. A rodada excluiu as duas contas
temporárias. Também passaram 12 testes do serviço e contexto do Coach no
NestJS, 33 testes do app e a checagem de tipos.

## Qualidade das respostas

A revisão considera se o texto resolve a pergunta e se a fonte exibida
sustenta a resposta. Receber HTTP 201 indica que a mensagem foi processada.
A revisão é assistida e usa o roteiro de desenvolvimento. Seus resultados
medem conclusão nas frases testadas.

As sete respostas completas cobriram séries, sono, proteína, duas perguntas
sobre refeições pré-treino, deload e efeitos de combinar cardio com
musculação. A pergunta sobre peso estável recebeu o trecho correto e um
aviso indevido de que parte da pergunta ficou sem resposta. As dúvidas
sobre sobrecarga progressiva, substituição de arroz e diferenças entre cardio
e musculação pararam no NLP. A pergunta sobre hidratação chegou à busca,
que trouxe trechos de outros assuntos, e o Qwen indicou a lacuna.

### Correção de hidratação

O trecho `hydration_is_individual` já estava na base. A busca 1.1.2 aproxima
“beber água” de “hidratação”, “líquido” e “suor” na pontuação por palavras
quando a pergunta trata de ingestão de água durante atividade física. A
seleção do Qwen usa a pergunta original e o índice conserva os 107 trechos.

A fonte ficou em primeiro lugar nas cinco formulações de hidratação, contra
uma de cinco na busca anterior. A ordem dos trechos foi idêntica nos quatro
controles e nos 104 casos arquivados da busca. A FastAPI com o NLP padrão
1.8.0 recuperou a fonte nas três formulações exercitadas em modo de análise.

O caso original foi repetido de ponta a ponta com busca 1.1.2. O Coach
explicou que a necessidade de líquido depende da situação e da pessoa.
O navegador mostrou o link **Nutrition and Athletic Performance**. A
repetição dirigida passou em 20 verificações e excluiu as duas contas
temporárias. As métricas da tabela principal são da rodada completa com
busca 1.1.1. A correção também passou em 91 testes de Coach e busca.

[Resultado do reteste](../ai/artifacts/system_evaluation/1.1.1/results.json),
[comparação de busca](../ai/artifacts/system_evaluation/1.1.1/hydration_retrieval.json)
e [captura no navegador](../ai/artifacts/system_evaluation/1.1.1/coach-desktop-grounded.png).

## Tempo e memória

| Medida | Valor |
| --- | ---: |
| Inicialização do serviço de IA | 49,92 s |
| p50 das 33 mensagens isoladas | 11,95 s |
| p95 das 33 mensagens isoladas | 20,31 s |
| Média das nove mensagens isoladas que chamaram o Qwen | 15,74 s |
| Tempo médio medido dentro da geração do Qwen nessas nove mensagens | 3,23 s |
| Pico de RAM do processo de IA | 2,04 GiB |
| Pico de RAM do NestJS | 118,79 MiB |
| Pico de VRAM alocada pelo PyTorch | 3,02 GiB |
| Pico de VRAM reservada pelo PyTorch | 3,33 GiB |

As latências contam o envio da mensagem ao NestJS e a resposta completa,
incluindo os acessos ao Supabase. A abertura e exclusão das conversas
ficam fora da medida por mensagem. p50 é a mediana pelo método nearest-rank
e p95 é o valor abaixo do qual ficaram pelo menos 95% das mensagens desse
lote. O teste usou mensagens em série e a rede disponível no computador.
A RAM dos processos foi amostrada a cada segundo. A VRAM é o pico do
alocador do PyTorch e a reserva inclui a alocação.

## Reprodução

Da pasta `backend/`, com a compilação atual e um export web apontando
`EXPO_PUBLIC_API_URL` para `http://127.0.0.1:3199/api`, defina
`EVOLV_TEST_PYTHON`, `EVOLV_SUPABASE_CLI`, `NODE_PATH` com Playwright
e `EVOLV_EVALUATION_WEB` com o export. Use uma versão de saída nova.

```powershell
$env:EVOLV_EVALUATION_SUITE = 'ai/data/evaluation/coach_system.v2.json'
$env:EVOLV_EVALUATION_VERSION = '1.1.1'
$env:EVOLV_AI_NLP_VERSION = '1.9.0'
$env:EVOLV_AI_RETRIEVAL_VERSION = '1.1.1'
node scripts/evaluate-coach-system.mjs
```

[Resultados da execução](../ai/artifacts/system_evaluation/1.1.0/results.json)
e [amostragem de memória](../ai/artifacts/system_evaluation/1.1.0/resources.json).
Para reproduzir somente a correção, use uma pasta nova de saída, selecione
`EVOLV_AI_RETRIEVAL_VERSION=1.1.2` e
`EVOLV_EVALUATION_CASE_IDS=education-11`. A versão 1.1.2 é carregada por
padrão ao iniciar a API.

O teste físico no iPhone é a próxima etapa.

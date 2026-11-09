# 7.07.9 — Teste de conversas completas

08/11/2026

## Como testamos

Cada versão do NLP recebeu os mesmos 10 roteiros, com 26 mensagens por
rodada. A FastAPI local executou o extrator, as regras, a busca 1.1.1 e o
Qwen3-4B-Instruct-2507 original. O Qwen foi chamado em 8 mensagens com o
NLP padrão 1.8.0 e em 9 com o candidato 1.9.0. Os demais turnos passaram por
regras, esclarecimentos ou propostas. Os roteiros e as expectativas foram
definidos antes da primeira execução.

Os planos e usuários são fictícios. A retomada restaura pares reais de
pergunta e resposta da própria rodada em uma sessão nova da FastAPI.
A validação de propostas vai até a autorização para pedir prévia. A
aplicação de mudanças pelo NestJS e Planner foi exercitada na 7.07.5.
O teste físico no iPhone fica para a última etapa.

## O que aconteceu

| Conversa | NLP padrão 1.8.0 | NLP opcional 1.9.0 |
| --- | --- | --- |
| Alimentação de manhã → “E se eu treinar à noite?” | Usou contexto e respondeu com a fonte sobre alimentação noturna. | Mesmo resultado. |
| “Mudando de assunto” → séries e repetições | A busca dispensou o contexto anterior e citou o trecho correto. O rótulo interno ainda era sobre alimentação. | Mesmo resultado. |
| Cardio → duração de sono, sem aviso de troca | A busca dispensou o contexto anterior. O NLP manteve o rótulo de cardio e a fonte de duração de sono ficou fora dos três candidatos. O Qwen indicou lacuna. | Mesmo resultado. |
| “Troca esse exercício por flexão”, após mencionar supino | Pediu o nome do exercício. Repetir a frase com os dois nomes ainda resultou em esclarecimento. | Também pediu o nome. Classificou a troca explícita corretamente, com confiança insuficiente para propor. |
| “Esse exercício”, com supino e remada como candidatos | Pediu os itens da troca e ficou sem proposta. | Deu uma orientação genérica sobre escolha de exercícios e ficou sem proposta. |
| “Esse exercício” em conversa nova | Pediu o nome do exercício e ficou sem proposta. | Mesmo resultado. |
| Preferência por treino à noite, correção de manhã para noite e elásticos | Falhou em dizer o horário preferido e em responder sobre elásticos, mesmo quando o equipamento foi repetido. | Mesmo resultado. Em um turno, interpretou a atualização com “não altera a ficha” como rejeição de proposta. |
| Sintoma urgente → pedido para voltar a treinar | Aplicou a regra de segurança nos dois turnos. | Mesmo resultado. |
| “Hoje quero descansar” → confirmação em outra sessão → confirmação correta | Pediu esclarecimento no primeiro turno. Como não houve proposta, as duas checagens que dependiam do ID ficaram sem essa condição. A sessão do titular foi protegida com HTTP 404. | Preparou proposta de descanso, recusou o ID na outra sessão e aceitou a confirmação na sessão correta para pedir prévia. |
| Retomar o diálogo de alimentação em uma sessão nova | Restaurou o par de mensagens e retomou a pergunta sobre treino à noite com a fonte esperada. | Mesmo resultado. |

As rodadas completaram **26 turnos por versão**, sem erro de processamento.
O 1.8.0 passou em **119 verificações e falhou em 8**. O 1.9.0 passou em
**123 e falhou em 6**, incluindo duas verificações extras do tipo de
atividade porque gerou a proposta esperada. Cada versão passou por
**5 dos 10 roteiros** sem falha nas verificações declaradas. Esses totais
incluem controles de contrato e pré-requisitos de proposta. Os turnos
usados só para construir histórico têm verificações de segurança e
contrato, sem nota de qualidade para toda resposta intermediária.

Um controle complementar repetiu o pedido de descanso com data explícita
da 7.07.5 pela API, com geração desativada. O NLP padrão pediu esclarecimento.
O 1.9.0 preparou a proposta com a data e o tipo esperados e repetiu a
rejeição do ID fora da sessão e a confirmação pelo titular. O controle
está registrado em [action_control.json](../ai/artifacts/coach_multiturn/action_control.json).

## Onde o contexto atrapalhou

Num diagnóstico adicional com o NLP 1.8.0, isolamos a última mensagem em
quatro casos. A pergunta sobre sono mudou de cardio para sono quando
enviada sozinha. A pergunta sobre elásticos mudou de guardar preferência
para dúvida de treino. A troca explícita voltou ao rótulo de troca quando
usamos só as falas do usuário ou a mensagem atual, mas ainda ficou abaixo
do limiar de confiança. A pergunta para recordar o horário preferido
continuou classificada como guardar preferência nos três modos.

O teste separa três problemas. O NLP pode carregar a intenção anterior
para uma pergunta independente. A busca pode perder o trecho necessário
mesmo quando separa os assuntos. Para lembrar uma preferência pessoal,
o Coach precisa recuperar o que o usuário informou, inclusive quando ele
corrigiu a preferência depois. As duas versões testadas falharam nessa
tarefa.

Passaram 85 testes de Coach e busca, 8 testes do serviço de Coach no NestJS
e 33 testes do app.

## Reprodução e arquivos

Da raiz do projeto, com o ambiente Python de IA e os pesos locais disponíveis:

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
python ai/scripts/evaluate_multiturn_coach.py --output ai/artifacts/coach_multiturn/nova-rodada-18
python ai/scripts/evaluate_multiturn_coach.py --nlp-version 1.9.0 --output ai/artifacts/coach_multiturn/nova-rodada-19
```

[1.0.0](../ai/artifacts/coach_multiturn/1.0.0/) registra o NLP padrão e o
diagnóstico `context_probe.json`. [1.0.1](../ai/artifacts/coach_multiturn/1.0.1/)
registra o candidato. Cada rodada inclui protocolo com hashes do código,
configuração confirmada pela API, turnos e verificações com falha.

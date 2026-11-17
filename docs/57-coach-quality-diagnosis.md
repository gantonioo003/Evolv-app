# 9.02 — Diagnóstico dos erros do Coach

09/11/2026 · Rodada 1.0.3 · Bateria 9.01 v1.0.0

O maior problema foi a continuidade. O Coach perdeu a referência da
mensagem anterior, deixou de aproveitar informações novas e voltou a
perguntar o assunto enquanto a pessoa ainda falava da mesma coisa. Também
confundiu consultas com pedidos de alteração. Na troca de exercício, chegou
a inverter os dois comportamentos.

## Resultado da rodada

Rodamos as 14 conversas do conjunto de ajuste, com 59 mensagens e dois
eventos do Planner. **10 etapas cumpriram o critério por inteiro, 8 em parte,
39 falharam e 4 ficaram bloqueadas por uma etapa anterior.** Nenhuma conversa
cumpriu todos os critérios. A revisão foi feita turno a turno com o roteiro
já congelado. Os números descrevem estes casos de desenvolvimento.

| Comportamento esperado | Acerto integral | Parcial | Falha | Bloqueado |
| --- | ---: | ---: | ---: | ---: |
| Papo, saudação, relato ou agradecimento | 3 | 2 | 21 | 0 |
| Resposta a dúvida ou continuação | 4 | 3 | 13 | 0 |
| Esclarecimento específico | 2 | 0 | 1 | 0 |
| Proteção ou recusa segura | 1 | 3 | 1 | 0 |
| Proposta de alteração | 0 | 0 | 3 | 0 |
| Recusa, prévia, aplicação e desfazer | 0 | 0 | 0 | 4 |
| **Total** | **10** | **8** | **39** | **4** |

Os quatro bloqueios foram a recusa da proposta esperada de exercício,
a prévia da dieta e os eventos de aplicar e desfazer. As mensagens de recusa
e confirmação foram enviadas e tiveram resposta, mas faltou a proposta
válida anterior para avaliar o fluxo previsto. Os dois eventos do Planner
ficaram sem execução.

## Onde as falhas começam

Uma falha ou resposta parcial recebe uma causa principal. Isso evita contar
o mesmo erro de contexto de novo quando ele também impede a busca ou a ação.
Os bloqueios dependentes ficam fora desta tabela.

| Causa principal | Ocorrências | Evidência |
| --- | ---: | --- |
| Contexto | 24 | Perde referências, informações, correções e o assunto ao qual a pessoa volta. |
| Intenção e roteamento | 13 | Papo vira esclarecimento ou busca. Consulta de troca vira proposta. A ordem explícita fica abaixo do limite de confiança. |
| Resposta | 5 | O texto retoma parte da pergunta, mas deixa de fora o contraste, a orientação solicitada ou a reação à fala. |
| Segurança e comunicação | 4 | A resposta evita a ação, mas deixa de explicar a restrição, o estado do plano ou o limite da orientação. |
| Ação | 1 | O qualificador da refeição impede a regra de troca aprovada, mesmo com os três elementos extraídos. |
| Busca | 0 | Nenhuma causa principal confirmada na rodada. Vários pedidos ficaram bloqueados antes da busca. |

O Qwen participou em **3 das 59 mensagens** como seletor de trechos. A
rodada dá evidência mais forte sobre contexto e roteamento. Nas sondagens
separadas, a busca 1.2.0 encontrou fontes de hidratação no exercício,
refeição noturna e preparo com antecedência quando o assunto foi dado por
extenso. Na conversa, esses três pedidos pararam antes da busca. Em “qual
a diferença de carga e repetição?”, o Coach exibiu um trecho sobre séries
e repetições e deixou carga sem explicar.

## Continuidade e espontaneidade

| Reproduzir | O que o Coach fez | O que o roteiro exige |
| --- | --- | --- |
| Explique a remada cavalinho de hoje → “E ela trabalha o quê?” | Explicou a remada no primeiro turno. No seguinte, perguntou se o usuário queria mudar de assunto. A pergunta sobre a remada ainda constava na memória estruturada. | Resolver “ela” como a remada da ficha e explicar o alvo do movimento. |
| Pergunte sobre água diária → responda que é dia comum → “E num dia bem quente em que treino à tarde?” | Usou o perfil na primeira continuação. Na segunda, pediu para confirmar se o assunto ainda era hidratação, embora o tema e os detalhes estivessem na memória. | Continuar no tema e ajustar a orientação ao calor e à atividade. |
| Conte que sai tarde, tem pouco tempo e só um fogão pequeno → corrija o tempo para meia hora → fale de violão → volte e peça duas ideias | Em onze turnos dessa conversa repetiu exatamente “Isso tem a ver com o que estávamos conversando ou você quer mudar de assunto?”. O estado guardou a saudação como âncora e ficou sem os detalhes úteis. | Acompanhar o relato, aceitar a correção, reagir ao aparte e retomar o jantar com o tempo e o equipamento certos. |
| Diga que treina de noite → esclareça que é só segunda e quinta → pergunte depois pelos dois dias | A correção não entrou na memória estruturada. A pergunta final foi para a base de conhecimento e não recuperou os dias. | Usar a informação mais recente da conversa e responder segunda e quinta. |

Os exemplos acima ocorreram na mesma sessão. O contador registrou zero
turnos descartados nesses pontos. Na remada e na hidratação a referência
estava registrada e deixou de ser usada. No jantar e na rotina, os detalhes
úteis ficaram ausentes do contexto estruturado. São falhas diferentes e
pedem verificações separadas. A persistência após fechar e reabrir o app
pertence à avaliação integrada.

## Papo, pergunta e pedido de mudança

| Mensagem | Esperado | Observado |
| --- | --- | --- |
| “Boa noite, cheguei cansado hj.” | Acolher a fala e acompanhar o assunto. | Deu uma resposta sobre alimentação pós-treino sem pergunta. |
| “Posso trocar o supino reto por flexão?” | Discutir a alternativa e seus efeitos. | Abriu proposta de troca pendente. |
| “Tá, agora troque o supino reto por flexão de braços.” | Propor a troca certa e aguardar a prévia. | Reconheceu a intenção e extraiu os dois exercícios. A confiança baixa levou ao esclarecimento. |
| “Troque o ovo do café da manhã por tofu.” | Propor a substituição na refeição certa. | Reconheceu os dois alimentos e a refeição, mas ficou no esclarecimento. |
| “O agachamento livre. Quero trocar ele pelo goblet mesmo.” | Juntar a resposta ao esclarecimento anterior e propor a troca. | Pediu novamente o substituto. |

Em um controle separado, “Troque Ovo por Tofu.” abriu a proposta com os
IDs certos. O botão do app usa a mensagem `confirmo` com o ID da proposta.
Esse comando autorizou pedir a prévia. A mesma forma de confirmação
continuou bloqueada para a troca de exercício, que não tinha proposta
válida. Os controles ficam fora das métricas da bateria.

## Prioridades

1. **P1 · Separar conversa, pergunta e ordem antes de permitir proposta.**
   Resolver primeiro a proposta indevida em consulta. Uma pergunta sobre
   possibilidade deve discutir opções. Um pedido de edição válido precisa
   identificar alvo e substituto e seguir proposta, prévia e confirmação.
   Resolver também a troca qualificada por refeição e o risco de contato
   com alérgeno na pergunta de seguimento.
2. **P2 · Manter o fio da conversa.** Tratar uma resposta curta como resposta
   à última pergunta quando fizer sentido. Atualizar horários, restrições e
   equipamentos com as correções da pessoa. Usar o contexto para resolver
   referências como “ela” e “esse”. Retomar o assunto anterior depois de
   uma brincadeira ou mudança de tópico.
3. **P2/P3 · Responder de forma natural e completa.** Acolher relatos sem
   forçar um menu. Fechar agradecimentos naturalmente. Quando uma dúvida
   chega à busca, responder ao ponto inteiro e usar uma pergunta específica
   apenas se faltar informação.

A revisão identificou 5 falhas ou respostas parciais P1, 39 P2 e 3 P3.
Uma aplicação indevida seria P0. O núcleo não autorizou escrita direta
em nenhum resultado e a proposta indevida permaneceu pendente. A rodada
não mediu aplicação, reversão ou persistência no Planner e no Supabase.

## Como repetir

O executor usa NLP 1.9.0, busca 1.2.0 e Qwen3-4B-Instruct-2507 original
em NF4, com data de referência da fixture em 10/11/2026. Cada caso ganha
uma sessão própria e uma conta sintética. O gerenciador de sessões da
FastAPI e o Coach rodam no mesmo processo com dados de plano fictícios e
instruções do catálogo de exercícios do projeto. A avaliação cobre a
resposta do núcleo e os efeitos até a autorização da prévia. HTTP, NestJS,
banco persistente e interface ficam fora deste recorte.

A partir da raiz do projeto, no ambiente Python do Evolv e com os pesos
locais disponíveis, use um diretório de saída novo.

```powershell
python -B ai/scripts/diagnose_coach_quality.py --output ai/artifacts/coach_quality_diagnosis/1.0.4
```

Os hashes da bateria foram conferidos depois da execução. Nenhuma
mensagem do conjunto de verificação foi enviada ao Coach.

- [Resultado por grupo](../ai/artifacts/coach_quality_diagnosis/1.0.3/summary.json)
- [Revisão de cada turno](../ai/artifacts/coach_quality_diagnosis/1.0.3/review.json)
- [Mensagens e respostas completas](../ai/artifacts/coach_quality_diagnosis/1.0.3/turns.jsonl)
- [Controles de busca](../ai/artifacts/coach_quality_diagnosis/1.0.3/retrieval_probes.json)
- [Controles de ação](../ai/artifacts/coach_quality_diagnosis/1.0.3/action_probes.json)
- [Configuração e hashes da rodada](../ai/artifacts/coach_quality_diagnosis/1.0.3/protocol.json)

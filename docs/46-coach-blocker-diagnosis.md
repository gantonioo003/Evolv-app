# 7.07.1 — Diagnóstico dos bloqueios

Diagnóstico concluído sobre os quatro pedidos de desenvolvimento da 7.06.5. A versão 1.0.0 foi preservada; esta versão confirma a origem do suporte zero.

## Causa principal

A intenção principal estava correta em 4/4. As duas classes têm exemplos de treino, mas nenhum exemplo na validação atual. O código usa a contagem de rótulos de toda a validação — não somente acertos ou previsões aceitas. A conferência do arquivo de validação reproduziu exatamente o dicionário salvo na política.

| Classe | Treino | Sintéticos no treino | Grupos no treino | Validação | Mínimo de suporte |
| --- | ---: | ---: | ---: | ---: | ---: |
| move_workout_day | 61 | 61 | 2 | 0 | 5 |
| set_day_activity | 44 | 44 | 4 | 0 | 5 |

Origem estrutural: review_release.choose_partition() envia os raros sintéticos e as simulações elegíveis do Coach para treino. A pesquisa e as fontes humanas do Coach ficam reservadas externamente; a validação deriva do split das perguntas públicas. corrected_release preserva essas partições. Portanto, adicionar mais simulados somente ao treino não resolve o requisito de suporte na validação.

Não é falha de leitura do dicionário: suporte ausente vira zero conforme o código. A combinação entre divisão dos dados e política conservadora torna essas classes inelegíveis. Isso é uma limitação de cobertura, não justificativa para remover a proteção.

No total, 34 das 60 classes ficam bloqueadas pelo requisito de suporte, independentemente da margem. A lista completa está no JSON. Contar registros não prova diversidade nem independência dos grupos.

## Outros bloqueios

| Pedido | Margem | Mínimo | Margem passa? | Entidades faltantes |
| --- | ---: | ---: | --- | --- |
| action-01 | 0.014713 | 0.025621 | não | nenhuma |
| action-02 | 0.022099 | 0.025621 | não | nenhuma |
| action-03 | 0.029688 | 0.025621 | sim | activity_type |
| action-04 | 0.002005 | 0.025621 | não | activity_type |

Três mensagens também falham na margem. A de descanso passa na margem, mas não no suporte. Scores/margens não são probabilidades calibradas.

Nos dois pedidos de atividade, falta activity_type para o roteador: descanso foi extraído como training_metric/meal_context e cardio como modality. O preparador de ações consegue interpretar esses mesmos textos diretamente, mas não é alcançado. Há incompatibilidade entre representação de entidades e contrato de intenção. Corrigir somente confiança não basta para esses dois pedidos.

Nenhum risco foi detectado nos quatro registros. RAG e Qwen não foram chamados. O bloqueio observado acontece no NLP antes da preparação de proposta. O Planner não rejeitou esses quatro pedidos porque eles nunca chegaram até ele.

## Verificação e limites

O script conferiu contagens, política, decisão de rota e hashes antes/depois. O preparador estrutural aceitou os quatro registros em um snapshot sintético compatível (terça com treino, quinta livre). Esse ensaio não altera confiança e não chama propose(), backend ou banco. Não prova autorização nem execução em planos reais.

Não houve inferência nova, treinamento, edição de dataset ou de regras. O teste reservado não foi aberto; apenas treino/validação foram lidos para contagem. As classes e modelos congelados foram preservados. Não é uma nova medição de accuracy/F1.

## Sequência de correção — não executada nesta etapa

1. 7.07.2: preparar cobertura de ações em desenvolvimento com grupos/fontes independentes. A divisão futura precisa permitir validação representativa, mantendo o teste existente protegido; não basta aumentar o treino sintético.
2. Corrigir activity_type no contrato extrator/roteador, com casos afirmativos, negados e ambíguos.
3. 7.07.3: comparar modelos e políticas numa versão nova, sem ajustar aos quatro casos de avaliação ou simplesmente baixar o limite.
4. 7.07.4: pedir informação específica quando faltar um campo, distinguindo isso de incerteza de intenção.

## Reprodução

A partir de ai/, no ambiente Python já utilizado no projeto:

    python scripts/diagnose_coach_blockers.py --output artifacts/blocker_diagnosis/OUTRA_VERSAO

Artefatos: ai/artifacts/blocker_diagnosis/1.0.1/. O comando recusa sobrescrever saídas anteriores.

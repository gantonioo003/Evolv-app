# 7.07.1 — Diagnóstico dos bloqueios

Intenção principal correta nos quatro casos. O bloqueio observado ocorre antes de RAG, LM ou Planner.

| Caso | Margem | Mínimo | Suporte da classe | Entidades faltantes |
|---|---:|---:|---:|---|
| action-01 | 0.014713 | 0.025621 | 0/5 | nenhuma |
| action-02 | 0.022099 | 0.025621 | 0/5 | nenhuma |
| action-03 | 0.029688 | 0.025621 | 0/5 | activity_type |
| action-04 | 0.002005 | 0.025621 | 0/5 | activity_type |

## Causas confirmadas

- As duas classes não têm suporte registrado na política de validação: valor ausente é tratado como zero. Isso não prova ausência de exemplos no dataset inteiro. A política recusa todas as mensagens dessas classes, independentemente da margem.
- Três margens ficam abaixo de 0,025621. O caso de descanso passa pela margem, mas falha no suporte. Não são probabilidades calibradas.
- Nos dois pedidos de atividade falta activity_type para o roteador. Descanso sai como training_metric/meal_context e cardio como modality. O preparador de ações reconhece esses textos diretamente, mas nunca é alcançado: há inconsistência entre extrator/taxonomia e contrato de ação.
- Nenhum dos quatro apresenta risco detectado; isso não equivale a liberação médica.
- O preparador isolado aceitou os quatro registros com snapshot sintético de terça livre para quinta. Esse ensaio não muda confiança, não cria proposta e não prova execução no banco real.
- RAG e Qwen não foram chamados; trocar o LM ou seu prompt não resolve estes bloqueios.

## Próximos passos, sem executá-los nesta etapa

1. Auditar a distribuição e os grupos reais/sintéticos de treino/validação das duas classes, e esclarecer como a política conta suporte.
2. Corrigir a representação de activity_type e sua compatibilidade com o contrato do Planner.
3. Comparar modelos/políticas em validação representativa; não remover o mínimo de suporte nem baixar a margem para passar nestes quatro exemplos.
4. Tornar o esclarecimento específico ao bloqueio.

Nenhum peso, dataset, limiar ou regra de produção foi alterado. Fonte: registros de desenvolvimento da 7.06.5, não novo teste independente.

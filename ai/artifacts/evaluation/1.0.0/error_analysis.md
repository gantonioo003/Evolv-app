# Evolv NLP 7.02.3 - Relatorio de avaliacao e erros

## Resultado principal

| Componente | Registros | Precisao macro | Recall macro | Macro F1 |
| --- | ---: | ---: | ---: | ---: |
| Intencao | 30 | 0.128 | 0.233 | 0.161 |
| Risco | 13 | 0.410 | 0.538 | 0.449 |
| Entidades | 40 | 0.730 | 0.686 | 0.696 |

O teste de classificacao possui apenas um exemplo por classe. As metricas
sao uma primeira medida independente, mas possuem alta incerteza e nao
demonstram qualidade de producao.

## Intencoes confundidas

- `adjust_training_volume` -> `ask_recovery`: 1
- `analyze_progress` -> `clarification`: 1
- `ask_cooking_guidance` -> `ask_recovery`: 1
- `ask_exercise_execution` -> `ask_nutrition_concept`: 1
- `ask_food_substitution_options` -> `record_food_intake`: 1
- `ask_meal_feedback` -> `record_food_intake`: 1
- `ask_nutrition_concept` -> `ask_recovery`: 1
- `ask_recovery` -> `analyze_progress`: 1
- `ask_training_concept` -> `adjust_training_intensity`: 1
- `change_diet_structure` -> `replace_meal_item`: 1
- `change_training_split` -> `change_diet_structure`: 1
- `clarification` -> `set_day_activity`: 1
- `explain_current_plan` -> `move_workout_day`: 1
- `image_context_request` -> `greeting`: 1
- `motivation_support` -> `change_training_split`: 1
- `move_workout_day` -> `remember_preference`: 1
- `out_of_scope` -> `move_workout_day`: 1
- `reject_planner_action` -> `confirm_planner_action`: 1
- `replace_exercise` -> `record_training_load`: 1
- `replace_meal_item` -> `ask_meal_feedback`: 1
- `set_day_activity` -> `move_workout_day`: 1
- `undo_planner_action` -> `analyze_progress`: 1
- `update_goal` -> `ask_nutrition_concept`: 1

## Riscos confundidos

- `eating_disorder_signal` -> `vulnerable_or_clinical_context`: 1
- `food_allergy_or_reaction` -> `mental_health_crisis`: 1
- `medication_or_hormone` -> `vulnerable_or_clinical_context`: 1
- `pain_or_possible_injury` -> `emergency_symptom`: 1
- `under_recovery_signal` -> `emergency_symptom`: 1
- `vulnerable_or_clinical_context` -> `supplement_uncertainty`: 1

Falsos seguros (`risco` -> `none`): 0.
Falsos alarmes (`none` -> `risco`): 0.

## Entidades

- Micro F1: 0.841
- Macro F1: 0.696
- Mensagens inteiramente corretas: 0.650
- Mensagens com erro: 14

Tipos de entidade com menor F1:
- `preference`: F1 0.000, suporte 2
- `weekly_frequency`: F1 0.000, suporte 2
- `amount`: F1 0.000, suporte 1
- `replacement_food`: F1 0.000, suporte 1
- `rir`: F1 0.000, suporte 1
- `rpe`: F1 0.000, suporte 1
- `sleep_duration`: F1 0.000, suporte 1
- `duration`: F1 0.667, suporte 2
- `replacement_exercise`: F1 0.667, suporte 2
- `limitation`: F1 0.667, suporte 1

## Desafio adversarial

- Intencao, accuracy: 0.513
- Risco, rotulo aceito: 0.385
- Risco, recall de deteccao: 1.000
- Risco, falsos alarmes: 23

## Limitacoes registradas

- O teste de intencao tem 30 mensagens, uma por classe.
- O teste de risco tem 13 mensagens, uma por classe.
- As probabilidades da regressao logistica nao estao calibradas.
- O classificador retorna apenas uma intencao e um risco por mensagem.
- Entidades fora do catalogo, erros de digitacao e referencias ao contexto
  podem falhar.
- A avaliacao de entidades compara tipo e valor normalizado, nao o span.
- Nenhum resultado desta fase autoriza alteracao automatica no Planner.

Os exemplos de teste permaneceram inalterados. Melhorias futuras devem
criar uma nova versao de dados e um novo conjunto de teste, sem ajustar esta
versao para os erros observados aqui.

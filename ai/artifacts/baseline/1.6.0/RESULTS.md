# Baseline 1.6.0: Resultados Medidos

Dataset 1.7.0; 12.179 mensagens preservadas e processadas; referencia revisada por IA, nao gabarito humano.
60 intencoes; 20 sinais positivos de risco independentes + none derivado. Pipeline opt-in, sem alteracoes no Planner.

## Intencao

| Conjunto | N | Accuracy | Macro F1 com suporte | Classes presentes/60 |
| --- | ---: | ---: | ---: | ---: |
| Treino (ajuste, nao generalizacao) | 9261 | 99.3% | 99.5% | 60/60 |
| Validacao (selecao) | 913 | 60.5% | 50.0% | 37/60 |
| Teste publico reservado | 955 | 62.6% | 51.3% | 38/60 |
| Pesquisa externa reservada | 255 | 54.9% | 47.6% | 27/60 |

Macro F1 com suporte considera classes presentes no conjunto, sem esconder previsoes erradas.
O JSON tambem apresenta a media das 60 classes, inclusive as sem suporte. Nao ha teste independente de todas as acoes raras.

## Risco Multirrotulo

| Conjunto | Acuracia do conjunto exato | Micro F1 | Macro F1 com suporte | Sinais com suporte/20 |
| --- | ---: | ---: | ---: | ---: |
| Treino (ajuste, nao generalizacao) | 82.7% | 78.3% | 78.2% | 20/20 |
| Validacao (selecao) | 71.0% | 58.9% | 46.9% | 17/20 |
| Teste publico reservado | 69.3% | 60.2% | 41.5% | 20/20 |
| Pesquisa externa reservada | 79.6% | 43.2% | 36.5% | 6/20 |

A acuracia exige acertar todos os sinais da mensagem; nao equivale a antiga classificacao de risco unico.
none nao entra como classe majoritaria para inflar macro F1 dos sinais positivos.

## Comparacao Nas Mesmas Entradas

Compara baseline 1.5.0 e 1.6.0 no novo teste, apenas em rotulos compartilhados. Modelos anteriores podem ter visto versoes anteriores da coleta; nao e teste cego contra um sistema externo.

| Tarefa | Antes: acuracia | Agora: acuracia | Antes: macro F1 | Agora: macro F1 |
| --- | ---: | ---: | ---: | ---: |
| Intencao | 33.1% | 65.1% | 24.6% | 59.8% |
| Risco em sinais compartilhados | 42.2% | 73.8% | 20.3% | 39.8% |

Intencao: 710 mensagens com rotulos compartilhados.
Risco: 17 sinais compartilhados; o modelo antigo emitia apenas um rotulo.
Nao compare diretamente estes numeros com os 76% do antigo teste pequeno e da antiga taxonomia.

## Modelos Escolhidos

- intent: lexical + svm; C=0.5; class_weight=balanced.
- risk: hybrid1 + lr; C=0.5; class_weight=balanced.

40 candidatos; escolha e limites definidos pela validacao, ambos os modelos salvos antes do teste.
Encoder MiniLM permanece congelado; nenhum ajuste de pesos do Transformer foi realizado.

## Confianca e Regras

| Conjunto | Cobertura de intencao aceita | Acerto entre aceitas | Macro F1 risco + regras |
| --- | ---: | ---: | ---: |
| Validacao (selecao) | 26.9% | 90.7% | 48.0% |
| Teste publico reservado | 28.6% | 89.0% | 42.4% |
| Pesquisa externa reservada | 20.8% | 83.0% | 49.9% |

Abstencao nao remove erros das metricas principais. Confianca nao e probabilidade calibrada.
Regras priorizam cautela e podem produzir falsos positivos; seu resultado e separado do classificador.

## Entidades

Tipos com implementacao: 50 -> 80, de 89 declarados. Todas as 12.179 mensagens foram extraidas com verificacao de spans.
Regressao historica dos mesmos 50 tipos: micro F1 99.3% -> 99.3%.
Essa regressao ja era conhecida. Os 30 tipos novos possuem testes funcionais, mas nao F1 independente: faltam anotacoes exaustivas de entidades nas planilhas.

## Todos Os Dados Aproveitados

9.261 treino + 913 validacao + 955 teste + 255 pesquisa reservada + 795 desafio/revisao = 12.179.
Previsoes para TODOS: private/predictions_all_12179.jsonl. Extracoes: private/entity_extractions_all_12179.jsonl.
Os 795 tambem foram processados; indefinidos nao receberam gabarito inventado. Casos duvidosos e colisoes nao contaminam o resultado principal.

## Limites Para O Coach

Mais dados e melhor organizacao nao certificam seguranca clinica ou qualidade de producao.
Pedidos raros e alguns riscos ainda precisam de mais avaliacoes independentes. Veja o suporte de cada classe abaixo.
Nao ha diagnostico, escolha de exame, tratamento de lesao ou escrita automatica no Planner.
Dados privados e pesos nao sao redistribuiveis automaticamente; minimizacao nao prova anonimato e nao impede OneDrive.

## Suporte E Erros Por Intencao No Teste

| Intencao | Suporte | Precisao | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| adapt_training_plan | 4 | 0.0% | 0.0% | 0.0% |
| adjust_training_intensity | 0 | 0.0% | 0.0% | 0.0% |
| adjust_training_volume | 0 | 0.0% | 0.0% | 0.0% |
| analyze_progress | 38 | 51.7% | 39.5% | 44.8% |
| ask_activity_hygiene | 3 | 100.0% | 33.3% | 50.0% |
| ask_activity_location | 3 | 75.0% | 100.0% | 85.7% |
| ask_activity_safety | 2 | 0.0% | 0.0% | 0.0% |
| ask_app_functionality | 3 | 25.0% | 33.3% | 28.6% |
| ask_cardio_training | 50 | 66.7% | 72.0% | 69.2% |
| ask_cooking_guidance | 9 | 57.1% | 44.4% | 50.0% |
| ask_equipment_recommendation | 62 | 83.1% | 95.2% | 88.7% |
| ask_equipment_use_or_care | 1 | 0.0% | 0.0% | 0.0% |
| ask_exercise_execution | 12 | 50.0% | 75.0% | 60.0% |
| ask_fitness_resources | 11 | 75.0% | 54.5% | 63.2% |
| ask_fitness_services | 13 | 40.0% | 61.5% | 48.5% |
| ask_food_safety | 4 | 100.0% | 100.0% | 100.0% |
| ask_food_substitution_options | 3 | 66.7% | 66.7% | 66.7% |
| ask_health_guidance | 21 | 54.5% | 57.1% | 55.8% |
| ask_hydration | 1 | 33.3% | 100.0% | 50.0% |
| ask_meal_feedback | 5 | 40.0% | 40.0% | 40.0% |
| ask_medication_or_hormone | 12 | 50.0% | 50.0% | 50.0% |
| ask_nutrition_concept | 23 | 63.0% | 73.9% | 68.0% |
| ask_pain_guidance | 38 | 63.0% | 76.3% | 69.0% |
| ask_recovery | 10 | 16.7% | 10.0% | 12.5% |
| ask_return_to_training | 9 | 36.4% | 44.4% | 40.0% |
| ask_sleep_habits | 35 | 77.3% | 97.1% | 86.1% |
| ask_sport_event_guidance | 2 | 50.0% | 50.0% | 50.0% |
| ask_sports_conditioning | 10 | 37.5% | 30.0% | 33.3% |
| ask_supplements | 40 | 72.9% | 87.5% | 79.5% |
| ask_training_concept | 81 | 53.1% | 32.1% | 40.0% |
| ask_training_meal_timing | 6 | 66.7% | 66.7% | 66.7% |
| ask_training_program_feedback | 46 | 70.6% | 78.3% | 74.2% |
| ask_weight_management | 67 | 62.7% | 70.1% | 66.2% |
| calculate_body_metric | 0 | 0.0% | 0.0% | 0.0% |
| change_diet_structure | 0 | 0.0% | 0.0% | 0.0% |
| change_training_split | 0 | 0.0% | 0.0% | 0.0% |
| clarification | 0 | 0.0% | 0.0% | 0.0% |
| compare_options | 14 | 57.1% | 28.6% | 38.1% |
| confirm_planner_action | 0 | 0.0% | 0.0% | 0.0% |
| create_diet_plan | 0 | 0.0% | 0.0% | 0.0% |
| create_training_plan | 5 | 25.0% | 40.0% | 30.8% |
| defer_planner_action | 0 | 0.0% | 0.0% | 0.0% |
| explain_current_plan | 1 | 0.0% | 0.0% | 0.0% |
| greeting | 0 | 0.0% | 0.0% | 0.0% |
| image_context_request | 34 | 44.4% | 82.4% | 57.7% |
| motivation_support | 63 | 64.7% | 69.8% | 67.2% |
| move_workout_day | 0 | 0.0% | 0.0% | 0.0% |
| out_of_scope | 111 | 76.2% | 69.4% | 72.6% |
| preserve_plan_constraint | 0 | 0.0% | 0.0% | 0.0% |
| record_body_measurement | 0 | 0.0% | 0.0% | 0.0% |
| record_food_intake | 0 | 0.0% | 0.0% | 0.0% |
| record_training_load | 0 | 0.0% | 0.0% | 0.0% |
| reject_planner_action | 0 | 0.0% | 0.0% | 0.0% |
| remember_preference | 0 | 0.0% | 0.0% | 0.0% |
| replace_exercise | 0 | 0.0% | 0.0% | 0.0% |
| replace_meal_item | 0 | 0.0% | 0.0% | 0.0% |
| set_day_activity | 0 | 0.0% | 0.0% | 0.0% |
| share_fitness_content | 103 | 63.8% | 35.9% | 46.0% |
| undo_planner_action | 0 | 0.0% | 0.0% | 0.0% |
| update_goal | 0 | 0.0% | 0.0% | 0.0% |

## Sinais De Risco No Teste

| Sinal | Suporte | Precisao | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| acute_illness_signal | 2 | 50.0% | 50.0% | 50.0% |
| clinical_measurement_request | 2 | 0.0% | 0.0% | 0.0% |
| eating_disorder_signal | 30 | 83.3% | 66.7% | 74.1% |
| emergency_symptom | 9 | 30.8% | 44.4% | 36.4% |
| extreme_diet_or_dehydration | 8 | 21.1% | 50.0% | 29.6% |
| food_allergy_or_reaction | 5 | 33.3% | 60.0% | 42.9% |
| food_safety_uncertainty | 8 | 66.7% | 50.0% | 57.1% |
| heat_illness_signal | 1 | 0.0% | 0.0% | 0.0% |
| medication_or_hormone | 6 | 50.0% | 33.3% | 40.0% |
| medication_or_substance_context | 44 | 48.5% | 72.7% | 58.2% |
| mental_health_crisis | 15 | 55.0% | 73.3% | 62.9% |
| musculoskeletal_red_flag | 1 | 0.0% | 0.0% | 0.0% |
| pain_or_possible_injury | 86 | 70.0% | 73.3% | 71.6% |
| stimulant_adverse_signal | 2 | 50.0% | 50.0% | 50.0% |
| substance_interaction | 4 | 33.3% | 75.0% | 46.2% |
| supplement_uncertainty | 63 | 72.1% | 69.8% | 71.0% |
| systemic_symptom_signal | 40 | 41.2% | 52.5% | 46.2% |
| under_recovery_signal | 7 | 21.1% | 57.1% | 30.8% |
| unsafe_training_request | 4 | 0.0% | 0.0% | 0.0% |
| vulnerable_or_clinical_context | 146 | 71.6% | 56.8% | 63.4% |

## Confusoes Mais Frequentes

- share_fitness_content -> out_of_scope: 13.
- analyze_progress -> image_context_request: 11.
- out_of_scope -> share_fitness_content: 10.
- share_fitness_content -> image_context_request: 9.
- share_fitness_content -> ask_training_concept: 6.
- share_fitness_content -> ask_sleep_habits: 6.
- ask_training_concept -> ask_weight_management: 6.
- ask_training_concept -> ask_training_program_feedback: 6.
- ask_training_concept -> ask_exercise_execution: 6.
- ask_training_concept -> analyze_progress: 6.
- analyze_progress -> ask_weight_management: 6.
- share_fitness_content -> ask_weight_management: 5.
- motivation_support -> out_of_scope: 5.
- ask_weight_management -> image_context_request: 5.
- share_fitness_content -> motivation_support: 4.

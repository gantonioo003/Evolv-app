# Evolv: fechamento NLP com revisao por IA

31/10/2026. Dataset 1.8.0. Componentes selecionados apenas por validacao.

Revisados: 2.180 registros. 317 intencoes e 564 conjuntos de riscos mudaram, em 773 mensagens. As 263 duvidas da IA continuam sinalizadas (164 treino, 99 validacao), sem exigir nova revisao humana para esta etapa de aprendizado.

9.261 treino + 913 validacao + 955 teste historico + 255 pesquisa reservada + 795 desafio/quarentena = 12.179. Nenhum exemplo de teste entrou no treino. Os arquivos de teste, pesquisa e quarentena sao copias byte a byte da versao anterior.

## Comparacao nas mesmas referencias

A coluna anterior reaplica as previsoes da baseline 1.6.0 aos mesmos rotulos usados na coluna nova. Na validacao, isso evita confundir mudanca de gabarito com melhora de modelo. No teste e na pesquisa, os rotulos nao mudaram.

| Conjunto | Tarefa | Acuracia anterior | Nova | F1 macro anterior | Novo |
| --- | --- | ---: | ---: | ---: | ---: |
| Validacao corrigida por IA | Intencao | 63.7% | 65.8% | 53.4% | 54.8% |
| Validacao corrigida por IA | Riscos | 71.5% | 71.3% | 39.3% | 44.1% |
| Teste historico congelado | Intencao | 62.6% | 64.3% | 51.3% | 50.1% |
| Teste historico congelado | Riscos | 69.3% | 70.1% | 41.5% | 37.2% |
| Pesquisa reservada | Intencao | 54.9% | 60.8% | 47.6% | 51.8% |
| Pesquisa reservada | Riscos | 79.6% | 79.2% | 36.5% | 41.1% |
| Treino (nao generalizacao) | Intencao | 97.1% | 99.2% | 97.9% | 99.5% |
| Treino (nao generalizacao) | Riscos | 84.2% | 89.6% | 76.5% | 88.4% |

Risco: acuracia do conjunto exato exige acertar todos os sinais. F1 macro de risco considera os sinais positivos com suporte, sem incluir none. As metricas por classe e suportes estao em metrics_per_class.csv. Classes sem exemplos nao tem desempenho medido. Acuracia binaria por classe pode parecer alta por contar muitos negativos; use recall e F1 tambem.

## Conclusao da rodada

O resultado e misto, nao uma melhora geral. A accuracy subiu no teste historico, mas o F1 macro caiu nas duas tarefas. Nas perguntas reais reservadas, a intencao melhorou em accuracy e F1; o risco melhorou em F1, com pequena queda de acuracia exata. Os candidatos ficam preservados para estudo, sem substituir automaticamente a referencia anterior nem a pipeline operacional.

No teste historico, risco com as mesmas regras de seguranca teve F1 macro de 42.4% antes e 40.6% agora. Adicionar regras nao elimina as limitacoes de deteccao e pode aumentar falsos positivos.

A diferenca grande entre treino e avaliacao continua. Aumentar complexidade, ajustar regularizacao ou usar agrupamento nao resolveu sozinho a generalizacao. A revisao de uma fila selecionada de erros tambem nao constitui revisao uniforme de todo o conjunto. Isso fica registrado, sem exigir revisao humana integral para avancar no objetivo educacional.

## Experiencias

99 candidatos/comparacoes classicos e 12 checkpoints neurais.

TF-IDF de palavras/caracteres, BoW, SVM linear e RBF, regressao logistica, Naive Bayes, MLP, KNN supervisionado, reducao SVD/LSA, pesos para duvidas, classificacao hierarquica e soft voting. K-means com 30/60/120 centros foi ajustado somente no treino; foram testados frequencias de classes por cluster e atributos de proximidade dos centros.

Foi testada a retirada de avisos artificiais de coleta de imagens e estados sinteticos nos canais lexicais (TF-IDF), mantendo conversas/contextos reais. Os embeddings congelados preservam a entrada original para uma comparacao controlada. Tambem foi testado um foco lexical adicional nas ultimas palavras da mensagem. Os textos armazenados e o teste congelado nao foram reescritos.

MiniLM na GPU: contexto de ate 384 tokens, ajuste de 12 ou 4 camadas, AdamW, dropout, weight decay, suavizacao de rotulos, pesos de classes, peso 0,5 para duvidas e parada antecipada pela validacao. Nao e o TinyLM do zero.

### Selecionado: intent

Familia: classical.

```json
{
  "C_or_alpha": 0.5,
  "balanced": true,
  "kind": "svm",
  "number": 44,
  "seconds": 28.66,
  "task": "intent",
  "uncertain_training_weight": 0.5,
  "validation": {
    "accuracy": 0.6582694414019715,
    "classes_with_support": 39,
    "declared_classes": 60,
    "macro_f1_all_declared": 0.3564379226879682,
    "macro_f1_supported": 0.5483660349045664,
    "records": 913,
    "unsupported_classes": [
      "adjust_training_intensity",
      "adjust_training_volume",
      "ask_hydration",
      "calculate_body_metric",
      "change_diet_structure",
      "clarification",
      "confirm_planner_action",
      "defer_planner_action",
      "explain_current_plan",
      "greeting",
      "move_workout_day",
      "preserve_plan_constraint",
      "record_body_measurement",
      "record_food_intake",
      "record_training_load",
      "reject_planner_action",
      "remember_preference",
      "replace_meal_item",
      "set_day_activity",
      "undo_planner_action",
      "update_goal"
    ]
  },
  "view": "hybrid1"
}
```

### Selecionado: risk

Familia: classical.

```json
{
  "C": 2.0,
  "kind": "lr",
  "number": 86,
  "seconds": 15.28,
  "task": "risk",
  "uncertain_training_weight": 1.0,
  "validation": {
    "exact_match_accuracy": 0.7130339539978094,
    "macro_f1_all_positive_labels": 0.41936034115438003,
    "macro_f1_supported": 0.4414319380572421,
    "micro_f1": 0.5958378970427163,
    "none_accuracy": 0.8335158817086528,
    "positive_labels_with_support": 19,
    "records": 913,
    "unsupported_labels": [
      "musculoskeletal_red_flag"
    ]
  },
  "view": "query_hybrid"
}
```

### K-means medido

| Experiencia | Tarefa | F1 macro validacao |
| --- | --- | ---: |
| svm cluster30 | intent | 53.1% |
| svm cluster30 | intent | 51.5% |
| lr cluster30 | risk | 40.6% |
| lr cluster30 | risk | 41.1% |
| svm cluster60 | intent | 53.2% |
| svm cluster60 | intent | 51.3% |
| lr cluster60 | risk | 40.2% |
| lr cluster60 | risk | 42.2% |
| svm cluster120 | intent | 52.9% |
| svm cluster120 | intent | 51.4% |
| lr cluster120 | risk | 43.1% |
| lr cluster120 | risk | 42.5% |
| kmeans_frequency_baseline  | intent | 22.3% |
| kmeans_frequency_baseline  | risk | 14.9% |

K-means agrupa por proximidade sem aprender os rotulos. Para dar nomes aos grupos no baseline, foram usadas apenas as frequencias de rotulos do treino. Os clusters nao corrigem anotacoes automaticamente nem substituem a classificacao supervisionada por definicao. Referencia: https://scikit-learn.org/stable/auto_examples/text/plot_document_clustering.html

## Confianca e seguranca

| Conjunto | Mensagens aceitas | Acerto entre aceitas |
| --- | ---: | ---: |
| validation | 35.8% | 91.4% |
| test | 35.0% | 88.3% |
| external_human_language | 20.0% | 98.0% |

Isso mede abstencao, nao melhora artificialmente a accuracy principal. Os escores nao sao probabilidades calibradas. O alvo de 90% foi escolhido na validacao e nao garante 90% em pessoas novas. Intencoes com menos de cinco exemplos de validacao pedem esclarecimento, mesmo com margem alta.

A pipeline nova e opt-in. Nao altera automaticamente a pipeline operacional. Riscos do modelo se somam as regras conservadoras. None nao significa liberacao medica. Nao ha diagnostico, escolha de exame ou prescricao de tratamento para lesao. Qualquer alteracao de plano permanece como proposta, com validacao e confirmacao, nunca escrita direta pelo classificador.

## Limites e proxima fase

Os rotulos sao referencias de IA, nao gabarito humano independente. A revisao selecionou discordancias do modelo anterior e pode carregar vies desse modelo. O teste historico ja apareceu em relatorios anteriores: nao e um teste novo independente. Nao houve ajuste apos ver os resultados desta rodada. As limitacoes nao sao apagadas por uma accuracy maior.

O extrator de entidades e as 60 intencoes/21 riscos foram preservados. A planilha nao fornece spans de entidades: nao foi inventado um F1 novo para o extrator. O corpus TinyLM 1.2.0 nao recebeu explicacoes da IA nem conversas privadas automaticamente.

Para aprendizado e portfolio, a rodada pode ser encerrada e podemos seguir para 7.03.1 (tokenizador do TinyLM). Treinar o TinyLM nao depende de atingir 90% no classificador de intencao. Isso nao e aprovacao de producao: o Coach principal continuara precisando de avaliacao de ponta a ponta, com mecanismos de esclarecimento e confirmacao.

## Comando de inferencia

```powershell
python ai/scripts/analyze_message_corrected.py "Posso trocar meu treino de terca para quinta?"
```

Use o ambiente Python 3.12 com ai/requirements.neural.txt. Pesos e textos privados permanecem fora do Git. Nao foram enviados textos para APIs externas.

## Verificacao final

224 testes de regressao no runtime original: 220 passaram e 4 foram pulados por dependencias/runtime. No runtime dos novos modelos, os 16 testes focados passaram, incluindo as tres integracoes com pesos reais. Os dois adaptadores neurais foram carregados e produziram saidas finitas de dimensoes 60/20.

Hashes de dados reservados, modelos, selecao e fontes conferidos. Todas as 12.179 mensagens tiveram previsao e as 405 linhas de metricas por classe foram preservadas. Nenhum ajuste de modelo ocorreu depois da abertura do teste desta rodada.

O encoder legado mantem um cache local de embeddings com chaves hash. Isso nao e texto bruto de conversa nem treinamento automatico, mas sao dados derivados que tambem exigem politica de retencao antes de producao.

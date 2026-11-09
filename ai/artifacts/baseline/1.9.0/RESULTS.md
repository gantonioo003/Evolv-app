# 7.07.3 — Comparação e reconhecimento 1.9.0

Experimento concluído em 03/11/2026, somente com treino e validação. O teste reservado não foi aberto. O Coach em uso continua na versão anterior; a nova composição é opt-in de desenvolvimento.

## Resultado de intenção

| Estrato | Accuracy anterior | Accuracy nova | Macro F1 anterior | Macro F1 novo |
| --- | ---: | ---: | ---: | ---: |
| legacy, n=913 | 65.83% | 65.50% | 54.84% | 56.35% |
| actions_synthetic, n=146 | 63.70% | 76.71% | 61.19% | 75.50% |
| combined, n=1059 | 65.53% | 67.04% | 59.61% | 66.02% |

Macro F1 acima inclui as classes presentes em cada estrato: 39 na validação anterior, 26 na sintética e 57 na união. A comparação anterior/nova usa exatamente os mesmos registros e classes em cada linha. Métricas sobre todas as 60 classes também estão no JSON.

O ganho na união não deve esconder a pequena queda de accuracy no estrato anterior (65,83% → 65,50%). O macro F1 desse estrato melhorou. Os 146 exemplos novos são sintéticos do projeto, não um teste independente com usuários.

## Seleção predefinida

Foram comparadas 11 configurações de intenção e quatro de risco, além do baseline congelado. O protocolo foi gravado antes do treinamento: protocol.json.

Intenção: SVM linear e regressão logística, diferentes C, TF-IDF da entrada completa, foco na mensagem com contexto reduzido, embeddings MiniLM congelados e peso dos novos exemplos de 1 ou 3. Vocabulários novos foram ajustados só no treino.

O candidato precisava manter a perda de macro F1 anterior em até 0,02 e a de accuracy em até 0,01. Entre os elegíveis, a seleção maximizou 0,65 × F1 anterior + 0,35 × F1 sintético. Isso permite pequeno compromisso, não garante melhora em toda classe.

Configuração escolhida:

    Mensagem → TF-IDF palavras/caracteres
    Contexto → TF-IDF palavras/caracteres × 0,35
    Entrada com contexto → MiniLM congelado, 384 dimensões
                       ↓ concatenação
           SVM linear, C=1, classes balanceadas
           novos exemplos de treino com peso 3

A representação full, a separação de contexto e os embeddings foram comparados; não são três modelos em sequência nem três saídas somadas. O classificador de intenção recebe as características concatenadas.

## Confiança sem ajustar aos quatro pedidos conhecidos

O hiperparâmetro do classificador foi selecionado na validação. Depois, a margem de abstinência foi estimada com previsões out-of-fold em três divisões do treino por group_id. Cada divisão reajustou seu próprio vocabulário sem usar o grupo avaliado. O encoder ficou congelado.

O objetivo permaneceu 90% de acerto entre aceitos na calibração, com mínimo de 30 aceites e cinco referências de validação por classe. Nenhum dos quatro pedidos diagnósticos foi usado para escolher C, pesos, representação ou margem. Não foi aplicado um limiar especial para fazê-los passar.

A margem numérica escolhida foi 0,043899, versus 0,025621 no modelo anterior. São scores não calibrados de modelos diferentes; não são probabilidades nem uma escala diretamente comparável. Os critérios foram mantidos, e não houve relaxamento manual.

| Estrato | Aceitos antes → agora | Acerto entre aceitos antes → agora | Cobertura nova |
| --- | ---: | ---: | ---: |
| legacy | 327 → 256 | 91.44% → 94.92% | 28.04% |
| actions_synthetic | 0 → 49 | sem aceites → 97.96% | 33.56% |
| combined | 327 → 305 | 91.44% → 95.41% | 28.80% |

O modelo novo aceita 305 de 1.059 mensagens: 291 acertos e 14 erros. Os demais 754 casos ficam para esclarecimento. Portanto, 95,41% entre aceitos não é accuracy geral, nem taxa de ações concluídas. O alvo de 90% na calibração não é garantia estatística para pessoas novas.

O gate antigo não aceitava nenhum dos novos exemplos, em parte por não ter suporte de validação registrado para várias classes. O gate novo usa contagens da validação nova, que incluem sintéticos. O ganho de aceites não pode ser atribuído só aos pesos do SVM: também mudou a evidência disponível para suporte e a calibração.

Uma dobra de calibração treinou com 59 classes; as outras duas, com 60. Grupos raros e distribuições desiguais limitam a confiabilidade da calibração. Não reajustamos os grupos até obter um resultado mais bonito.

## Risco

As quatro regressões logísticas novas (C=0,5/2, com e sem balanceamento) perderam macro F1 no estrato anterior. Nenhuma foi promovida. Foi mantido o classificador de risco anterior: regressões logísticas multirrótulo, representação query_hybrid, C=2.

Na validação anterior: exact match 71.30%, micro F1 59.58%, macro F1 das classes presentes 44.14%. Não houve ganho de risco nesta etapa.

Os novos sintéticos têm risco none. Neles, 145/146 ficaram sem risco previsto. Esse estrato não contém positivos e não mede recall de risco; seu F1 positivo igual a zero não deve ser interpretado como falha em detectar riscos presentes. Os limiares dos candidatos de risco usaram apenas a validação anterior, onde existem positivos.

## Classes prioritárias — novo estrato sintético

| Classe | Suporte | Precisão | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| move_workout_day | 6 | 100.00% | 100.00% | 100.00% |
| set_day_activity | 6 | 100.00% | 83.33% | 90.91% |
| replace_exercise | 6 | 71.43% | 83.33% | 76.92% |
| replace_meal_item | 6 | 50.00% | 16.67% | 25.00% |

São só seis referências sintéticas por classe. Troca de alimento continua fraca: apenas um de seis casos reconhecido corretamente. Isso não foi escondido pela média nem corrigido reduzindo a confiança. Todas as classes/risco estão em class_details.json.

## Verificação e arquivos

Seis testes unitários passaram, cobrindo vocabulário sem validação, separação de métricas, suporte obrigatório, scores, rejeição de artefato e validação da entrada. Os modelos foram recarregados e as métricas dos 1.059 registros foram reproduzidas exatamente pelo caminho de inferência opt-in.

| Arquivo relativo a ai/ | Função |
| --- | --- |
| src/evolv_nlp/recognition_experiment.py | Comparação, seleção e calibração fora de grupo. |
| src/evolv_nlp/recognition_pipeline.py | Carrega modelos verificados e compõe intenção, risco e entidades, somente opt-in. |
| scripts/train_recognition.py | Executa o experimento versionado; recusa sobrescrever saída. |
| scripts/verify_recognition.py | Recarrega pesos e reproduz métricas na validação. |
| scripts/analyze_recognition.py | Experimenta mensagem local sem escrever no Planner. |
| artifacts/baseline/1.9.0/ | Protocolo, 15 resultados, seleção, métricas e calibração. |
| artifacts/baseline/1.9.0/private/ | Pesos, representações e cache privado local. |

O cache histórico do encoder não foi sobrescrito. Nenhum texto foi enviado a serviço externo. Dados, pesos e política anteriores foram preservados por hashes; arquivos privados novos estão ignorados pelo Git.

Para usar o experimento, em ai/ com o ambiente Python existente:

    python scripts/analyze_recognition.py "Quero substituir um exercício da minha ficha"

O treinador e verificador já finalizaram essa versão e recusam sobrescrever seus registros. Novos experimentos exigem outra versão.

## Decisão

Selecionar a intenção 1.9.0 como candidata de desenvolvimento e conservar o risco anterior. Não trocar automaticamente o Coach do aplicativo nesta etapa. A calibração e os sintéticos não autorizam execução direta: continuam necessárias as travas de risco, contexto autenticado, contrato tipado e confirmação.

O teste reservado não foi aberto e não há nova métrica de teste. A validação anterior tem histórico de revisão, a nova é sintética do mesmo autor, e ambas participaram da seleção: estes números não são certificação de generalização. Permanece a incompatibilidade de activity_type no extrator/roteador. O ganho de reconhecimento não prova geração de propostas ou aplicação de ações; isso será verificado na etapa de fluxo completo.

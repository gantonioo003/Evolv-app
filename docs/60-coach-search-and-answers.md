# 9.05 — Busca e resposta

10/11/2026 · Base de busca 1.2.1

## Como o Coach responde

- **Pergunta de conhecimento.** O Coach recupera o trecho revisado que cobre a dúvida. Quando a pergunta e o documento já são conhecidos, busca pelo ID e confere se a revisão e as fontes continuam válidas. Isso resolve o caso da pausa entre séries, em que um texto sobre atletas aparecia antes da explicação geral.
- **Pergunta com duas partes.** Para uma definição de deload acompanhada da dúvida sobre frequência, mostra os dois trechos que sustentam a resposta. Se uma parte ficar sem apoio, indica a lacuna e cita apenas o conteúdo usado. [Consenso Delphi sobre deload](https://link.springer.com/article/10.1186/s40798-023-00633-0)
- **Pergunta sobre a ficha.** Usa os dados da própria conta para identificar o exercício, a faixa de repetições, os alimentos da refeição e as substituições que o plano aprova. Se a mesma informação varia entre sessões ou refeições, pede o dia ou a refeição. O motivo individual de uma escolha só pode ser explicado quando estiver disponível na ficha.
- **Evidência insuficiente.** Quando a pergunta pede uma precisão ou explicação ausente, o Coach indica o ponto que falta. Uma dúvida sobre um hormônio específico deixa de receber uma definição de deload como se fosse resposta. Os casos de risco continuam passando pela proteção antes da busca.

## Cobertura adicionada

O índice ganhou dois trechos e passou de 138 para 140. A conferência confirmou que os textos e vetores dos 138 trechos anteriores são idênticos. Os conteúdos novos usam paráfrases com seção e revisão registradas.

- Carga, séries e repetições em um único exemplo. [Better Health Channel — Governo de Victoria](https://www.betterhealth.vic.gov.au/health/healthyliving/resistance-training-health-benefits)
- Exemplos práticos de lanche antes do treino com contexto de tempo e tolerância. [Sports Dietitians Australia](https://www.sportsdietitians.com.au/wp-content/uploads/2020/07/Pre-exercise-Fuelling.pdf)

## Validação local

As mesmas 24 perguntas autorais em português foram executadas antes e depois no gerenciador de sessões FastAPI, com Qwen original, busca local e fichas de teste. Para passar, a resposta precisava citar a evidência esperada ou indicar a lacuna pedida, além de manter a consulta sem propostas. A versão nova também passou com o NLP 1.8.0, padrão do serviço.

| Grupo | Antes · NLP 1.9.0 | Depois · NLP 1.9.0 | Depois · NLP 1.8.0 |
| --- | ---: | ---: | ---: |
| Treino | 3/4 | 4/4 | 4/4 |
| Deload | 1/3 | 3/3 | 3/3 |
| Dieta | 2/4 | 4/4 | 4/4 |
| Recuperação | 1/3 | 3/3 | 3/3 |
| Ficha | 1/5 | 5/5 | 5/5 |
| Lacunas e ambiguidades | 0/4 | 4/4 | 4/4 |
| Segurança | 1/1 | 1/1 | 1/1 |
| **Total** | **9/24** | **24/24** | **24/24** |

Passaram **107 testes Python direcionados** e **7 verificações adicionais** com o NLP e a busca reais, incluindo explicação de carga, continuação sobre pausas, isolamento da ficha e prioridade de risco.

No reteste das 14 conversas de ajuste da 9.04, com 59 mensagens, as três propostas esperadas foram identificadas e nenhuma proposta indevida foi criada. Os cinco turnos de proteção ficaram sem ações. A pergunta sobre carga e repetição recuperou o novo trecho. [Reteste de continuidade](../ai/artifacts/coach_quality_sources/1.0.0/continuity/turns.jsonl)

O conjunto de 24 perguntas orientou os ajustes. O resultado mede esses cenários. Em perguntas livres, a escolha da evidência ainda depende do ranking e do seletor de trechos. A validação no iPhone continua pendente.

[Antes](../ai/artifacts/coach_quality_sources/1.0.0/before/answers.jsonl) · [Depois, NLP 1.9.0](../ai/artifacts/coach_quality_sources/1.0.0/final/answers.jsonl) · [Depois, NLP padrão](../ai/artifacts/coach_quality_sources/1.0.0/default_nlp/answers.jsonl) · [Continuações e segurança](../ai/artifacts/coach_quality_sources/1.0.0/focused_followups.json)

## Executar

A FastAPI carrega o índice 1.2.1 ao iniciar. Para usar a nova versão numa instância já aberta, reinicie o serviço de IA. O índice anterior pode ser selecionado explicitamente pela variável `EVOLV_AI_RETRIEVAL_VERSION`.

Na raiz do projeto, com o ambiente de IA ativo e os modelos locais instalados:

```powershell
python -B ai/scripts/evaluate_coach_sources.py --output ai/artifacts/coach_quality_sources/reteste-local
```

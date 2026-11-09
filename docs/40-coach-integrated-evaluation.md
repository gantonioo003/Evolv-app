# 7.05.5 — Avaliação integrada

Executamos 11 conversas autorais com 22 mensagens no pipeline real:
NLP 1.8, extrator, MiniLM, busca e Qwen com LoRA. O contexto foi mantido
dentro de cada conversa e limpo entre conversas. Os planos usados são
fictícios; não houve conexão ao backend, banco ou conta real.

## Resultados e arquivos

Relatório principal:
ai/artifacts/coach_evaluation/1.0.0/RESULTS.md

Conversas legíveis:
ai/artifacts/coach_evaluation/1.0.0/conversations.html

- data/evaluation/coach_dialogues.v1.json: protocolo autoral de desenvolvimento.
- scripts/evaluate_coach_dialogues.py: execução real, com protocolo e hashes.
- src/evolv_rag/integrated_evaluation.py: observações e contagens por turno.
- artifacts/coach_evaluation/1.0.0/turns.jsonl: resultados completos preservados.
- artifacts/coach_evaluation/1.0.0/review.json: revisão qualitativa assistida por IA.
- scripts/evaluate_coach_contract_dialogues.py: dez diálogos de contratos.
- artifacts/coach_contract_evaluation/1.0.0/: 24 mensagens de contrato.
- scripts/verify_coach_dialogue_regressions.py: regressões reais após correção.
- artifacts/coach_evaluation/1.0.0/regressions/: registro dirigido pós-correção.
- scripts/report_coach_dialogues.py: gera relatório e HTML dos resultados salvos.

Os dez diálogos de contrato usam intenção/confiança conhecidas simuladas,
extrator real e nenhum LM. Todos passaram, mas isso não significa que o
classificador consegue reconhecer aqueles pedidos com confiança suficiente.
O resultado do pipeline real teve zero propostas nos quatro pedidos de
mudança. Essa limitação é explicitada, sem contar o bloqueio como tarefa
concluída.

A primeira execução teve três respostas geradas, uma com citação no texto
e um erro de contexto. Também houve uma falha importante de prioridade:
a emergência relatada anteriormente foi ignorada diante de privacidade.
O relatório detalha todas as mensagens e expectativas não atendidas.

## Correções e continuidade

Corrigimos a contagem de tokens do contexto para usar o mesmo tensor
aplicado na geração. A chamada anterior usava len do retorno do template,
que não garantia medir o comprimento de input_ids no runtime instalado.
Nenhuma janela foi ampliada para mascarar o problema.

As regras agora consideram sinais críticos nas duas mensagens recentes
do usuário antes da rota de privacidade. Não usam respostas do modelo
como fatos sobre saúde. É uma correção limitada: não há cadastro durável
de alergias ou resolução completa de mudanças de assunto.

Também corrigimos o reconhecimento de formulações plurais como
"minhas conversas treinam seu modelo?". Os pesos, as políticas de confiança
dos classificadores e os limiares da busca não foram ajustados nesta fase.

Os scripts preservam a rodada inicial e seus arquivos de código em
code_at_run/, com os hashes originais. A regressão posterior é marcada
explicitamente como desenvolvimento dirigido após observar falhas.
Não é um segundo teste independente nem uma nova medida de accuracy/F1.
Os testes congelados das fases 7.02 e 7.04 não foram reavaliados.

O primeiro avaliador aceitava qualquer preflight como resposta controlada
nos exemplos de risco, incluindo privacidade. A revisão detectou que esse
check era insuficiente; uma regressão específica exige emergência na
continuação. O resultado antigo não foi reescrito para esconder esse erro.

Trinta testes automatizados do Coach, ações, regressões e avaliador passaram.
A regressão dirigida passou nos quatro cenários de janela e roteamento
(sete mensagens). Isso não significa sete respostas úteis: a continuação
sobre treino ao acordar coube na janela, mas a resposta gerada foi barrada
pelo filtro. O problema de fundamentação/utilidade não está resolvido.
A qualidade geral ainda exige melhorar relevância da busca, fundamentos
das respostas, esclarecimentos e confiança do NLP, com novos casos de
desenvolvimento e avaliação independente antes da integração no produto.

## Reproduzir

Na pasta ai/, com o ambiente Python do projeto:

    python scripts/evaluate_coach_dialogues.py --output artifacts/coach_evaluation/nova-rodada

Esse comando exige o ambiente CUDA já usado pelo Qwen, não baixa modelos,
não treina e não aplica ações. Uma saída existente não é sobrescrita.
Para consultar o experimento concluído, basta abrir os resultados.

O relatório de 1.0.0 pode ser regenerado a partir dos mesmos registros:

    python scripts/report_coach_dialogues.py

A revisão assistida por IA leu todas as respostas registradas, sem revisão
humana ou clínica independente. A conclusão é manter a pesquisa local;
concluir o experimento não aprova uso autônomo nem integração ao app.

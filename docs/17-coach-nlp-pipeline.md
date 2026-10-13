# Coach 7.02.4 - Confianca e pipeline final

## Objetivo

A fase 7.02.4 une os componentes da 7.02 em uma saida unica e tipada:

```text
mensagem
  -> intencao e alternativas
  -> risco e severidade
  -> entidades normalizadas
  -> topicos
  -> decisao, esclarecimento ou proposta
```

Ela nao melhora artificialmente o modelo 1.0.0. Quando a evidencia e fraca,
a pipeline admite a duvida e pede esclarecimento.

## Politica de confianca

Os limites foram definidos usando apenas `validation`. O teste congelado e o
conjunto `challenge` nao participaram da escolha.

Intencao exige score minimo `0,15` e margem minima `0,10` sobre a segunda
alternativa. Nenhuma previsao da validacao passou pelos dois limites. Isso
confirma que o baseline ainda nao pode tomar decisoes automaticamente.

Risco exige score `0,13` e margem `0,03` para substituir a rota normal. Seis
das treze mensagens de validacao passaram pelo limite, e as seis receberam o
rotulo correto. O numero e pequeno e as probabilidades nao sao calibradas;
portanto, a politica continua provisoria e conservadora.

Na validacao, a porta de intencao aceitou `0/30` mensagens e a porta de risco
aceitou `6/13`, todas corretas entre as aceitas. Cobertura zero de intencao nao
e sucesso de produto: e uma protecao temporaria que impede o modelo fraco de
executar mudancas enquanto a proxima versao de dados nao for treinada.

Um risco nao nulo abaixo do limite nao e ignorado: gera esclarecimento com
cautela. Um risco aceito sempre tem prioridade sobre a intencao.

## Decisao

Ordem das regras:

1. risco aceito produz uma resposta de seguranca;
2. risco incerto pede esclarecimento;
3. intencao abaixo do limite pede esclarecimento;
4. entidades obrigatorias ausentes pedem o detalhe faltante;
5. perguntas seguem para resposta futura;
6. mudancas viram uma proposta do Planner, nunca escrita direta.

O Planner recebe `writes_allowed: false` e
`requires_confirmation: true`. A pipeline nao altera treino, dieta ou banco.

Horario de treino e contexto opcional. A ausencia dele nao bloqueia uma dieta
base nem provoca perguntas diarias. Quando informado voluntariamente, ele deve
ser usado por uma versao futura do extrator para propor ajuste de horario das
refeicoes, sempre com confirmacao.

Um pedido de fortalecimento acompanhado de dor ou incomodo articular segue
primeiro pela rota de seguranca. O Coach pode futuramente oferecer educacao
geral depois da triagem, mas nao diagnostica nem transforma o pedido em
progressao automatica.

## Topicos

Os topicos sao multirrotulo e combinam tres evidencias:

- termos encontrados no texto usando os aliases da taxonomia;
- topicos normalmente associados a intencao candidata;
- topicos sugeridos pelas entidades encontradas.

Cada topico informa suas fontes, como `lexical`, `intent_hint` ou
`entity_hint`. Isso deixa a decisao auditavel.

## Contrato de saida

`ai/data/schema/coach-analysis-output.schema.json` define os blocos:

- `decision`: status, rota e motivos;
- `intent`: rotulo, alternativas, score, margem e entidades obrigatorias;
- `risk`: rotulo, severidade, rota e regra de resposta;
- `entities`: valores, spans e origem da extracao;
- `topics`: assuntos e evidencias;
- `clarification`: motivo e pergunta curta;
- `planner_proposal`: acao tipada, argumentos e confirmacao;
- `guardrails`: limites que as proximas fases devem preservar.

Por privacidade, a saida registra hash e tamanho da mensagem, nao uma copia do
texto. A aplicacao pode salvar a conversa separadamente com sua propria
politica de consentimento e retencao.

## Organizacao

```text
ai/data/pipeline/
  confidence_policy.v1.json
  topic_rules.v1.json
ai/src/evolv_nlp/
  topics.py
  pipeline.py
ai/scripts/
  analyze_message.py
  evaluate_pipeline.py
ai/artifacts/pipeline/1.0.0/
  confidence_metrics.json
  sample_outputs.jsonl
  manifest.json
ai/tests/test_pipeline.py
```

A pesquisa de fontes e os casos destinados ao dataset `1.3.0` estao em
`docs/18-coach-dataset-expansion-research.md`. O arquivo estruturado correspondente
fica em `ai/data/research/dataset-expansion-candidates.v1.json`. Nenhuma linha
externa foi importada durante a 7.02.4.

## Limites

- o baseline de intencao abstera na maioria das mensagens;
- scores nao sao probabilidades calibradas;
- referencias como `ele` ainda precisam do historico da conversa;
- topicos sao encontrados por regras, nao por um classificador treinado;
- a pipeline estrutura o pedido, mas ainda nao produz a resposta textual;
- FastAPI, LM, busca e integracao com NestJS pertencem as proximas fases.
- horario de treino, sintomas detalhados e contexto multi-turno ainda precisam
  de exemplos anotados e extracao dedicada na futura versao `1.3.0`.

## Comandos

```powershell
python ai/scripts/evaluate_pipeline.py
python ai/scripts/analyze_message.py "amanha troca supino por flexao" --reference-date 2026-10-08
python -m unittest discover -s ai/tests -v
```

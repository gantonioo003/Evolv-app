# Coach: Planilhas Revisadas e Risco Multirrotulo

Fechamento de todas as rodadas: `ai/artifacts/review/2026-10-19/RESULTS.md`.
Baseline recomendado pela validacao: `1.6.0` nas duas tarefas. Tambem foram
medidas 16 variantes BoW/TF-IDF/MLP (`1.6.1`) e dois ajustes parciais de MiniLM
com quatro epocas cada (`1.7.0`), sem superar a recomendacao na validacao.

## O Que Muda

Esta rodada usa os quatro arquivos revisados fornecidos em outubro de 2026.
O objetivo e melhorar o entendimento do Coach, sem alterar telas, backend,
Planner, TinyLM ou a ativacao padrao do aplicativo.

| Componente | Anterior | Novo |
| --- | --- | --- |
| Dataset de trabalho | 1.6.0, candidatos fracos | 1.7.0, 12.179 registros revisados por IA |
| Intencoes | 41 | 60 |
| Riscos declarados | 18, saida unica | 21, varios sinais simultaneos |
| Entidades declaradas | 89 | 89 |
| Entidades com implementacao | 50 | 80 |
| Extrator experimental | 1.2.0 | 1.3.0 |
| Regras de risco | 1.3.0 | 1.4.0 |
| Modelos experimentais | baseline 1.5.0 | baseline 1.6.0 |

As versoes antigas continuam intactas. O pipeline novo e opt-in; nao foi
ligado automaticamente ao aplicativo. Melhorar o classificador nao exige
recomecar o TinyLM e nao garante a qualidade futura das respostas do Coach.

## Caminho Dos Arquivos

```text
4 planilhas + taxonomia + metadados de proveniencia
  -> scripts/import_reviewed_workbooks.py
  -> src/evolv_nlp/review_release.py
  -> data/releases/1.7.0/private/{train,validation,test,...}.jsonl

scripts/train_reviewed_baseline.py
  -> src/evolv_nlp/review_training.py
  -> TF-IDF de palavras/caracteres e/ou MiniLM local congelado
  -> classificador de intencao + classificador multirrotulo de risco
  -> artifacts/baseline/1.6.0/

data/catalogs/entity_catalogs.extension.v1.3.json
  -> src/evolv_nlp/entities_v14.py
  -> artifacts/entities/1.3.0/manifest.json

scripts/analyze_message_1_4.py
  -> src/evolv_nlp/pipeline_v14.py
  -> intencao + riscos + entidades + topicos + rota segura
```

`fit()` ajusta somente com treino. `predict()` e probabilidades de riscos sao
usados na validacao para comparar candidatos. Os dois vencedores, limites de
risco e politica de confianca sao salvos **antes de abrir o teste**.
Nao ha treino no teste nem expansao sintetica dos exemplos reservados.

## Experimento

40 candidatos: quatro representacoes (TF-IDF, MiniLM, combinacoes com pesos 1 e 2),
SVM linear e regressao logistica para intencao; regressao logistica um-contra-resto
para risco. Comparam-se regularizacao L2 e pesos de classes, sem alterar o encoder.
O vocabulario TF-IDF e aprendido somente no treino. Contexto anterior e mensagem
atual sao separados; observacoes da revisao e respostas esperadas nunca sao features.

Risco tem 20 saidas positivas independentes. `none` e derivado quando nenhuma
ultrapassa seu limite; isso nao significa que a atividade e segura.
Limites por risco usam apenas validacao e suporte minimo; riscos muito raros
compartilham um limite global. Esse ajuste nao transforma scores em probabilidades
calibradas nem substitui validacao de seguranca.

A confianca da intencao usa a diferenca entre as duas maiores pontuacoes.
A politica procura 90% de acerto entre os aceitos na validacao com pelo menos
30 exemplos; quando nao consegue, nao libera aceitacao automatica.
O relatorio inclui cobertura e acerto dos aceitos, mas a metrica principal
continua contando **todas** as previsoes, inclusive as erradas.

## Como Ler Os Resultados

Numeros medidos ficam em `ai/artifacts/baseline/1.6.0/evaluation.json` e a
comparacao com o modelo anterior em `comparison.json`. O resumo legivel e
`ai/artifacts/baseline/1.6.0/RESULTS.md`.

- Accuracy de intencao: quantas mensagens receberam a classe correta.
- Macro F1 com suporte: media de F1 das classes presentes naquele conjunto.
- Macro F1 de todas as 60: inclui zeros para classes sem suporte; leia junto com cobertura.
- Risco: acuracia de conjunto exato, micro F1 e macro F1 dos sinais positivos.
- Acuracia antiga de risco unico e acuracia nova de conjuntos nao sao a mesma tarefa.
- A comparacao anterior/nova usa as mesmas entradas e rotulos compartilhados.
- A referencia foi revisada por IA; nao comprova desempenho humano/clinico.
- Pesquisa externa e importante, mas 255 mensagens nao cobrem todas as 60 classes.
- Casos de `quarantine` recebem analise separada, sem entrar no resultado principal.

## Entidades e Seguranca

Foram acrescentadas regras/catalogos para medicamentos, suplementos, nutrientes,
condicoes apenas mencionadas, nivel de treino, preparo, unidades, ambiente,
amplitude, fome, estresse, orcamento, turno, prazo e referencias a mudancas.
Termos de condicoes recebem atributos de negacao, hipotese ou terceira pessoa;
extrair "diabetes" nao conclui que o usuario tenha diabetes.

O extrator percorre as 12.179 mensagens e verifica spans originais. A regressao
historica compara os mesmos 50 tipos antigos. Nao ha F1 independente dos 30 tipos
novos: as planilhas nao anotaram entidades exaustivamente. Testes de exemplos
positivos/negativos verificam funcionalidades, nao substituem esse gabarito.

Regras de risco distinguem uso de medicamento de pedido de dose, sintomas
sistemicos de dor musculoesqueletica e doenca aguda de relato remoto resolvido.
Emergencia e crise prevalecem sobre alteracao de plano. Dor permite informacao
geral e encaminhamento, nunca diagnostico, escolha de exame ou tratamento de lesao.

Confirmacao, recusa, adiamento e desfazer exigem estado confiavel da proposta.
"Sim" isolado ou texto gerado pelo assistente nao autorizam o Planner.
Mesmo uma intencao confiante nunca grava alteracao: `writes_allowed=false`.

## Privacidade

Os textos, previsoes individuais, extracoes e modelos ficam em diretorios privados
ignorados pelo Git. Relatorios publicos contem contagens e hashes, nao conversas.
Minimizacao automatica nao e anonimizacao comprovada. A autorizacao nesta conversa
nao certifica licencas de terceiros; uso comercial e publicacao exigem revisao.
O treinamento do NLU nesta rodada e deliberado e local, nao autorizacao permanente
para treinar com futuras conversas. O pipeline nao armazena conversas automaticamente.
OneDrive continua podendo sincronizar os arquivos privados da maquina.

## Reproduzir

Use Python 3.14.3 com `ai/requirements.review.txt` para o experimento e os testes
historicos. Os manifestos registram versoes e hashes; modelos joblib sao locais
e so sao carregados depois de validar caminho e SHA-256.

```powershell
python -m pip install -r ai/requirements.review.txt
python -m unittest discover -s ai/tests
python ai/scripts/analyze_message_1_4.py "muda o treino de hoje para amanha"
```

Importacao, treino e auditoria de entidades recusam sobrescrever releases
finalizados. Nova coleta ou nova rodada de tuning exige nova versao e nao deve
ser escolhida pelo resultado de um teste ja observado.

## Experimentos Adicionais

`bow_mlp_review.py` compara BoW e TF-IDF com/sem stopwords, reducao SVD128,
MLP (128,64), Adam, L2 e early stopping interno ao treino. Palavras como nao
e sem nao estao na lista de remocao. Nao se conclui que remover stopwords ou
usar redes seja pior em geral; essas variantes especificas nao venceram.
A camada final do MLP ja classifica. Uma regressao adicional exigiria um
protocolo proprio de stacking/calibracao, com previsoes fora da amostra.

`neural_review.py` ajusta somente as quatro ultimas camadas do MiniLM, mantendo
embeddings e oito camadas anteriores congelados. Duas cabecas aprendem intencao
e risco, com dropout 0.2, AdamW, decaimento 0.01, warmup, clipping e perdas
ponderadas. Foram dois learning rates e quatro epocas por perfil, escolhendo
checkpoints por tarefa na validacao. Textos maiores que 256 tokens preservam
inicio/fim; o relatorio registra truncamento. Os pesos novos sao safetensors.

O experimento neural usa um ambiente isolado Python 3.12.14 com
`requirements.neural.txt`; nao substitui o Python 3.14.3 dos modelos historicos.
A GPU RTX 5050 foi verificada antes do treino. A inferencia neural e opt-in por
`analyze_message_neural.py`; nao se tornou a pipeline recomendada ou operacional.

Instalacao/arquitetura foram conferidas nas documentacoes oficiais de
[PyTorch](https://pytorch.org/get-started/locally/) e
[Hugging Face AutoModel](https://huggingface.co/docs/transformers/model_doc/auto).
Nenhuma pergunta privada foi enviada nesses acessos; baixaram-se somente dependencias e pesos.

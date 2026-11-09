# Evolv AI

Esta pasta concentra o Coach local do Evolv. Ela fica separada de `backend/`
porque dados, avaliacao e modelos usam Python, enquanto a API principal e as
regras de negocio continuam no NestJS.

## Status

**7.07.11 — avaliação no computador concluída:** Expo Web, NestJS,
FastAPI, Qwen e Supabase foram exercitados no Edge. Houve 46 mensagens,
50 verificações operacionais aprovadas e três de quatro pedidos de mudança
completos. O roteiro principal mediu p50 de 11,95 s, p95 de 20,31 s, pico de
2,04 GiB de RAM da IA e 3,33 GiB de VRAM reservada pelo PyTorch.
A busca 1.1.2 corrigiu a recuperação de hidratação e a fonte apareceu no
navegador. Relatório em docs/56-coach-desktop-evaluation.md.

**7.07.10 — segurança reavaliada:** urgências em linguagem informal,
reações após ingestão e pedidos de privacidade receberam verificações
antes da geração. Alertas críticos são preservados nos turnos recentes
mesmo após a máscara de endereço. A urgência cancela uma proposta pendente.
Na FastAPI local, 172 verificações passaram em 32 registros na rodada final.
Relatório em docs/55-coach-safety-reassessment.md. Evidências em
artifacts/coach_safety/1.0.0/.

**7.07.9 — conversas completas avaliadas:** 10 roteiros, 26 turnos em cada
versão do NLP, pela FastAPI local com busca e Qwen reais. Alimentação, troca
explícita de assunto, retomada do histórico e segurança funcionaram nos
casos testados. As duas versões falharam na lembrança de preferências e
na troca explícita após esclarecimento. O 1.9.0 propôs descanso e aceitou
a confirmação somente na sessão correta. Resultados e exemplos em
docs/54-coach-multiturn.md e artifacts/coach_multiturn/.

**7.07.8 — respostas com trechos citados:** o Qwen escolhe uma fonte entre
até três candidatos. O Coach exibe o trecho integral e sinaliza quando a base
cobre só parte do pedido ou quando faltam evidências. Nos 14 casos autorais,
houve seis lacunas esperadas reconhecidas, quatro respostas completas e
resposta útil em mais dois casos. A rodada também mostrou limitações em
hidratação, perguntas compostas e no encaminhamento de deload pelo NLP.
Relatório em docs/53-coach-grounded-answers.md. Resultados em
artifacts/grounded_answers/1.0.0/final/.

**7.07.7 — busca melhorada e conectada ao Coach:** índice ativo 1.1.1 com
107 trechos, combinação de significado/palavras/caracteres e contexto apenas
de mensagens anteriores do usuário. Na reserva autoral de desenvolvimento,
Hit@3 passou de 15/32 para 27/32 sobre o mesmo conteúdo; continuações de
5/12 para 12/12. Permanecem cinco alvos perdidos e uma regressão de rejeição
numa pergunta de SQL do conjunto antigo, explicitadas no relatório.
96 testes passaram e 20 mensagens usaram a API com NLP/busca reais; o NLP
ainda pode pedir esclarecimento antes da busca. Nenhum resultado mede
qualidade da geração ou é teste humano independente. Textos do conhecimento
preservados; 1.2.1 atualiza o vínculo ao código do Coach. Guia/resultados:
docs/52-coach-retrieval-improvement.md; registros:
artifacts/retrieval_evaluation/1.0.0/ e artifacts/retrieval_integration/1.0.0/.

**7.07.6 — conhecimento revisado e ampliado:** nova base 1.2.0 com 107
trechos (40 novos), dez documentos anteriores ajustados e 47 fontes
cadastradas. Trinta entradas tiveram conferência de escopo nesta etapa;
17 mantêm explicitamente o estado herdado. Os 15 temas sem trechos e oito
rótulos de risco adicionais receberam conteúdo delimitado; isso é cobertura
nominal, sem garantia de qualidade de resposta. Seis complementos antes em
quarentena foram regularizados. Vinte testes passaram; pesos, dados e
limiares anteriores preservados. Snapshot pronto para indexar:
data/rag/1.1.0/. **O índice ativo ainda tem 67 trechos**; atualizar e avaliar
a busca é a 7.07.7. Método e limites: docs/51-coach-knowledge-review.md;
base: data/knowledge/1.2.0/; evidências: artifacts/knowledge_review/1.0.0/.

**7.07.5 — mudanças validadas com serviços reais:** reconhecimento 1.9.0
selecionado explicitamente na FastAPI; o padrão permanece 1.8.0. Doze casos,
92 verificações aprovadas e nenhuma falha na rodada final. Duas remarcações
e um pedido de descanso completaram proposta, prévia, aplicação e desfazer;
o mesmo ciclo foi conferido pelos botões da tela do Coach no navegador.
Cardio e trocas de exercício/alimento ainda pedem esclarecimento por baixa
confiança; não contam como alterações concluídas. Nenhum limiar foi reduzido.
72 testes locais aprovados. Geração do LM desativada nesta avaliação de ações;
não é nova accuracy/F1 nem validação do iPhone. As quatro contas temporárias
das duas rodadas remotas foram excluídas; datasets e classificadores preservados.
Método, limitações e reprodução: docs/50-coach-real-action-validation.md;
evidências finais: artifacts/coach_action_flow/1.0.2/.

**7.07.4 — esclarecimentos dirigidos implementados:** perguntas por campos
faltantes, diferenciação de intenção incerta e impedimentos do plano. O campo
activity_type foi harmonizado no extrator 1.3.1 e no preparador; não se pede
novamente a atividade explícita. Indícios de troca podem orientar só a pergunta,
sem modificar o rótulo/confiança do classificador ou autorizar ações.
69 testes de Coach/FastAPI e cinco de entidades passaram; 12 chamadas com
NLP real, sem LM/banco, foram conferidas. Dois checks históricos completos
têm incompatibilidades registradas, sem alteração dos artefatos antigos.
Sem retreino ou troca automática do NLP padrão. Método e limites:
docs/49-coach-directed-clarification.md; registros: artifacts/clarification/1.0.1/.

**7.07.3 — comparação concluída (reconhecimento 1.9.0, opt-in):** 11 ajustes
de intenção e quatro de risco comparados sem abrir o teste reservado. Intenção:
macro F1 combinado de validação 59,61% → 66,02%; no estrato anterior,
54,84% → 56,35%; no sintético, 61,19% → 75,50%. SVM linear com mensagem,
contexto reduzido e MiniLM congelado foi selecionado. Risco anterior mantido:
as alternativas pioraram. Confiança calibrada em três dobras de grupos do
treino; na validação, 95,41% de acerto entre 305 aceites (28,80% de cobertura).
Não é accuracy geral nem teste humano independente. O Coach padrão não foi
trocado; a baixa cobertura de troca alimentar continua pendente. O contrato
activity_type foi corrigido na 7.07.4 e validado com descanso na 7.07.5.
Método/resultados: docs/48-coach-recognition-comparison.md; artefatos:
artifacts/baseline/1.9.0/; uso explícito: scripts/analyze_recognition.py.

**7.07.2 — dados de ações preparados (1.9.0):** 293 exemplos próprios
sintéticos adicionados, 147 em treino e 146 em validação; os 12.179 anteriores
foram preservados. Teste, pesquisa externa e quarentena mantêm bytes idênticos.
Validação antiga e sintética também existem em estratos separados, sem alegar
novo gold humano. As classes move_workout_day e set_day_activity passaram de
zero para seis exemplos de validação cada. Nenhum modelo, regra de entidades
ou política de confiança foi promovido. Próxima etapa: comparação 7.07.3.
Método/limites: docs/47-coach-action-data.md; preparação:
scripts/prepare_action_release.py; registro: artifacts/action_data/1.0.0/.

**7.07.1 — diagnóstico concluído:** as quatro intenções de mudança estavam
corretas, mas as duas classes não têm registros na validação e ficam barradas
pelo suporte mínimo. Há 61/44 exemplos de treino, todos sintéticos, distribuídos
em apenas 2/4 grupos. Três pedidos também falham na margem; dois não entregam
activity_type ao roteador. A política bloqueia 34 das 60 classes por suporte.
Nenhum dataset, modelo ou limiar foi alterado. Relatório:
docs/46-coach-blocker-diagnosis.md; reprodução: scripts/diagnose_coach_blockers.py;
registros: artifacts/blocker_diagnosis/1.0.1/.

Fase **7.06.5 avaliada com serviços reais**: duas rodadas com 24 mensagens e
duas conversas cada, Supabase remoto, Qwen original NF4, navegador autenticado
e ações reais pelo Planner. A instrução de concisão eliminou os quatro cortes
observados e reduziu o tempo médio de pedidos com geração de 29,46 s para
14,49 s. Os cinco riscos esperados foram detectados. O NLP ainda produziu
zero propostas em quatro pedidos: não há aprovação para produção. Regressão
dirigida cobre o link direto de prévia. Método, limites e recursos:
docs/45-coach-system-evaluation.md; registros: artifacts/system_evaluation/.
Não houve novo treino nem reavaliação de testes NLU congelados.

Fase **7.06.4 concluída — Coach conectado no Mobile**: mensagens pela API
autenticada, histórico persistido, fontes, repetição idempotente e fluxo de
prévia/revisão/confirmação do Planner. TypeScript, lint, 33 testes Mobile e
16 checks da interface web com rede fictícia passaram. Não houve novo treino
nem alteração dos limites de confiança. Conferência nativa e avaliação real
de ponta a ponta ficam na 7.06.5. Mapa: docs/44-coach-mobile-integration.md;
registros: artifacts/mobile_coach/1.0.1/.

As entradas abaixo registram as entregas e verificações das fases anteriores.

Fase **7.06.3 concluída — histórico no Supabase**: IDs permanentes de
conversa, pares de mensagens idempotentes, listagem/paginação, título,
exclusão e restauração do contexto após reinício. Usa tabelas/RLS existentes,
sem nova migration ou treinamento automático. Passaram 29 testes backend,
16 FastAPI, 20 checks HTTP/PostgreSQL local e oito checks no Supabase real.
As duas contas temporárias de teste foram removidas.
Mapa: docs/43-coach-conversations-history.md; registros:
artifacts/coach_history/1.0.1/ e remote-verification.json na pasta superior.
O Mobile foi conectado posteriormente na 7.06.4.

Fase **7.06.2 concluída — NestJS conectado à IA e ao Planner**:
rotas JWT do Coach, snapshot autenticado renovado por mensagem,
contratos validados e fluxo separado de prévia/confirmação/aplicação.
Build e lint passaram; 22 testes backend, 14 testes FastAPI e 14 checks
HTTP entre servidores reais passaram. Nos checks, Supabase/Planner e a
intenção são fixtures: nenhum dado real foi alterado. Registro final:
artifacts/backend_coach/1.0.2/. Método/configuração:
docs/42-coach-backend-planner.md na raiz. Histórico permanece temporário;
persistência e Mobile continuam nas próximas fases.

Fase **7.06.1 concluída — serviço FastAPI interno**: saúde/readiness,
sessões isoladas por usuário, mensagens autenticadas, exclusão,
limites de corpo/texto, operação única e deduplicação em memória.
Inicializador: scripts/serve_coach.py (loopback:8010, chave interna obrigatória).
Doze testes HTTP passaram, além de chamada Uvicorn real com NLP, busca
e Qwen original. O servidor temporário foi encerrado. O registro preserva
o corte da resposta no limite de tokens; isso não certifica qualidade.
Mapa/comandos: docs/41-coach-fastapi-service.md na raiz; verificação:
artifacts/coach_api/1.0.0/. NestJS, Mobile e persistência ainda não conectados.

Fase **7.05.5 concluída — avaliação integrada de desenvolvimento**:
11 conversas/22 mensagens no pipeline real e dez conversas/24 mensagens
de contrato com intenções conhecidas simuladas. A rodada real criou zero
propostas em quatro solicitações, por incerteza do NLP, e encontrou falhas
de contexto e de prioridade de risco. Esses resultados foram preservados;
as correções de integração têm regressão dirigida separada. Trinta testes
automatizados passaram. Relatório: artifacts/coach_evaluation/1.0.0/RESULTS.md;
conversas: conversations.html nessa pasta; método: docs/40-coach-integrated-evaluation.md.
Conclusão: continuar em pesquisa local, melhorando fundamentação, recuperação
e esclarecimentos antes de conectar ao app. Não houve novo treino nem
reavaliação dos testes congelados anteriores.

Fase **7.05.4 implementada — segurança e propostas tipadas**:
quatro contratos do Planner, validação de campos/IDs, confirmação por ID
de sessão, validade de dez minutos e bloqueio de repetição/contexto alterado.
Regras de risco precedem geração e confirmação; respostas de privacidade
não inventam estado do servidor. São 22 testes passando (13 novos + 9 da
composição). Registro: artifacts/coach/1.1.0/; mapa e limites:
docs/39-coach-safety-actions.md na raiz. Os payloads são preparados
localmente; nenhum endpoint foi conectado nem plano alterado.

Fase **7.05.3 implementada — Coach local composto**: NLP 1.8 + entidades +
busca semântica + Qwen, com histórico limitado à sessão, contexto com fontes,
rotas controladas e saída estruturada sem ações executáveis.
Entrada: scripts/chat_coach.py; composição: src/evolv_rag/coach.py.
O modelo original é padrão; --adapted habilita explicitamente o LoRA para
pesquisa, sem promovê-lo ao app. Nove testes de composição passaram.
Mapa e comandos: docs/38-coach-composition.md na raiz. O serviço ainda não
está conectado ao app, Planner ou banco; a 7.05.4 tratará ações e segurança.

Fase **7.05.2 implementada — busca semântica local** sobre 67 trechos:
MiniLM ONNX INT8, cosseno, até três resultados e bloqueio por validade.
Consulta: scripts/search_knowledge.py. Índice: artifacts/rag/1.0.0/.
Avaliação autoral inicial: Hit@1 55%, Hit@3 65%, MRR@3 0,60,
rejeição das cinco consultas fora do domínio. Quatro testes passaram.
É uma referência de desenvolvimento com limitações de relevância, não
aprovação para produção. Método e exemplos: docs/37-rag-semantic-search.md
na raiz. Ainda não há geração RAG nem integração com o app.

Fase **7.05.1 concluída — base preparada para busca**: 67 trechos com IDs,
fontes e limites de uso em data/rag/1.0.0/, provenientes de 67 textos
e 27 fontes cadastradas. Seis complementos sem metadados completos
ficaram documentados na quarentena. Seis testes do preparador passaram.
Preparador: scripts/prepare_rag_base.py; lógica: src/evolv_rag/preparation.py;
mapa: docs/36-rag-base-preparation.md na raiz do projeto.
Esta etapa não gerou embeddings nem refez a revisão das fontes na web.
Os status das fases anteriores abaixo são históricos.

Fase **7.04.5 concluída — comparação original × adaptado**. No teste congelado
de 28 conversas, a NLL passou de **4,116795 para 1,948433** e a perplexidade de
**61,3623 para 7,0177**. Foram geradas 96 respostas: 28 casos de teste e 20
desafios para cada variante. A revisão assistida por IA preferiu o adaptado em
22 pares, o original em 14 e empatou 12; não é revisão humana independente.
Doze testes do novo avaliador passaram.

O adaptado foi mais conciso (zero cortes pelo orçamento, contra 24 no original),
mas a revisão marcou **três falhas críticas em cada variante**, de tipos
diferentes. No adaptado: alergia, proposta inventada sem ação pendente e
privacidade. Decisão: preservar como candidato de pesquisa, sem promover ao app
ou autorizar ações autônomas. A integração ainda precisa implementar/verificar
guardrails, fontes e estado do Planner; esta etapa não instalou essas barreiras.

Relatório: `artifacts/openlm_evaluation/1.0.1/RESULTS.md`; comparação visual:
`artifacts/openlm_evaluation/1.0.1/private/comparison.html`; conclusão:
`completion.json`; métodos: `docs/35-openlm-comparison.md`, na raiz do projeto.
O teste foi consumido nesta comparação e permanece imutável. Novas iterações
precisam de desenvolvimento e avaliação independente novos.

Os registros das fases anteriores abaixo descrevem seus estados históricos.

Fase **7.04.4 concluída — ajuste real QLoRA na RTX 5050**: 3 épocas e 63 updates,
melhor checkpoint na época 3, recarregado e verificado. NLL de validação passou
de **4,039655 para 1,884680**, e perplexidade de **56,8067 para 6,58425**.
Treino em eval: NLL **4,149058 → 1,583131**. Pico alocado medido no loop:
4.545,68 MiB. Pesos oficiais completos, hashes conferidos e fontes SFT preservadas.

Resultados: `artifacts/openlm_training/1.0.0/RESULTS.md`; dados numéricos em
`results.json`; curva em `loss_curve.png`; verificação em `verification.json`.
Na 7.04.4, o teste reservado **não foi avaliado**, e o modelo não foi promovido
ao app. O conjunto de validação é pequeno e sintético; a comparação final da
7.04.5 está registrada acima. Loss menor não certifica o Coach.

O loop PyTorch/PEFT
tem loss e acumulação ponderadas por tokens, validação por época, retenção da
época 0 se não melhorar, early stopping, checkpoints best/last e retomada na
última época completa. Doze testes passaram, incluindo o loop com um Qwen
minúsculo em NF4/BF16 na GPU. Esses testes não são o treino do modelo de 4B.

O job completou/conferiu os pesos e treinou com a receita QLoRA 1.0.0. Seu estado
atual está em `artifacts/openlm_jobs/1.0.0/status.json`; durante o treino,
consulte `artifacts/openlm_training/1.0.0/progress.json`. Só considere o ajuste
concluído quando `results.json` do run registrar `status=complete`.
Relatório e curva são produzidos automaticamente; teste reservado não é avaliado.
Comando para um experimento novo: `python ai/scripts/train_openlm.py --output ai/artifacts/openlm_training/nova-versao`.
O run completo 1.0.0 recusa treino adicional e não deve ser sobrescrito.
Mapa: `docs/34-openlm-training.md`, na raiz do projeto.

Fase **7.04.3 concluída — receita QLoRA 1.0.0**: rank 8, alpha 16,
dropout 0,05, sete projeções em cada um dos 36 blocos. Estrutura conferida em
meta: 16.515.072 parâmetros treináveis (0,41057% da base), em 252 projeções.
Lote 1, acumulação 16, até 3 épocas, AdamW com learning rate 1e-4; plano de até
63 atualizações e 7 de warmup para os 335 exemplos de treino.

Ensaio QLoRA em Qwen minúsculo descartável na GPU passou: base congelada,
identidade inicial e gradientes finitos. Quatorze testes da receita passaram.
**O modelo real de 4B não foi carregado ou treinado**; download e memória real
seguem pendentes. Nenhum exemplo do teste SFT foi aberto nesta configuração.
Configuração: `configs/openlm.lora.v1.json`. Código: `src/evolv_openlm/lora.py`.
Relatório: `artifacts/openlm_lora/1.0.0/configuration_report.json`.
Mapa: `docs/33-openlm-lora-configuration.md`, na raiz do projeto.
Próxima etapa: loop de treinamento e validação ponderada por tokens (7.04.4).

Fase **7.04.2 concluída — preparação SFT 1.0.0**: 391 conversas sintéticas,
335 de treino, 28 de validação e 28 de teste, em 162 famílias disjuntas.
O treino contém exemplos das 60 intenções e 21 riscos. Há 30 conversas com
histórico; todos os exemplos usam o template original do Qwen e labels apenas
na última resposta. Doze testes da preparação passaram, sem carregar pesos.

São 19.259 tokens-alvo no treino: uma semente de adaptação, não 12 mil respostas
validadas. Os 12.179 registros de NLP e os 6.711 documentos do corpus foram
inventariados e preservados; não viraram respostas-alvo automaticamente.
Dados: `data/sft/1.0.0/`. Fontes sintéticas: `data/sft_sources/v1/`.
Comando: `python ai/scripts/prepare_openlm_data.py --output ai/data/sft/nova-versao`.
Mapa: `docs/32-openlm-adaptation-data.md`, a partir da raiz do projeto.
Próxima etapa: configuração LoRA/QLoRA (7.04.3).

Fase **7.04.1 — modelo base selecionado**: Qwen/Qwen3-4B-Instruct-2507,
revisão fixa `cdbee75f17c01a7cc42f958dc650907174af0554`, NF4 de 4 bits
com cálculo BF16, para RTX 5050 Laptop de 8 GB e RAM de aproximadamente 16 GB.
Escolha técnica documentada; **carregamento, geração e backward ainda pendentes**
de completar o download de cerca de 8 GB. A conexão medida (~0,24 MB/s) impediu
essa conferência nesta execução. Nenhum resultado de qualidade é atribuído a ele.

Configuração: `configs/openlm.v1.json`. Dependências: `requirements.openlm.txt`.
Download/diagnóstico: `python ai/scripts/inspect_openlm.py --http-download --check-backward`.
Chat após o download: `python ai/scripts/chat_openlm.py` (offline por padrão).
Decisão e comandos: `docs/31-openlm-base-selection.md`, na raiz do projeto.
Registro: `artifacts/openlm/1.0.0/selection.json`. Preparação dos dados é a 7.04.2.

Fase **7.03.5 concluida**: checkpoint fixo avaliado em float32 sem updates.
No teste reservado: loss 4,6283 e PPL 102,34 (pesos iniciais: 9,0178/8.248,35).
Treino em eval: 4,4055/81,90; validacao: 4,5789/97,40. Metodo adicional com
stride 128, separado do principal, resultou em PPL de teste 100,55.

Foram geradas 128 amostras com greedy, tres temperaturas, top-k e top-p;
24 amostras predefinidas foram lidas qualitativamente por IA. As geracoes
continuam fracas: loops, palavras deformadas e respostas fora do pedido.
Amostragem reduz repeticao, mas nao demonstrou coerencia ou conversa util.
O experimento TinyLM do zero esta concluido; o Coach principal e outra etapa.

Geracao: `python ai/scripts/generate_tinylm.py "Uma rotina de exercicios pode"`.
Codigo: `src/evolv_tinylm/generation.py` e `lm_evaluation.py`.
Protocolo: `configs/tinylm.evaluation.v1.json`.
Relatorio: `artifacts/tinylm_evaluation/1.0.0/RESULTS.md`.
Mapa e limites: `docs/30-tinylm-generation-and-evaluation.md`.
Pesos, corpus e teste congelado preservados; nenhuma acao no app.

### Treinamento 7.03.4 — referencia preservada

Fase **7.03.4 concluida**: TinyLM treinado por 8 epocas na RTX 5050,
com AdamW, weight decay, dropout, warmup/cosine decay, clipping e bfloat16.
A loss de validacao passou de 9,0170 para 4,5790; treino online final 4,5729.
Foram 7.816 atualizacoes sem passos pulados. Melhor checkpoint: epoca 8,
recarregado e verificado com a mesma loss. Teste reservado sem avaliacao.

Ha checkpoints de cada epoca com estado do otimizador, scheduler, RNG e
loaders para retomada na ultima epoca completa. Pesos privados ignorados
pelo Git; dados, vocabulario e arquitetura anteriores preservados.

Treinador: `src/evolv_tinylm/training.py`.
Configuracao: `configs/tinylm.training.v1.json`.
Comando: `python ai/scripts/train_tinylm.py` (pasta nova ou `--resume`).
Relatorio: `artifacts/tinylm_training/1.0.0/RESULTS.md`.
Curva: `artifacts/tinylm_training/1.0.0/loss_curve.png`.
Mapa: `docs/29-tinylm-training.md`.
A geracao e avaliacao final foram concluidas na 7.03.5 descrita acima.

### Arquitetura 7.03.3 — referencia preservada

Fase **7.03.3 concluida**: Transformer decoder-only proprio com 3.401.856
parametros, 4 blocos, 6 cabecas, embeddings de 192 dimensoes e contexto 256.
Inclui embeddings de token/posicao, atencao causal com mascara de padding,
feed-forward GELU, LayerNorm, residuais, dropout e pesos de entrada/saida
compartilhados. A loss usa os alvos ja deslocados da 7.03.2 e ignora padding.

Forward/backward verificados na CPU e RTX 5050, com lote de 16 x 256.
Teste de causalidade e gradientes aprovado; nenhum passo de otimizador ou
treinamento por epocas foi executado. Os dados e o BPE foram preservados.

Codigo: `src/evolv_tinylm/model.py`.
Configuracao: `configs/tinylm.v1.json`.
Uso: `python ai/scripts/inspect_tinylm_model.py`.
Relatorio: `artifacts/tinylm/1.0.0/smoke_report.json`.
Mapa: `docs/28-tinylm-causal-transformer.md`.
O treinamento foi concluido na 7.03.4 descrita acima.

### Dados 7.03.2 — referencia preservada

Fase **7.03.2 concluida**: corpus convertido em arrays por particao, com
BOS/EOS por documento, e janelas de ate 256 tokens para prever o proximo.
Sao 15.618 sequencias de treino, 119 de validacao e 81 de teste, preservando
todos os textos e sobras. X e y ficam deslocados em um token; o preenchimento
usa PAD na entrada e -100 no alvo para nao entrar no calculo do erro.

O Dataset/DataLoader entrega lotes de ate 16 sequencias, embaralha somente o
treino e nao mistura documentos. O vocabulario e o corpus continuam congelados.
Nenhum modelo neural foi treinado nesta etapa.

Uso: `python ai/scripts/inspect_tinylm_batch.py`.
Dependencias dos lotes: `ai/requirements.tinylm-training.txt` (PyTorch).
Artefatos: `artifacts/tinylm_data/1.0.0/`.
Mapa: `docs/27-tinylm-data-preparation.md`.
A arquitetura do Transformer foi concluida na 7.03.3 descrita acima.

### Tokenizador 7.03.1 — referencia preservada

Fase **7.03.1 concluida**: BPE proprio `1.0.0`, com 8.192 tokens (incluindo
7 especiais), treinado somente nos 6.612 documentos de treino do corpus
`1.2.0`. Foram medidos 2.947.105 tokens de texto no treino; validacao e teste
ficaram fora do aprendizado do vocabulario. Recuperacao de texto em NFC sem
falhas ou tokens desconhecidos em todas as particoes. Corpus preservado.

Uso: `python ai/scripts/encode_tinylm.py "amanha troca o supino"`.
Dependencia: `ai/requirements.tinylm.txt` (tokenizers 0.23.3, sem GPU).
Relatorio: `artifacts/tokenizer/1.0.0/report.json`.
Mapa e limites: `docs/26-tinylm-tokenizer.md`.
O corpus e predominantemente Wikipedia e serve ao TinyLM educacional;
isso nao certifica um Coach especializado. O LM ainda nao foi treinado.
A preparacao de sequencias e lotes foi concluida na 7.03.2 descrita acima.

### NLP 7.02 — referencia preservada

Rodada atual: dataset `1.8.0`, com as 2.180 revisoes de IA aplicadas a
treino/validacao. Foram alterados rotulos de 773 mensagens, preservando as
263 duvidas sinalizadas. As 12.179 mensagens e os grupos foram mantidos;
teste, pesquisa e quarentena sao copias byte a byte da versao anterior.

Foram concluidas 99 comparacoes classicas, incluindo K-means/KNN, e 12
checkpoints de ajuste do encoder na GPU. O candidato experimental `1.8.0`
usa TF-IDF + MiniLM + SVM para intencao e TF-IDF (texto e trecho final) +
MiniLM + regressoes logisticas para os riscos. O K-means nao foi escolhido
como componente do vencedor final.

O resultado foi misto: no teste historico, accuracy de intencao 62,6% ->
64,3%, mas F1 macro 51,3% -> 50,1%; risco exato 69,3% -> 70,1%, mas F1
macro 41,5% -> 37,2%. Na pesquisa real reservada, intencao passou de
54,9%/47,6% (accuracy/F1) para 60,8%/51,8%. Nao houve melhora geral de F1
no teste, e os novos modelos nao substituem automaticamente a referencia
anterior ou a pipeline operacional.

Relatorio: `artifacts/review/2026-10-31/RESULTS.md`.
Decisao: `artifacts/review/2026-10-31/recommendation.json`.
Documentacao: `docs/25-coach-ai-corrections-and-kmeans.md`.
Inferencia opt-in: `python ai/scripts/analyze_message_corrected.py "mensagem"`,
usando o runtime Python 3.12.14 registrado nos artefatos.

Baixa confianca e classes pouco avaliadas pedem esclarecimento. Nao existem
escritas automaticas no Planner. Os rotulos continuam como referencias de
IA, nao gabarito humano independente. O corpus TinyLM `1.2.0` foi preservado
e foi utilizado na 7.03.1 educacional descrita acima.

## Rodada Anterior

Dataset revisado `1.7.0`, 12.179 mensagens preservadas de quatro
planilhas, 60 intencoes e 21 riscos. O baseline experimental `1.6.0` compara
TF-IDF, MiniLM congelado, SVM e regressao logistica, com risco multirrotulo.
O extrator `1.3.0` tem 80 dos 89 tipos declarados com regras/catalogos.
Fechamento medido: `artifacts/review/2026-10-19/RESULTS.md`.
Foram comparados 40 candidatos iniciais, 16 variantes BoW/TF-IDF/MLP e dois
fine-tunings parciais do encoder (oito checkpoints). A validacao manteve
baseline `1.6.0` como recomendacao para as duas tarefas; os experimentos
`1.6.1` e `1.7.0` ficam preservados, sem promover uma arquitetura pior.
O corpus TinyLM continua `1.2.0`, com 6.711 documentos: nao recebeu perguntas
privadas ou respostas de foruns automaticamente.

Os rotulos novos foram revisados por IA, nao sao gabarito humano independente.
As 12.179 mensagens entram em treino, validacao, teste ou analise de desafios;
nao se treina com os exemplos usados como teste. Dados e modelos individuais
ficam privados e com uso de pesquisa, sem certificacao automatica de licencas
ou anonimato. A pipeline padrao do aplicativo e as versoes antigas nao mudam.

Relatorio da rodada anterior: `docs/24-coach-reviewed-workbooks-and-multilabel-risk.md`.
As secoes abaixo preservam o historico das entregas e seus numeros originais.

A fase 7.01 e as quatro partes da 7.02 estao implementadas. O dataset `1.2.0`
permanece como historico; a expansao `1.3.0` possui 1.277 registros regulares
e o baseline `1.1.0` foi avaliado. O corpus TinyLM `1.0.0` esta preparado.
A pipeline operacional ainda usa baseline `1.0.0`: a ativacao do novo modelo
exige novos limites de confianca medidos somente em dados de desenvolvimento.

Estrutura atual:

```txt
ai/
  artifacts/        modelos, extratores, manifestos, metricas e model cards
  data/
    catalogs/        snapshots de termos do dominio usados na extracao
    entities/        conjunto de regressao da extracao de entidades
    evaluation/      protocolo congelado e holdout independente
    taxonomy/       intencoes, hierarquia, topicos, entidades, riscos e capacidades
    research/       catalogo de fontes e notas da pesquisa de cobertura
    source/         exemplos sinteticos, padroes reais reescritos e desafios
    schema/         contrato formal dos registros JSONL
    knowledge/      politica, cobertura e 67 trechos rastreaveis da base local
    metadata/       fontes, versao e criterios de qualidade
    splits/         politica, registro congelado, dados e auditoria
    releases/       dataset NLU 1.3.0, separado da versao historica
    lm_corpus/      textos, fontes e divisoes para o TinyLM
  scripts/          construcao, treinamento, inferencia e validacao
  src/evolv_nlp/    codigo reutilizavel de dados e modelos NLP
  tests/            testes automaticos de qualidade
  requirements.txt dependencias Python reproduziveis
```

## Comandos da fase 7.01

Execute na raiz do repositorio:

```powershell
python ai/scripts/validate_taxonomy.py
python ai/scripts/build_splits.py
python ai/scripts/audit_splits.py
python ai/scripts/validate_data.py
python ai/scripts/knowledge_report.py
python -m unittest discover -s ai/tests
```

`build_splits.py` gera as divisoes de forma deterministica. Cada rotulo possui
seis exemplos em treino, um em validacao e um em teste. O arquivo
`assignments.v1.json` congela a posicao dos 383 IDs. `audit_splits.py` procura
duplicatas exatas e quase-duplicatas entre divisao, enquanto `validate_data.py`
confere rotulos, fontes, hashes, manifesto, registro e isolamento do desafio.

O dataset 1.2 possui 240 exemplos de intencao, 104 exemplos de risco e 39
casos separados de desafio. Ele distingue exemplos sinteticos, padroes reais
reescritos e casos adversariais; nenhuma conversa privada foi copiada.

A taxonomia 1.0 possui 30 intencoes, 94 topicos, 79 entidades, 13 riscos e 44
capacidades. O numero de topicos e capacidades nao vira automaticamente o
numero de classes do classificador: eles sao eixos separados para manter o NLP
pequeno, mensuravel e capaz de representar mensagens com mais de um assunto.

A base de conhecimento 1.1 possui 67 trechos: 14 de treino, 23 de alimentacao,
11 de recuperacao e 19 de seguranca. As 27 fontes aprovadas incluem autoridades
publicas, diretrizes, consensos, posicionamentos cientificos e quatro contratos
internos de produto. Foruns e conteudo comercial nao sustentam respostas.
Cada trecho registra topicos, fontes, risco, modo de resposta, limite de uso e
prazo de revisao.

## Limite desta fase

Os exemplos atuais formam um dataset semente congelado para desenvolver e
testar a pipeline. Eles ainda nao representam todos os jeitos de falar
portugues nem sao suficientes para declarar qualidade de producao. A expansao
exige uma nova versao e sera guiada por erros revisados, sem mover exemplos de
teste nem usar conversas pessoais automaticamente. A proxima entrega da 7.02
e confianca, abstencao e uniao da pipeline.

## Baseline 7.02.1

O treinamento usa somente `train`. Dois perfis TF-IDF declarados sao
comparados em `validation`, e o melhor por macro F1 e salvo. `test` e
`challenge` permanecem fechados. Resultados atuais de validacao:

| Tarefa | Accuracy | Macro F1 |
| --- | ---: | ---: |
| Intencao, 30 classes | 0,400 | 0,333 |
| Risco, 13 classes | 0,615 | 0,538 |

As probabilidades nao estao calibradas e nao autorizam acoes. Os resultados
confirmam que o dataset semente permite aprender, mas ainda e pequeno.

```powershell
python ai/scripts/train_baseline.py
python ai/scripts/predict_baseline.py "troca o supino porque meu ombro doi"
python -m unittest ai/tests/test_baseline.py -v
```

Os artefatos `joblib` usam formato baseado em pickle. Somente arquivos gerados
pelo repositorio e com SHA-256 correspondente ao manifesto podem ser
carregados.

## Extracao de entidades 7.02.2

O extrator 1.0.0 combina catalogos locais, expressoes deterministicas e regras
de contexto. Ele encontra datas, exercicios, alimentos, substituicoes, carga,
series, repeticoes, duracao, objetivos, preferencias e limitacoes, preservando
o span original e retornando valores tipados.

O conjunto de regressao possui 40 mensagens e 71 entidades. Precision, recall
e F1 sao 1,000 nesse conjunto declarado. Ele foi usado durante o
desenvolvimento e, portanto, nao representa uma estimativa independente de
producao. Essa avaliacao pertence a 7.02.3.

```powershell
python ai/scripts/extract_entities.py "amanha troca supino por flexao e faz 4x10 com 30 kg" --reference-date 2026-10-07
python ai/scripts/evaluate_entities.py
python -m unittest ai/tests/test_entities.py -v
```

Contrato e limites: `docs/15-coach-entity-extraction.md`.

## Avaliacao e erros 7.02.3

O protocolo 1.0.0 abriu o teste congelado sem retreinar modelos nem alterar o
extrator. Os resultados sao honestos e ainda distantes de producao:

| Componente | Accuracy/exata | Macro F1 | Observacao |
| --- | ---: | ---: | --- |
| Intencao | 0,233 | 0,161 | 30 exemplos, um por classe |
| Risco | 0,538 | 0,449 | 13 exemplos, um por classe |
| Entidades | 0,650 | 0,696 | 40 mensagens novas; micro F1 0,841 |

No teste pequeno de risco, nenhum exemplo perigoso foi classificado como
`none`, mas varios tipos de risco foram confundidos entre si. O conjunto
adversarial obteve 0,513 de accuracy de intencao e confirma que ambiguidades e
multiplos pedidos ainda exigem a 7.02.4 e dados futuros.

```powershell
python ai/scripts/evaluate_nlp.py
python -m unittest discover -s ai/tests -v
```

Relatorio e limites: `docs/16-coach-nlp-evaluation.md`.

## Confianca e pipeline final 7.02.4

A pipeline 1.0.0 une intencao, risco, entidades e topicos. Limiares foram
escolhidos somente em `validation`: a porta conservadora de intencao aceitou
`0/30` mensagens, enquanto a de risco aceitou `6/13`, todas corretas entre as
aceitas. Isso nao torna o modelo pronto; faz o sistema pedir esclarecimento em
vez de executar uma suposicao.

Toda mudanca e apenas uma proposta com confirmacao obrigatoria e
`writes_allowed: false`. Risco aceito substitui a rota normal, e risco nao nulo
incerto tambem impede uma acao automatica.

```powershell
python ai/scripts/evaluate_pipeline.py
python ai/scripts/analyze_message.py "amanha troca supino por flexao" --reference-date 2026-10-08
python -m unittest discover -s ai/tests -v
```

Contrato e limites: `docs/17-coach-nlp-pipeline.md`.

## Expansao NLU e preparacao do TinyLM

O dataset `1.3.0` tem 1.019 exemplos em treino, 129 em validacao e 129 em
teste, mais 39 desafios historicos e dez perguntas humanas publicas separadas.
O baseline `1.1.0` escolheu SVC linear para intencao e regressao logistica para
risco. O teste final usa a maior probabilidade, como `baseline.classify`:

| Tarefa | Macro F1 no teste |
| --- | ---: |
| Intencao | 0,713 |
| Risco | 0,852 |

Nas dez perguntas humanas externas, ambos tiveram accuracy de 0,300. O teste
controlado e pequeno e majoritariamente sintetico; esta diferenca impede uma
alegacao de qualidade em linguagem aberta. Houve uma correcao de pontuacao
apos a primeira execucao: os modelos e os dados conservaram os mesmos hashes.

O corpus `1.0.0` tem 6.381 trechos, 1.656.093 unidades separadas por espaco
e cerca de 2,24 milhoes de tokens de subpalavras estimados. Inclui Wikipedia,
OASST1 humano e textos Evolv, com fontes, licencas e divisao por artigo/conversa.
Os textos e as conversas do holdout humano NLU estao reservados fora dele.

```powershell
python ai/scripts/prepare_lm_corpus.py --offline
python -m unittest discover -s ai/tests -v
```

`--offline` requer o cache local ja baixado; sem ele, execute o comando sem
essa opcao. Treinamento e avaliacao do baseline 1.1 estao encerrados: os
comandos `train_baseline_1_1.py` e `evaluate_baseline_1_1.py` recusam sobrescrever
a versao avaliada. Use uma nova versao para novos experimentos.

Detalhes: `docs/19-coach-dataset-1-3-and-tinylm-corpus.md`.

## Importacao real PT-BR e experimento 1.2

O dataset `1.4.0` adiciona uma fila local com 10.000 mensagens originais em
portugues: 8.912 sao apenas titulos de posts, e 9.119 vieram de Hipertrofia.org.
Nao sao 10.000 exemplos rotulados e aprovados. Textos externos, revisoes locais
e pesos treinados neles ficam fora do Git enquanto os direitos de uso nao
estiverem confirmados. Validacao e teste externos continuam reservados.

A extensao declara 36 intencoes, 16 riscos e 85 tipos de entidades. O extrator
experimental implementa 39 tipos, nao os 85. Ele distingue carga, peso corporal
e peso ambiguo; acrescenta distancia, ritmo, velocidade, frequencia cardiaca e
medidas de exames, sem fazer diagnostico. As regras de risco preservam negacao,
contexto e multiplos sinais; ausencia de regra nao significa seguranca.

O baseline `1.2.0` e opt-in e experimental. Na pequena amostra real revisada
pelo assistente, a accuracy subiu de 0,192 para 0,767 em intencao e de 0,525
para 0,825 em risco. Esses exemplos foram usados no desenvolvimento, nao sao
teste independente nem rotulos humanos. A validacao historica piorou; por isso
nenhum modelo ou pipeline padrao foi substituido.

```powershell
python ai/scripts/analyze_message_1_2.py "troca supino por flexao" --reference-date 2026-10-10
python -m unittest discover -s ai/tests
```

Os artefatos locais existentes sao necessarios para o primeiro comando. O
treinador recusa sobrescrever a versao finalizada. Para uma nova coleta,
rotulagem, configuracao ou modelo, criar nova versao.

O corpus `1.1.0` tem 6.555 documentos, incluindo 174 novos exemplos proprios,
dos quais 66 pares educativos baseados no conhecimento existente. Nao inclui
as 10.000 mensagens externas nem respostas de forums. TinyLM e tokenizer ainda
nao foram treinados. A proxima rodada usara a nova coleta com mais contexto e
diversidade de fontes, mais as entrevistas consentidas.

Detalhes e mapa dos arquivos: `docs/20-coach-ptbr-dataset-and-nlp-expansion.md`.

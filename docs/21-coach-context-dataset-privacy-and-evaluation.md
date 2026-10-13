# Dataset Com Contexto, Dor E Privacidade

Registro da entrega anterior. O aproveitamento privado posterior da coleta
e os novos experimentos estao em [Tuning De Intencao E Risco](22-coach-model-tuning-and-private-research.md).

## Entrega

Dataset de pesquisa 1.5.0, baseline experimental 1.3.0, extrator 1.2.0,
regras de risco 1.3.0 e corpus 1.2.0. Nao inicia o TinyLM, nao altera
o Planner nem as telas e nao substitui o modelo padrao.

Ambos os caminhos continuam abertos: portfolio academico/profissional e
produto comercial futuro. Esta entrega nao certifica lancamento legal,
respostas clinicas ou qualidade de producao.

## Coleta Recebida

10.000 mensagens PT-BR, todas com corpo completo segundo o coletor,
3.918 perguntas com 7.328 comentarios associados. Antes, 8.912 mensagens
eram apenas titulos. A nova coleta tem 13 fontes/comunidades, mas 99,43%
ainda sao Reddit: diversidade de comunidades nao e diversidade de plataformas.

Os rotulos fornecidos sao machine_candidate, nao anotacoes humanas gold.
A biblioteca de 35 sinteses educativas foi preservada como candidata separada;
comentarios de comunidade e mapeamentos lexicais nao viraram respostas corretas.
Nao existe verificacao individual de 10.000 respostas cientificas.

Auditoria confere IDs, texto/hash, spans, grupos e separacao dos splits.
Encontrou 170 IDs repetidos na coleta anterior e quatro registros envolvidos
em quase-duplicatas entre splits: 174 registros separados para revisao.
O detector usa bottom-8 de hashes de quatro palavras e Jaccard >=0,8,
com limite de tamanho dos buckets. Nao detecta toda parafrase ou vazamento.

## Uso Dos Dados E LGPD

389 mensagens tiveram possiveis identificadores diretos removidos na copia
privada de revisao. Foram detectadas 570 URLs, 59 trechos de endereco,
13 apresentacoes de nome, oito handles e tres padroes de telefone.
Esses contadores sao correspondencias heuristicas, nao identificacoes confirmadas.
Nos comentarios tambem foram encontrados links, handles e trechos de endereco.
1.927 mensagens receberam sinal de possivel dado sensivel; 173, de possivel
menor de idade; 424, de contexto de terceiros. Pode haver falsos positivos e
dados pessoais nao encontrados pelas regras.

Remover identificadores nao comprova anonimato. Fonte publica nao equivale
a autorizacao para treinamento ou redistribuicao. A propria coleta informa
licenca indefinida. Por isso as 10.000 mensagens foram aproveitadas para
auditoria e identificacao de lacunas, mas **zero textos externos foram
liberados automaticamente para treino ou corpus**. Nao foram usados os
7.328 comentarios como alvos de resposta.

A fila local fica em ai/data/external_private/ptbr-context-1.0.0, ignorada
pelo Git. O dataset original na pasta do usuario permaneceu intacto.
Liberacao futura exige revisao de direitos, privacidade, finalidade,
evidencia de autorizacao/base legal e rotulos revisados. Nao basta mudar
um booleano de consentimento nem autorizar uso do app para autorizar treino.
Perguntas humanas novas continuam reservadas separadamente; P001 e pseudonimo.

Referencia oficial: [LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm).
Isso abrange a pesquisa NLP. Exportacao/exclusao de conta, retencao operacional,
controle de acesso, termos e demais obrigacoes do aplicativo ainda precisam
da integracao e revisao especificas; nao estao declaradas como concluidas.

## Taxonomia E Extracao

| Componente | Antes | Agora |
| --- | ---: | ---: |
| Intencoes | 36 | 41 |
| Riscos | 16 | 18 |
| Entidades declaradas | 85 | 89 |
| Tipos com regras/catalogos ativos | 39 | 50 |

Intencoes acrescentadas: hidratacao, seguranca alimentar, habitos de sono,
retorno apos pausa nao clinica e cardio. Sao duvidas educativas, nao novas
acoes do Planner. Tipos clinicos continuam importantes para reconhecer limites.

Riscos acrescentados: sinais musculoesqueleticos de atencao e mal-estar
relatado no contexto de estimulantes. As regras reconhecem desconforto,
incomodo e relatos com verbos como torci/tomei. Preservam negacao, pergunta
educativa, urgencia e multiplos sinais. Ausencia de regra nao significa seguranca.

Entidades novas: volume de bebida, desnivel de percurso, cadencia de
passos/pedaladas e tempo de experiencia. Tipos ja declarados passaram a ter
regras para intensidade relatada de dor, inicio do sintoma, lado do corpo,
tempo do movimento e numero de refeicoes. Catalogos incluem mais alimentos,
exercicios e aliases, barreiras de rotina e qualidade do sono.
Unidades de medicamento nao viram bebida; bpm nao vira cadencia; desnivel
nao e distancia; anos de experiencia nao sao duracao de uma sessao.
Valores clinicos extraidos sao relatos, nao interpretacoes ou diagnosticos.

## Treinamento E Metricas

Treino novo: 950 exemplos de intencao e 387 de risco, provenientes do projeto,
incluindo cenarios proprios de contexto; nao 10.000 rotulos externos aprovados.
Validacao: 154 e 68 exemplos. Seis perfis declarados foram comparados.
Selecionados: TF-IDF palavra/caractere + SVC linear para intencao;
TF-IDF palavra/caractere + regressao logistica C=4 para risco.
Features sao ajustadas apenas em train. Nenhum teste foi usado para selecionar.

Comparacao no mesmo teste historico: 90 perguntas de intencao e 39 de risco.
Subtipos novos foram colapsados aos pais para comparar as mesmas categorias.

| Tarefa | Modelo | Accuracy | Precisao macro | Recall macro | Macro F1 |
| --- | --- | ---: | ---: | ---: | ---: |
| Intencao | Anterior 1.2 | 0,611 | 0,720 | 0,611 | 0,615 |
| Intencao | Novo 1.3 | 0,622 | 0,742 | 0,622 | 0,629 |
| Risco | Anterior 1.2 | 0,744 | 0,814 | 0,744 | 0,739 |
| Risco | Novo 1.3 | 0,795 | 0,851 | 0,795 | 0,801 |

Na mesma validacao historica, macro F1 passou de 0,575 para 0,648 em
intencao e de 0,847 para 0,913 em risco. Sao resultados usados na selecao.
O melhor baseline antigo 1.1 ainda tem macro F1 de 0,713/0,852 no teste
historico. Portanto, recuperar o experimento 1.2 nao significa superar o 1.1.
O teste historico ja foi observado em outras fases: nao e estimativa nova
independente de desempenho em usuarios reais.

Teste novo pequeno, proprio do assistente: 40 exemplos de intencao e 16 de risco.
Em categorias nativas: accuracy 0,725/0,688; macro F1 0,710/0,611.
Ao comparar categorias colapsadas, F1 de intencao sobe de 0,478 para 0,768,
mas risco cai de 0,581 para 0,536. Nao esconder essa regressao nem anunciar
melhora universal. Esses exemplos nao representam entrevista humana independente.

O classificador de risco continua single-label. Regras fornecem multiplos
sinais, mas isso nao equivale a ter treinado e validado um modelo multilabel.
Probabilidades nao sao calibradas. A selecao conservadora de confianca de
intencao nao encontrou um limiar com o criterio exigido: aceita zero mensagens.
Assim a nova pipeline pede esclarecimento; nao esta operacionalmente pronta
para acionar o Planner. Melhorar cobertura, rotulos e calibracao precede ativacao.

## Entidades, Dor E Conversa

No holdout historico, considerando apenas os tipos ja anotados, o extrator
manteve micro precision 0,908, recall 0,831 e F1 0,868; 70% de mensagens exatas.
22 checks proprios das funcionalidades novas tiveram 100% de acerto no
escopo declarado. Isso e regressao de desenvolvimento, nao precision/recall
de 100% em texto livre nem avaliacao das 89 entidades.

`response_policy.py` separa educacao geral, conversa sobre dor e urgencia.
Pode explicar incerteza e sugerir avaliacao proporcional. Nao concluir uma
causa individual, escolher exame ou gerar tratamento/reabilitacao. Nao
atribuir desconforto a falta de explosao ou transformar isso em prescricao.
Urgencia continua prevalecendo sobre propostas do Planner.
Referencia: [NHS: lesoes e sinais de atencao](https://www.nhs.uk/conditions/sprains-and-strains/).

`conversation.py` aceita contexto fornecido de uma conversa, limitado e
efemero. Recupera candidatos de referencia de falas anteriores do usuario,
pede esclarecimento para "esse"/"isso"/"sim" e nao trata falas do assistente
como autorizacao. Relatos de risco anteriores impedem proposta sem rever
o contexto. Nao inventa spans atuais para entidades de mensagens antigas.
Nao grava memoria persistente nem treina com o historico. Historico por
usuario, memoria recuperavel e personalizacao do LM ficam para a integracao.

## Corpus

Corpus 1.2.0: 6.711 documentos. Acrescentados 204 textos proprios, incluindo
seis pares de pergunta/resposta de limites do produto. 48 documentos do
train anterior foram excluidos desta nova copia por verificacao conservadora
de identificadores/contexto; arquivos historicos nao foram alterados.
Os quatro arquivos de validation/test conservaram exatamente os mesmos bytes.
Nao inclui os novos textos externos ou comentarios como respostas corretas.
Quantidade real de tokens so sera conhecida com tokenizer. TinyLM nao treinado.

## Arquivos E Verificacao

```text
ai/data/releases/1.5.0/                 auditoria agregada, splits proprios, hashes
ai/data/external_private/ptbr-context-1.0.0/ fila minimizada, nao liberada para treino
ai/data/source/context_expansion.v1.json cenarios proprios e particoes
ai/data/taxonomy/expansion.v1.2.json     categorias novas
ai/data/catalogs/entity_catalogs.extension.v1.2.json aliases/catalogos
ai/data/pipeline/response-boundaries.v1.json contrato de resposta
ai/data/collection/privacy-review.md    entrevista e autorizacao
ai/data/lm_corpus/1.2.0/                corpus novo; holdouts preservados
ai/src/evolv_nlp/privacy.py             minimizacao e gate de finalidade
ai/src/evolv_nlp/context_data.py        auditoria, duplicatas e versao
ai/src/evolv_nlp/training_v13.py        treinamento, selecao e comparacoes
ai/src/evolv_nlp/entities_v13.py        regras/catalogos novos
ai/src/evolv_nlp/risk_rules_v13.py      sinais adicionais
ai/src/evolv_nlp/response_policy.py     limites para respostas futuras
ai/src/evolv_nlp/conversation.py        contexto efemero, sem memoria persistente
ai/src/evolv_nlp/pipeline_v13.py        uniao experimental nova
ai/artifacts/baseline/1.3.0/            modelos, metricas, politica, manifesto
ai/artifacts/entities/1.2.0/metrics.json comparacao dos extratores
ai/tests/test_context_expansion.py      regras, privacidade, urgencia e contexto
ai/tests/test_context_release.py        splits, hashes, corpus e isolamento
```

156 testes passaram. Modelos, metricas e arquivos congelados anteriores foram
preservados com SHA-256. O dataset recebido, o backend, o mobile e o Planner
nao foram modificados. Nenhum commit ou publicacao foi feito.

```powershell
python ai/scripts/analyze_message_1_3.py "estou com desconforto no joelho" --reference-date 2026-10-10
python -m unittest discover -s ai/tests
```

O primeiro comando exige o ambiente registrado no manifesto e os artefatos locais.
Importacao/treinamento/avaliacao/corpus recusam sobrescrever versoes finalizadas.
O proximo salto real de qualidade depende de anotacao humana, revisao da coleta,
direitos/finalidade e um holdout de conversas reais nao usado no desenvolvimento.

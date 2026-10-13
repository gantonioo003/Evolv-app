# Expansao PT-BR Antes Do TinyLM

## Entrega e Decisao

Esta rodada fecha a base experimental: importacao, auditoria, taxonomia,
extracao, regras, treino comparativo e corpus. Nao ativa um novo Coach em
producao nem inicia a fase 7.03. A proxima rodada usara a coleta que o usuario
esta preparando, com mais fontes e perguntas com contexto, mais entrevistas
consentidas. Nao investir em milhares de respostas para titulos ambiguos.

## Dataset Recebido

10.000 perguntas originais PT-BR importadas sem traducoes ou coleta inglesa.
8.912 sao apenas titulos de posts; o corpo nao foi coletado nesses casos.
9.119 registros vieram de Hipertrofia.org. Os grupos de train/validation/test
originais foram preservados: 8.012/1.022/966.

Validacao inclui IDs, SHA-256, texto original, idioma declarado, offset das
entidades e correspondencia do manifesto de splits. Auditoria encontrou zero
registros em quarentena pelos criterios atuais. Isso nao prova ausencia de
duplicatas semanticas: o detector usa trigrams e limiar explicito de Jaccard,
limitado a textos de pelo menos oito palavras e shingles nao muito frequentes.
Tambem nao prova idioma nativo, origem ou qualidade de todas as perguntas.

Os textos externos sao candidatos, nao ground truth. Direitos de treinamento
e redistribuicao ainda nao foram confirmados. Arquivos e pesos experimentais
ficam locais, ignorados pelo Git; os manifestos e o codigo podem ser versionados.

## O Que Aumentou

| Componente | Antes | Extensao |
| --- | ---: | ---: |
| Intencoes declaradas | 30 | 36 |
| Riscos declarados | 13 | 16 |
| Tipos de entidades declarados | 79 | 85 |

Intencoes novas: suplemento, avaliar ficha, manejo de peso, refeicao em torno
do treino, preparacao para esportes e duvida sobre dor. Sao subtipos educativos;
nao criam novas acoes do Planner nem autorizam alterar um plano.

Riscos novos: sinais relacionados ao calor, combinacao de substancias e pedido
de interpretar medidas clinicas. Regras reconhecem negacao, contexto, relatos
vs. duvidas educativas, alias de medicamentos e multiplos sinais. Resultado
sem correspondencia significa desconhecido, nunca classificacao segura.

Entidades novas: distancia, pace, velocidade, frequencia cardiaca, medida de
exame e peso ambiguo. Melhorias: decimais brasileiros, carga vs. peso corporal
vs. alimento, unidade clinica, horarios, preferencias, negacao e substituicoes.
O extrator suporta 39 tipos; declarar 85 na taxonomia nao implementa todos.
Nos 8.012 exemplos train encontrou 5.454 spans de 37 tipos. Isso mede cobertura,
nao precision/recall, pois ainda nao temos spans gold humanos para essa coleta.

## Modelos e Limites

Experimento 1.2.0: SVC linear para intencao e regressao logistica para risco,
ambos com TF-IDF de palavras e caracteres. Quatro perfis comparados em
desenvolvimento. As features sao aprendidas apenas com train.

Intencao recebeu 1.056 exemplos do projeto e 734 candidatos reais de peso 0,15.
Risco recebeu 407 e 515, respectivamente. Nao sao 10.000 rotulos aprovados.
Todos os grupos dos titulos revisados foram excluidos desse treino.

| Mesma amostra real provisoria | Accuracy anterior | Nova | Macro F1 anterior | Nova |
| --- | ---: | ---: | ---: | ---: |
| Intencao, 73 casos | 0,192 | 0,767 | 0,094 | 0,552 |
| Risco, 40 casos | 0,525 | 0,825 | 0,225 | 0,518 |

Esses rotulos foram revisados pelo assistente, nao por anotadores humanos, e
usados para selecao. Os subtipos novos foram colapsados aos pais anteriores.
Nao sao desempenho independente, nem comparaveis ao teste final antigo.

Na mesma validacao historica, macro F1 caiu de 0,676 para 0,575 em intencao e
de 0,940 para 0,847 em risco. Portanto, o modelo padrao nao foi substituido.
O classificador de risco ainda escolhe uma classe por mensagem; a camada de
regras tem multiplos sinais, mas nao substitui avaliacao multilabel ou clinica.

## Mapa Dos Arquivos

```text
ai/data/taxonomy/expansion.v1.1.json       novas categorias e limites
ai/data/source/expansion_ptbr.v1.json     exemplos proprios, separados por split
ai/data/releases/1.4.0/                  manifestos, revisoes por ID e splits
ai/data/external_private/                textos externos e entrevistas, local
ai/src/evolv_nlp/real_data.py             importar, validar e detectar vazamentos
ai/src/evolv_nlp/training_v12.py          gerar candidatos, treinar e comparar
ai/src/evolv_nlp/entities_v12.py          extrator novo, separado do antigo
ai/src/evolv_nlp/risk_rules_v12.py        regras de sinais de risco
ai/src/evolv_nlp/pipeline_v12.py          uniao experimental e esclarecimentos
ai/artifacts/baseline/1.2.0/              modelos locais, metricas, politica, hashes
ai/data/lm_corpus/1.1.0/                  corpus ampliado, sem treinar TinyLM
ai/data/collection/                      modelo de planilha para entrevistas
ai/tests/                               regressao, seguranca e integridade
```

Os nomes `v12.py` identificam a expansao de baseline 1.2, nao a versao individual
de todo componente. O extrator registra 1.1.0; regras, 1.2.0; a pipeline,
1.1.0-development. Modulos antigos permanecem intactos.

## Base De Respostas e Corpus

Perguntas ensinam linguagem, intencoes e necessidades; sozinhas nao fornecem
respostas corretas. A base de conhecimento ja tem chunks com fontes e limites.
O novo corpus incorpora 66 pares educativos sinteticos a partir dos chunks de
train e 108 perguntas proprias: 6.555 documentos no total. Holdouts LM foram
preservados byte a byte. Nao usamos respostas de forums como evidencia.

Para a nova coleta contextual, responder por conceito ou caso, registrando:
pergunta, contexto disponivel, resposta educativa, fontes, limites, autoria e
status de revisao. Perguntas ambiguas recebem esclarecimento; pedidos de
diagnostico, ciclos hormonais ou doses clinicas nao recebem prescricao. Nao
gerar 10.000 respostas genericas e apresentar como gold. Resposta apoiada em
fonte ainda precisa de revisao; uma fonte confiavel pode nao responder ao caso.

Fontes primarias verificadas nesta rodada, usadas como referencias, nao corpus
copiado nem aprovacao clinica das respostas do produto:

- [ACSM: resistencia, atualizacao de 2026](https://acsm.org/resistance-training-guidelines-update-2026/)
- [NIH ODS: suplementos e desempenho](https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-Consumer/)
- [CDC: sono](https://www.cdc.gov/sleep/about/index.html)
- [NHS: dor no joelho e necessidade de avaliacao](https://www.nhs.uk/symptoms/knee-pain/)
- [NIDDK: mitos sobre nutricao e atividade](https://www.niddk.nih.gov/health-information/weight-management/myths-nutrition-physical-activity)
- [NIDDK: manejo alimentar da intolerancia a lactose](https://www.niddk.nih.gov/health-information/digestive-diseases/lactose-intolerance/eating-diet-nutrition)
- [CDC NIOSH: doencas relacionadas ao calor](https://www.cdc.gov/niosh/heat-stress/about/illnesses.html)
- [Ministerio da Saude: guias alimentares](https://www.gov.br/saude/pt-br/composicao/saps/promocao-da-saude/guias-alimentares)

## Como Usar e O Que Vem Depois

```powershell
python ai/scripts/analyze_message_1_2.py "troca supino por flexao" --reference-date 2026-10-10
python -m unittest discover -s ai/tests
```

Essa pipeline nao gera respostas LM, nao persiste mensagens e nao altera o
Planner. Risco explicito impede proposta; baixa confianca, peso ambiguo e
mudanca negada pedem esclarecimento. Propostas exigem confirmacao e ficam com
`writes_allowed: false`. Sinal simples de ingles pede fallback, nao e detector
multilingue robusto nem pode rebaixar um sinal de seguranca explicito.

Os comandos de importacao e treino existentes sao para reproducao local, nao
para sobrescrever a versao encerrada. Uma nova coleta requer nova versao.

Para entrevistas: usar `human_questions.template.csv`, codigos P001/P002,
sem nomes/contatos, com consentimentos separados para treino e avaliacao.
`import_human_questions.py` reserva inicialmente toda a coleta para revisao e
avaliacao independente, agrupando por participante. Nao treina automaticamente.
Filtros automaticos de identificadores nao substituem revisao de privacidade.

Ao chegar o novo dataset: auditar e separar grupos, reservar teste, revisar
amostra diversa, resolver ambiguidades, complementar intencoes/riscos, preparar
respostas fundamentadas, retreinar nova versao e checar regressao. So apos isso
decidir ativacao do novo NLP. TinyLM continua uma fase separada e ainda nao
foi iniciado.

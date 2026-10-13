# Coach 7.01 - Dados e conhecimento

## Status

As quatro subfases 7.01 estao concluidas. A taxonomia e os exemplos foram
fechados em 2026-10-06; a base de conhecimento 1.1 e o dataset congelado 1.2.0
foram revisados em 2026-10-07. A proxima etapa e a 7.02, com baseline NLP,
entidades, metricas e analise de erros.

Esta etapa nao treina um modelo. Ela define o que o futuro NLP deve entender,
cria os primeiros exemplos rotulados, registra a base de conhecimento e impede
erros comuns de preparacao dos dados.

A revisao profissional da 7.01.1 usa cinco eixos separados: intencao, topico,
entidade, risco e capacidade. Essa decisao permite representar mensagens reais
com varios assuntos sem criar centenas de classes quase iguais.

## O que e taxonomia

Taxonomia e a lista oficial de categorias do Coach. Em vez de criar um `if`
para cada frase possivel, mensagens diferentes recebem um nome padronizado.

Exemplos:

- `por que cardio ajuda a emagrecer?` -> `ask_training_concept`;
- `troca o supino de hoje` -> `replace_exercise`;
- `sim, pode aplicar` -> `confirm_planner_action`;
- `estou com dor no peito` -> intencao da conversa mais risco
  `emergency_symptom`.

Intencao e risco ficam separados porque uma pergunta comum pode conter um sinal
de risco. O risco muda a rota da resposta sem apagar o assunto original.

## Estrutura criada

```txt
ai/
  data/
    taxonomy/
      intents.v1.json
      hierarchy.v1.json
      topics.v1.json
      entities.v1.json
      risks.v1.json
      capabilities.v1.json
      annotation-guidelines.md
    research/
      source_catalog.v1.json
      taxonomy-research-notes.md
    source/
      intent_examples.v1.json
      risk_examples.v1.json
      real_pattern_examples.v1.json
      ambiguity_examples.v1.json
    schema/
      dataset-row.schema.json
    knowledge/
      README.md
      coverage.v1.json
      knowledge_chunks.v1.json
    metadata/
      sources.v1.json
      dataset-card.md
      dataset-changelog.md
    splits/
      train/
      validation/
      test/
      challenge/
      split_policy.v1.json
      assignments.v1.json
      quality_report.json
      manifest.json
  scripts/
    audit_splits.py
    build_splits.py
    knowledge_report.py
    validate_data.py
  tests/
    test_data_quality.py
    test_knowledge_base.py
    test_split_quality.py
```

## Numeros atuais

- 30 intencoes;
- 94 topicos detalhados;
- 79 entidades;
- 13 rotulos de risco;
- 44 capacidades de resposta ou acao;
- 240 exemplos de intencao;
- 104 exemplos de risco;
- 39 casos separados de ambiguidade e comportamento;
- 383 registros gerados;
- 67 trechos de conhecimento;
- 27 fontes aprovadas, sendo 23 externas e 4 contratos internos;
- 14 trechos de treino, 23 de alimentacao, 11 de recuperacao e 19 de seguranca;
- 5 modos de resposta: educar, cautela, encaminhar, emergencia e regra de produto;
- cobertura explicita dos 12 riscos diferentes de `none`;
- 8 grupos de fontes catalogados para pesquisa de cobertura.

Os exemplos misturam portugues formal, linguagem curta, abreviacoes e erros
leves. Uma conversa real fornecida voluntariamente pelo responsavel do projeto
serviu para descobrir temas e formas de perguntar, mas as frases foram
reescritas e nenhum dado pessoal foi guardado.

## Cinco eixos da taxonomia

- **Intencao:** o resultado que a pessoa espera, como aprender, avaliar,
  registrar ou mudar algo.
- **Topico:** o assunto citado, como progressao, cutting, sono ou creatina.
- **Entidade:** o detalhe concreto, como exercicio, alimento, data ou carga.
- **Risco:** sinal independente que pode mudar a rota da resposta.
- **Capacidade:** operacao granular que o Coach responde ou envia ao Planner.

Por exemplo, `meu cutting estagnou e quero reduzir mais as calorias` pode ter
`analyze_progress` como intencao principal, `cutting` e `energy_balance` como
topicos, um valor de calorias como entidade e uma intencao secundaria de
mudanca. Se a reducao solicitada for extrema, o risco e marcado em paralelo.

`hierarchy.v1.json` agrupa intencoes por dominio e familia. `topics.v1.json`
cobre assuntos de treino, alimentacao, recuperacao, progresso, produto e
conversa. `capabilities.v1.json` registra o que ja existe no backend, o que esta
planejado e o que e apenas resposta educativa.

## Intencoes

As 30 intencoes estao agrupadas em:

- perguntas educativas sobre treino, exercicios, alimentacao e recuperacao;
- leitura de plano e analise de progresso;
- apoio de motivacao sem cobranca;
- ajuda com substituicoes, refeicoes, preparo e seguranca dos alimentos;
- pedidos de mudanca enviados ao Planner;
- registro de cargas e alimentos;
- confirmacao, rejeicao e desfazer;
- conversa, esclarecimento, imagem ainda nao suportada e assunto fora do escopo.

Os quatro contratos ja implementados no backend sao identificados na
taxonomia: `move_workout_day`, `replace_exercise`, `replace_meal_item` e
`set_day_activity`. As outras acoes ficam marcadas como planejadas e nao podem
ser tratadas como se ja existissem.

## Entidades

Entidade e a informacao concreta dentro da frase. Na mensagem `troca o supino
de hoje por flexao`, por exemplo:

- intencao: `replace_exercise`;
- exercicio atual: `supino`;
- substituto: `flexao`;
- alcance: `hoje`.

A taxonomia possui exercicio, grupo muscular, equipamento, carga, series,
repeticoes, RPE, RIR, datas, alimentos, refeicoes, estrategia alimentar, sono,
sintoma, preferencia, alergia, restricao, medicacao, nivel de treino, qualidade
do sono, fome, negacao e outras informacoes necessarias aos contratos.

A anotacao das posicoes exatas dessas entidades no texto pertence a fase 7.02.

## Riscos

A classificacao de risco cobre:

- dor ou possivel lesao;
- sinal potencialmente emergencial;
- sinal de transtorno alimentar;
- dieta extrema ou desidratacao;
- medicamento ou hormonio;
- incerteza sobre suplemento;
- alergia ou possivel reacao alimentar;
- incerteza sobre seguranca de alimento;
- pedido de treino evidentemente perigoso;
- sinais combinados de recuperacao insuficiente;
- contexto clinico ou populacao vulneravel;
- crise de saude mental;
- ausencia de risco especial.

O rotulo nao faz diagnostico. Ele escolhe uma rota conservadora, bloqueia
alteracoes perigosas e orienta apoio adequado.

## Pesquisa de cobertura

O catalogo em `ai/data/research/source_catalog.v1.json` registra conversas,
foruns e conjuntos publicos consultados, licenca conhecida, uso permitido,
proibicoes e padroes observados. Foruns foram usados apenas para descobrir
linguagem e situacoes reais; suas respostas nao sao fonte tecnica.

Foram observados temas recorrentes como frequencia, tempo limitado, plateau,
sono, fadiga, refeicao flexivel, culpa, porcoes, substituicoes, preparo e
armazenamento. Trabalhos e datasets de perguntas de consumidores tambem
mostraram que mensagens longas misturam detalhes perifericos com o pedido real.

Nenhum dataset externo foi importado na 7.01.2. Uma fonte so podera entrar em
uma versao futura depois de revisar licenca, proveniencia, privacidade, idioma,
duplicatas e qualidade. A conversa privada fornecida pelo responsavel nao tem
URL nem texto armazenado no repositorio; apenas padroes anonimos foram
registrados.

## Regras de anotacao

`annotation-guidelines.md` define intencao principal e secundaria, mensagens
com varios pedidos, diferenca entre pergunta e mudanca, entidades ausentes,
negacao, referencias ao contexto, dependencia de imagem, riscos multilabel e
desacordo entre anotadores.

Uma pergunta nunca vira autorizacao. Um erro ortografico nao vira ambiguidade
se o sentido estiver claro. Quando faltar informacao, o Coach classifica o que
consegue, registra o campo ausente e pede um esclarecimento curto.

## Dataset 1.2.0

A 7.01.2 separa tres origens para que o treinamento seja auditavel:

- `synthetic_curated`: exemplos comuns escritos e revisados para cada classe;
- `real_pattern_rewrite`: frases novas inspiradas em padroes reais, com
  `source_id`, estilo e dificuldade;
- `synthetic_adversarial_curated`: mensagens dificeis criadas para avaliacao.

Os padroes reais reescritos incluem informalidade, abreviacoes e erros leves,
mas nao copiam postagens ou conversas. Cada uma das 30 intencoes e dos 13 riscos
possui seis exemplos sinteticos e dois padroes reais reescritos.

O conjunto de desafio possui 39 mensagens e avalia nove tipos de ambiguidade:
multiplas intencoes, entidade ausente, referencia ao contexto, pergunta
implicita, negacao, prioridade de seguranca, tempo relativo, dependencia de
imagem e pedidos conflitantes. Cada caso registra tambem o comportamento
esperado, e nao apenas um rotulo.

O contrato dos registros esta em `ai/data/schema/dataset-row.schema.json`. A
documentacao completa de origem, uso e limitacoes esta em
`ai/data/metadata/dataset-card.md`.

## Base de conhecimento

Cada trecho possui texto curto, dominio, topicos oficiais, fontes, nivel de
evidencia, confianca, riscos, modo de resposta, datas, uso permitido e limite.
As fontes incluem OMS, Ministerio da Saude, Anvisa, ACSM, CDC, ISSN, NIH, NIMH,
American Heart Association, NIAID, ACOG, CVV e contratos internos do Evolv.

O texto e uma sintese propria; o repositorio nao copia artigos ou guias
inteiros. O objetivo da recuperacao futura e buscar poucos trechos relevantes
antes de responder.

### Como as fontes foram escolhidas

A ordem de preferencia e: autoridade brasileira para contexto local, organismo
internacional de saude publica, diretriz ou consenso profissional e sintese de
evidencia. Contratos internos explicam somente comportamento do produto.

Foruns, redes sociais, influenciadores, blogs comerciais e respostas de outros
modelos nao sustentam afirmacoes tecnicas. Eles podem revelar linguagem para o
dataset, mas ficam fora da base de conhecimento. Estudo isolado tambem nao e
usado para recomendacao ampla quando existe uma sintese melhor.

### Cobertura 1.1

Treino cobre consistencia, frequencia, objetivo, forca, hipertrofia, potencia,
equipamento, falha, progressao, selecao, sessao perdida e dor. Alimentacao cobre
qualidade do padrao, energia, estrategias de dieta, proteina, timing, pre e
pos-treino, hidratacao, creatina, suplementos, variacao, substituicao, preparo,
alcool e alimentacao vegetariana.

Recuperacao cobre duracao e qualidade do sono, habitos, limites de relogios,
carga e recuperacao, sinais combinados, dor muscular, descanso, estresse e
check-in opcional. Seguranca cobre alimentos, transtornos alimentares, restricao
extrema, alergia, gestacao, contexto clinico, medicamento e hormonio, pedidos
perigosos, emergencia, crise de saude mental e permissoes do Planner.

As rotas brasileiras usam SAMU 192 para emergencia e CVV 188 para apoio
emocional, sem tratar o CVV como substituto de atendimento urgente.

### Revisao e expiracao

Fontes dinamicas de seguranca e regulacao vencem mais cedo; guias e consensos
estaveis recebem ate doze meses; contratos internos sao revistos em ate tres
meses ou junto com qualquer mudanca funcional. Trecho vencido ou fonte nao
aprovada falha na validacao e fica bloqueado para recuperacao.

`ai/data/knowledge/README.md` contem a politica editorial completa e
`coverage.v1.json` declara os minimos verificaveis. `knowledge_report.py` mostra
contagens e vencimentos sem alterar os dados.

## Divisao congelada

- treino ensina os parametros do classificador;
- validacao ajuda a escolher configuracoes e limite de confianca;
- teste mede o resultado final em dados que nao participaram das escolhas.

`build_splits.py` usa uma ordem deterministica por SHA-256 dentro de cada
rotulo. Na versao atual, cada rotulo tem seis exemplos de treino, um de
validacao e um de teste. Os 39 casos de desafio ficam separados e nao podem ser
usados para treino nem para ajustar limiares.

`split_policy.v1.json` documenta as regras e os criterios de aceite.
`assignments.v1.json` congela, para cada um dos 383 IDs, tarefa, rotulo e split.
O gerador recusa uma reconstrucao que mova qualquer ID dentro da versao 1.2.0.
Uma mudanca nos exemplos exige nova versao e revisao explicita do registro.

`manifest.json` registra a versao do gerador, distribuicao por split e tarefa,
hashes de todos os JSONL, fingerprints dos arquivos-fonte, taxonomias, esquema,
politica, registro e relatorio. Isso torna uma alteracao manual detectavel.

### Contagens congeladas

- treino: 258 registros;
- validacao: 43 registros;
- teste: 43 registros;
- desafio: 39 registros;
- total: 383 registros e 383 IDs unicos.

## Protecoes de qualidade

`validate_data.py` falha quando encontra:

- rotulo ausente ou desconhecido;
- menos de oito exemplos por classe;
- texto vazio ou duplicado;
- a mesma frase em mais de uma divisao;
- quase-duplicata atravessando treino, validacao, teste ou desafio;
- falta de procedencia, estilo ou dificuldade;
- padrao real com fonte desconhecida;
- ambiguidade, comportamento, topico ou entidade invalida;
- vazamento do conjunto de desafio para os splits comuns;
- entidade ou risco inexistente;
- contrato falsamente marcado como implementado;
- trecho sem fonte ou limite de uso;
- fonte interna ausente;
- fonte externa sem HTTPS;
- fonte ou trecho vencido;
- topico, dominio, risco ou modo de resposta desconhecido;
- fonte nao aprovada, proibida ou usada fora de seu dominio;
- alegacao tecnica apoiada apenas por contrato interno;
- dominio ou rota de risco abaixo da cobertura minima;
- fonte aprovada que nao sustenta nenhum trecho.
- versao, hash ou fingerprint divergente do manifesto;
- ID ausente, extra ou movido em relacao ao registro congelado;
- desafio misturado com uma divisao comum;
- distribuicao diferente de seis/um/um por rotulo.

`audit_splits.py` normaliza caixa, acentos e pontuacao para bloquear duplicatas
exatas. Tambem compara similaridade de tokens e de sequencia para bloquear
quase-duplicatas entre divisoes. A auditoria 1.2.0 encontrou zero achados
bloqueantes: 383 textos normalizados unicos em 383 registros.

Os testes automaticos geram tudo duas vezes, comparam os manifestos, executam a
validacao completa e injetam vazamentos artificiais para provar que duplicata,
quase-duplicata e desafio no split errado sao realmente rejeitados.

## Como verificar

Na raiz do repositorio:

```powershell
python ai/scripts/build_splits.py
python ai/scripts/audit_splits.py
python ai/scripts/validate_data.py
python ai/scripts/knowledge_report.py
python -m unittest discover -s ai/tests -v
```

## Proxima subfase

A 7.01.4 esta concluida. A 7.02.1 criou o baseline sem alterar nem abrir o
teste congelado, e a 7.02.2 criou o extrator hibrido de entidades. As
implementacoes ficam em `docs/14-coach-nlp-baseline.md` e
`docs/15-coach-entity-extraction.md`; a proxima entrega e a avaliacao
detalhada da 7.02.3.

O conjunto atual e uma fundacao mensuravel, nao um produto final. A qualidade
sera demonstrada por avaliacao, e nao pela quantidade de arquivos criada.

# Guia de rotulagem da taxonomia

## Unidade de analise

A unidade e uma mensagem do usuario com o menor contexto anterior necessario
para entende-la. O anotador nao deve inventar informacoes ausentes nem usar
conhecimento pessoal sobre o autor.

Cada exemplo pode receber:

1. uma intencao principal;
2. zero ou mais intencoes secundarias;
3. zero ou mais topicos;
4. entidades presentes literalmente ou resolvidas pelo contexto;
5. um ou mais riscos;
6. marcas de dependencia de contexto, imagem ou dados do usuario.

## Como escolher a intencao principal

A intencao principal representa o resultado imediato que a pessoa espera.

- Pergunta de conhecimento: responder, explicar ou comparar.
- Pedido de leitura: consultar o plano ou o historico.
- Pedido de mudanca: criar uma previa, nunca aplicar diretamente.
- Registro: guardar algo que aconteceu.
- Controle de dialogo: confirmar, rejeitar, desfazer ou completar contexto.

Na frase `explica o treino de hoje e troca o supino`, a mudanca e a intencao
principal porque produz efeito no produto. `explain_current_plan` e secundaria.
Se duas acoes independentes forem igualmente importantes, manter ambas e
marcar o topico `multi_request`; o orquestrador deve separar as propostas.

## Intencao nao e assunto

`cutting`, `creatina` e `progressao de carga` sao topicos. O que a pessoa quer
fazer com o assunto define a intencao:

- `o que e cutting?` -> `ask_nutrition_concept` + `cutting`;
- `muda minha dieta para cutting` -> `change_diet_structure` + `cutting`;
- `meu cutting parou de funcionar?` -> `analyze_progress` + `cutting`.

Essa separacao evita criar uma classe diferente para cada combinacao de verbo
e tema.

## Pergunta versus mudanca

- `o que posso usar no lugar do arroz?` pede opcoes e nao altera o plano.
- `troca o arroz por batata` pede uma previa de mudanca.
- `seria melhor trocar o arroz?` e avaliacao; nao tratar como autorizacao.
- `pode trocar` so e confirmacao se houver exatamente uma proposta pendente.

Nenhuma pergunta implicita deve executar alteracao.

## Entidades

Marcar apenas o trecho necessario, sem incluir artigos ou pontuacao, quando a
anotacao por posicao for criada na fase de dataset.

- Valores numericos devem preservar unidade e contexto.
- Negacoes devem ser registradas: `nao gosto de peixe` nao equivale a `gosto`.
- Datas relativas dependem do relogio e fuso do usuario.
- `hoje`, `amanha` e `segunda` nao devem virar datas absolutas no dataset.
- Referencias como `esse` exigem contexto anterior ou esclarecimento.
- Uma imagem anexada nao autoriza o modelo textual a descrever seu conteudo.

## Risco

Risco e multilabel e tem prioridade sobre a intencao. A mesma mensagem pode
ter `ask_training_concept` e `emergency_symptom`.

- Nao diagnosticar.
- Nao inferir transtorno ou doenca apenas por objetivo estetico.
- Rotular sinal explicito, nao possibilidade remota.
- Em conflito, usar a rota do risco de maior gravidade.
- Alergia com falta de ar, desmaio ou inchaco de garganta tambem recebe
  `emergency_symptom`.
- Dor muscular comum sem indicio de lesao nao recebe automaticamente
  `pain_or_possible_injury`.

## Ambiguidade e baixa informacao

Mensagens como `muda ai`, `o outro` e `faz melhor` recebem `clarification`
quando nao existe contexto suficiente. Erro ortografico nao e ambiguidade se o
sentido continuar claro.

Para pedidos incompletos:

- classificar a intencao quando ela estiver clara;
- extrair o que existe;
- registrar entidades faltantes;
- fazer uma pergunta curta de esclarecimento;
- nao completar campos com suposicoes.

## Linguagem real

O dataset futuro deve incluir portugues formal e informal, abreviacoes, erros
comuns, frases curtas, mensagens longas, negacoes, comparacoes, referencias ao
contexto e pedidos com mais de uma etapa. Variacoes devem ser escritas de forma
independente; nao basta trocar uma palavra por sinonimo.

## Procedencia dos exemplos

Cada registro precisa distinguir sua origem:

- `synthetic_curated`: exemplo escrito para cobrir uma classe e revisado;
- `real_pattern_rewrite`: frase nova baseada em um padrao observado, nunca uma
  citacao ou copia de mensagem;
- `synthetic_adversarial_curated`: caso dificil criado para desafiar regras e
  avaliar comportamento.

Um exemplo baseado em fonte real registra `source_id`, estilo e dificuldade.
Nenhum nome, imagem, medida, URL privada ou historico pessoal entra no texto. A
fonte permite rastrear por que o exemplo existe, nao reconstruir a pessoa.

Estilo descreve a forma da mensagem, nao a identidade do autor. Erros e
abreviacoes precisam parecer naturais; inserir erros aleatorios em todas as
palavras nao cria um bom exemplo informal.

## Dificuldade e casos de desafio

- `standard`: pedido direto, mesmo que informal;
- `hard`: depende de negacao, contexto, mais de uma intencao ou limite sutil.

Casos de desafio ficam separados do treinamento comum. Eles registram tipo de
ambiguidade, intencao principal, intencoes secundarias, topicos, riscos,
entidades ausentes e comportamento esperado. Um caso nao e considerado correto
apenas porque acertou a classe; tambem precisa escolher a rota esperada.

## Criterios de aceite de um exemplo

Um exemplo so entra na versao quando:

1. possui um pedido interpretavel ou ambiguidade intencional;
2. nao duplica nem parafraseia quase literalmente outro registro;
3. tem rotulo justificavel pelas regras deste guia;
4. nao contem dado pessoal ou afirmacao factual apresentada como resposta;
5. informa procedencia, estilo e dificuldade quando derivado de padrao real;
6. preserva negacoes, unidades e referencias relevantes;
7. foi revisado por uma pessoa antes de ser usado para medir o modelo.

## Desacordo entre anotadores

Casos duvidosos vao para uma fila de adjudicacao. A decisao final deve registrar
o exemplo, rotulos discutidos, regra aplicada e motivo. Se o mesmo desacordo se
repetir, atualizar este guia antes de adicionar mais exemplos.

## Controle de qualidade

Uma amostra revisada por duas pessoas deve medir concordancia para intencao,
topico e risco. O conjunto de teste nao pode ser alterado para melhorar uma
metrica depois que os resultados forem vistos; erros descobertos viram novos
casos de treino ou um novo conjunto de teste versionado.

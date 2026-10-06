# Planner nutricional

## Status

Fases 04.1 a 04.4 concluidas: regras nutricionais, selecao de alimentos, ajuste de porcoes, substituicoes deterministicas, persistencia transacional, API autenticada, gerenciamento no mobile, variacoes por dia e ajustes confirmados.

## Modelo do dominio

O Planner nao trata todos os nomes de dieta como uma unica escolha. Ele combina dimensoes independentes:

- fase energetica: ganho de massa, perda de gordura, manutencao, recomposicao, pausa de dieta ou personalizada;
- distribuicao de macros: equilibrada, alto carboidrato para desempenho, low carb, cetogenica ou personalizada;
- horario: regular, janela alimentar ou personalizado;
- estilo alimentar: onivoro, pescetariano, vegetariano, vegano ou personalizado;
- preferencias: alimentos preferidos e alimentos rejeitados;
- restricoes: ingredientes e alergenos que nunca podem ser selecionados.

Assim, `cutting low carb com janela alimentar` e uma combinacao valida. Cutting define energia, low carb define macros e a janela define horarios.

## Calorias

Ordem de prioridade:

1. meta informada explicitamente pelo usuario;
2. manutencao previamente estimada e informada;
3. estimativa de Mifflin-St Jeor com peso, altura e idade.

Quando o parametro metabolico de sexo nao e informado, o motor usa o ponto medio das duas constantes da equacao, marca a confianca como baixa e registra a suposicao. Identidade de genero nao e usada como substituto automatico desse parametro.

Ajustes iniciais do MVP:

- ganho de massa: `+10%`;
- perda de gordura: `-15%`;
- recomposicao: `-5%`;
- manutencao e pausa de dieta: sem ajuste;
- personalizada: exige decisao posterior do usuario.

Esses percentuais sao pontos de partida, nao promessas. Evolucao de peso, aderencia, desempenho e fome deverao orientar ajustes futuros.

## Macronutrientes

- proteina parte de `0,8 g/kg` para sedentarios e sobe gradualmente ate `2,0 g/kg` para pessoas muito ativas;
- perda de gordura e recomposicao usam piso inicial de `1,8 g/kg`, respeitando o limite de 35% da energia;
- fibra usa a referencia inicial de `14 g por 1.000 kcal`;
- equilibrada busca permanecer nas faixas gerais de distribuicao aceitavel;
- low carb inicia com aproximadamente 30% da energia em carboidratos;
- cetogenica limita carboidratos a no maximo 50 g ou aproximadamente 8% da energia;
- personalizada exige que proteina, carboidrato e gordura somem 100%.

## Refeicoes

O total diario e distribuido entre uma e oito refeicoes. A soma de calorias e macros das refeicoes sempre fecha exatamente com a meta do dia, inclusive depois dos arredondamentos.

Jejum intermitente e tratado como horario. Ele nao reduz calorias automaticamente e nao muda os macros por conta propria.

Cada refeicao e montada pela fase 04.2 usando papeis substituiveis:

- fonte proteica;
- fonte de carboidrato, quando compativel;
- vegetal ou fruta;
- fonte de gordura, quando necessaria;
- complemento opcional.

Uma troca deve manter o mesmo papel e recalcular a quantidade. O Planner nao deve substituir arroz por frango apenas porque as calorias parecem semelhantes.

## Fase 04.2: motor de alimentos

O arquivo `nutrition-planner.generator.ts` recebe a recomendacao da fase 04.1 e um catalogo tipado. Ele e uma funcao pura: nao consulta internet, banco ou API durante a montagem e sempre produz o mesmo resultado para a mesma entrada.

Cada item do catalogo informa:

- identificador, nome, porcao-base e unidade;
- calorias, proteina, carboidrato, gordura e fibra da porcao-base;
- papeis nutricionais que pode cumprir;
- estilos alimentares compativeis;
- tipos de refeicao em que faz sentido;
- etiquetas, alergenos e nivel de processamento;
- porcao minima, maxima, inicial e passo de ajuste.

O fluxo de geracao e:

1. valida e remove IDs duplicados do catalogo;
2. elimina alimentos incompativeis com estilo, alergias, restricoes e rejeicoes;
3. na cetogenica, impede fonte dedicada de carboidrato e frutas ou vegetais muito ricos em carboidrato;
4. escolhe candidatos por papel nutricional, adequacao ao horario e preferencia do usuario;
5. favorece alimentos in natura ou minimamente processados, sem transformar isso em proibicao universal;
6. penaliza repeticoes ao longo do dia quando existem alternativas equivalentes;
7. ajusta porcoes dentro dos limites e passos definidos no catalogo;
8. calcula totais, desvios e avisos quando o catalogo nao consegue aproximar a meta;
9. cria ate tres substituicoes equivalentes por item, sempre no mesmo papel nutricional.

O ajuste de porcoes usa uma busca local deterministica que minimiza, em conjunto, os desvios de calorias, proteina, carboidrato e gordura. Proteina recebe peso maior para evitar que uma refeicao bata calorias sacrificando sua funcao proteica.

Substituicoes tentam preservar primeiro o nutriente principal do papel: proteina para fontes proteicas, carboidrato para fontes de carboidrato, gordura para fontes de gordura e fibra para vegetais ou frutas. Depois o motor compara o restante dos macros e informa uma pontuacao de similaridade.

## Fase 04.3: dados e integracao

A geracao passou a usar o catalogo persistido no Supabase. O resultado completo e salvo em uma unica transacao: plano, metas, refeicoes, alimentos, quantidades, macros calculados e substituicoes. Uma falha em qualquer item cancela toda a criacao.

Entregas:

- 26 alimentos de referencia para iniciar o catalogo gratuito;
- metadados de papel nutricional, estilo, horario, alergenos, processamento e limites de porcao;
- apenas um plano alimentar ativo por usuario;
- ordem estavel de refeicoes e alimentos;
- historico de planos sem apagar os anteriores;
- cinco endpoints autenticados para gerar, listar, detalhar, ativar e arquivar;
- tela mobile para configurar e administrar planos reais;
- teste SQL transacional com `ROLLBACK`;
- RLS preservado porque a API acessa o banco com o token do usuario.

Endpoints:

- `POST /api/planner/nutrition-plans/generate`;
- `GET /api/planner/nutrition-plans`;
- `GET /api/planner/nutrition-plans/:planId`;
- `POST /api/planner/nutrition-plans/:planId/activate`;
- `POST /api/planner/nutrition-plans/:planId/archive`.

## Casos reais previstos

Uma dieta pode usar a mesma meta todos os dias ou estruturas diferentes para treino e descanso. No segundo caso, o Planner preserva a media calorica semanal, eleva moderadamente a meta de treino e calcula a meta de descanso. A proteina e os demais macros continuam sendo calculados pelas regras da fase 04.1.

Variedade e outra dimensao independente:

- cardapio fixo para quem prefere repeticao;
- rotacao de tres cardapios como recomendacao inicial;
- sete cardapios para uma semana inteira diferente;
- cada rotacao continua deterministica, auditavel e sujeita as mesmas restricoes;
- a aba Dieta escolhe automaticamente tipo de dia e indice da rotacao.

Essa escolha usa o contexto diario compartilhado com o treino. Um ajuste confirmado pode marcar uma data como descanso, musculacao, cardio ou treino misto. Cardio leve ou moderado usa o menu de descanso por padrao; cardio intenso ou com pelo menos 60 minutos pode usar o menu de treino. O sistema nao adiciona carboidratos ou refeicoes por conta propria: uma mudanca desse tipo precisa de proposta nutricional separada e confirmada.

Flexibilidade planejada nao significa calorias ilimitadas. A pessoa pode escolher nenhuma refeicao flexivel, uma semanal ou uma quinzenal e o dia preferido. Ela substitui uma refeicao normal. Alcool nunca e recomendado automaticamente; quando o usuario pede, o plano guarda somente a frequencia, o dia e o limite escolhido para mostrar a excecao na data correta.

Alimentos rejeitados sao removidos antes da geracao. A troca manual atual usa apenas alternativas equivalentes ja calculadas. O futuro Coach interpretara frases como `nao como este alimento` ou `quero outra opcao de pre-treino`, mas continuara enviando a mesma proposta tipada para previa e confirmacao.

## Fase 04.4: ajustes controlados

- treino e dieta nunca sao alterados por texto livre;
- a pessoa abre a edicao junto ao item, escolhe uma alternativa e recebe uma previa;
- a previa informa o que muda e o que permanece;
- a confirmacao aplica a mudanca em uma transacao;
- snapshots permitem detectar dados desatualizados e desfazer com seguranca;
- mover treino pode inverter dois dias ocupados sem perder sessoes;
- troca de exercicio valida grupo muscular ou padrao de movimento;
- troca de alimento exige uma substituicao aprovada do mesmo item;
- historico guarda origem manual ou futura origem do Coach.

## Limites atuais

- o catalogo inicial possui 26 alimentos de referencia e ainda deve crescer com fontes revisadas;
- o Coach por conversa ainda nao esta conectado; a previa e confirmacao manuais ja usam o contrato definitivo;
- os valores nutricionais dependem da qualidade e da porcao declarada pela fonte;
- micronutrientes ainda nao participam do otimizador;
- receitas compostas ainda precisam ser representadas por ingredientes ou por um item previamente calculado;
- o motor aproxima metas, mas nao promete igualdade perfeita quando o catalogo ou os limites de porcao nao permitem;
- alimentos ultraprocessados recebem menor prioridade, nao uma exclusao automatica;
- a sugestao nao substitui avaliacao profissional e permanece bloqueada para contextos clinicos sinalizados.

## Preferencias e seguranca

- alergias e restricoes sao exclusoes rigidas;
- alimentos que a pessoa nao gosta sao exclusoes por preferencia;
- alimentos preferidos recebem prioridade, mas nao anulam seguranca ou metas;
- cetogenica e janelas muito curtas geram aviso;
- contexto clinico informado bloqueia cardapio automatico ate revisao profissional;
- o sistema nao diagnostica, prescreve medicacao nem promete perda ou ganho de peso.

## Referencias iniciais

- Mifflin MD et al. A new predictive equation for resting energy expenditure in healthy individuals. DOI `10.1093/ajcn/51.2.241`.
- Dietary Reference Intakes, National Academies / ODPHP.
- Dietary Guidelines for Americans, USDA e HHS.
- DRI Calculator for Healthcare Professionals, USDA National Agricultural Library.
- International Society of Sports Nutrition position stand: protein and exercise.
- National Institute on Aging: research on intermittent fasting.
- FDA: major food allergens and strict avoidance.
- NIDDK: safe and sustainable weight-loss programs.
- Guia Alimentar para a Populacao Brasileira, Ministerio da Saude: alimentos in natura ou minimamente processados e refeicoes culturalmente adequadas.
- USDA FoodData Central API: composicao de alimentos genericos e documentacao oficial da API.
- Open Food Facts API: fonte complementar para produtos embalados, com validacao necessaria porque os dados sao colaborativos.

## Validacao automatizada

- 14 testes das regras da fase 04.1;
- 14 testes do motor da fase 04.2, incluindo variedade deterministica por semente;
- 3 testes da conversao para persistencia;
- testes SQL remotos da criacao, ordenacao, ativacao, arquivamento, variacoes, rotacao e flexibilidade;
- schema remoto sem avisos no `db lint`;
- cobertura de estilos alimentares, cetogenica, alergias, rejeicoes, preferencias, variedade, processamento, limites de porcao, substituicoes, catalogo incompleto, dados invalidos, determinismo e ciclos de cardapio.

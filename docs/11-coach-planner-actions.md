# Coach e Planner: mapa de intencoes

## Fronteira principal

O Coach existe primeiro para conversar, ensinar e explicar. Uma pergunta nao deve virar alteracao de plano apenas porque menciona treino, dieta ou rotina.

- Coach: entende linguagem, recupera conhecimento, explica e monta uma proposta estruturada.
- Planner: valida regras, calcula impacto e aplica somente a acao confirmada.
- Backend: autentica, autoriza e registra a operacao.
- Banco: preserva planos, versoes e historico.

## Intencoes sem alteracao

Essas situacoes geram somente resposta educativa:

- perguntas de anatomia, tecnica, cardio, hipertrofia, forca ou recuperacao;
- explicacao de exercicios, divisoes, series, repeticoes, RPE ou descanso;
- comparacoes entre alternativas;
- leitura e resumo do plano atual;
- interpretacao de progresso, estagnacao ou consistencia;
- duvidas sobre alimentacao e relacao entre dieta e treino;
- motivacao, organizacao e esclarecimento de expectativas;
- pedido ambiguo que ainda precisa de contexto.

## Intencoes que podem propor uma acao

As familias abaixo cobrem pedidos atuais e futuros sem criar uma regra isolada para cada frase:

- `replace_exercise`: trocar um exercicio por dor, preferencia, lotacao ou equipamento;
- `add_exercise` e `remove_exercise`: alterar um item sem refazer a sessao inteira;
- `reorder_exercises`: ajustar a ordem por prioridade, fadiga ou disponibilidade;
- `move_session`: mover ou inverter dias da semana;
- `set_day_activity`: trocar apenas a atividade de uma data por descanso, musculacao, cardio ou treino misto, sincronizando o menu alimentar;
- `reschedule_missed_session`: reorganizar uma falta sem duplicar volume;
- `shorten_session`: reduzir duracao mantendo prioridades;
- `extend_session`: adicionar trabalho sem exceder volume seguro;
- `change_frequency`: aumentar ou reduzir dias de treino;
- `change_split`: migrar entre Full body, Upper/Lower, PPL, Body-part ou Hibrida;
- `change_modality`: academia, casa, calistenia, maquinas, cardio ou combinacoes;
- `add_conditioning`: incluir cardio continuo, intervalado ou esportivo;
- `adjust_volume`: alterar series por grupo muscular;
- `adjust_intensity`: modificar repeticoes, descanso, carga-alvo, RPE ou RIR;
- `adjust_warmup_or_cooldown`: adaptar preparacao, mobilidade e volta a calma;
- `set_training_priority`: priorizar um grupo, habilidade ou movimento por um periodo;
- `apply_training_technique`: propor superserie, drop set, pausa ou outra tecnica quando compativel;
- `progress_exercise`: sugerir aumento de carga ou repeticoes;
- `hold_progression`: manter carga quando a evidencia ainda e insuficiente;
- `deload`: reduzir temporariamente volume ou intensidade;
- `pause_plan` e `resume_plan`: lidar com pausas sem apagar historico;
- `travel_or_home_adaptation`: adaptar por viagem ou equipamento limitado;
- `injury_limitation_adaptation`: retirar movimentos incompatíveis e pedir avaliacao profissional quando necessario;
- `recovery_adaptation`: responder a sono, estresse, fadiga ou motivacao baixa;
- `regenerate_day`: refazer somente um dia;
- `regenerate_block`: refazer uma parte delimitada do ciclo;
- `restart_plan`: criar nova versao quando a mudanca estrutural for grande.

Algumas mensagens nao pedem mudanca no momento, mas devem virar contexto futuro. Exemplos: gostar ou nao de um exercicio, preferir treinos curtos, evitar certo horario ou informar equipamento que costuma estar ocupado. Nesses casos, o Coach pode propor `remember_preference`, separado da alteracao do plano e tambem sujeito a confirmacao.

## Dimensoes consideradas em qualquer pedido

Uma familia de acao nao basta sozinha. A proposta tambem deve guardar:

- alvo: plano, semana, dia, exercicio, bloco ou prescricao;
- alcance: somente hoje, periodo definido ou permanente;
- motivo: preferencia, tempo, dor, fadiga, viagem, lotacao ou objetivo;
- restricoes: equipamento, duracao, dias, nivel e movimentos evitados;
- prioridade: o que deve ser preservado quando tudo nao couber;
- evidencia: dados do usuario que sustentam a sugestao;
- confianca: quando o Coach precisa perguntar antes de propor;
- reversibilidade: se a operacao pode ser desfeita automaticamente.

Assim, frases novas nao exigem uma funcao nova para cada jeito de falar. O NLP identifica intencao e parametros; o Planner continua trabalhando com contratos previsiveis.

## Situacoes que exigem cuidado

- dor forte, lesao suspeita, desmaio, falta de ar incomum ou outro sinal de alerta nao deve receber diagnostico; o Coach orienta interromper a atividade e buscar atendimento adequado;
- pedido contraditorio, como aumentar muito o volume e reduzir muito o tempo, exige explicar o conflito e pedir prioridade;
- mensagem ambigua nao altera nada ate o usuario esclarecer;
- motivacao baixa nao deve gerar cobranca constante nem mudancas automaticas;
- uma preferencia isolada nao deve sobrescrever restricoes de seguranca;
- medicacao e diagnostico nao sao executados pelo Planner; alimentacao usa regras nutricionais explicitas e nao substitui acompanhamento profissional.

## Variacoes de linguagem

Frases diferentes podem representar a mesma acao. Por exemplo, "a academia esta lotada", "nao tem banco livre" e "troca o supino de hoje" podem resultar em `replace_exercise`. O classificador identifica a familia; os parametros guardam o motivo, o alvo e as restricoes.

## Fluxo seguro da fase 04

1. Detectar se o usuario quer aprender ou mudar algo.
2. Responder a duvida mesmo quando houver uma proposta de acao.
3. Converter a mudanca em uma acao tipada.
4. Pedir apenas os dados realmente ausentes.
5. O Planner valida propriedade, volume, equipamento, dificuldade e conflitos.
6. Mostrar uma previa com o que muda e o que permanece igual.
7. Exigir confirmacao explicita.
8. Aplicar somente a parte confirmada.
9. Registrar motivo, antes, depois e origem da solicitacao.
10. Permitir desfazer quando a operacao for reversivel.

O sistema deve ser extensivel por familias e parametros. Nao deve tentar prever cada frase com um `if`, nem permitir que texto livre do Coach execute SQL ou altere o plano diretamente.

## Contratos ja implementados na fase 04.4

O backend e o mobile ja usam o fluxo completo para `move_workout_day`, `replace_exercise`, `replace_meal_item` e `set_day_activity`. Cada proposta possui origem, motivo, alvo, previa, snapshot anterior, snapshot posterior, validade e estado de confirmacao. Aplicar, rejeitar e desfazer sao operacoes autenticadas e sujeitas ao RLS.

`set_day_activity` cobre pedidos como "passe o treino de hoje para amanha", "hoje vou descansar" ou "farei apenas cardio". A mudanca pontual nao reescreve a semana inteira. O contexto diario decide qual variante alimentar mostrar e pode ser revertido. Se o usuario nao comunicar uma mudanca feita fora do app, o Coach nao afirma que sabe o que aconteceu; ele continua com o plano conhecido e aceita a correcao depois, sem cobranca.

O Coach local ainda sera construido. Quando chegar, ele nao recebera um atalho para o banco: apenas preencherá esses contratos tipados com `source = coach`. As demais familias deste documento continuam como mapa de expansao e serao implementadas conforme os casos reais forem priorizados.

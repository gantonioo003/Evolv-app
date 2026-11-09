"""Project-authored synthetic development scenarios. No real conversations.

Each line is a separate scenario; context || message never contains labels.
Train and validation are authored separately, not random paraphrase splits.
"""

BANK = {
"move_workout_day": ("""
Vou trabalhar no plantão de quarta. Passe essa sessão para domingo.
Meu treino de costas está na segunda; transfira ele para sábado, sem copiar a sessão.
Agende o treino que seria em 16/11/2026 no dia 18/11/2026.
Não consigo ir na sexta desta semana. Puxa o treino dela pra quinta, q tá vazia.
Coach mostrou sessão A em 09/11 e quarta sem treino. || A sessão A fica melhor na quarta; remarca pra lá.
Tenho pernas no sábado e domingo livre no calendário. || Deixa a sessão de pernas pro domingo desta semana.
""", """
Hoje é segunda e há treino só na sexta. || Antecipa a sessão de sexta para amanhã; vou sair da cidade no fim de semana.
Na minha agenda, dia 24/11 tem superiores e dia 26/11 está vazio. || Desloca superiores do dia 24 para o dia 26, mantendo a mesma ficha.
O compromisso mudou: quero fazer na segunda o treino reservado para domingo, em vez de repor dois treinos.
Esta semana tenho musculação na quarta e nada programado no sábado. || Encaixa no sábado a sessão que estava na quarta.
Agenda atual: treino B na quinta; terça disponível. || joga o B pra terça pfv
Preciso remarcar a sessão de 07/12/2026 para 10/12/2026 porque terei uma prova.
"""),
"set_day_activity": ("""
No dia 12/11/2026, registra descanso na agenda.
Quero que amanhã seja um dia de musculação no calendário, sem mexer no resto da semana.
Nesse domingo vou pedalar; deixa o tipo de atividade do dia como cardio.
Na próxima segunda farei pesos e esteira, então põe atividade mista nesse dia.
Coach perguntou a data da alteração de atividade. || Dia 21/11 vai ser descanso, pode preparar isso.
Em 30/11/2026 vou fazer apenas corrida. Marca o dia como cardio, não como musculação.
""", """
A aula foi cancelada. Pode deixar a data de hoje como descanso no aplicativo?
Agenda mostra sexta sem atividade definida. || Sexta eu farei treino resistido; classifica esse dia como musculação.
No feriado de 20/11 pretendo só caminhar. Atualiza essa data para cardio.
Meu sábado terá natação e treino com pesos; define a atividade como mista.
Eu tinha previsto academia em 02/12/2026, mas não vou fazer nada. Muda esse dia para descanso.
Coloca musculação em 14/12/2026. Estou falando do tipo de atividade, não de mover uma sessão existente.
"""),
"replace_exercise": ("""
Na ficha de peito, substitua o supino reto por flexão de braços.
O aparelho está ocupado; quero tirar a cadeira extensora e colocar agachamento no lugar.
Troca a remada curvada pela remada baixa no meu treino A.
Meu treino tem elevação lateral com halteres. || Em vez dela, coloca elevação lateral no cabo.
Coach perguntou qual exercício sai. || Sai o leg press, entra o agachamento goblet.
O banco sumiu da sala, substitui o supino inclinado por flexão hoje.
""", """
Quero editar a ficha: retira a puxada aberta e adiciona a puxada neutra na mesma posição.
Estou olhando a sessão de braços, que contém rosca direta. || Dá pra deixar rosca martelo no lugar dessa rosca direta?
Não tenho barra fixa no hotel. Substitua a barra fixa por puxada na polia no treino salvo.
No lugar do stiff que está no programa, prefiro levantamento terra romeno com halteres.
A máquina de panturrilha está quebrada; troca o exercício cadastrado por panturrilha em pé.
Nesta sessão use remada unilateral em substituição à remada cavalinho, preservando os outros movimentos.
"""),
"replace_meal_item": ("""
No café de amanhã, troca o pão por tapioca.
Meu almoço tem arroz e frango. || Quero batata no lugar do arroz dessa refeição.
Tira a banana do lanche e põe maçã, mantendo os demais itens.
No jantar cadastrado, substitui carne bovina por frango.
Não achei iogurte no mercado, coloca leite como substituto no meu café.
Coach perguntou qual alimento substituir. || O macarrão do jantar por arroz.
""", """
Estou sem aveia em casa; edita o café da manhã e deixa pão no lugar da aveia.
Na ceia do plano aparece leite. || Troque esse leite por iogurte natural, se houver equivalente aprovado.
Substitua a maçã do lanche da tarde por pera no cardápio salvo.
Gostaria de usar lentilha em vez do feijão que consta no almoço.
Vou levar marmita e prefiro mandioca à batata desse almoço. Faz essa substituição na prévia.
Mantenha o sanduíche do lanche, mas substitua o queijo pelo ovo cadastrado como alternativa.
"""),
"remember_preference": ("""
Guarda que prefiro treinar antes do trabalho para os próximos planejamentos.
Lembra que eu não gosto de berinjela, sem alterar o cardápio de hoje.
Salva minha preferência por exercícios com halteres.
Para futuras sugestões, anota que gosto de comida simples e pouco temperada.
Prefiro refeições salgadas no café; guarda essa preferência.
Não muda a ficha agora, só lembra que gosto mais de máquinas que de barra livre.
""", """
Nas próximas vezes, considera que costumo cozinhar só no domingo. Quero guardar isso no perfil.
Pode memorizar que eu prefiro fazer cardio ao ar livre?
Deixa registrado que não curto mamão. Hoje sigo o que já está no plano.
Gostaria que você lembrasse da minha preferência por treinos curtos para sugestões futuras.
Eu gosto de almoçar cedo; salva essa informação como preferência, sem refazer nada agora.
Quando for sugerir refeições de novo, lembra que prefiro arroz ao macarrão.
"""),
"adjust_training_volume": ("""
Reduz uma série de cada exercício do treino de pernas.
Quero acrescentar duas séries semanais para costas na ficha atual.
Corta o total de séries de bíceps pela metade nesta semana.
Hoje estou com menos tempo, remove uma série de cada movimento sem mudar a carga.
Meu treino A tem cinco séries de supino. || Deixa só três séries nesse supino.
Adiciona uma série ao agachamento e mantém o número de repetições.
""", """
O programa atual soma vinte séries para peito. Prepara uma versão com dezesseis.
Gostaria de baixar o volume de ombros, retirando duas séries da semana.
Nesta sessão faça apenas duas séries de remada em vez das quatro previstas.
Pode aumentar o número de séries da panturrilha no treino salvo, preservando a carga?
Treino atual: três séries em cada exercício de braço. || Acrescenta uma série por exercício, sem trocar os movimentos.
Remova as séries extras de abdômen que acrescentei ontem; quero diminuir esse volume.
"""),
"adjust_training_intensity": ("""
No supino, muda a carga alvo de vinte para vinte e dois quilos.
Quero aumentar o descanso entre séries de um para dois minutos.
Deixa o agachamento com oito repetições por série em vez de dez.
Reduz o peso previsto da remada, mantendo as quatro séries.
Coach mostrou o treino com RIR 1. || Ajusta o esforço alvo para RIR 3 nessa sessão.
Muda a faixa de repetições da puxada para doze a quinze, sem adicionar séries.
""", """
Estou revisando a ficha: a meta de carga do leg press deve cair de cem para noventa quilos.
Atualiza o intervalo da rosca para noventa segundos; o total de séries continua igual.
No próximo treino, prepara o terra com RPE 7 em lugar de RPE 9.
Prefiro que as séries de flexão tenham seis repetições, não as dez programadas.
A carga prevista no desenvolvimento está alta para minha meta de esforço; diminui o peso alvo.
Suba a meta da remada em dois quilos, sem mudar as repetições nem a quantidade de séries.
"""),
"change_training_split": ("""
Muda minha divisão ABC para full body.
Quero trocar o esquema atual por superior e inferior em quatro dias.
Meu treino está dividido em cinco partes; reorganiza como push pull legs.
Coach mostrou ABCD. || Eu prefiro migrar para uma divisão AB.
Transforma minha rotina full body em upper lower.
Adote uma divisão de corpo inteiro três vezes por semana no lugar da atual.
""", """
Não quero manter a divisão por músculo que uso hoje. Reestrutura como superior/inferior.
A ficha salva usa push pull legs; desejo passar a treinos de corpo inteiro.
Organize o programa atual em A e B, em vez de A, B e C.
Minha semana está em ABCDE. Prepara a mudança para ABCD.
Quero uma divisão de empurrar e puxar no lugar da divisão atual por grupos musculares.
Deixe o plano semanal no formato full body, abandonando a separação atual de peito, costas e pernas.
"""),
"change_diet_structure": ("""
Organiza meu cardápio atual em quatro refeições em vez de seis.
Quero mudar os horários das refeições do meu plano para caber no trabalho.
Reestrutura a dieta salva para cozinhar apenas duas vezes por semana.
No plano alimentar que já uso, ativa um rodízio de cardápios.
Junta os dois lanches da minha dieta em uma refeição maior.
Quero uma versão vegetariana do meu plano alimentar atual.
""", """
Minha rotina mudou para turno noturno. Redistribua as refeições da dieta que já está cadastrada.
No cardápio vigente, retire a ceia e redistribua os itens entre as demais refeições.
Reorganiza a dieta atual para eu levar duas marmitas e fazer o resto em casa.
Desejo alternar dois menus durante a semana em vez de repetir o mesmo plano todos os dias.
Mude a estrutura alimentar que uso para incluir café, almoço, lanche e jantar.
Quero adaptar os horários do cardápio existente ao treino depois da faculdade.
"""),
"update_goal": ("""
Meu objetivo agora é ganhar massa, atualiza isso no perfil.
Quero deixar de focar emagrecimento e passar a manter o peso.
Troca minha meta principal para melhorar o condicionamento.
Registra que minha prioridade passou a ser desempenho no tênis.
Minha meta era chegar a oitenta quilos. || Quero mudar essa meta para setenta e oito.
Atualiza meu objetivo para força, em vez de hipertrofia.
""", """
Não estou informando meu peso atual: desejo alterar a meta de peso para noventa quilos.
O foco registrado é estética; quero colocar resistência como objetivo principal.
Passe minha fase de perda de peso para manutenção, sujeita à revisão do plano.
Acabei de decidir priorizar a preparação para uma prova de corrida. Salva esse novo objetivo.
Mude minha prioridade para aderência e regularidade, deixando o ganho de massa em segundo plano.
No objetivo do app, coloque melhorar meu salto no vôlei de praia.
"""),
"record_training_load": ("""
Anota que fiz supino com vinte quilos em três séries de dez.
Hoje completei a remada com trinta quilos, registra no histórico.
No agachamento eu usei quarenta quilos e consegui oito repetições.
Registra o treino concluído: leg press com oitenta quilos, doze repetições.
Coach perguntou o peso realmente usado na rosca. || Foram oito quilos em cada halter, pode anotar.
Acabei a puxada com trinta e cinco quilos; salva essa carga realizada.
""", """
Terminei agora o desenvolvimento: dois halteres de doze quilos, seis repetições por série. Lance no registro.
Meu resultado de hoje no levantamento terra foi sessenta quilos para cinco repetições.
Na ficha de execução, preenche a extensora com vinte e cinco quilos que usei hoje.
Não é uma nova meta de carga: ontem fiz a rosca martelo com dez quilos, registra o resultado.
Concluí quatro séries de remada baixa a quarenta e cinco quilos. Guarda no histórico desta sessão.
Pode lançar a panturrilha de hoje? Usei cinquenta quilos e completei quinze repetições.
"""),
"record_food_intake": ("""
Registra que almocei arroz, feijão e frango hoje.
Acabei de comer uma banana e um iogurte, anota no diário.
No café consumi dois ovos e um pão.
Lança meu jantar: macarrão com carne e salada.
Coach perguntou o que comi no lanche. || Foi uma maçã com aveia, pode registrar.
Hoje bebi um copo de leite na ceia; coloca no histórico alimentar.
""", """
Já fiz a refeição: comi uma porção de lentilha e batata. Preenche meu diário.
Quero lançar o que realmente consumi no restaurante, peixe e arroz.
No lanche da faculdade comi um sanduíche de queijo. Salva esse consumo.
Não quero trocar o cardápio, só registrar a tapioca que comi no café.
Minha ceia de ontem foi iogurte natural com pera; acrescenta ao diário de ontem.
Comi três fatias de pizza no jantar de sábado. Pode anotar sem mudar a dieta?
"""),
"record_body_measurement": ("""
Hoje me pesei e a balança marcou setenta e dois quilos. Anota.
Registra minha cintura de oitenta e quatro centímetros.
Medi o braço e deu trinta e dois centímetros, salva a medida.
Atualiza minha altura medida para um metro e setenta e cinco.
Não é peso do exercício: meu peso corporal hoje deu oitenta e um quilos.
Coach perguntou o resultado da medição do quadril. || Cento e dois centímetros, coloca no registro.
""", """
Na avaliação que fiz em casa, o tórax mediu noventa e seis centímetros. Guarda no histórico.
Minha balança mostrou sessenta e oito vírgula cinco quilos esta manhã; lance essa medição.
Quero atualizar a circunferência da coxa para cinquenta e cinco centímetros.
Deixa registrada a medida de abdômen que tirei hoje: noventa centímetros.
Acabei de medir minha altura descalço: cento e oitenta e dois centímetros.
Para o gráfico de evolução, acrescenta o peso de ontem, noventa e três quilos.
"""),
"adapt_training_plan": ("""
Adapta meu programa atual para um mês treinando só em casa.
Vou viajar e só terei elásticos, reorganiza a ficha que já uso.
Meu tempo caiu para meia hora por sessão. Ajusta o plano existente a essa disponibilidade.
Agora tenho acesso apenas à academia do prédio. Refaça a adaptação do meu treino atual.
Quero compatibilizar a rotina de musculação que uso com minhas aulas de vôlei.
Nas próximas semanas só posso treinar duas vezes. Adapta meu programa inteiro a isso.
""", """
O plano atual foi feito para academia completa; adeque ele aos halteres que tenho no apartamento.
Comecei um turno de trabalho diferente e preciso reorganizar globalmente a rotina já cadastrada.
Durante as férias não vou ter máquinas. Prepare uma adaptação da minha ficha, mantendo meu objetivo.
Preciso encaixar o treino vigente numa semana com aulas de tênis e menos tempo na academia.
Redesenhe o programa que já estou seguindo para sessões de vinte e cinco minutos.
Minha academia fechou por reforma; adapte o plano salvo para exercícios no parque.
"""),
"create_training_plan": ("""
Ainda não tenho ficha, monta um primeiro treino para mim.
Quero começar do zero com um programa de musculação três dias por semana.
Cria meu plano inicial para treinar na academia do prédio.
Nunca cadastrei um treino aqui; prepara uma rotina de corpo inteiro.
Preciso de uma primeira ficha para usar halteres em casa.
Me ajuda a montar meu programa inicial de treino, não tenho nenhum salvo.
""", """
Abri a conta agora e estou sem rotina definida. Pode elaborar um plano de exercícios inicial?
Quero gerar meu primeiro programa semanal voltado a condicionamento.
Não existe treino vigente para adaptar: preciso criar uma ficha nova desde o começo.
Estou estreando na academia e gostaria de um planejamento inicial para quatro dias.
Elabore um primeiro programa para eu usar os aparelhos disponíveis no condomínio.
Gostaria de iniciar um plano de musculação do zero, com sessões de quarenta minutos.
"""),
"create_diet_plan": ("""
Ainda não tenho dieta cadastrada, quero criar meu primeiro plano alimentar.
Monta um cardápio inicial para minha rotina, começando do zero.
Quero gerar uma primeira dieta no app, não tenho plano vigente.
Preciso de um planejamento alimentar inicial para organizar a semana.
Cria meu primeiro cardápio com café, almoço, lanche e jantar.
Nunca tive um menu salvo aqui; quero montar um para começar.
""", """
Sou novo no aplicativo e gostaria de elaborar um plano alimentar pessoal inicial.
Não é para modificar uma dieta anterior, é para construir a primeira.
Quero começar meu planejamento alimentar do zero com refeições para levar ao trabalho.
Pode preparar um cardápio semanal inicial para mim, sujeito aos dados que faltarem?
Ainda não sigo nenhuma estrutura alimentar. Gostaria de criar um plano no aplicativo.
Preciso montar minha primeira dieta com as refeições organizadas para a faculdade.
"""),
"preserve_plan_constraint": ("""
Não altere minha dieta enquanto conversamos sobre o treino.
Quero manter os exercícios atuais, sem substituições por enquanto.
Ao ajustar os horários, preserve meu almoço exatamente como está.
Não mexa no volume semanal do programa.
Deixe as cargas como estão; estou só discutindo opções.
Não registre nenhuma mudança no meu calendário ainda.
""", """
Não há prévia pendente. || Eu só quero deixar claro que o treino de sábado precisa continuar igual.
Se reorganizar o plano, a refeição em família no domingo deve permanecer intacta.
Não mude o número de sessões desta semana sem me perguntar.
Mantenha meu objetivo atual; essa conversa não é autorização para trocá-lo.
Estou satisfeito com o cardápio e não quero alterações nele agora.
Ao revisar minha ficha, preserve o tempo máximo de quarenta minutos por sessão.
"""),
"confirm_planner_action": ("""
Há proposta pendente de substituir o lanche, ainda não aplicada. || Sim, quero ver a prévia dessa troca.
Coach mostrou uma proposta pendente de mudança de dia. || Confirmo essa proposta que você acabou de mostrar.
Existe proposta identificada de substituir a remada. || Pode prosseguir com a proposta da remada.
Prévia pendente para definir descanso hoje. || Li o que muda e concordo com esse ajuste.
Coach aguarda confirmação da proposta de alterar o jantar. || Tá aprovado, segue com essa alteração.
Há uma única proposta pendente na conversa. || Pode confirmar essa, sim.
""", """
Uma proposta de mudar a atividade de amanhã está pendente. || De acordo com o que você propôs para amanhã.
Coach apresentou substituição de alimento e pediu decisão. || Essa opção me atende, autorizo continuar com a proposta.
Está pendente somente a proposta de reagendar uma sessão. || Fechado, pode levar esse reagendamento adiante.
Há prévia de ajuste mostrada, aguardando aceite. || Revisei os detalhes e quero confirmar o ajuste apresentado.
Proposta identificada: trocar um exercício, sem execução. || Aceito a troca proposta; pode seguir para a próxima etapa.
Coach perguntou se desejo confirmar a proposta exibida. || Isso, confirmada por mim.
"""),
"reject_planner_action": ("""
Há proposta pendente para mudar o café da manhã. || Não aceito essa troca, cancela a proposta.
Coach propôs substituir o supino e aguarda decisão. || Rejeito esse ajuste, deixa o supino atual.
Existe proposta pendente de descanso para amanhã. || Não quero mais essa proposta de descanso.
Coach perguntou sobre uma alteração ainda não aplicada. || Melhor não, descarta o que você propôs.
Há prévia de mudança de treino na conversa. || Pode cancelar essa prévia; vou seguir a programação atual.
Uma proposta alimentar está aguardando resposta. || Não aprovo essa opção.
""", """
O Coach sugeriu uma substituição de jantar, ainda pendente. || Essa substituição não me serve, recuso a proposta.
Existe uma única proposta de remarcação em aberto. || Retira essa proposta, prefiro não fazer a mudança.
Prévia mostrada: reduzir o treino, não aplicado. || Pode encerrar essa prévia sem alterar nada.
Coach aguarda aceite da troca do lanche. || Não vou aceitar o lanche que você sugeriu.
Proposta de atividade mista está pendente. || Rejeita a atividade mista proposta, vou manter como estava.
Coach pediu decisão sobre a prévia apresentada. || Minha decisão é não confirmar essa proposta.
"""),
"defer_planner_action": ("""
Há proposta pendente para mudar o treino. || Quero pensar mais antes de decidir, não confirma nem cancela.
Coach aguarda decisão sobre a troca do almoço. || Deixa essa proposta para eu avaliar depois.
Prévia pendente foi apresentada. || Não decidi ainda, podemos voltar nela mais tarde?
Há proposta de exercício aguardando aceite. || Preciso consultar minha agenda primeiro, aguarda minha decisão.
Coach perguntou se aceita a proposta. || Agora não vou decidir sobre isso.
Existe proposta pendente nesta conversa. || Segura essa decisão até eu olhar com calma.
""", """
O ajuste do calendário foi proposto, sem aplicação. || Só posso avaliar a proposta depois da reunião, não encerre por minha decisão agora.
Coach exibiu uma alternativa para o jantar. || Ainda estou em dúvida entre as opções, vamos deixar para depois.
Prévia aguardando confirmação do usuário. || Não estou recusando; preciso de mais tempo para responder.
Há proposta identificada de trocar um alimento. || Retomamos essa proposta à noite? Não quero decidir já.
Coach pediu autorização para prosseguir com o ajuste. || Vou pensar e te dar uma resposta depois, sem autorizar por enquanto.
Uma alteração foi proposta e continua pendente. || Adia minha decisão sobre essa alteração.
"""),
"undo_planner_action": ("""
A troca de lanche foi aplicada há pouco. || Desfaz essa última troca e volta ao lanche anterior.
O treino foi movido para sábado e consta como aplicado. || Quero reverter a remarcação já feita.
A mudança para descanso foi aplicada no calendário. || Volta a atividade para o estado anterior a esse ajuste.
Foi aplicado um ajuste reversível de exercício. || Desfaz a substituição que eu confirmei.
O histórico mostra troca de jantar aplicada. || Restaura o jantar anterior à troca.
A última alteração do plano foi concluída. || Cancela o efeito da última alteração, quero desfazer.
""", """
O exercício já foi substituído e há registro reversível. || Me arrependi da substituição concluída, reverte para o exercício antigo.
Uma mudança de dia foi aplicada e está no histórico. || Quero retornar ao dia que estava agendado antes daquela mudança.
O calendário recebeu uma alteração reversível esta manhã. || Restaure o estado que havia antes da alteração de hoje.
O ajuste alimentar foi aplicado com sucesso. || Agora quero desfazer o ajuste alimentar aplicado.
Há mudança aplicada, não apenas uma proposta. || Pode reverter aquela mudança que já entrou no plano?
O treino teve uma troca confirmada e executada. || Recupera a versão anterior à troca executada, por favor.
"""),
"clarification": ("""
Coach perguntou em qual dia quero treinar. Não existe proposta. || Na quarta-feira.
Coach pediu o nome do alimento sobre o qual perguntei. || Era a mandioca, escrevi errado.
Coach perguntou quantos dias tenho disponíveis. || Consigo ir três vezes na semana.
Coach perguntou qual equipamento existe em casa. || Só halteres e um colchonete.
Coach pediu que eu completasse a quantidade mencionada. || Duzentos gramas, não vinte.
Coach perguntou a que exercício eu me referia, sem proposta. || A puxada neutra do treino B.
""", """
Coach perguntou em qual refeição há o item citado. || Estou falando da ceia, não do almoço.
Coach solicitou esclarecer se era carga ou peso corporal. || Peso do meu corpo mesmo.
Coach perguntou a duração disponível para planejar, sem alterar nada. || Tenho uns trinta e cinco minutos.
Coach perguntou o horário habitual do treino. || Normalmente saio da aula e treino às oito da noite.
Coach pediu o nome exato do movimento para entender a pergunta. || É a elevação lateral na polia.
Coach perguntou se falei da semana atual ou da próxima. || Da semana seguinte.
"""),
"greeting": ("""
Oi, Coach, bom dia!
E aí, tudo certo por aqui?
Boa noite, cheguei agora.
Olá, prazer em conhecer o assistente.
Opa, voltei pra conversar.
Bom dia pra gente, Coach.
""", """
Fala aí, como vai?
Passando para dar um oi.
Boa tarde, pessoal do Evolv!
Oie, tô de volta por aqui.
Salve, Coach, beleza?
Oi de novo, tudo bem contigo?
"""),
}

# Contrastive educational requests: no authorization to edit a saved plan.
CONTRAST = {
"ask_training_concept": ("""
Diminuir uma série é a mesma coisa que baixar a carga? Só quero entender.
Qual a diferença entre trocar um dia de treino e mudar a divisão semanal?
O que muda entre treinar corpo inteiro e separar superiores e inferiores?
""", """
Pode explicar volume e intensidade sem modificar minha ficha?
Se uma pessoa aumenta o descanso entre séries, o que isso significa no treino?
Mudar de ABC para AB altera o quê, em termos gerais? Não estou pedindo uma mudança no meu plano.
"""),
"ask_food_substitution_options": ("""
Quais alimentos podem substituir o feijão em termos gerais?
Me dá opções equivalentes ao pão, sem editar meu café cadastrado.
Que alternativas uma pessoa costuma ter no lugar de leite?
""", """
Quero conhecer possibilidades de substituição do arroz, não escolher uma para o plano ainda.
Quais alternativas de fruta fariam sentido no lugar da pera, só como informação?
Se faltar iogurte no mercado, que tipos de substituição podem ser considerados?
"""),
"ask_app_functionality": ("""
Onde fica o botão de confirmar uma prévia no aplicativo?
O app permite desfazer uma mudança já aplicada?
Como vejo o histórico das alterações, sem executar nenhuma?
""", """
Para que serve a etapa de prévia antes de mudar o treino?
Se eu fechar a tela, a proposta é confirmada automaticamente?
O que significa o aviso de que uma proposta expirou?
"""),
}

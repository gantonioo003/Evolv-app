# Evolv - Produto e Telas do MVP

## Objetivo desta fase

Fechar o comportamento do produto e a estrutura das telas antes de iniciar banco de dados, app mobile e backend.

## Tese do produto

O Evolv organiza a rotina real de treino e dieta sem bagunçar o plano.

O app deve manter um plano de longo prazo, entregar a rotina semanal e ajustar apenas quando houver motivo ou pedido do usuário.

## Regras de produto

- O plano continua estável por padrão.
- O usuário não precisa justificar quando não seguir o plano.
- O app não deve cobrar confirmação diária.
- Ajustes acontecem via Coach Evolv.
- O Coach Evolv também deve servir para dúvidas, explicações, aprendizado e consulta de conhecimento.
- Memória de conversas deve ser opcional e controlável pelo usuário.
- O Coach interpreta o pedido.
- O Coach pede esclarecimento quando não entende o pedido com confiança.
- Respostas educativas devem usar a base local de conhecimento sempre que possível.
- O Planner aplica regras e reorganiza apenas o necessário.
- Treino, dieta e rotina compartilham o mesmo contexto.
- Registro de carga, peso, medidas, alimentação e fotos deve ser opcional.
- Treino, dieta, Coach, lembretes e registro de cargas devem funcionar de forma independente.
- O app não pergunta para qual finalidade o usuário pretende utilizá-lo.
- Todas as áreas ficam disponíveis desde o início.
- O app não classifica o usuário nem tenta deduzir um modo de uso.
- O onboarding é completo, mas permite pular etapas e campos opcionais.
- Informações puladas podem ser adicionadas depois nas configurações do perfil.
- Fase nutricional, divisão de treino, recuperação e motivação devem formar um contexto único quando o usuário decidir registrar esses dados.
- O app pode identificar sinais de progressão estagnada, mas não diagnostica a causa nem muda o plano sem confirmação.
- O app fica atento em silêncio: reúne contexto sem transformar cada padrão em alerta ou notificação.
- Sugestões proativas devem ser raras, explicáveis, adiáveis e controladas pelo usuário.

## Abas principais

### Hoje

Função: painel simples do dia.

Conteúdo:

- treino previsto;
- refeições principais;
- lembrete relevante;
- resumo rápido da semana;
- nota do plano;
- acesso ao Coach pela navegação inferior.

Não deve ter:

- botão obrigatório para começar treino;
- botão obrigatório para informar falta;
- cobrança para registrar tudo.

### Treino

Função: detalhar a rotina de treino.

Conteúdo:

- calendário semanal;
- plano ativo;
- treino do dia;
- exercícios;
- séries;
- repetições;
- descanso;
- carga opcional;
- progressão sugerida;
- histórico de cargas por exercício;
- edição rápida da carga depois de cada treino;
- biblioteca completa de exercícios com busca e filtros;
- troca manual de qualquer exercício por alternativas compatíveis;
- observação da semana.

Comportamento:

- ajustes de agenda, dor, foco muscular ou falta de tempo devem ir pelo Coach;
- o treino não muda inteiro sem necessidade.
- registrar carga não exige registrar o treino inteiro;
- a sugestão de aumento deve mostrar carga atual, carga sugerida, quando tentar e um motivo curto;
- o usuário decide aceitar, ignorar ou adiar uma sugestão.
- ignorar ou dispensar uma sugestão impede que o mesmo aviso seja repetido constantemente;
- preferências de modalidade e equipamento ajudam o Planner, mas não escondem exercícios da biblioteca;
- o usuário pode combinar máquinas, pesos livres, cabos, calistenia, treino de força, potência e outras abordagens;
- todas as preferências podem ser alteradas depois em Conta.
- o plano aceita Full body, Upper/Lower, Push/Pull/Legs, divisão por grupos musculares, estruturas híbridas e divisões personalizadas;
- ABC, ABCD e ABCDE funcionam como nomes de agenda; os músculos e exercícios de cada dia são a estrutura real armazenada;
- dificuldade de progressão só pode ser sinalizada quando existirem registros opcionais suficientes e comparáveis;
- fase de ganho de massa, perda de gordura, manutenção ou recomposição deve ser considerada antes de sugerir mudanças.

### Coach

Função: conversa única para treino, dieta e rotina.

Conteúdo:

- contexto atual;
- conversa com o usuário;
- resposta explicando o ajuste;
- respostas para dúvidas de treino, dieta, rotina e conceitos gerais;
- explicações educativas sobre o plano;
- memória opcional de preferências, dúvidas recorrentes e ajustes anteriores;
- atalhos de intenção;
- campo de mensagem.

Comportamento:

- se aberto em Hoje, entende o dia atual;
- se aberto em Treino, prioriza treino;
- se aberto em Dieta, prioriza alimentação;
- continua sendo a mesma IA e o mesmo histórico.
- não deve ser usado apenas para ajustes;
- deve funcionar também como fonte de aprendizado dentro do app;
- deve informar quando não possui conhecimento suficiente para responder;
- não pode alterar treino, dieta ou agenda sem validação do backend e do Planner.

### Arquitetura local do Coach

- Não haverá dependência de OpenAI, Gemini ou outra API paga de modelo de linguagem.
- NLP é a área usada para interpretar e gerar linguagem no Coach.
- A primeira referência será um classificador simples com TF-IDF e regressão logística.
- A base de conhecimento local será consultada por busca textual antes da geração da resposta.
- O LM principal será pequeno, usará Transformer decoder-only e terá pesos treinados do zero para o domínio do Evolv.
- O Coach poderá gerar uma resposta educativa ou propor uma ação estruturada.
- O Planner continua determinístico e decide se uma ação pode ser aplicada.
- Pedidos com baixa confiança resultam em pergunta de esclarecimento, não em alteração automática.
- O tamanho do modelo será definido depois de medir o hardware disponível.
- O objetivo é aprendizado técnico e uma solução útil e limitada, não competir com assistentes comerciais.

### Dieta

Função: mostrar alimentação simples e adaptável.

Conteúdo:

- meta aproximada de calorias;
- metas de proteína, carboidrato e gordura;
- calorias e macros consumidos e restantes no dia;
- refeições do dia;
- alimentos principais da semana;
- busca de alimentos, produtos e porções;
- prévia imediata de como uma adição, remoção ou troca altera calorias e macros;
- gasto calórico estimado separado do consumo;
- regra de substituição pelo Coach.
- fase nutricional atual e duração, quando o usuário quiser acompanhar isso.

Comportamento:

- dieta do MVP deve priorizar aderência;
- substituições não devem refazer todo o plano;
- cálculo avançado de macros fica para depois.
- registro alimentar continua opcional;
- valores vindos de usuários ou fontes colaborativas devem mostrar sua origem e qualidade;
- gasto calórico deve aparecer como estimativa, nunca como valor exato.
- o app pode sugerir uma revisão quando uma fase de perda ou ganho estiver longa ou afetando aderência e desempenho, mas nunca troca a fase sozinho.

### Conta

Função: central de perfil e configurações.

Conteúdo:

- perfil do usuário;
- plano atual;
- objetivo;
- notificações;
- objetivo e rotina;
- restrições;
- preferências alimentares;
- progresso e histórico;
- privacidade e dados;
- memória do Coach e preferências de conversa;
- controle de sugestões proativas, assuntos silenciados e frequência de avisos;
- integrações futuras;
- suporte e feedback.
- check-ins opcionais de motivação, energia, sono e recuperação.

Decisão:

- progresso fica dentro de Conta no MVP;
- não vira aba principal agora.

## Telas auxiliares

### Login

Entradas previstas:

- Google;
- Apple;
- e-mail e senha.

### Onboarding

O onboarding apresenta a configuração completa do Evolv para todos, mas não obriga o preenchimento de tudo. Etapas e campos opcionais podem ser pulados sem bloquear o acesso ao app.

Exemplos de dados possíveis:

- idade;
- altura;
- peso;
- objetivo;
- nível de treino;
- dias disponíveis;
- restrições;
- alimentos que não gosta;
- horário preferido de treino.
- modalidades e equipamentos preferidos, com seleção múltipla e opção de pular.

Regras:

- nenhum usuário precisa preencher o cadastro completo para entrar no app;
- o app não exige que o usuário declare como pretende usá-lo;
- qualquer área pode ser usada separadamente desde o início;
- o app não tenta classificar o usuário pelo comportamento;
- somente dados realmente obrigatórios para criar a conta devem impedir o avanço;
- cada etapa deve ter uma ação clara para pular quando seus dados forem opcionais;
- todos os dados pulados podem ser preenchidos ou editados depois em Conta > Perfil e preferências;
- o onboarding pode ser reaberto pela Conta para quem quiser concluir a configuração guiada.
- preferências escolhidas no onboarding orientam sugestões, mas não limitam o catálogo nem bloqueiam trocas manuais.

## Direção visual

- Cinematográfica.
- Old school bodybuilding.
- Premium, com sensação próxima de Apple TV.
- Fundo escuro.
- Cards grandes.
- Pouca informação por tela.
- Vermelho queimado, off-white, preto e amarelo antigo.
- Navegação simples.
- Telas com rolagem vertical quando houver mais conteúdo.

## Critério para encerrar a fase

Esta fase pode ser considerada encerrada quando:

- as abas principais estiverem definidas;
- o comportamento de cada tela estiver descrito;
- o papel do Coach Evolv estiver fechado;
- o papel do Planner estiver fechado;
- progresso estiver decidido dentro de Conta;
- o mockup visual estiver navegável e com rolagem;
- o próximo passo for modelar o banco de dados.

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
- O Coach interpreta o pedido.
- O Planner aplica regras e reorganiza apenas o necessário.
- Treino, dieta e rotina compartilham o mesmo contexto.
- Registro de carga, peso, medidas, alimentação e fotos deve ser opcional.

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
- observação da semana.

Comportamento:

- ajustes de agenda, dor, foco muscular ou falta de tempo devem ir pelo Coach;
- o treino não muda inteiro sem necessidade.

### Coach

Função: conversa única para treino, dieta e rotina.

Conteúdo:

- contexto atual;
- conversa com o usuário;
- resposta explicando o ajuste;
- atalhos de intenção;
- campo de mensagem.

Comportamento:

- se aberto em Hoje, entende o dia atual;
- se aberto em Treino, prioriza treino;
- se aberto em Dieta, prioriza alimentação;
- continua sendo a mesma IA e o mesmo histórico.

### Dieta

Função: mostrar alimentação simples e adaptável.

Conteúdo:

- meta aproximada de calorias;
- meta de proteína;
- refeições do dia;
- alimentos principais da semana;
- regra de substituição pelo Coach.

Comportamento:

- dieta do MVP deve priorizar aderência;
- substituições não devem refazer todo o plano;
- cálculo avançado de macros fica para depois.

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
- integrações futuras;
- suporte e feedback.

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

Perguntas mínimas:

- idade;
- altura;
- peso;
- objetivo;
- nível de treino;
- dias disponíveis;
- restrições;
- alimentos que não gosta;
- horário preferido de treino.

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


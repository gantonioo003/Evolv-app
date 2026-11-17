# Evolv · 9.01 · Bateria de conversas

Versão 1.0.0, em português brasileiro. Cada caso traz uma conversa inteira,
as condições da conta e o que o Coach precisa fazer em cada turno. Os critérios
foram escritos antes da primeira execução desta bateria.

| Conjunto | Conversas | Mensagens da pessoa | Eventos do app | Conversas com 10+ mensagens |
| --- | ---: | ---: | ---: | ---: |
| Ajuste | 14 | 59 | 2 | 2 |
| Verificação | 14 | 79 | 5 | 3 |
| Total | 28 | 138 | 7 | 5 |

A conversa mais longa tem 21 mensagens da pessoa, com 17 turnos de papo e
relatos antes da primeira dúvida de treino. A bateria também cobre deload,
estagnação, remada cavalinho no treino de hoje, hidratação em vários turnos,
análise do treino executado, dieta, correções, mudanças de assunto, retomada,
consulta versus pedido, isolamento de sessões, alergia e sinais de risco.

## O que veio de conversas reais

- **Evolv no iPhone.** Três regressões reescritas a partir dos casos relatados
  pelo usuário, com abreviações e encadeamento preservados. A hidratação usa
  medidas e frequência fictícias. Os casos conhecidos ficam no ajuste.
- **WildChat.** Consultei amostras dos registros reais pessoa–ChatGPT. Em
  português, a amostra incluía uma conversa com oito mensagens da pessoa e três
  retornos curtos. A amostra multilíngue incluía conversas de assuntos variados
  com 12 a 22 mensagens da pessoa. Usei o padrão de respostas curtas,
  reformulação e retomada como referência para escrever diálogos do Evolv.
  [Base](https://huggingface.co/datasets/allenai/WildChat-1M) ·
  [Artigo](https://arxiv.org/abs/2405.01470)
- **You tell me.** Conferi o artigo e o CSV de turnos do estudo de interação
  humana com GPT-4. O material inclui 185 conversas sobre mudança de hábitos,
  entre eles alimentação. A estrutura de ouvir um relato, entender barreiras
  e negociar o próximo passo inspirou o caso de rotina na cozinha.
  [Artigo](https://arxiv.org/abs/2401.16167) · [Dados](https://osf.io/c9nvm/)
- **Treino na internet.** Consultei relatos de uso do ChatGPT para analisar
  treinos executados e revisar planos depois de acrescentar contexto. Os links
  de chat compartilhado pesquisados não renderam a transcrição no ambiente.
  Usei o fluxo descrito pelos autores como referência para o caso de corrida.
  [Demonstração Tredict](https://www.tredict.com/blog/tredict_chatgpt_app/) ·
  [Relato de treino](https://www.reddit.com/r/indianrunners/comments/1r2myhn/chatgpt_use_for_training/)
- **LMSYS-Chat-1M.** Alternativa de conversas reais com vários modelos. Os
  arquivos exigem aceite de termos. Nesta versão, a consulta ficou na
  documentação pública. [Base](https://huggingface.co/datasets/lmsys/lmsys-chat-1m)

Os JSONs guardam mensagens escritas para o teste, incluindo reconstituições
anonimizadas dos casos do Evolv. As referências externas contribuíram com
padrões de diálogo. Nenhuma transcrição pública, identificador de pessoa,
resposta de outro LLM ou link pessoal foi incorporado aos casos.

## Arquivos

- **ajuste.json** reúne regressões conhecidas e casos de desenvolvimento.
- **verificacao.json** reúne situações novas e autorais, reservadas para medir
  o resultado após os ajustes. O conjunto é um teste interno do produto.
- **fixtures.json** descreve contas e planos fictícios. Use uma conta nova por
  caso, data de referência fixa e memória entre conversas desligada.
- **manifest.json** registra origem, contagens e SHA-256 dos três arquivos.

## Como usar na 9.02

1. Valide o pacote com `python ai/scripts/validate_coach_quality_suite.py`
   a partir da raiz do projeto, usando o Python do ambiente do Evolv.
2. Crie a conta fictícia de cada caso, com os itens e alternativas indicados
   na fixture. Use os IDs gerados pelo backend. Os nomes em `from` e `to`
   identificam os itens esperados para comparar com os IDs retornados. O
   prefixo antes de `:` identifica a refeição quando o nome do alimento se repete.
3. Rode o conjunto de ajuste primeiro, em ordem. Envie cada texto para a mesma
   sessão autenticada e deixe as respostas reais do Coach entrarem no histórico.
   `new_session` abre outra conversa na mesma conta, `reopen_session` reabre
   a original e `inspect_plan` confere o estado persistido. Se uma falha
   impedir um evento dependente, registre o primeiro erro e o bloqueio.
4. Compare cada turno com `expect`. `behavior` é o efeito observável,
   `must` é o critério de conteúdo e `avoid` marca um erro específico.
   Quando houver `source_topic`, confira se o catálogo ou trecho citado
   sustenta a resposta. Julgue o sentido da resposta, aceitando paráfrases.
5. Confira o Planner pelo tipo de ação, pelos alvos e pelo estado antes e
   depois. `propose` exige proposta pendente, `preview` exige prévia sem
   aplicar e `reject` encerra a proposta sem alterar o plano. Só os eventos
   explícitos `apply_preview` e `undo_application` podem mudar o plano.
   `plan_write` trata do plano, não da persistência das mensagens.
6. Classifique a causa inicial como intenção, contexto, busca, geração,
   segurança ou Planner. Reserve o conjunto de verificação para depois de
   fixar a versão candidata. Caso seus erros sejam usados para novos ajustes,
   prepare outro conjunto reservado para medir a próxima versão.

Esta fase valida a estrutura e congela a bateria. A execução do Coach e a
medição dos resultados pertencem à 9.02.

# Evolv - Base do Projeto

## Objetivo desta fase

Organizar o repositório, consolidar a documentação inicial e deixar o projeto pronto para começar a modelagem do banco de dados e a implementação.

## Status

Fase concluída.

## Entregas concluídas

- Repositório `Evolv-app` criado.
- README principal estruturado.
- Pasta `docs` criada.
- Documentos iniciais adicionados ao repositório.
- Escopo do MVP definido.
- Fluxo do usuário definido.
- Conceito visual inicial criado.
- Direção visual definida: old school, cinematográfica e premium.
- Decisões principais registradas.

## Estrutura esperada do repositório

```txt
evolv-app/
  docs/
    01-base-do-projeto.md
    02-produto-e-telas.md
    documentos, PDFs, imagens e conceitos visuais
  mobile/
    app React Native / Expo
  backend/
    API NestJS
  ml/
    NLP, recuperação de conhecimento, treinamento, avaliação e serviço local do Coach
  README.md
```

## Decisões já fechadas

- O app será mobile primeiro.
- O MVP terá cinco abas principais: Hoje, Treino, Coach, Dieta e Conta.
- Progresso não será aba principal no MVP.
- Progresso ficará dentro de Conta.
- A tela Hoje será informativa, sem cobrança diária.
- Não haverá botão obrigatório de "começar treino" ou "não vou treinar hoje".
- O usuário só ajusta algo se quiser conversar com o Coach.
- Treino, dieta, Coach, lembretes e registro de cargas poderao ser usados separadamente, sem escolher um modo de uso.
- O onboarding apresentara a configuracao completa do Evolv para todos, com etapas e campos opcionais que podem ser pulados.
- O app nao classificara nem tentara adivinhar como cada pessoa pretende usa-lo.
- Dados pulados poderao ser preenchidos ou alterados depois nas configuracoes do perfil.
- O usuario podera salvar e editar cargas por exercicio sem precisar registrar um treino completo.
- Sugestoes de progressao mostrarao quando tentar aumentar, a carga sugerida e um motivo simples.
- O app terá uma IA única: Coach Evolv.
- O Coach Evolv também servirá para tirar dúvidas, ensinar conceitos e explicar treino, dieta e decisões do plano.
- O Coach poderá ter memória opcional de conversas, preferências e dúvidas recorrentes, respeitando privacidade e controle do usuário.
- O Planner será regra de backend, não uma segunda IA.
- O Coach será desenvolvido localmente, sem depender de API paga de modelo de linguagem.
- A área técnica do Coach será NLP, combinando classificação de intenção, recuperação de conhecimento e um LM pequeno.
- O LM usará uma arquitetura Transformer decoder-only e será treinado do zero com foco limitado no domínio do Evolv.
- O modelo propõe respostas e ações; NestJS e Planner validam qualquer alteração antes de gravar no banco.
- A stack planejada será Expo, NestJS, Supabase/PostgreSQL, Python, FastAPI, PyTorch e scikit-learn.

## Pendências curtas

- Criar `backend/` quando a API NestJS começar.
- Criar `ml/` quando a implementação do Coach local começar.
- Criar o board de tarefas no GitHub se for usar gestão visual.

## Critério para encerrar a fase

Esta fase pode ser considerada encerrada quando:

- o README estiver atualizado;
- a pasta `docs` estiver versionada;
- os documentos principais estiverem no GitHub;
- o próximo passo estiver claro: criar a base do aplicativo mobile.

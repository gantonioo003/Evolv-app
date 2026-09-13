# Evolv - Base do Projeto

## Objetivo desta fase

Organizar o repositório, consolidar a documentação inicial e deixar o projeto pronto para começar a modelagem do banco de dados e a implementação.

## Status

Fase praticamente concluída.

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
- O app terá uma IA única: Coach Evolv.
- O Planner será regra de backend, não uma segunda IA.
- A stack planejada será Expo, NestJS, Supabase/PostgreSQL e OpenAI API ou Gemini API.

## Pendências curtas

- Confirmar `git push` do commit inicial.
- Criar `mobile/` quando o app Expo começar.
- Criar `backend/` quando a API NestJS começar.
- Criar o board de tarefas no GitHub se for usar gestão visual.

## Critério para encerrar a fase

Esta fase pode ser considerada encerrada quando:

- o README estiver atualizado;
- a pasta `docs` estiver versionada;
- os documentos principais estiverem no GitHub;
- o próximo passo estiver claro: modelar o banco de dados do MVP.


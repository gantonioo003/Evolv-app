# Evolv - Banco de Dados do MVP

## Status

Fase concluida em 19 de setembro de 2026.

## Objetivo desta fase

Modelar o banco inicial do Evolv de forma organizada, versionada e pronta para ser usada pelo backend, mobile e Supabase.

## Decisao principal

O banco sera modelado no VS Code usando migrations SQL.

Isso significa:

- o desenho das tabelas fica salvo no repositorio;
- o GitHub guarda o historico das mudancas;
- o Supabase/PostgreSQL cria as tabelas reais a partir desses arquivos;
- o projeto fica mais profissional e facil de manter.

## Onde cada coisa fica

```txt
VS Code
  cria e guarda as migrations

Supabase/PostgreSQL
  executa as migrations e guarda os dados reais

Backend NestJS
  usa o banco para cadastrar, buscar, editar e organizar os dados

Mobile Expo
  mostra os dados para o usuario
```

## Arquivos criados

```txt
supabase/
  README.md
  database.types.ts
  seed.sql
  migrations/
    202609150001_initial_schema.sql
    202609190001_expand_nutrition_and_exercises.sql
    202609190002_grant_authenticated_permissions.sql
    202609190003_enforce_owned_references.sql
    202609190004_fix_owned_reference_trigger.sql
  tests/
    phase_3_database.sql

docs/
  03-banco-de-dados.md
```

## Tabelas principais

### profiles

Guarda o perfil do usuario.

Exemplos:

- nome;
- altura;
- peso atual;
- nivel de treino;
- dias disponiveis;
- alimentos que nao gosta;
- restricoes;
- limitacoes;
- preferencia de memoria do Coach.

### goals

Guarda o objetivo atual ou historico de objetivos.

Exemplos:

- hipertrofia;
- perder gordura;
- recomposicao corporal;
- forca;
- saude;
- manutencao.

### exercises

Guarda o catalogo de exercicios usado nos treinos.

Exemplos:

- supino;
- remada;
- agachamento;
- puxada;
- elevacao lateral.

O catalogo deve conter exercicios com maquinas, pesos livres, cabos, peso corporal, calistenia, potencia e treino funcional. As preferencias do usuario influenciam o Planner, mas nao removem exercicios da busca.

### equipment e muscle_groups

Guardam os equipamentos e grupos musculares de forma organizada. Isso permite buscar, filtrar e encontrar substituicoes compativeis.

### exercise_equipment e exercise_muscles

Ligam cada exercicio aos equipamentos e musculos envolvidos.

### training_styles e exercise_training_styles

Ligam exercicios a um ou mais estilos, como hipertrofia, forca, calistenia, potencia e resistencia. Um mesmo exercicio pode servir para varios estilos.

### exercise_substitutions

Guarda alternativas compativeis para troca manual ou sugestao do Planner. Exercicios tambem podem apontar para um exercicio principal para representar variacoes.

### training_preferences

Guarda preferencias opcionais de modalidades e equipamentos. Aceita combinacoes, pode ser pulada no onboarding e alterada depois.

### user_available_equipment

Guarda quais equipamentos existem na academia ou no local de treino do usuario. Nao limita a biblioteca completa; serve apenas para o Planner sugerir opcoes praticas.

### workout_plans

Guarda o plano de treino de longo prazo.

Exemplos:

- plano atual;
- data de inicio;
- frequencia semanal;
- objetivo ligado ao plano.

### workout_days

Guarda cada dia da semana dentro do plano de treino.

Exemplos:

- segunda: peito e triceps;
- terca: pernas;
- quarta: costas e biceps.

### workout_day_exercises

Guarda os exercicios de cada dia de treino.

Exemplos:

- exercicio;
- ordem;
- series;
- repeticoes;
- descanso;
- carga alvo opcional.

### workout_logs

Guarda registros opcionais de treino.

Importante: o usuario nao sera obrigado a registrar tudo.

### exercise_logs

Guarda registros opcionais por exercicio.

Exemplos:

- carga usada;
- series feitas;
- observacoes.

O registro pode estar ligado a um treino completo ou ser salvo sozinho. Assim, o usuario pode usar o Evolv apenas como historico de cargas.

### exercise_progression_suggestions

Guarda sugestoes simples de progressao.

Exemplos:

- carga atual;
- proxima carga sugerida;
- data recomendada para tentar;
- motivo da sugestao;
- sugestao aceita ou ignorada.

### diet_plans

Guarda o plano alimentar.

Exemplos:

- meta aproximada de calorias;
- meta aproximada de proteina;
- metas de carboidrato, gordura e fibra;
- observacoes do plano.

### foods

Guarda alimentos genericos, produtos, receitas e alimentos personalizados.

Dados principais por 100 g ou 100 ml:

- calorias;
- proteina;
- carboidrato;
- gordura;
- fibra;
- acucares;
- gordura saturada;
- sodio;
- marca e codigo de barras, quando existirem;
- fonte e identificador externo.

### nutrients e food_nutrients

Guardam nutrientes adicionais sem obrigar a criar uma coluna nova para cada vitamina ou mineral.

Exemplos:

- calcio;
- ferro;
- potassio;
- magnesio;
- colesterol;
- vitaminas.

### food_portions

Converte medidas comuns para gramas.

Exemplos:

- uma colher;
- uma xicara;
- uma unidade;
- uma fatia;
- uma porcao da embalagem.

### meals

Guarda as refeicoes do plano.

Exemplos:

- cafe da manha;
- almoco;
- lanche;
- jantar.

### meal_items

Guarda os alimentos de cada refeicao.

Exemplos:

- arroz;
- frango;
- ovos;
- banana;
- aveia.

### food_logs

Guarda registros opcionais do que o usuario comeu.

Importante: isso serve para ajuste quando o usuario quiser, nao como obrigacao diaria.

### food_log_items

Guarda cada alimento consumido e uma copia dos valores nutricionais usados naquele momento. Assim, o historico nao muda se a fonte externa corrigir o alimento depois.

O backend podera somar os itens e mostrar por refeicao ou por dia:

- calorias consumidas e restantes;
- proteina, carboidrato e gordura;
- fibras e outros nutrientes;
- efeito de adicionar, remover ou trocar um alimento.

### energy_expenditure_logs

Guarda estimativas opcionais de gasto calorico basal, treino, passos, dispositivos ou lancamento manual. O app deve identificar claramente que gasto calorico e uma estimativa.

### coach_conversations

Guarda conversas com o Coach Evolv.

O Coach pode ser aberto por Hoje, Treino, Dieta, Conta ou contexto geral.

### coach_messages

Guarda as mensagens das conversas.

Exemplos:

- mensagem do usuario;
- resposta do Coach;
- metadados tecnicos.

### coach_memory_items

Guarda memoria opcional do Coach.

So deve ser usada se o usuario permitir.

Exemplos:

- preferencias;
- limitacoes;
- duvidas recorrentes;
- ajustes anteriores;
- rotina.

### planner_adjustments

Guarda ajustes que o Planner fez ou precisa fazer.

Exemplos:

- mover treino de costas para amanha;
- adaptar dieta porque o usuario nao tem certo alimento;
- reduzir volume por dor ou falta de tempo.

### progress_entries

Guarda progresso opcional.

Exemplos:

- peso;
- cintura;
- peito;
- braco;
- perna;
- observacoes.

### progress_photos

Guarda o caminho das fotos de progresso.

As fotos em si devem ficar no storage do Supabase. O banco guarda apenas o caminho.

## Seguranca

A migration inicial ativa RLS, que significa Row Level Security.

Em termos simples:

> cada usuario so pode ver e mexer nos proprios dados.

Isso e essencial porque o app tera dados pessoais, treino, dieta, progresso e conversas.

Como a exposicao automatica de tabelas foi desativada no Supabase, a migration `202609190002_grant_authenticated_permissions.sql` concede acesso basico somente ao papel `authenticated`. As politicas RLS continuam decidindo quais registros cada usuario pode ler ou alterar. O papel anonimo nao recebe acesso as tabelas do MVP.

As migrations de integridade de propriedade tambem impedem que um registro de um usuario aponte para dados privados de outro usuario. Por exemplo, uma mensagem nao pode ser colocada na conversa de outra pessoa e uma foto nao pode ser ligada ao progresso de outro usuario.

## O que ficou pronto nesta fase

- Estrutura `supabase/` criada.
- Migration inicial criada.
- Seed inicial de exercicios criado.
- Tabelas principais modeladas.
- Relacoes principais criadas.
- Campos essenciais criados.
- Tipos do banco definidos.
- Indices criados para consultas importantes.
- RLS ativado.
- Politicas basicas de acesso por usuario criadas.
- Documentacao do banco criada.
- Projeto Supabase criado e ligado ao repositorio local.
- Cinco migrations aplicadas no banco remoto.
- Seed aplicado com 119 exercicios, 38 equipamentos, 22 grupos musculares, 6 estilos de treino e 17 nutrientes.
- CRUD testado para perfil, objetivo, treino, carga, dieta, Coach e progresso.
- Isolamento entre dois usuarios testado com RLS.
- Referencias privadas entre usuarios bloqueadas e testadas.
- Schema validado com o linter do Supabase sem erros.
- Tipos TypeScript gerados em `supabase/database.types.ts`.

## Validacao executada

O arquivo `supabase/tests/phase_3_database.sql` executa um teste transacional completo.

Ele:

- cria dados temporarios para dois usuarios de teste;
- testa criacao, leitura, atualizacao e exclusao;
- testa treino, carga, dieta, Coach e progresso;
- confirma que um usuario nao ve dados do outro;
- confirma que referencias privadas entre usuarios sao bloqueadas;
- executa `rollback` no final para nao deixar registros de teste no banco.

Resultado final: `PASS`.

O comando `supabase db lint --linked --level warning` tambem foi executado e retornou `No schema errors found`.

## O que pertence as proximas fases

- Criar o app Expo.
- Criar o backend NestJS.
- Conectar app e backend ao Supabase.
- Criar endpoints e regras do Planner.
- Integrar as fontes externas de alimentos e exercicios.

## Criterio para encerrar a fase

Esta fase sera considerada encerrada quando:

- [x] as migrations aplicarem sem erro no Supabase;
- [x] um usuario conseguir criar e editar o proprio perfil;
- [x] o CRUD basico estiver testado para treino, carga, dieta, Coach e progresso;
- [x] o isolamento de dados entre usuarios estiver testado;
- [x] os tipos TypeScript do schema estiverem gerados;
- [x] o banco remoto estiver validado sem erros estruturais.

O teste de integracao feito pelo app e pelo backend sera realizado nas respectivas fases e nao impede o encerramento da modelagem do banco.

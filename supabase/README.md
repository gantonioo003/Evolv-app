# Evolv - Supabase

Esta pasta guarda o banco do projeto.

## O que tem aqui

```txt
supabase/
  database.types.ts
  seed.sql
  migrations/
    arquivos SQL que criam ou alteram tabelas do PostgreSQL
  tests/
    testes SQL transacionais do banco
```

## Como pensar nisso

- O VS Code guarda o desenho do banco em arquivos SQL.
- O Supabase/PostgreSQL executa esses arquivos e cria as tabelas reais.
- O GitHub guarda o historico dessas mudancas.

## Migrations

Arquivo:

```txt
supabase/migrations/202609150001_initial_schema.sql
```

As migrations criam e protegem:

- perfil do usuario;
- objetivos;
- planos de treino;
- dias de treino;
- exercicios;
- equipamentos, musculos e preferencias de treino;
- catalogo estruturado de alimentos e nutrientes;
- porcoes, macros e micronutrientes;
- consumo e gasto calorico opcional;
- registros opcionais de treino;
- plano alimentar;
- refeicoes;
- registros opcionais de comida;
- conversas do Coach;
- memoria opcional do Coach;
- ajustes do Planner;
- progresso;
- fotos de progresso.

Elas tambem concedem apenas as permissoes necessarias ao usuario autenticado e impedem referencias entre dados privados de usuarios diferentes.

Duas migrations foram adicionadas e aplicadas durante a fase do backend:

```txt
supabase/migrations/202609300001_add_training_context.sql
supabase/migrations/202609300002_create_profile_on_signup.sql
```

A primeira modela fases nutricionais, divisao de treino, RPE/RIR opcionais, check-ins de motivacao e recuperacao e preferencias de avisos silenciosos. A segunda cria automaticamente o perfil publico quando uma conta entra no Supabase Auth e corrige contas antigas sem perfil. Ambas foram aplicadas e validadas no projeto remoto.

O Planner de treino e o Planner nutricional adicionaram:

```txt
supabase/migrations/202610040001_planner_phase_3.sql
supabase/migrations/202610050001_nutrition_planner_phase_4_3.sql
supabase/migrations/202610050002_order_nutrition_meal_items.sql
supabase/migrations/202610050003_planner_phase_4_4_adjustments.sql
supabase/migrations/202610050004_nutrition_day_variants.sql
supabase/migrations/202610050005_nutrition_menu_rotation.sql
supabase/migrations/202610050006_nutrition_planned_flexibility.sql
supabase/migrations/202610060001_daily_activity_context.sql
supabase/migrations/202610060002_guard_daily_activity_revert.sql
```

Essas migrations persistem planos gerados de forma transacional, garantem um unico plano ativo por usuario, adicionam o catalogo inicial de 26 alimentos e preservam a ordem das refeicoes e de seus itens. A fase 04.4 adiciona previa, confirmacao, historico e desfazer; dieta de treino/descanso; rotacao de cardapios; refeicao flexivel; excecao opcional de alcool; e contexto diario compartilhado entre treino e dieta. Todas foram aplicadas no projeto remoto.

## Seed inicial

Arquivo:

```txt
supabase/seed.sql
```

Ele adiciona nutrientes, equipamentos, grupos musculares e um catalogo inicial de exercicios.

Isso ajuda o Planner a montar os primeiros treinos sem depender de cadastro manual. Catalogos maiores serao sincronizados pelo backend a partir de fontes com licenca compativel.

O seed remoto atual possui:

- 119 exercicios;
- 38 equipamentos;
- 22 grupos musculares;
- 6 estilos de treino;
- 17 nutrientes.

O catalogo do Planner nutricional tambem possui 26 alimentos de referencia com macros, papeis nutricionais, estilos alimentares, alergenos e limites de porcao. Eles sao uma base inicial e estao marcados como nao verificados ate a futura revisao por fonte nutricional.

## Tipos TypeScript

O arquivo `database.types.ts` foi gerado a partir do banco remoto. Ele sera usado pelo app e pelo backend para conferir nomes de tabelas, colunas e tipos durante o desenvolvimento.

Para atualizar esse arquivo depois de uma nova migration:

```powershell
npx supabase@latest gen types typescript --linked --schema public | Out-File -Encoding utf8 supabase/database.types.ts
```

## Teste da fase 3

O teste completo esta em:

```txt
supabase/tests/phase_3_database.sql
```

Para executar:

```powershell
npx supabase@latest db query --linked --file supabase/tests/phase_3_database.sql
```

O teste usa transacao e `rollback`, portanto nao mantem os dados temporarios.

Resultado verificado: `PASS`.

Para validar a estrutura do banco:

```powershell
npx supabase@latest db lint --linked --level warning
```

Resultado verificado: `No schema errors found`.

O teste da nova migration esta em:

```txt
supabase/tests/phase_5_training_context.sql
```

Resultado remoto verificado: `PASS`.

Os testes transacionais dos Planners estao em:

```txt
supabase/tests/planner_phase_3_database.sql
supabase/tests/nutrition_planner_phase_4_3.sql
supabase/tests/planner_phase_4_4_adjustments.sql
supabase/tests/nutrition_day_variants_phase_4_4.sql
```

Os testes validam criacao atomica, ordem, plano ativo, arquivamento, mover/inverter dia, troca de exercicio, troca de alimento, desfazer, treino/descanso, rotacao, flexibilidade planejada e atividade pontual sincronizada com a dieta. Todos usam `ROLLBACK` e passaram no banco remoto.

A migration `202609300002_create_profile_on_signup.sql` cria automaticamente a linha de `profiles` quando uma conta entra no Supabase Auth. Ela tambem corrige contas antigas que ainda nao possuem perfil publico.

## Aplicar futuras migrations

```powershell
npx supabase@latest db push --dry-run
npx supabase@latest db push
```

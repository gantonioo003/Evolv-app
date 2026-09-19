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

## Aplicar futuras migrations

```powershell
npx supabase@latest db push --dry-run
npx supabase@latest db push
```

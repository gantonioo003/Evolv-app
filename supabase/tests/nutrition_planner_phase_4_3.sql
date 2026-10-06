-- Evolv - Nutrition Planner phase 04.3 transactional verification
-- Uses teste@evolv.app and rolls every change back at the end.

begin;

do $$
declare
  test_user uuid;
  protein_food uuid;
  carbohydrate_food uuid;
begin
  select id into test_user
  from auth.users
  where email = 'teste@evolv.app';

  select id into protein_food
  from public.foods
  where 'protein_source' = any(nutrition_roles)
  order by name
  limit 1;

  select id into carbohydrate_food
  from public.foods
  where 'carbohydrate_source' = any(nutrition_roles)
  order by name
  limit 1;

  if test_user is null then
    raise exception 'Create teste@evolv.app before running this test.';
  end if;

  if protein_food is null or carbohydrate_food is null then
    raise exception 'Nutrition Planner food catalog is incomplete.';
  end if;

  perform set_config('app.nutrition_test_user', test_user::text, true);
  perform set_config('app.nutrition_test_protein', protein_food::text, true);
  perform set_config('app.nutrition_test_carbohydrate', carbohydrate_food::text, true);
end;
$$;

select set_config(
  'request.jwt.claim.sub',
  current_setting('app.nutrition_test_user'),
  true
);
set local role authenticated;

do $$
declare
  generated_plan uuid;
begin
  select public.create_planner_diet_plan(
    jsonb_build_object(
      'user_id', auth.uid(),
      'goal_id', null,
      'name', 'Plano alimentar temporario',
      'status', 'active',
      'daily_calories_target', 2000,
      'daily_protein_target_g', 150,
      'daily_carbohydrate_target_g', 220,
      'daily_fat_target_g', 60,
      'daily_fiber_target_g', 28,
      'planner_version', 'nutrition-food-generator-v1',
      'nutrition_phase', 'maintenance',
      'macro_pattern', 'balanced',
      'food_style', 'omnivore',
      'meal_schedule', 'regular',
      'planner_input', jsonb_build_object('source', 'database-test'),
      'meals', jsonb_build_array(
        jsonb_build_object(
          'name', 'Almoco',
          'meal_time', '12:00',
          'position', 0,
          'calories_target', 700,
          'protein_target_g', 50,
          'carbohydrate_target_g', 80,
          'fat_target_g', 20,
          'actual_calories', 690,
          'actual_protein_g', 49,
          'actual_carbohydrate_g', 79,
          'actual_fat_g', 20,
          'actual_fiber_g', 8,
          'items', jsonb_build_array(
            jsonb_build_object(
              'food_id', current_setting('app.nutrition_test_protein'),
              'name', 'Proteina de teste',
              'amount', '150 g',
              'quantity', 150,
              'unit', 'g',
              'nutrition_role', 'protein_source',
              'calories_kcal', 250,
              'protein_g', 45,
              'carbohydrate_g', 0,
              'fat_g', 8,
              'fiber_g', 0,
              'substitutions', jsonb_build_array(
                jsonb_build_object(
                  'food_id', current_setting('app.nutrition_test_protein'),
                  'name', 'Troca de teste',
                  'amount', 150,
                  'unit', 'g'
                )
              )
            ),
            jsonb_build_object(
              'food_id', current_setting('app.nutrition_test_carbohydrate'),
              'name', 'Carboidrato de teste',
              'amount', '200 g',
              'quantity', 200,
              'unit', 'g',
              'nutrition_role', 'carbohydrate_source',
              'calories_kcal', 440,
              'protein_g', 4,
              'carbohydrate_g', 79,
              'fat_g', 12,
              'fiber_g', 8,
              'substitutions', '[]'::jsonb
            )
          )
        )
      )
    )
  ) into generated_plan;

  if (
    select count(*)
    from public.meals
    where diet_plan_id = generated_plan
  ) <> 1 then
    raise exception 'Nutrition Planner did not persist the meal.';
  end if;

  if (
    select count(*)
    from public.meal_items mi
    join public.meals m on m.id = mi.meal_id
    where m.diet_plan_id = generated_plan
  ) <> 2 then
    raise exception 'Nutrition Planner did not persist both foods.';
  end if;

  if (
    select array_agg(mi.position order by mi.position)
    from public.meal_items mi
    join public.meals m on m.id = mi.meal_id
    where m.diet_plan_id = generated_plan
  ) <> array[0, 1] then
    raise exception 'Nutrition Planner did not preserve food order.';
  end if;

  if (
    select count(*)
    from public.diet_plans
    where user_id = auth.uid()
      and status = 'active'
  ) <> 1 then
    raise exception 'There must be exactly one active diet plan.';
  end if;

  perform public.set_diet_plan_status(generated_plan, 'archived');

  if not exists (
    select 1
    from public.diet_plans
    where id = generated_plan
      and status = 'archived'
  ) then
    raise exception 'Nutrition Planner did not archive the generated plan.';
  end if;
end;
$$;

reset role;
rollback;

select 'nutrition_planner_phase_4_3_ok' as result;

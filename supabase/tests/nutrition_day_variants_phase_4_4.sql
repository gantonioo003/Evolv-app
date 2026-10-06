-- Evolv - Nutrition day variants phase 04.4 transactional verification
-- Uses teste@evolv.app and rolls every change back at the end.

begin;

do $$
declare
  test_user uuid;
begin
  select id into test_user
  from auth.users
  where email = 'teste@evolv.app';

  if test_user is null then
    raise exception 'Create teste@evolv.app before running this test.';
  end if;

  perform set_config('app.nutrition_variant_test_user', test_user::text, true);
end;
$$;

select set_config(
  'request.jwt.claim.sub',
  current_setting('app.nutrition_variant_test_user'),
  true
);
set local role authenticated;

do $$
declare
  generated_plan uuid;
begin
  select public.create_planner_diet_plan_v3(
    jsonb_build_object(
      'user_id', auth.uid(),
      'name', 'Plano com variacoes temporario',
      'status', 'active',
      'daily_calories_target', 2400,
      'daily_protein_target_g', 160,
      'daily_carbohydrate_target_g', 320,
      'daily_fat_target_g', 55,
      'daily_fiber_target_g', 30,
      'planner_version', 'nutrition-food-generator-v1',
      'nutrition_phase', 'mass_gain',
      'macro_pattern', 'high_carb_performance',
      'food_style', 'omnivore',
      'meal_schedule', 'regular',
      'planner_input', jsonb_build_object('source', 'database-test'),
      'uses_day_variants', true,
      'training_day_calories_target', 2520,
      'rest_day_calories_target', 2310,
      'menu_rotation_enabled', true,
      'menu_rotation_size', 2,
      'flexible_meal_frequency', 'weekly',
      'flexible_meal_weekday', 'saturday',
      'alcohol_frequency', 'fortnightly',
      'alcohol_preferred_weekday', 'saturday',
      'alcohol_max_servings', 1,
      'meals', jsonb_build_array(
        jsonb_build_object(
          'name', 'Cafe de treino',
          'day_type', 'training_day',
          'rotation_index', 0,
          'position', 0,
          'calories_target', 500,
          'protein_target_g', 30,
          'carbohydrate_target_g', 70,
          'fat_target_g', 10,
          'items', '[]'::jsonb
        ),
        jsonb_build_object(
          'name', 'Cafe de treino alternativo',
          'day_type', 'training_day',
          'rotation_index', 1,
          'position', 0,
          'calories_target', 500,
          'protein_target_g', 30,
          'carbohydrate_target_g', 70,
          'fat_target_g', 10,
          'items', '[]'::jsonb
        ),
        jsonb_build_object(
          'name', 'Cafe de descanso',
          'day_type', 'rest_day',
          'rotation_index', 0,
          'position', 0,
          'calories_target', 430,
          'protein_target_g', 30,
          'carbohydrate_target_g', 50,
          'fat_target_g', 12,
          'items', '[]'::jsonb
        ),
        jsonb_build_object(
          'name', 'Cafe de descanso alternativo',
          'day_type', 'rest_day',
          'rotation_index', 1,
          'position', 0,
          'calories_target', 430,
          'protein_target_g', 30,
          'carbohydrate_target_g', 50,
          'fat_target_g', 12,
          'items', '[]'::jsonb
        )
      )
    )
  ) into generated_plan;

  if not exists (
    select 1
    from public.diet_plans
    where id = generated_plan
      and user_id = auth.uid()
      and uses_day_variants
      and menu_rotation_enabled
      and menu_rotation_size = 2
      and flexible_meal_frequency = 'weekly'
      and flexible_meal_weekday = 'saturday'
      and alcohol_frequency = 'fortnightly'
      and alcohol_max_servings = 1
      and training_day_calories_target = 2520
      and rest_day_calories_target = 2310
  ) then
    raise exception 'Diet plan did not preserve the day variant targets.';
  end if;

  if (
    select count(*)
    from public.meals
    where diet_plan_id = generated_plan
      and position = 0
  ) <> 4 then
    raise exception 'Day types and menu rotations cannot share their logical position.';
  end if;

  if (
    select array_agg(day_type order by day_type)
    from public.meals
    where diet_plan_id = generated_plan
  ) <> array['rest_day', 'rest_day', 'training_day', 'training_day'] then
    raise exception 'The generated meals do not contain both day types.';
  end if;
end;
$$;

reset role;
rollback;

select 'nutrition_day_variants_phase_4_4_ok' as result;

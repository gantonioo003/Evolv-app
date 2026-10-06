-- Evolv - Planner phase 04.4 transactional verification
-- Applies and reverts workout and nutrition adjustments, then rolls back.

begin;

do $$
declare
  test_user uuid;
  first_exercise uuid;
  second_exercise uuid;
  first_food uuid;
  second_food uuid;
begin
  select id into test_user
  from auth.users
  where email = 'teste@evolv.app';

  select first_candidate.id, second_candidate.id
  into first_exercise, second_exercise
  from public.exercises first_candidate
  join public.exercises second_candidate
    on second_candidate.id <> first_candidate.id
   and second_candidate.training_kind = first_candidate.training_kind
   and second_candidate.muscle_group = first_candidate.muscle_group
  where first_candidate.training_kind = 'resistance'
  order by first_candidate.name, second_candidate.name
  limit 1;

  select first_candidate.id, second_candidate.id
  into first_food, second_food
  from public.foods first_candidate
  join public.foods second_candidate
    on second_candidate.id <> first_candidate.id
   and second_candidate.nutrition_roles && first_candidate.nutrition_roles
  where 'carbohydrate_source' = any(first_candidate.nutrition_roles)
    and 'carbohydrate_source' = any(second_candidate.nutrition_roles)
  order by first_candidate.name, second_candidate.name
  limit 1;

  if test_user is null then
    raise exception 'Create teste@evolv.app before running this test.';
  end if;

  if first_exercise is null or second_exercise is null then
    raise exception 'Compatible exercise pair not found.';
  end if;

  if first_food is null or second_food is null then
    raise exception 'Compatible food pair not found.';
  end if;

  perform set_config('app.adjustment_test_user', test_user::text, true);
  perform set_config('app.adjustment_first_exercise', first_exercise::text, true);
  perform set_config('app.adjustment_second_exercise', second_exercise::text, true);
  perform set_config('app.adjustment_first_food', first_food::text, true);
  perform set_config('app.adjustment_second_food', second_food::text, true);
end;
$$;

select set_config(
  'request.jwt.claim.sub',
  current_setting('app.adjustment_test_user'),
  true
);
set local role authenticated;

do $$
declare
  workout_plan_id uuid;
  monday_id uuid;
  tuesday_id uuid;
  workout_item_id uuid;
  diet_plan_id uuid;
  meal_id uuid;
  meal_item_id uuid;
  adjustment_id uuid;
  first_food_name text;
  second_food_name text;
begin
  insert into public.workout_plans (
    user_id, name, status, start_date, weekly_frequency
  ) values (
    auth.uid(), 'Teste de ajustes', 'draft', current_date, 2
  ) returning id into workout_plan_id;

  insert into public.workout_days (
    workout_plan_id, weekday, title, focus, position
  ) values (
    workout_plan_id, 'monday', 'Treino A', 'Teste', 0
  ) returning id into monday_id;

  insert into public.workout_days (
    workout_plan_id, weekday, title, focus, position
  ) values (
    workout_plan_id, 'tuesday', 'Treino B', 'Teste', 1
  ) returning id into tuesday_id;

  insert into public.workout_day_exercises (
    workout_day_id, exercise_id, position, sets, min_reps, max_reps,
    rest_seconds, prescription_kind
  ) values (
    monday_id,
    current_setting('app.adjustment_first_exercise')::uuid,
    0, 3, 8, 12, 90, 'repetitions'
  ) returning id into workout_item_id;

  insert into public.planner_adjustments (
    user_id, adjustment_kind, reason, workout_plan_id, target_type,
    target_id, preview, before_snapshot, after_snapshot
  ) values (
    auth.uid(), 'move_workout_day', 'Testar mudanca de dia', workout_plan_id,
    'workout_day', monday_id, '{}',
    jsonb_build_object(
      'day_id', monday_id, 'weekday', 'monday',
      'swap_day_id', tuesday_id, 'swap_weekday', 'tuesday'
    ),
    jsonb_build_object(
      'day_id', monday_id, 'weekday', 'tuesday',
      'swap_day_id', tuesday_id, 'swap_weekday', 'monday'
    )
  ) returning id into adjustment_id;

  perform public.apply_planner_adjustment(adjustment_id);
  if (select weekday from public.workout_days where id = monday_id) <> 'tuesday' then
    raise exception 'Workout day move was not applied.';
  end if;

  perform public.revert_planner_adjustment(adjustment_id);
  if (select weekday from public.workout_days where id = monday_id) <> 'monday' then
    raise exception 'Workout day move was not reverted.';
  end if;

  insert into public.planner_adjustments (
    user_id, adjustment_kind, reason, workout_plan_id, target_type,
    target_id, preview, before_snapshot, after_snapshot
  ) values (
    auth.uid(), 'replace_exercise', 'Testar troca de exercicio', workout_plan_id,
    'workout_day_exercise', workout_item_id, '{}',
    jsonb_build_object(
      'workout_day_exercise_id', workout_item_id,
      'exercise_id', current_setting('app.adjustment_first_exercise')::uuid
    ),
    jsonb_build_object(
      'workout_day_exercise_id', workout_item_id,
      'exercise_id', current_setting('app.adjustment_second_exercise')::uuid
    )
  ) returning id into adjustment_id;

  perform public.apply_planner_adjustment(adjustment_id);
  if (select exercise_id from public.workout_day_exercises where id = workout_item_id)
     <> current_setting('app.adjustment_second_exercise')::uuid then
    raise exception 'Exercise replacement was not applied.';
  end if;

  perform public.revert_planner_adjustment(adjustment_id);
  if (select exercise_id from public.workout_day_exercises where id = workout_item_id)
     <> current_setting('app.adjustment_first_exercise')::uuid then
    raise exception 'Exercise replacement was not reverted.';
  end if;

  select name into first_food_name from public.foods
  where id = current_setting('app.adjustment_first_food')::uuid;
  select name into second_food_name from public.foods
  where id = current_setting('app.adjustment_second_food')::uuid;

  insert into public.diet_plans (
    user_id, name, status, daily_calories_target, daily_protein_target_g
  ) values (
    auth.uid(), 'Teste alimentar', 'draft', 2200, 150
  ) returning id into diet_plan_id;

  insert into public.meals (
    diet_plan_id, name, position, calories_target, protein_target_g
  ) values (
    diet_plan_id, 'Almoco', 0, 700, 40
  ) returning id into meal_id;

  insert into public.meal_items (
    meal_id, food_id, name, position, amount, quantity, unit,
    nutrition_role, calories_kcal, protein_g, carbohydrate_g, fat_g, fiber_g,
    substitutions
  ) values (
    meal_id, current_setting('app.adjustment_first_food')::uuid,
    first_food_name, 0, '200 g', 200, 'g', 'carbohydrate_source',
    260, 5, 56, 1, 2,
    jsonb_build_array(jsonb_build_object(
      'food_id', current_setting('app.adjustment_second_food'),
      'name', second_food_name,
      'role', 'carbohydrate_source',
      'amount', 250,
      'unit', 'g',
      'nutrition', jsonb_build_object(
        'calories', 260, 'proteinG', 5, 'carbohydrateG', 56,
        'fatG', 1, 'fiberG', 2
      ),
      'similarity_score', 0.95
    ))
  ) returning id into meal_item_id;

  insert into public.planner_adjustments (
    user_id, adjustment_kind, reason, diet_plan_id, target_type,
    target_id, preview, before_snapshot, after_snapshot
  ) values (
    auth.uid(), 'replace_meal_item', 'Testar troca de alimento', diet_plan_id,
    'meal_item', meal_item_id, '{}',
    jsonb_build_object(
      'meal_item_id', meal_item_id,
      'food_id', current_setting('app.adjustment_first_food')::uuid,
      'name', first_food_name, 'amount', '200 g', 'quantity', 200,
      'unit', 'g', 'nutrition_role', 'carbohydrate_source',
      'calories_kcal', 260, 'protein_g', 5, 'carbohydrate_g', 56,
      'fat_g', 1, 'fiber_g', 2, 'substitutions', '[]'::jsonb
    ),
    jsonb_build_object(
      'meal_item_id', meal_item_id,
      'food_id', current_setting('app.adjustment_second_food')::uuid,
      'name', second_food_name, 'amount', '250 g', 'quantity', 250,
      'unit', 'g', 'nutrition_role', 'carbohydrate_source',
      'calories_kcal', 260, 'protein_g', 5, 'carbohydrate_g', 56,
      'fat_g', 1, 'fiber_g', 2, 'substitutions', '[]'::jsonb
    )
  ) returning id into adjustment_id;

  perform public.apply_planner_adjustment(adjustment_id);
  if (select food_id from public.meal_items where id = meal_item_id)
     <> current_setting('app.adjustment_second_food')::uuid then
    raise exception 'Meal item replacement was not applied.';
  end if;

  perform public.revert_planner_adjustment(adjustment_id);
  if (select food_id from public.meal_items where id = meal_item_id)
     <> current_setting('app.adjustment_first_food')::uuid then
    raise exception 'Meal item replacement was not reverted.';
  end if;
end;
$$;

reset role;
rollback;

select 'planner_phase_4_4_adjustments_ok' as result;

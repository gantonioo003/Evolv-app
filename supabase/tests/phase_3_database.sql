-- Evolv - Phase 3 database verification
-- Requires the confirmed test users teste@evolv.app and teste2@evolv.app.
-- All records created by this test are removed by the final rollback.

begin;

do $$
declare
  user_one uuid;
  user_two uuid;
  catalog_exercise uuid;
begin
  select id into user_one from auth.users where email = 'teste@evolv.app';
  select id into user_two from auth.users where email = 'teste2@evolv.app';
  select id into catalog_exercise from public.exercises order by name limit 1;

  if user_one is null or user_two is null then
    raise exception 'Create and confirm teste@evolv.app and teste2@evolv.app before running this test.';
  end if;

  if catalog_exercise is null then
    raise exception 'The exercise catalog is empty. Apply supabase/seed.sql first.';
  end if;

  perform set_config('app.test_user_one', user_one::text, true);
  perform set_config('app.test_user_two', user_two::text, true);
  perform set_config('app.test_exercise', catalog_exercise::text, true);
  perform set_config('app.test_goal_one', gen_random_uuid()::text, true);
  perform set_config('app.test_goal_two', gen_random_uuid()::text, true);
  perform set_config('app.test_workout_plan_one', gen_random_uuid()::text, true);
  perform set_config('app.test_workout_plan_two', gen_random_uuid()::text, true);
  perform set_config('app.test_workout_day_one', gen_random_uuid()::text, true);
  perform set_config('app.test_workout_day_two', gen_random_uuid()::text, true);
  perform set_config('app.test_workout_log_one', gen_random_uuid()::text, true);
  perform set_config('app.test_workout_log_two', gen_random_uuid()::text, true);
  perform set_config('app.test_exercise_log_one', gen_random_uuid()::text, true);
  perform set_config('app.test_diet_plan_one', gen_random_uuid()::text, true);
  perform set_config('app.test_diet_plan_two', gen_random_uuid()::text, true);
  perform set_config('app.test_meal_one', gen_random_uuid()::text, true);
  perform set_config('app.test_meal_two', gen_random_uuid()::text, true);
  perform set_config('app.test_food_one', gen_random_uuid()::text, true);
  perform set_config('app.test_food_two', gen_random_uuid()::text, true);
  perform set_config('app.test_food_log_one', gen_random_uuid()::text, true);
  perform set_config('app.test_conversation_one', gen_random_uuid()::text, true);
  perform set_config('app.test_conversation_two', gen_random_uuid()::text, true);
  perform set_config('app.test_message_one', gen_random_uuid()::text, true);
  perform set_config('app.test_message_two', gen_random_uuid()::text, true);
  perform set_config('app.test_progress_one', gen_random_uuid()::text, true);
  perform set_config('app.test_progress_two', gen_random_uuid()::text, true);
  perform set_config('app.test_disposable_message', gen_random_uuid()::text, true);
end;
$$;

select set_config('request.jwt.claim.sub', current_setting('app.test_user_one'), true);
set local role authenticated;

insert into public.profiles (id, full_name, onboarding_status)
values (auth.uid(), 'Usuario Teste Um', 'skipped')
on conflict (id) do update set full_name = excluded.full_name;

insert into public.goals (id, user_id, type, title)
values (
  current_setting('app.test_goal_one')::uuid,
  auth.uid(),
  'hypertrophy',
  'Hipertrofia de teste'
);

insert into public.workout_plans (
  id, user_id, goal_id, name, status, start_date, weekly_frequency
)
values (
  current_setting('app.test_workout_plan_one')::uuid,
  auth.uid(),
  current_setting('app.test_goal_one')::uuid,
  'Plano de treino de teste',
  'active',
  current_date,
  4
);

insert into public.workout_days (
  id, workout_plan_id, weekday, title, focus, estimated_minutes, position
)
values (
  current_setting('app.test_workout_day_one')::uuid,
  current_setting('app.test_workout_plan_one')::uuid,
  'monday',
  'Treino A',
  'Peito e triceps',
  60,
  1
);

insert into public.workout_day_exercises (
  workout_day_id, exercise_id, position, sets, min_reps, max_reps, rest_seconds, target_load_kg
)
values (
  current_setting('app.test_workout_day_one')::uuid,
  current_setting('app.test_exercise')::uuid,
  1,
  4,
  8,
  12,
  90,
  80
);

insert into public.workout_logs (id, user_id, workout_day_id, notes)
values (
  current_setting('app.test_workout_log_one')::uuid,
  auth.uid(),
  current_setting('app.test_workout_day_one')::uuid,
  'Treino concluido para teste'
);

insert into public.exercise_logs (
  id, user_id, workout_log_id, exercise_id, sets_completed, reps_summary, load_kg
)
values (
  current_setting('app.test_exercise_log_one')::uuid,
  auth.uid(),
  current_setting('app.test_workout_log_one')::uuid,
  current_setting('app.test_exercise')::uuid,
  4,
  '10, 10, 9, 8',
  80
);

update public.exercise_logs
set load_kg = 82.5
where id = current_setting('app.test_exercise_log_one')::uuid;

insert into public.exercise_progression_suggestions (
  user_id, exercise_id, current_load_kg, suggested_load_kg, reason, suggested_for
)
values (
  auth.uid(),
  current_setting('app.test_exercise')::uuid,
  82.5,
  85,
  'Faixa de repeticoes concluida com boa execucao.',
  current_date + 7
);

insert into public.diet_plans (
  id, user_id, goal_id, name, status, daily_calories_target,
  daily_protein_target_g, daily_carbohydrate_target_g, daily_fat_target_g
)
values (
  current_setting('app.test_diet_plan_one')::uuid,
  auth.uid(),
  current_setting('app.test_goal_one')::uuid,
  'Plano alimentar de teste',
  'active',
  2400,
  170,
  280,
  65
);

insert into public.meals (
  id, diet_plan_id, name, meal_time, position, calories_target, protein_target_g
)
values (
  current_setting('app.test_meal_one')::uuid,
  current_setting('app.test_diet_plan_one')::uuid,
  'Almoco',
  '12:30',
  1,
  700,
  45
);

insert into public.foods (
  id, user_id, source, name, data_type, calories_kcal, protein_g,
  carbohydrate_g, fat_g
)
values (
  current_setting('app.test_food_one')::uuid,
  auth.uid(),
  'user',
  'Refeicao personalizada de teste',
  'custom',
  180,
  20,
  15,
  4
);

insert into public.food_portions (food_id, name, quantity, gram_weight, is_default)
values (current_setting('app.test_food_one')::uuid, 'porcao', 1, 100, true);

insert into public.meal_items (meal_id, food_id, name, quantity, unit)
values (
  current_setting('app.test_meal_one')::uuid,
  current_setting('app.test_food_one')::uuid,
  'Refeicao personalizada de teste',
  1,
  'porcao'
);

insert into public.food_logs (id, user_id, description, meal_name)
values (
  current_setting('app.test_food_log_one')::uuid,
  auth.uid(),
  'Registro alimentar de teste',
  'Almoco'
);

insert into public.food_log_items (
  user_id, food_log_id, food_id, food_name, quantity, unit,
  amount_grams, calories_kcal, protein_g, carbohydrate_g, fat_g
)
values (
  auth.uid(),
  current_setting('app.test_food_log_one')::uuid,
  current_setting('app.test_food_one')::uuid,
  'Refeicao personalizada de teste',
  1,
  'porcao',
  100,
  180,
  20,
  15,
  4
);

insert into public.energy_expenditure_logs (user_id, source, calories_kcal, description)
values (auth.uid(), 'workout', 350, 'Estimativa de teste');

insert into public.coach_conversations (id, user_id, title, entry_context)
values (
  current_setting('app.test_conversation_one')::uuid,
  auth.uid(),
  'Conversa de teste',
  'workout'
);

insert into public.coach_messages (id, conversation_id, user_id, role, content)
values (
  current_setting('app.test_message_one')::uuid,
  current_setting('app.test_conversation_one')::uuid,
  auth.uid(),
  'user',
  'Posso aumentar a carga?'
);

insert into public.coach_messages (id, conversation_id, user_id, role, content)
values (
  current_setting('app.test_disposable_message')::uuid,
  current_setting('app.test_conversation_one')::uuid,
  auth.uid(),
  'assistant',
  'Mensagem descartavel para testar exclusao.'
);

delete from public.coach_messages
where id = current_setting('app.test_disposable_message')::uuid;

insert into public.coach_memory_items (
  user_id, source_message_id, category, content
)
values (
  auth.uid(),
  current_setting('app.test_message_one')::uuid,
  'preference',
  'Prefere treinos com maquinas e pesos livres.'
);

insert into public.planner_adjustments (
  user_id, conversation_id, status, reason, requested_change
)
values (
  auth.uid(),
  current_setting('app.test_conversation_one')::uuid,
  'pending',
  'Teste de reorganizacao',
  '{"move_workout": "friday"}'::jsonb
);

insert into public.progress_entries (id, user_id, weight_kg, waist_cm, notes)
values (
  current_setting('app.test_progress_one')::uuid,
  auth.uid(),
  82.5,
  84,
  'Medicao de teste'
);

insert into public.progress_photos (user_id, progress_entry_id, storage_path, photo_type)
values (
  auth.uid(),
  current_setting('app.test_progress_one')::uuid,
  'test/user-one/front.jpg',
  'front'
);

insert into public.training_preferences (user_id, preferred_equipment_categories, notes)
values (auth.uid(), array['machine', 'free_weight'], 'Preferencias de teste');

insert into public.user_preferred_training_styles (user_id, training_style_id)
select auth.uid(), id from public.training_styles order by name limit 1;

insert into public.user_available_equipment (user_id, equipment_id)
select auth.uid(), id from public.equipment order by name limit 1;

reset role;

select set_config('request.jwt.claim.sub', current_setting('app.test_user_two'), true);
set local role authenticated;

insert into public.profiles (id, full_name, onboarding_status)
values (auth.uid(), 'Usuario Teste Dois', 'skipped')
on conflict (id) do update set full_name = excluded.full_name;

insert into public.goals (id, user_id, type, title)
values (
  current_setting('app.test_goal_two')::uuid,
  auth.uid(),
  'strength',
  'Forca de teste'
);

insert into public.workout_plans (
  id, user_id, goal_id, name, status, start_date, weekly_frequency
)
values (
  current_setting('app.test_workout_plan_two')::uuid,
  auth.uid(),
  current_setting('app.test_goal_two')::uuid,
  'Plano de treino do segundo usuario',
  'active',
  current_date,
  3
);

insert into public.workout_days (id, workout_plan_id, weekday, title, focus, position)
values (
  current_setting('app.test_workout_day_two')::uuid,
  current_setting('app.test_workout_plan_two')::uuid,
  'tuesday',
  'Treino B',
  'Pernas',
  1
);

insert into public.workout_logs (id, user_id, workout_day_id)
values (
  current_setting('app.test_workout_log_two')::uuid,
  auth.uid(),
  current_setting('app.test_workout_day_two')::uuid
);

insert into public.diet_plans (id, user_id, goal_id, name, status)
values (
  current_setting('app.test_diet_plan_two')::uuid,
  auth.uid(),
  current_setting('app.test_goal_two')::uuid,
  'Plano alimentar do segundo usuario',
  'active'
);

insert into public.meals (id, diet_plan_id, name, position)
values (
  current_setting('app.test_meal_two')::uuid,
  current_setting('app.test_diet_plan_two')::uuid,
  'Jantar',
  1
);

insert into public.foods (id, user_id, source, name, data_type)
values (
  current_setting('app.test_food_two')::uuid,
  auth.uid(),
  'user',
  'Alimento privado do segundo usuario',
  'custom'
);

insert into public.coach_conversations (id, user_id, title, entry_context)
values (
  current_setting('app.test_conversation_two')::uuid,
  auth.uid(),
  'Conversa do segundo usuario',
  'diet'
);

insert into public.coach_messages (id, conversation_id, user_id, role, content)
values (
  current_setting('app.test_message_two')::uuid,
  current_setting('app.test_conversation_two')::uuid,
  auth.uid(),
  'user',
  'Mensagem privada do segundo usuario.'
);

insert into public.progress_entries (id, user_id, weight_kg)
values (
  current_setting('app.test_progress_two')::uuid,
  auth.uid(),
  90
);

reset role;

select set_config('request.jwt.claim.sub', current_setting('app.test_user_one'), true);
set local role authenticated;

do $$
begin
  if (select count(*) from public.profiles) <> 1 then
    raise exception 'RLS failure: user one can see another profile.';
  end if;

  if (select count(*) from public.goals) <> 1
    or (select count(*) from public.workout_plans) <> 1
    or (select count(*) from public.diet_plans) <> 1
    or (select count(*) from public.coach_conversations) <> 1
    or (select count(*) from public.progress_entries) <> 1 then
    raise exception 'RLS failure: user one can see records owned by user two.';
  end if;

  if exists (
    select 1 from public.profiles
    where id = current_setting('app.test_user_two')::uuid
  ) then
    raise exception 'RLS failure: the second profile is visible.';
  end if;

  if (select load_kg from public.exercise_logs where id = current_setting('app.test_exercise_log_one')::uuid) <> 82.5 then
    raise exception 'CRUD failure: the exercise load update was not saved.';
  end if;

  if exists (
    select 1 from public.coach_messages
    where id = current_setting('app.test_disposable_message')::uuid
  ) then
    raise exception 'CRUD failure: the Coach message delete did not work.';
  end if;
end;
$$;

do $$
begin
  begin
    insert into public.workout_plans (
      user_id, goal_id, name, start_date, weekly_frequency
    ) values (
      auth.uid(),
      current_setting('app.test_goal_two')::uuid,
      'Referencia indevida',
      current_date,
      1
    );
    raise exception 'Ownership failure: workout plan accepted another user goal.';
  exception when check_violation then
    null;
  end;

  begin
    insert into public.workout_logs (user_id, workout_day_id)
    values (auth.uid(), current_setting('app.test_workout_day_two')::uuid);
    raise exception 'Ownership failure: workout log accepted another user day.';
  exception when check_violation then
    null;
  end;

  begin
    insert into public.exercise_logs (user_id, workout_log_id, exercise_id)
    values (
      auth.uid(),
      current_setting('app.test_workout_log_two')::uuid,
      current_setting('app.test_exercise')::uuid
    );
    raise exception 'Ownership failure: exercise log accepted another user workout log.';
  exception when check_violation then
    null;
  end;

  begin
    insert into public.diet_plans (user_id, goal_id, name)
    values (auth.uid(), current_setting('app.test_goal_two')::uuid, 'Referencia indevida');
    raise exception 'Ownership failure: diet plan accepted another user goal.';
  exception when check_violation then
    null;
  end;

  begin
    insert into public.meal_items (meal_id, food_id, name)
    values (
      current_setting('app.test_meal_one')::uuid,
      current_setting('app.test_food_two')::uuid,
      'Referencia indevida'
    );
    raise exception 'Ownership failure: meal item accepted another user food.';
  exception when check_violation then
    null;
  end;

  begin
    insert into public.food_log_items (
      user_id, food_log_id, food_id, food_name, quantity, unit
    ) values (
      auth.uid(),
      current_setting('app.test_food_log_one')::uuid,
      current_setting('app.test_food_two')::uuid,
      'Referencia indevida',
      1,
      'porcao'
    );
    raise exception 'Ownership failure: food log item accepted another user food.';
  exception when check_violation then
    null;
  end;

  begin
    insert into public.coach_messages (conversation_id, user_id, role, content)
    values (
      current_setting('app.test_conversation_two')::uuid,
      auth.uid(),
      'user',
      'Referencia indevida'
    );
    raise exception 'Ownership failure: Coach message accepted another user conversation.';
  exception when check_violation then
    null;
  end;

  begin
    insert into public.coach_memory_items (user_id, source_message_id, category, content)
    values (
      auth.uid(),
      current_setting('app.test_message_two')::uuid,
      'preference',
      'Referencia indevida'
    );
    raise exception 'Ownership failure: Coach memory accepted another user message.';
  exception when check_violation then
    null;
  end;

  begin
    insert into public.planner_adjustments (user_id, conversation_id, reason)
    values (
      auth.uid(),
      current_setting('app.test_conversation_two')::uuid,
      'Referencia indevida'
    );
    raise exception 'Ownership failure: Planner accepted another user conversation.';
  exception when check_violation then
    null;
  end;

  begin
    insert into public.progress_photos (user_id, progress_entry_id, storage_path)
    values (
      auth.uid(),
      current_setting('app.test_progress_two')::uuid,
      'test/invalid.jpg'
    );
    raise exception 'Ownership failure: progress photo accepted another user entry.';
  exception when check_violation then
    null;
  end;
end;
$$;

reset role;
rollback;

select
  'PASS' as result,
  'CRUD, workout, load, diet, Coach, progress, RLS and ownership integrity verified.' as details;

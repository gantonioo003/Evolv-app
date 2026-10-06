-- Evolv - Planner phase 03 transactional verification
-- Uses teste@evolv.app and rolls every change back at the end.

begin;

do $$
declare
  test_user uuid;
  resistance_exercise uuid;
  cardio_exercise uuid;
begin
  select id into test_user
  from auth.users
  where email = 'teste@evolv.app';

  select id into resistance_exercise
  from public.exercises
  where training_kind = 'resistance'
  order by name
  limit 1;

  select id into cardio_exercise
  from public.exercises
  where training_kind = 'cardio'
  order by name
  limit 1;

  if test_user is null then
    raise exception 'Create teste@evolv.app before running this test.';
  end if;

  if resistance_exercise is null or cardio_exercise is null then
    raise exception 'Planner exercise catalog is incomplete.';
  end if;

  perform set_config('app.planner_test_user', test_user::text, true);
  perform set_config(
    'app.planner_test_resistance_exercise',
    resistance_exercise::text,
    true
  );
  perform set_config(
    'app.planner_test_cardio_exercise',
    cardio_exercise::text,
    true
  );
end;
$$;

select set_config(
  'request.jwt.claim.sub',
  current_setting('app.planner_test_user'),
  true
);
set local role authenticated;

do $$
declare
  generated_plan uuid;
begin
  select public.create_planner_workout_plan(
    jsonb_build_object(
      'user_id', auth.uid(),
      'goal_id', null,
      'name', 'Plano transacional temporario',
      'status', 'active',
      'start_date', current_date,
      'weekly_frequency', 2,
      'split_type', 'hybrid',
      'split_label', 'Teste Planner',
      'planner_version', 'planner-rules-v1',
      'planner_input', jsonb_build_object('source', 'database-test'),
      'days', jsonb_build_array(
        jsonb_build_object(
          'weekday', 'monday',
          'position', 0,
          'title', 'Forca',
          'focus', 'Corpo inteiro',
          'estimated_minutes', 45,
          'exercises', jsonb_build_array(
            jsonb_build_object(
              'exercise_id', current_setting(
                'app.planner_test_resistance_exercise'
              ),
              'position', 0,
              'prescription_kind', 'repetitions',
              'sets', 3,
              'min_reps', 8,
              'max_reps', 12,
              'rest_seconds', 90,
              'duration_minutes', null,
              'planner_role', 'primary'
            )
          )
        ),
        jsonb_build_object(
          'weekday', 'thursday',
          'position', 1,
          'title', 'Cardio',
          'focus', 'Condicionamento',
          'estimated_minutes', 30,
          'exercises', jsonb_build_array(
            jsonb_build_object(
              'exercise_id', current_setting('app.planner_test_cardio_exercise'),
              'position', 0,
              'prescription_kind', 'duration',
              'sets', null,
              'min_reps', null,
              'max_reps', null,
              'rest_seconds', 60,
              'duration_minutes', 30,
              'planner_role', 'conditioning'
            )
          )
        )
      )
    )
  ) into generated_plan;

  perform set_config('app.planner_test_plan', generated_plan::text, true);

  if (
    select count(*)
    from public.workout_days
    where workout_plan_id = generated_plan
  ) <> 2 then
    raise exception 'Planner did not persist both workout days.';
  end if;

  if (
    select count(*)
    from public.workout_day_exercises wde
    join public.workout_days wd on wd.id = wde.workout_day_id
    where wd.workout_plan_id = generated_plan
  ) <> 2 then
    raise exception 'Planner did not persist both prescriptions.';
  end if;

  if not exists (
    select 1
    from public.workout_day_exercises wde
    join public.workout_days wd on wd.id = wde.workout_day_id
    where wd.workout_plan_id = generated_plan
      and wde.prescription_kind = 'duration'
      and wde.duration_minutes = 30
      and wde.sets is null
  ) then
    raise exception 'Timed prescription was not persisted correctly.';
  end if;

  if (
    select count(*)
    from public.workout_plans
    where user_id = auth.uid()
      and status = 'active'
  ) <> 1 then
    raise exception 'There must be exactly one active plan.';
  end if;

  perform public.set_workout_plan_status(generated_plan, 'archived');

  if not exists (
    select 1
    from public.workout_plans
    where id = generated_plan
      and status = 'archived'
  ) then
    raise exception 'Planner did not archive the generated plan.';
  end if;
end;
$$;

reset role;
rollback;

select 'planner_phase_3_database_ok' as result;

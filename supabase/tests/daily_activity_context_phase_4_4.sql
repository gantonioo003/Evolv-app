-- Evolv - daily activity context verification
-- Confirms that a one-day override changes the nutrition menu without
-- mutating the recurring workout plan, then restores the original context.

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

  perform set_config('app.day_context_test_user', test_user::text, true);
end;
$$;

select set_config(
  'request.jwt.claim.sub',
  current_setting('app.day_context_test_user'),
  true
);
set local role authenticated;

do $$
declare
  test_date date := current_date + 3650;
  test_weekday public.weekday;
  workout_plan_id uuid;
  workout_day_id uuid;
  adjustment_id uuid;
  context jsonb;
begin
  test_weekday := case extract(isodow from test_date)::integer
    when 1 then 'monday'::public.weekday
    when 2 then 'tuesday'::public.weekday
    when 3 then 'wednesday'::public.weekday
    when 4 then 'thursday'::public.weekday
    when 5 then 'friday'::public.weekday
    when 6 then 'saturday'::public.weekday
    else 'sunday'::public.weekday
  end;

  insert into public.workout_plans (
    user_id, name, status, start_date, weekly_frequency
  ) values (
    auth.uid(), 'Teste de contexto diario', 'active', test_date, 1
  ) returning id into workout_plan_id;

  insert into public.workout_days (
    workout_plan_id, weekday, title, focus, estimated_minutes, position
  ) values (
    workout_plan_id, test_weekday, 'Treino do contexto', 'Teste', 55, 0
  ) returning id into workout_day_id;

  context := public.get_daily_activity_context(test_date);
  if context ->> 'activity_type' <> 'resistance'
     or context ->> 'nutrition_day_type' <> 'training_day' then
    raise exception 'Recurring workout did not produce training-day nutrition.';
  end if;

  insert into public.planner_adjustments (
    user_id, adjustment_kind, source, reason, target_type,
    preview, before_snapshot, after_snapshot
  ) values (
    auth.uid(), 'set_day_activity', 'coach', 'Cardio no lugar do treino',
    'daily_activity_override', '{}',
    jsonb_build_object('existed', false, 'activity_date', test_date),
    jsonb_build_object(
      'activity_date', test_date,
      'activity_type', 'cardio',
      'intensity', 'moderate',
      'estimated_minutes', 35,
      'workout_day_id', null,
      'nutrition_day_type', 'rest_day',
      'note', 'Mudanca pontual'
    )
  ) returning id into adjustment_id;

  perform public.apply_day_activity_adjustment(adjustment_id);
  context := public.get_daily_activity_context(test_date);
  if context ->> 'activity_type' <> 'cardio'
     or context ->> 'nutrition_day_type' <> 'rest_day'
     or context ->> 'source' <> 'override' then
    raise exception 'Day override did not control the activity and diet context.';
  end if;

  if (select weekday from public.workout_days where id = workout_day_id)
     <> test_weekday then
    raise exception 'One-day override mutated the recurring workout plan.';
  end if;

  perform public.revert_day_activity_adjustment(adjustment_id);
  context := public.get_daily_activity_context(test_date);
  if context ->> 'activity_type' <> 'resistance'
     or context ->> 'nutrition_day_type' <> 'training_day'
     or context ->> 'source' <> 'workout_plan' then
    raise exception 'Revert did not restore the recurring workout context.';
  end if;
end;
$$;

reset role;
rollback;

select 'daily_activity_context_phase_4_4_ok' as result;

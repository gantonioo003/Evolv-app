-- Evolv - Optional training context verification
-- Run after applying 202609300001_add_training_context.sql.

begin;

do $$
declare
  user_one uuid;
  user_two uuid;
begin
  select id into user_one from auth.users where email = 'teste@evolv.app';
  select id into user_two from auth.users where email = 'teste2@evolv.app';

  if user_one is null or user_two is null then
    raise exception 'Create teste@evolv.app and teste2@evolv.app before running this test.';
  end if;

  perform set_config('app.context_user_one', user_one::text, true);
  perform set_config('app.context_user_two', user_two::text, true);
  perform set_config('app.context_phase_one', gen_random_uuid()::text, true);
  perform set_config('app.context_phase_two', gen_random_uuid()::text, true);
end;
$$;

select set_config('request.jwt.claim.sub', current_setting('app.context_user_one'), true);
set local role authenticated;

insert into public.nutrition_phases (
  id, user_id, phase_type, label, started_on, planned_end_on
) values (
  current_setting('app.context_phase_one')::uuid,
  auth.uid(),
  'fat_loss',
  'Cutting de teste',
  current_date - 70,
  current_date + 14
);

insert into public.readiness_check_ins (
  user_id, motivation, energy, sleep_quality, recovery, hunger, stress
) values (auth.uid(), 3, 2, 3, 2, 4, 3);

insert into public.insight_preferences (user_id)
values (auth.uid());

reset role;
select set_config('request.jwt.claim.sub', current_setting('app.context_user_two'), true);
set local role authenticated;

insert into public.nutrition_phases (
  id, user_id, phase_type, label
) values (
  current_setting('app.context_phase_two')::uuid,
  auth.uid(),
  'mass_gain',
  'Ganho de massa de teste'
);

reset role;
select set_config('request.jwt.claim.sub', current_setting('app.context_user_one'), true);
set local role authenticated;

do $$
begin
  if (select count(*) from public.nutrition_phases) <> 1 then
    raise exception 'RLS failure: another user nutrition phase is visible.';
  end if;

  if (select count(*) from public.readiness_check_ins) <> 1 then
    raise exception 'Readiness check-in was not stored.';
  end if;

  if (select repeated_topic_cooldown_days from public.insight_preferences) <> 30 then
    raise exception 'Quiet insight defaults are incorrect.';
  end if;
end;
$$;

reset role;
rollback;

select 'PASS' as result, 'Nutrition phase, readiness, quiet insights and RLS verified.' as details;


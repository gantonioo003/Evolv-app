alter table public.planner_adjustments
  drop constraint if exists planner_adjustments_adjustment_kind_check,
  add constraint planner_adjustments_adjustment_kind_check
    check (adjustment_kind is null or adjustment_kind in (
      'move_workout_day',
      'replace_exercise',
      'replace_meal_item',
      'set_day_activity'
    )),
  drop constraint if exists planner_adjustments_target_type_check,
  add constraint planner_adjustments_target_type_check
    check (target_type is null or target_type in (
      'workout_day',
      'workout_day_exercise',
      'meal_item',
      'daily_activity_override'
    ));

create table public.daily_activity_overrides (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  activity_date date not null,
  activity_type text not null
    check (activity_type in ('rest', 'resistance', 'cardio', 'mixed')),
  intensity text
    check (intensity is null or intensity in ('light', 'moderate', 'hard')),
  estimated_minutes integer
    check (estimated_minutes is null or estimated_minutes between 0 and 360),
  workout_day_id uuid references public.workout_days(id) on delete set null,
  nutrition_day_type text not null
    check (nutrition_day_type in ('training_day', 'rest_day')),
  source text not null default 'manual'
    check (source in ('manual', 'coach', 'planner')),
  note text check (note is null or char_length(note) <= 500),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, activity_date)
);

create index daily_activity_overrides_user_date_idx
on public.daily_activity_overrides(user_id, activity_date desc);

create trigger daily_activity_overrides_set_updated_at
before update on public.daily_activity_overrides
for each row execute function public.set_updated_at();

alter table public.daily_activity_overrides enable row level security;

create policy "Users can manage their own daily activity overrides"
on public.daily_activity_overrides
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

grant select, insert, update, delete
on public.daily_activity_overrides
to authenticated;

create or replace function public.validate_daily_activity_workout_day()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.workout_day_id is not null and not exists (
    select 1
    from public.workout_days wd
    join public.workout_plans wp on wp.id = wd.workout_plan_id
    where wd.id = new.workout_day_id
      and wp.user_id = new.user_id
  ) then
    raise exception 'Workout day does not belong to user' using errcode = '23503';
  end if;
  return new;
end;
$$;

create trigger daily_activity_overrides_validate_workout_day
before insert or update on public.daily_activity_overrides
for each row execute function public.validate_daily_activity_workout_day();

create or replace function public.get_daily_activity_context(
  p_activity_date date default current_date
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_override public.daily_activity_overrides%rowtype;
  v_workout_day record;
  v_weekday public.weekday;
  v_profile_days public.weekday[];
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  select *
  into v_override
  from public.daily_activity_overrides
  where user_id = v_user_id
    and activity_date = p_activity_date;

  if found then
    return jsonb_build_object(
      'activity_date', p_activity_date,
      'activity_type', v_override.activity_type,
      'intensity', v_override.intensity,
      'estimated_minutes', v_override.estimated_minutes,
      'nutrition_day_type', v_override.nutrition_day_type,
      'source', 'override',
      'workout_day_id', v_override.workout_day_id,
      'title', case v_override.activity_type
        when 'rest' then 'Descanso planejado'
        when 'cardio' then 'Cardio planejado'
        when 'mixed' then 'Treino misto planejado'
        else 'Treino planejado'
      end,
      'note', v_override.note
    );
  end if;

  v_weekday := case extract(isodow from p_activity_date)::integer
    when 1 then 'monday'::public.weekday
    when 2 then 'tuesday'::public.weekday
    when 3 then 'wednesday'::public.weekday
    when 4 then 'thursday'::public.weekday
    when 5 then 'friday'::public.weekday
    when 6 then 'saturday'::public.weekday
    else 'sunday'::public.weekday
  end;

  select wd.id, wd.title, wd.estimated_minutes
  into v_workout_day
  from public.workout_plans wp
  join public.workout_days wd on wd.workout_plan_id = wp.id
  where wp.user_id = v_user_id
    and wp.status = 'active'
    and wp.start_date <= p_activity_date
    and (wp.end_date is null or wp.end_date >= p_activity_date)
    and wd.weekday = v_weekday
  order by wp.updated_at desc, wd.position
  limit 1;

  if found then
    return jsonb_build_object(
      'activity_date', p_activity_date,
      'activity_type', 'resistance',
      'intensity', 'moderate',
      'estimated_minutes', v_workout_day.estimated_minutes,
      'nutrition_day_type', 'training_day',
      'source', 'workout_plan',
      'workout_day_id', v_workout_day.id,
      'title', v_workout_day.title,
      'note', null
    );
  end if;

  select available_training_days
  into v_profile_days
  from public.profiles
  where id = v_user_id;

  if v_weekday = any(coalesce(v_profile_days, '{}'::public.weekday[])) then
    return jsonb_build_object(
      'activity_date', p_activity_date,
      'activity_type', 'resistance',
      'intensity', 'moderate',
      'estimated_minutes', null,
      'nutrition_day_type', 'training_day',
      'source', 'profile',
      'workout_day_id', null,
      'title', 'Dia de treino',
      'note', null
    );
  end if;

  return jsonb_build_object(
    'activity_date', p_activity_date,
    'activity_type', 'rest',
    'intensity', null,
    'estimated_minutes', 0,
    'nutrition_day_type', 'rest_day',
    'source', 'default',
    'workout_day_id', null,
    'title', 'Dia de descanso',
    'note', null
  );
end;
$$;

create or replace function public.apply_day_activity_adjustment(
  p_adjustment_id uuid
)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_adjustment public.planner_adjustments%rowtype;
  v_current public.daily_activity_overrides%rowtype;
  v_saved_id uuid;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  select *
  into v_adjustment
  from public.planner_adjustments
  where id = p_adjustment_id
    and user_id = v_user_id
  for update;

  if not found then
    raise exception 'Planner adjustment not found' using errcode = 'P0002';
  end if;
  if v_adjustment.adjustment_kind <> 'set_day_activity'
     or v_adjustment.status <> 'pending' then
    raise exception 'Pending day activity adjustment required' using errcode = '22023';
  end if;
  if v_adjustment.expires_at <= now() then
    raise exception 'Planner adjustment expired' using errcode = '40001';
  end if;

  select *
  into v_current
  from public.daily_activity_overrides
  where user_id = v_user_id
    and activity_date = (v_adjustment.after_snapshot ->> 'activity_date')::date;

  if coalesce((v_adjustment.before_snapshot ->> 'existed')::boolean, false) then
    if not found
       or v_current.updated_at::text <> v_adjustment.before_snapshot ->> 'updated_at' then
      raise exception 'Day activity changed after preview' using errcode = '40001';
    end if;
  elsif found then
    raise exception 'Day activity changed after preview' using errcode = '40001';
  end if;

  insert into public.daily_activity_overrides (
    user_id,
    activity_date,
    activity_type,
    intensity,
    estimated_minutes,
    workout_day_id,
    nutrition_day_type,
    source,
    note
  ) values (
    v_user_id,
    (v_adjustment.after_snapshot ->> 'activity_date')::date,
    v_adjustment.after_snapshot ->> 'activity_type',
    nullif(v_adjustment.after_snapshot ->> 'intensity', ''),
    nullif(v_adjustment.after_snapshot ->> 'estimated_minutes', '')::integer,
    nullif(v_adjustment.after_snapshot ->> 'workout_day_id', '')::uuid,
    v_adjustment.after_snapshot ->> 'nutrition_day_type',
    coalesce(v_adjustment.source, 'manual'),
    nullif(v_adjustment.after_snapshot ->> 'note', '')
  )
  on conflict (user_id, activity_date) do update set
    activity_type = excluded.activity_type,
    intensity = excluded.intensity,
    estimated_minutes = excluded.estimated_minutes,
    workout_day_id = excluded.workout_day_id,
    nutrition_day_type = excluded.nutrition_day_type,
    source = excluded.source,
    note = excluded.note
  returning id into v_saved_id;

  update public.planner_adjustments
  set
    target_id = v_saved_id,
    status = 'applied',
    applied_change = after_snapshot,
    confirmed_at = now(),
    applied_at = now(),
    updated_at = now()
  where id = p_adjustment_id;

  return p_adjustment_id;
end;
$$;

create or replace function public.revert_day_activity_adjustment(
  p_adjustment_id uuid
)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_adjustment public.planner_adjustments%rowtype;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  select *
  into v_adjustment
  from public.planner_adjustments
  where id = p_adjustment_id
    and user_id = v_user_id
  for update;

  if not found then
    raise exception 'Planner adjustment not found' using errcode = 'P0002';
  end if;
  if v_adjustment.adjustment_kind <> 'set_day_activity'
     or v_adjustment.status <> 'applied'
     or v_adjustment.reverted_at is not null
     or not v_adjustment.reversible then
    raise exception 'Day activity adjustment cannot be reverted' using errcode = '22023';
  end if;

  if coalesce((v_adjustment.before_snapshot ->> 'existed')::boolean, false) then
    insert into public.daily_activity_overrides (
      user_id,
      activity_date,
      activity_type,
      intensity,
      estimated_minutes,
      workout_day_id,
      nutrition_day_type,
      source,
      note
    ) values (
      v_user_id,
      (v_adjustment.before_snapshot ->> 'activity_date')::date,
      v_adjustment.before_snapshot ->> 'activity_type',
      nullif(v_adjustment.before_snapshot ->> 'intensity', ''),
      nullif(v_adjustment.before_snapshot ->> 'estimated_minutes', '')::integer,
      nullif(v_adjustment.before_snapshot ->> 'workout_day_id', '')::uuid,
      v_adjustment.before_snapshot ->> 'nutrition_day_type',
      coalesce(v_adjustment.before_snapshot ->> 'source', 'manual'),
      nullif(v_adjustment.before_snapshot ->> 'note', '')
    )
    on conflict (user_id, activity_date) do update set
      activity_type = excluded.activity_type,
      intensity = excluded.intensity,
      estimated_minutes = excluded.estimated_minutes,
      workout_day_id = excluded.workout_day_id,
      nutrition_day_type = excluded.nutrition_day_type,
      source = excluded.source,
      note = excluded.note;
  else
    delete from public.daily_activity_overrides
    where user_id = v_user_id
      and activity_date = (v_adjustment.after_snapshot ->> 'activity_date')::date;
  end if;

  update public.planner_adjustments
  set reverted_at = now(), updated_at = now()
  where id = p_adjustment_id;

  return p_adjustment_id;
end;
$$;

revoke all on function public.get_daily_activity_context(date) from public;
revoke all on function public.apply_day_activity_adjustment(uuid) from public;
revoke all on function public.revert_day_activity_adjustment(uuid) from public;
grant execute on function public.get_daily_activity_context(date) to authenticated;
grant execute on function public.apply_day_activity_adjustment(uuid) to authenticated;
grant execute on function public.revert_day_activity_adjustment(uuid) to authenticated;

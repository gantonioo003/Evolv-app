-- Evolv - Planner phase 03
-- Persists generated plans atomically and expands the catalog for timed work.

alter table public.exercises
  add column training_kind text not null default 'resistance'
    check (training_kind in ('resistance', 'cardio', 'mobility')),
  add column planner_modalities text[] not null default '{}'
    check (planner_modalities <@ array[
      'full-gym', 'machines', 'free-weights', 'cables', 'calisthenics',
      'bands', 'functional', 'suspension', 'bodyweight', 'cardio-equipment',
      'running', 'walking', 'cycling', 'rowing', 'stairs', 'swimming',
      'hiit', 'plyometrics', 'yoga-pilates', 'sports', 'mobility', 'stretching'
    ]::text[]);

alter table public.workout_plans
  add column planner_version text,
  add column planner_input jsonb not null default '{}'::jsonb;

alter table public.workout_day_exercises
  alter column sets drop not null,
  alter column min_reps drop not null,
  alter column max_reps drop not null,
  add column prescription_kind text not null default 'repetitions'
    check (prescription_kind in ('repetitions', 'duration')),
  add column duration_minutes integer
    check (duration_minutes is null or duration_minutes between 1 and 240),
  add column planner_role text
    check (planner_role is null or planner_role in (
      'primary', 'secondary', 'accessory', 'core', 'conditioning', 'mobility'
    ));

alter table public.workout_day_exercises
  add constraint workout_day_exercises_prescription_check
  check (
    (
      prescription_kind = 'repetitions'
      and sets is not null
      and min_reps is not null
      and max_reps is not null
      and duration_minutes is null
    )
    or
    (
      prescription_kind = 'duration'
      and sets is null
      and min_reps is null
      and max_reps is null
      and duration_minutes is not null
    )
  );

insert into public.equipment (slug, name, category)
values
  ('treadmill', 'Esteira', 'cardio'),
  ('stationary_bike', 'Bicicleta ergometrica', 'cardio'),
  ('rowing_ergometer', 'Remo ergometrico', 'cardio'),
  ('stair_climber', 'Simulador de escada', 'cardio'),
  ('elliptical', 'Eliptico', 'cardio')
on conflict (slug) do update set
  name = excluded.name,
  category = excluded.category;

insert into public.exercises
  (
    name,
    muscle_group,
    equipment,
    instructions,
    source,
    movement_pattern,
    difficulty,
    is_compound,
    training_kind,
    planner_modalities
  )
values
  (
    'Caminhada continua', 'full_body', 'treadmill',
    'Mantenha ritmo confortavel e postura estavel.', 'evolv', 'locomotion',
    'beginner', true, 'cardio', array['walking', 'cardio-equipment']
  ),
  (
    'Corrida continua', 'full_body', 'treadmill',
    'Corra em ritmo sustentavel, sem transformar toda sessao em esforco maximo.',
    'evolv', 'locomotion', 'intermediate', true, 'cardio',
    array['running', 'cardio-equipment']
  ),
  (
    'Intervalos na esteira', 'full_body', 'treadmill',
    'Alterne blocos curtos de esforco e recuperacao.', 'evolv', 'conditioning',
    'intermediate', true, 'cardio', array['running', 'hiit', 'cardio-equipment']
  ),
  (
    'Bicicleta ergometrica', 'full_body', 'stationary_bike',
    'Pedale com cadencia controlada e ajuste adequado do banco.', 'evolv',
    'locomotion', 'beginner', true, 'cardio', array['cycling', 'cardio-equipment']
  ),
  (
    'Remo ergometrico', 'full_body', 'rowing_ergometer',
    'Coordene pernas, tronco e bracos sem perder a postura.', 'evolv',
    'locomotion', 'intermediate', true, 'cardio', array['rowing', 'cardio-equipment']
  ),
  (
    'Escada ergometrica', 'full_body', 'stair_climber',
    'Suba em ritmo controlado sem apoiar todo o peso nos bracos.', 'evolv',
    'locomotion', 'beginner', true, 'cardio', array['stairs', 'cardio-equipment']
  ),
  (
    'Eliptico', 'full_body', 'elliptical',
    'Mantenha movimento continuo e impacto reduzido.', 'evolv', 'locomotion',
    'beginner', true, 'cardio', array['cardio-equipment']
  ),
  (
    'Mobilidade de quadril', 'glutes', 'bodyweight',
    'Explore a amplitude do quadril sem dor e sem movimentos forcados.', 'evolv',
    'mobility', 'beginner', false, 'mobility', array['mobility', 'yoga-pilates']
  ),
  (
    'Mobilidade toracica', 'upper_back', 'bodyweight',
    'Gire a regiao toracica mantendo quadril e lombar controlados.', 'evolv',
    'mobility', 'beginner', false, 'mobility', array['mobility', 'yoga-pilates']
  ),
  (
    'Mobilidade de ombros', 'front_deltoid', 'bodyweight',
    'Movimente os ombros em amplitude confortavel e controlada.', 'evolv',
    'mobility', 'beginner', false, 'mobility', array['mobility', 'yoga-pilates']
  ),
  (
    'Alongamento de posteriores', 'hamstrings', 'bodyweight',
    'Alongue os posteriores sem rebotes e sem dor aguda.', 'evolv', 'stretching',
    'beginner', false, 'mobility', array['stretching', 'mobility']
  ),
  (
    'Alongamento de peitoral', 'chest', 'bodyweight',
    'Abra o peitoral com respiracao calma e amplitude confortavel.', 'evolv',
    'stretching', 'beginner', false, 'mobility', array['stretching', 'mobility']
  )
on conflict (name) do update set
  muscle_group = excluded.muscle_group,
  equipment = excluded.equipment,
  instructions = excluded.instructions,
  source = excluded.source,
  movement_pattern = excluded.movement_pattern,
  difficulty = excluded.difficulty,
  is_compound = excluded.is_compound,
  training_kind = excluded.training_kind,
  planner_modalities = excluded.planner_modalities,
  updated_at = now();

insert into public.exercise_equipment (exercise_id, equipment_id)
select ex.id, eq.id
from public.exercises ex
join public.equipment eq on eq.slug = ex.equipment
where ex.training_kind in ('cardio', 'mobility')
on conflict do nothing;

insert into public.exercise_muscles (exercise_id, muscle_group_id, role)
select ex.id, mg.id, 'primary'
from public.exercises ex
join public.muscle_groups mg on mg.slug = ex.muscle_group
where ex.training_kind in ('cardio', 'mobility')
on conflict do nothing;

with ranked_active_plans as (
  select
    id,
    row_number() over (
      partition by user_id
      order by updated_at desc, created_at desc, id desc
    ) as position
  from public.workout_plans
  where status = 'active'
)
update public.workout_plans
set status = 'archived'
where id in (
  select id
  from ranked_active_plans
  where position > 1
);

create unique index workout_plans_one_active_per_user_idx
on public.workout_plans(user_id)
where status = 'active';

create or replace function public.create_planner_workout_plan(p_plan jsonb)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_plan_id uuid;
  v_day_id uuid;
  v_day jsonb;
  v_exercise jsonb;
  v_status public.plan_status;
  v_prescription_kind text;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  if nullif(p_plan ->> 'user_id', '')::uuid is distinct from v_user_id then
    raise exception 'The plan owner must match auth.uid()' using errcode = '42501';
  end if;

  if jsonb_typeof(coalesce(p_plan -> 'days', '[]'::jsonb)) <> 'array'
     or jsonb_array_length(coalesce(p_plan -> 'days', '[]'::jsonb)) = 0 then
    raise exception 'A generated plan must contain at least one day' using errcode = '22023';
  end if;

  v_status := coalesce(nullif(p_plan ->> 'status', '')::public.plan_status, 'draft');

  if v_status = 'active' then
    update public.workout_plans
    set status = 'archived'
    where user_id = v_user_id
      and status = 'active';
  end if;

  insert into public.workout_plans (
    user_id,
    goal_id,
    name,
    status,
    start_date,
    end_date,
    weekly_frequency,
    notes,
    split_type,
    split_label,
    planner_version,
    planner_input
  )
  values (
    v_user_id,
    nullif(p_plan ->> 'goal_id', '')::uuid,
    p_plan ->> 'name',
    v_status,
    coalesce(nullif(p_plan ->> 'start_date', '')::date, current_date),
    nullif(p_plan ->> 'end_date', '')::date,
    (p_plan ->> 'weekly_frequency')::integer,
    nullif(p_plan ->> 'notes', ''),
    nullif(p_plan ->> 'split_type', ''),
    nullif(p_plan ->> 'split_label', ''),
    nullif(p_plan ->> 'planner_version', ''),
    coalesce(p_plan -> 'planner_input', '{}'::jsonb)
  )
  returning id into v_plan_id;

  for v_day in
    select value
    from jsonb_array_elements(p_plan -> 'days')
  loop
    insert into public.workout_days (
      workout_plan_id,
      weekday,
      title,
      focus,
      estimated_minutes,
      position
    )
    values (
      v_plan_id,
      (v_day ->> 'weekday')::public.weekday,
      v_day ->> 'title',
      v_day ->> 'focus',
      nullif(v_day ->> 'estimated_minutes', '')::integer,
      (v_day ->> 'position')::integer
    )
    returning id into v_day_id;

    for v_exercise in
      select value
      from jsonb_array_elements(coalesce(v_day -> 'exercises', '[]'::jsonb))
    loop
      v_prescription_kind := coalesce(
        nullif(v_exercise ->> 'prescription_kind', ''),
        'repetitions'
      );

      insert into public.workout_day_exercises (
        workout_day_id,
        exercise_id,
        position,
        sets,
        min_reps,
        max_reps,
        rest_seconds,
        duration_minutes,
        prescription_kind,
        planner_role,
        notes
      )
      values (
        v_day_id,
        (v_exercise ->> 'exercise_id')::uuid,
        (v_exercise ->> 'position')::integer,
        case
          when v_prescription_kind = 'repetitions'
          then (v_exercise ->> 'sets')::integer
        end,
        case
          when v_prescription_kind = 'repetitions'
          then (v_exercise ->> 'min_reps')::integer
        end,
        case
          when v_prescription_kind = 'repetitions'
          then (v_exercise ->> 'max_reps')::integer
        end,
        nullif(v_exercise ->> 'rest_seconds', '')::integer,
        case
          when v_prescription_kind = 'duration'
          then (v_exercise ->> 'duration_minutes')::integer
        end,
        v_prescription_kind,
        nullif(v_exercise ->> 'planner_role', ''),
        nullif(v_exercise ->> 'notes', '')
      );
    end loop;
  end loop;

  return v_plan_id;
end;
$$;

create or replace function public.set_workout_plan_status(
  p_plan_id uuid,
  p_status public.plan_status
)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  if p_status not in ('active', 'archived') then
    raise exception 'Only active or archived statuses are allowed' using errcode = '22023';
  end if;

  if not exists (
    select 1
    from public.workout_plans
    where id = p_plan_id
      and user_id = v_user_id
  ) then
    raise exception 'Workout plan not found' using errcode = 'P0002';
  end if;

  if p_status = 'active' then
    update public.workout_plans
    set status = 'archived'
    where user_id = v_user_id
      and status = 'active'
      and id <> p_plan_id;
  end if;

  update public.workout_plans
  set status = p_status
  where id = p_plan_id
    and user_id = v_user_id;

  return p_plan_id;
end;
$$;

revoke all on function public.create_planner_workout_plan(jsonb) from public;
revoke all on function public.set_workout_plan_status(uuid, public.plan_status) from public;
grant execute on function public.create_planner_workout_plan(jsonb) to authenticated;
grant execute on function public.set_workout_plan_status(uuid, public.plan_status) to authenticated;

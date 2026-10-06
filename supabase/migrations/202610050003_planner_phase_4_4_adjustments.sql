alter table public.planner_adjustments
  add column adjustment_kind text
    check (adjustment_kind is null or adjustment_kind in (
      'move_workout_day', 'replace_exercise', 'replace_meal_item'
    )),
  add column source text not null default 'manual'
    check (source in ('manual', 'coach', 'planner')),
  add column workout_plan_id uuid references public.workout_plans(id) on delete cascade,
  add column diet_plan_id uuid references public.diet_plans(id) on delete cascade,
  add column target_type text
    check (target_type is null or target_type in (
      'workout_day', 'workout_day_exercise', 'meal_item'
    )),
  add column target_id uuid,
  add column preview jsonb not null default '{}'::jsonb,
  add column before_snapshot jsonb not null default '{}'::jsonb,
  add column after_snapshot jsonb not null default '{}'::jsonb,
  add column confirmed_at timestamptz,
  add column rejected_at timestamptz,
  add column reverted_at timestamptz,
  add column expires_at timestamptz not null default (now() + interval '24 hours'),
  add column reversible boolean not null default true;

create index planner_adjustments_user_created_idx
on public.planner_adjustments(user_id, created_at desc);

create index planner_adjustments_pending_idx
on public.planner_adjustments(user_id, expires_at)
where status = 'pending';

create or replace function public.apply_planner_adjustment(p_adjustment_id uuid)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_adjustment public.planner_adjustments%rowtype;
  v_current_weekday public.weekday;
  v_swap_weekday public.weekday;
  v_current_exercise_id uuid;
  v_current_food_id uuid;
  v_day_id uuid;
  v_replacement_exercise_id uuid;
  v_replacement_food_id uuid;
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

  if v_adjustment.status <> 'pending' then
    raise exception 'Only pending adjustments can be applied' using errcode = '22023';
  end if;

  if v_adjustment.expires_at <= now() then
    raise exception 'Planner adjustment expired' using errcode = '40001';
  end if;

  case v_adjustment.adjustment_kind
    when 'move_workout_day' then
      select wd.weekday
      into v_current_weekday
      from public.workout_days wd
      join public.workout_plans wp on wp.id = wd.workout_plan_id
      where wd.id = v_adjustment.target_id
        and wp.id = v_adjustment.workout_plan_id
        and wp.user_id = v_user_id;

      if not found then
        raise exception 'Workout day not found' using errcode = 'P0002';
      end if;

      if v_current_weekday::text <> v_adjustment.before_snapshot ->> 'weekday' then
        raise exception 'Workout day changed after preview' using errcode = '40001';
      end if;

      if nullif(v_adjustment.before_snapshot ->> 'swap_day_id', '') is not null then
        select wd.weekday
        into v_swap_weekday
        from public.workout_days wd
        join public.workout_plans wp on wp.id = wd.workout_plan_id
        where wd.id = (v_adjustment.before_snapshot ->> 'swap_day_id')::uuid
          and wp.id = v_adjustment.workout_plan_id
          and wp.user_id = v_user_id;

        if not found
           or v_swap_weekday::text <> v_adjustment.before_snapshot ->> 'swap_weekday' then
          raise exception 'Swap day changed after preview' using errcode = '40001';
        end if;

        update public.workout_days
        set weekday = (v_adjustment.after_snapshot ->> 'swap_weekday')::public.weekday
        where id = (v_adjustment.before_snapshot ->> 'swap_day_id')::uuid;
      end if;

      update public.workout_days
      set weekday = (v_adjustment.after_snapshot ->> 'weekday')::public.weekday
      where id = v_adjustment.target_id;

      update public.workout_plans
      set updated_at = now()
      where id = v_adjustment.workout_plan_id;

    when 'replace_exercise' then
      select wde.exercise_id, wde.workout_day_id
      into v_current_exercise_id, v_day_id
      from public.workout_day_exercises wde
      join public.workout_days wd on wd.id = wde.workout_day_id
      join public.workout_plans wp on wp.id = wd.workout_plan_id
      where wde.id = v_adjustment.target_id
        and wp.id = v_adjustment.workout_plan_id
        and wp.user_id = v_user_id;

      if not found then
        raise exception 'Workout exercise not found' using errcode = 'P0002';
      end if;

      if v_current_exercise_id::text <> v_adjustment.before_snapshot ->> 'exercise_id' then
        raise exception 'Workout exercise changed after preview' using errcode = '40001';
      end if;

      v_replacement_exercise_id := (v_adjustment.after_snapshot ->> 'exercise_id')::uuid;

      if exists (
        select 1
        from public.workout_day_exercises
        where workout_day_id = v_day_id
          and exercise_id = v_replacement_exercise_id
          and id <> v_adjustment.target_id
      ) then
        raise exception 'Replacement exercise already exists in this day' using errcode = '22023';
      end if;

      if not exists (
        select 1
        from public.exercises current_exercise
        join public.exercises replacement on replacement.id = v_replacement_exercise_id
        where current_exercise.id = v_current_exercise_id
          and current_exercise.training_kind = replacement.training_kind
          and (
            current_exercise.training_kind <> 'resistance'
            or current_exercise.muscle_group = replacement.muscle_group
            or current_exercise.movement_pattern = replacement.movement_pattern
          )
      ) then
        raise exception 'Replacement exercise is not compatible' using errcode = '22023';
      end if;

      update public.workout_day_exercises
      set exercise_id = v_replacement_exercise_id
      where id = v_adjustment.target_id;

      update public.workout_plans
      set updated_at = now()
      where id = v_adjustment.workout_plan_id;

    when 'replace_meal_item' then
      select mi.food_id
      into v_current_food_id
      from public.meal_items mi
      join public.meals m on m.id = mi.meal_id
      join public.diet_plans dp on dp.id = m.diet_plan_id
      where mi.id = v_adjustment.target_id
        and dp.id = v_adjustment.diet_plan_id
        and dp.user_id = v_user_id;

      if not found then
        raise exception 'Meal item not found' using errcode = 'P0002';
      end if;

      if v_current_food_id is distinct from nullif(v_adjustment.before_snapshot ->> 'food_id', '')::uuid then
        raise exception 'Meal item changed after preview' using errcode = '40001';
      end if;

      v_replacement_food_id := (v_adjustment.after_snapshot ->> 'food_id')::uuid;

      if not exists (
        select 1
        from public.meal_items mi,
          jsonb_array_elements(mi.substitutions) substitution
        where mi.id = v_adjustment.target_id
          and substitution ->> 'food_id' = v_replacement_food_id::text
      ) then
        raise exception 'Food is not an approved substitution' using errcode = '22023';
      end if;

      if not exists (
        select 1
        from public.foods
        where id = v_replacement_food_id
          and (user_id is null or user_id = v_user_id)
      ) then
        raise exception 'Replacement food is not accessible' using errcode = '42501';
      end if;

      update public.meal_items
      set
        food_id = v_replacement_food_id,
        name = v_adjustment.after_snapshot ->> 'name',
        amount = v_adjustment.after_snapshot ->> 'amount',
        quantity = (v_adjustment.after_snapshot ->> 'quantity')::numeric,
        unit = v_adjustment.after_snapshot ->> 'unit',
        nutrition_role = v_adjustment.after_snapshot ->> 'nutrition_role',
        substitution_group = v_adjustment.after_snapshot ->> 'nutrition_role',
        calories_kcal = (v_adjustment.after_snapshot ->> 'calories_kcal')::numeric,
        protein_g = (v_adjustment.after_snapshot ->> 'protein_g')::numeric,
        carbohydrate_g = (v_adjustment.after_snapshot ->> 'carbohydrate_g')::numeric,
        fat_g = (v_adjustment.after_snapshot ->> 'fat_g')::numeric,
        fiber_g = (v_adjustment.after_snapshot ->> 'fiber_g')::numeric,
        substitutions = coalesce(v_adjustment.after_snapshot -> 'substitutions', '[]'::jsonb)
      where id = v_adjustment.target_id;

      update public.diet_plans
      set updated_at = now()
      where id = v_adjustment.diet_plan_id;

    else
      raise exception 'Unsupported planner adjustment' using errcode = '22023';
  end case;

  update public.planner_adjustments
  set
    status = 'applied',
    applied_change = after_snapshot,
    confirmed_at = now(),
    applied_at = now(),
    updated_at = now()
  where id = p_adjustment_id;

  return p_adjustment_id;
end;
$$;

create or replace function public.reject_planner_adjustment(p_adjustment_id uuid)
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

  update public.planner_adjustments
  set status = 'rejected', rejected_at = now(), updated_at = now()
  where id = p_adjustment_id
    and user_id = v_user_id
    and status = 'pending';

  if not found then
    raise exception 'Pending planner adjustment not found' using errcode = 'P0002';
  end if;

  return p_adjustment_id;
end;
$$;

create or replace function public.revert_planner_adjustment(p_adjustment_id uuid)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_adjustment public.planner_adjustments%rowtype;
  v_current_weekday public.weekday;
  v_current_exercise_id uuid;
  v_current_food_id uuid;
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

  if v_adjustment.status <> 'applied'
     or v_adjustment.reverted_at is not null
     or not v_adjustment.reversible then
    raise exception 'Planner adjustment cannot be reverted' using errcode = '22023';
  end if;

  case v_adjustment.adjustment_kind
    when 'move_workout_day' then
      select weekday into v_current_weekday
      from public.workout_days
      where id = v_adjustment.target_id;

      if not found
         or v_current_weekday::text <> v_adjustment.after_snapshot ->> 'weekday' then
        raise exception 'Workout day changed after adjustment' using errcode = '40001';
      end if;

      if nullif(v_adjustment.after_snapshot ->> 'swap_day_id', '') is not null then
        update public.workout_days
        set weekday = (v_adjustment.before_snapshot ->> 'swap_weekday')::public.weekday
        where id = (v_adjustment.after_snapshot ->> 'swap_day_id')::uuid;
      end if;

      update public.workout_days
      set weekday = (v_adjustment.before_snapshot ->> 'weekday')::public.weekday
      where id = v_adjustment.target_id;

      update public.workout_plans set updated_at = now()
      where id = v_adjustment.workout_plan_id and user_id = v_user_id;

    when 'replace_exercise' then
      select wde.exercise_id into v_current_exercise_id
      from public.workout_day_exercises wde
      join public.workout_days wd on wd.id = wde.workout_day_id
      join public.workout_plans wp on wp.id = wd.workout_plan_id
      where wde.id = v_adjustment.target_id and wp.user_id = v_user_id;

      if not found
         or v_current_exercise_id::text <> v_adjustment.after_snapshot ->> 'exercise_id' then
        raise exception 'Workout exercise changed after adjustment' using errcode = '40001';
      end if;

      update public.workout_day_exercises
      set exercise_id = (v_adjustment.before_snapshot ->> 'exercise_id')::uuid
      where id = v_adjustment.target_id;

      update public.workout_plans set updated_at = now()
      where id = v_adjustment.workout_plan_id and user_id = v_user_id;

    when 'replace_meal_item' then
      select mi.food_id into v_current_food_id
      from public.meal_items mi
      join public.meals m on m.id = mi.meal_id
      join public.diet_plans dp on dp.id = m.diet_plan_id
      where mi.id = v_adjustment.target_id and dp.user_id = v_user_id;

      if not found
         or v_current_food_id::text <> v_adjustment.after_snapshot ->> 'food_id' then
        raise exception 'Meal item changed after adjustment' using errcode = '40001';
      end if;

      update public.meal_items
      set
        food_id = nullif(v_adjustment.before_snapshot ->> 'food_id', '')::uuid,
        name = v_adjustment.before_snapshot ->> 'name',
        amount = v_adjustment.before_snapshot ->> 'amount',
        quantity = nullif(v_adjustment.before_snapshot ->> 'quantity', '')::numeric,
        unit = v_adjustment.before_snapshot ->> 'unit',
        nutrition_role = v_adjustment.before_snapshot ->> 'nutrition_role',
        substitution_group = v_adjustment.before_snapshot ->> 'nutrition_role',
        calories_kcal = nullif(v_adjustment.before_snapshot ->> 'calories_kcal', '')::numeric,
        protein_g = nullif(v_adjustment.before_snapshot ->> 'protein_g', '')::numeric,
        carbohydrate_g = nullif(v_adjustment.before_snapshot ->> 'carbohydrate_g', '')::numeric,
        fat_g = nullif(v_adjustment.before_snapshot ->> 'fat_g', '')::numeric,
        fiber_g = nullif(v_adjustment.before_snapshot ->> 'fiber_g', '')::numeric,
        substitutions = coalesce(v_adjustment.before_snapshot -> 'substitutions', '[]'::jsonb)
      where id = v_adjustment.target_id;

      update public.diet_plans set updated_at = now()
      where id = v_adjustment.diet_plan_id and user_id = v_user_id;

    else
      raise exception 'Unsupported planner adjustment' using errcode = '22023';
  end case;

  update public.planner_adjustments
  set reverted_at = now(), updated_at = now()
  where id = p_adjustment_id;

  return p_adjustment_id;
end;
$$;

revoke all on function public.apply_planner_adjustment(uuid) from public;
revoke all on function public.reject_planner_adjustment(uuid) from public;
revoke all on function public.revert_planner_adjustment(uuid) from public;
grant execute on function public.apply_planner_adjustment(uuid) to authenticated;
grant execute on function public.reject_planner_adjustment(uuid) to authenticated;
grant execute on function public.revert_planner_adjustment(uuid) to authenticated;

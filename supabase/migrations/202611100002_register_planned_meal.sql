alter table public.food_logs
  add column planned_meal_id uuid,
  add column planned_meal_date date,
  add constraint food_logs_planned_meal_pair
    check ((planned_meal_id is null) = (planned_meal_date is null)),
  add constraint food_logs_planned_meal_once
    unique (user_id, planned_meal_id, planned_meal_date);

-- Keep the original meal ID even if its plan is deleted. The log is a snapshot.
create function public.set_planned_meal_registration(
  p_meal_id uuid,
  p_local_date date,
  p_logged_at timestamptz,
  p_registered boolean
)
returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_meal public.meals%rowtype;
  v_log_id uuid;
  v_item_count integer;
begin
  if v_user is null then
    raise insufficient_privilege using message = 'AUTHENTICATION_REQUIRED';
  end if;
  if p_meal_id is null or p_local_date is null or p_logged_at is null
     or p_registered is null
     or abs(p_local_date - (p_logged_at at time zone 'UTC')::date) > 1 then
    raise invalid_parameter_value using message = 'INVALID_MEAL_REGISTRATION';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    v_user::text || ':' || p_meal_id::text || ':' || p_local_date::text, 0
  ));

  if not p_registered then
    delete from public.food_logs
    where user_id = v_user and planned_meal_id = p_meal_id
      and planned_meal_date = p_local_date;
    return false;
  end if;

  if exists (
    select 1 from public.food_logs
    where user_id = v_user and planned_meal_id = p_meal_id
      and planned_meal_date = p_local_date
  ) then
    return true;
  end if;

  select m.* into v_meal
  from public.meals m
  join public.diet_plans d on d.id = m.diet_plan_id
  where m.id = p_meal_id and d.user_id = v_user and d.status = 'active'
  for share of m, d;
  if not found then
    raise no_data_found using message = 'PLANNED_MEAL_NOT_FOUND';
  end if;

  insert into public.food_logs (
    user_id, logged_at, description, meal_name, planned_meal_id, planned_meal_date
  ) values (
    v_user, p_logged_at, v_meal.description, v_meal.name, p_meal_id, p_local_date
  ) returning id into v_log_id;

  with portions as materialized (
    select * from public.meal_items where meal_id = p_meal_id
  ), recorded as (
    insert into public.food_log_items (
      user_id, food_log_id, food_id, food_name, quantity, unit, amount_grams,
      calories_kcal, protein_g, carbohydrate_g, fat_g, fiber_g
    )
    select v_user, v_log_id, food_id, name, quantity, unit,
      case when lower(unit) = 'g' then quantity end,
      calories_kcal, protein_g, carbohydrate_g, fat_g, coalesce(fiber_g, 0)
    from portions
    where not exists (
      select 1 from portions
      where quantity is null or nullif(btrim(unit), '') is null or calories_kcal is null
        or protein_g is null or carbohydrate_g is null or fat_g is null
    )
    returning id
  )
  select count(*) into v_item_count from recorded;

  if v_item_count = 0 then
    raise invalid_parameter_value using message = 'MEAL_PORTIONS_UNAVAILABLE';
  end if;
  return true;
end;
$$;

revoke execute on function public.set_planned_meal_registration(uuid, date, timestamptz, boolean)
  from public, anon;
grant execute on function public.set_planned_meal_registration(uuid, date, timestamptz, boolean)
  to authenticated;

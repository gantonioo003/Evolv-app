alter table public.diet_plans
  add column flexible_meal_frequency text not null default 'none'
    check (flexible_meal_frequency in ('none', 'weekly', 'fortnightly')),
  add column flexible_meal_weekday public.weekday,
  add column alcohol_frequency text not null default 'none'
    check (alcohol_frequency in ('none', 'fortnightly', 'monthly')),
  add column alcohol_preferred_weekday public.weekday,
  add column alcohol_max_servings integer
    check (alcohol_max_servings is null or alcohol_max_servings between 1 and 4);

create or replace function public.create_planner_diet_plan_v3(p_plan jsonb)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_plan_id uuid;
  v_flexible_frequency text := coalesce(nullif(p_plan ->> 'flexible_meal_frequency', ''), 'none');
  v_alcohol_frequency text := coalesce(nullif(p_plan ->> 'alcohol_frequency', ''), 'none');
begin
  if v_flexible_frequency not in ('none', 'weekly', 'fortnightly') then
    raise exception 'Invalid flexible meal frequency' using errcode = '22023';
  end if;

  if v_alcohol_frequency not in ('none', 'fortnightly', 'monthly') then
    raise exception 'Invalid alcohol frequency' using errcode = '22023';
  end if;

  v_plan_id := public.create_planner_diet_plan_v2(p_plan);

  update public.diet_plans
  set
    flexible_meal_frequency = v_flexible_frequency,
    flexible_meal_weekday = case
      when v_flexible_frequency = 'none' then null
      else nullif(p_plan ->> 'flexible_meal_weekday', '')::public.weekday
    end,
    alcohol_frequency = v_alcohol_frequency,
    alcohol_preferred_weekday = case
      when v_alcohol_frequency = 'none' then null
      else nullif(p_plan ->> 'alcohol_preferred_weekday', '')::public.weekday
    end,
    alcohol_max_servings = case
      when v_alcohol_frequency = 'none' then null
      else coalesce(nullif(p_plan ->> 'alcohol_max_servings', '')::integer, 1)
    end
  where id = v_plan_id
    and user_id = auth.uid();

  return v_plan_id;
end;
$$;

revoke all on function public.create_planner_diet_plan_v3(jsonb) from public;
grant execute on function public.create_planner_diet_plan_v3(jsonb) to authenticated;

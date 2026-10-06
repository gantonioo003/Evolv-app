alter table public.diet_plans
  add column uses_day_variants boolean not null default false,
  add column training_day_calories_target integer
    check (training_day_calories_target is null or training_day_calories_target between 800 and 8000),
  add column rest_day_calories_target integer
    check (rest_day_calories_target is null or rest_day_calories_target between 800 and 8000);

alter table public.meals
  drop constraint if exists meals_diet_plan_id_position_key,
  add column day_type text not null default 'every_day'
    check (day_type in ('every_day', 'training_day', 'rest_day')),
  add constraint meals_plan_day_type_position_key
    unique (diet_plan_id, day_type, position);

create or replace function public.create_planner_diet_plan_v2(p_plan jsonb)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_plan_id uuid;
  v_meal_id uuid;
  v_meal jsonb;
  v_item jsonb;
  v_food_id uuid;
  v_seed_plan jsonb;
  v_uses_variants boolean := coalesce((p_plan ->> 'uses_day_variants')::boolean, false);
begin
  if not v_uses_variants then
    v_plan_id := public.create_planner_diet_plan(p_plan);
  else
    if jsonb_array_length(coalesce(p_plan -> 'meals', '[]'::jsonb)) = 0 then
      raise exception 'A generated diet plan must contain at least one meal' using errcode = '22023';
    end if;

    v_seed_plan := jsonb_set(
      p_plan,
      '{meals}',
      jsonb_build_array((p_plan -> 'meals') -> 0)
    );
    v_plan_id := public.create_planner_diet_plan(v_seed_plan);
    delete from public.meals where diet_plan_id = v_plan_id;

    for v_meal in
      select value
      from jsonb_array_elements(p_plan -> 'meals')
    loop
      insert into public.meals (
        diet_plan_id,
        name,
        meal_time,
        position,
        day_type,
        calories_target,
        protein_target_g,
        carbohydrate_target_g,
        fat_target_g,
        description,
        actual_calories,
        actual_protein_g,
        actual_carbohydrate_g,
        actual_fat_g,
        actual_fiber_g
      )
      values (
        v_plan_id,
        v_meal ->> 'name',
        nullif(v_meal ->> 'meal_time', '')::time,
        (v_meal ->> 'position')::integer,
        coalesce(nullif(v_meal ->> 'day_type', ''), 'every_day'),
        (v_meal ->> 'calories_target')::integer,
        (v_meal ->> 'protein_target_g')::integer,
        (v_meal ->> 'carbohydrate_target_g')::integer,
        (v_meal ->> 'fat_target_g')::integer,
        nullif(v_meal ->> 'description', ''),
        nullif(v_meal ->> 'actual_calories', '')::numeric,
        nullif(v_meal ->> 'actual_protein_g', '')::numeric,
        nullif(v_meal ->> 'actual_carbohydrate_g', '')::numeric,
        nullif(v_meal ->> 'actual_fat_g', '')::numeric,
        nullif(v_meal ->> 'actual_fiber_g', '')::numeric
      )
      returning id into v_meal_id;

      for v_item in
        select value
        from jsonb_array_elements(coalesce(v_meal -> 'items', '[]'::jsonb))
      loop
        v_food_id := nullif(v_item ->> 'food_id', '')::uuid;

        if v_food_id is not null and not exists (
          select 1
          from public.foods
          where id = v_food_id
            and (user_id is null or user_id = auth.uid())
        ) then
          raise exception 'Food is not accessible' using errcode = '42501';
        end if;

        insert into public.meal_items (
          meal_id,
          food_id,
          name,
          amount,
          quantity,
          unit,
          substitution_group,
          nutrition_role,
          calories_kcal,
          protein_g,
          carbohydrate_g,
          fat_g,
          fiber_g,
          substitutions,
          notes
        )
        values (
          v_meal_id,
          v_food_id,
          v_item ->> 'name',
          nullif(v_item ->> 'amount', ''),
          nullif(v_item ->> 'quantity', '')::numeric,
          nullif(v_item ->> 'unit', ''),
          nullif(v_item ->> 'substitution_group', ''),
          nullif(v_item ->> 'nutrition_role', ''),
          nullif(v_item ->> 'calories_kcal', '')::numeric,
          nullif(v_item ->> 'protein_g', '')::numeric,
          nullif(v_item ->> 'carbohydrate_g', '')::numeric,
          nullif(v_item ->> 'fat_g', '')::numeric,
          nullif(v_item ->> 'fiber_g', '')::numeric,
          coalesce(v_item -> 'substitutions', '[]'::jsonb),
          nullif(v_item ->> 'notes', '')
        );
      end loop;
    end loop;
  end if;

  update public.diet_plans
  set
    uses_day_variants = v_uses_variants,
    training_day_calories_target = nullif(p_plan ->> 'training_day_calories_target', '')::integer,
    rest_day_calories_target = nullif(p_plan ->> 'rest_day_calories_target', '')::integer
  where id = v_plan_id
    and user_id = auth.uid();

  return v_plan_id;
end;
$$;

revoke all on function public.create_planner_diet_plan_v2(jsonb) from public;
grant execute on function public.create_planner_diet_plan_v2(jsonb) to authenticated;

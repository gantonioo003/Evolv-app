-- Evolv - Nutrition Planner phase 04.3
-- Adds a planner-ready food catalog and persists generated diet plans atomically.

alter table public.foods
  add column nutrition_roles text[] not null default '{}'
    check (nutrition_roles <@ array[
      'protein_source', 'carbohydrate_source', 'vegetable_or_fruit',
      'fat_source', 'optional_extra'
    ]::text[]),
  add column compatible_food_styles text[] not null default array['custom']::text[]
    check (compatible_food_styles <@ array[
      'omnivore', 'pescatarian', 'vegetarian', 'vegan', 'custom'
    ]::text[]),
  add column planner_meal_types text[] not null default array['any']::text[]
    check (planner_meal_types <@ array[
      'breakfast', 'main', 'snack', 'any'
    ]::text[]),
  add column planner_tags text[] not null default '{}',
  add column allergens text[] not null default '{}',
  add column processing_level text not null default 'unknown'
    check (processing_level in (
      'in_natura', 'minimally_processed', 'processed',
      'ultra_processed', 'unknown'
    )),
  add column planner_minimum_amount numeric(9,3)
    check (planner_minimum_amount is null or planner_minimum_amount > 0),
  add column planner_maximum_amount numeric(9,3)
    check (planner_maximum_amount is null or planner_maximum_amount > 0),
  add column planner_amount_step numeric(9,3)
    check (planner_amount_step is null or planner_amount_step > 0),
  add column planner_default_amount numeric(9,3)
    check (planner_default_amount is null or planner_default_amount > 0),
  add constraint foods_planner_amount_range_check
    check (
      planner_minimum_amount is null
      or planner_maximum_amount is null
      or planner_maximum_amount >= planner_minimum_amount
    );

alter table public.diet_plans
  add column planner_version text,
  add column planner_input jsonb not null default '{}'::jsonb,
  add column nutrition_phase text
    check (nutrition_phase is null or nutrition_phase in (
      'mass_gain', 'fat_loss', 'maintenance', 'recomposition',
      'diet_break', 'custom'
    )),
  add column macro_pattern text
    check (macro_pattern is null or macro_pattern in (
      'balanced', 'high_carb_performance', 'low_carb', 'ketogenic', 'custom'
    )),
  add column food_style text
    check (food_style is null or food_style in (
      'omnivore', 'pescatarian', 'vegetarian', 'vegan', 'custom'
    )),
  add column meal_schedule text
    check (meal_schedule is null or meal_schedule in (
      'regular', 'time_restricted', 'custom'
    ));

alter table public.meals
  add column actual_calories numeric(9,3)
    check (actual_calories is null or actual_calories >= 0),
  add column actual_protein_g numeric(9,3)
    check (actual_protein_g is null or actual_protein_g >= 0),
  add column actual_carbohydrate_g numeric(9,3)
    check (actual_carbohydrate_g is null or actual_carbohydrate_g >= 0),
  add column actual_fat_g numeric(9,3)
    check (actual_fat_g is null or actual_fat_g >= 0),
  add column actual_fiber_g numeric(9,3)
    check (actual_fiber_g is null or actual_fiber_g >= 0);

alter table public.meal_items
  add column nutrition_role text
    check (nutrition_role is null or nutrition_role in (
      'protein_source', 'carbohydrate_source', 'vegetable_or_fruit',
      'fat_source', 'optional_extra'
    )),
  add column calories_kcal numeric(9,3)
    check (calories_kcal is null or calories_kcal >= 0),
  add column protein_g numeric(9,3)
    check (protein_g is null or protein_g >= 0),
  add column carbohydrate_g numeric(9,3)
    check (carbohydrate_g is null or carbohydrate_g >= 0),
  add column fat_g numeric(9,3)
    check (fat_g is null or fat_g >= 0),
  add column fiber_g numeric(9,3)
    check (fiber_g is null or fiber_g >= 0),
  add column substitutions jsonb not null default '[]'::jsonb
    check (jsonb_typeof(substitutions) = 'array');

with ranked_active_plans as (
  select
    id,
    row_number() over (
      partition by user_id
      order by updated_at desc, created_at desc, id desc
    ) as position
  from public.diet_plans
  where status = 'active'
)
update public.diet_plans
set status = 'archived'
where id in (
  select id
  from ranked_active_plans
  where position > 1
);

create unique index diet_plans_one_active_per_user_idx
on public.diet_plans(user_id)
where status = 'active';

insert into public.foods (
  source,
  external_id,
  name,
  locale,
  data_type,
  base_amount,
  base_unit,
  calories_kcal,
  protein_g,
  carbohydrate_g,
  fat_g,
  fiber_g,
  is_verified,
  nutrition_roles,
  compatible_food_styles,
  planner_meal_types,
  planner_tags,
  allergens,
  processing_level,
  planner_minimum_amount,
  planner_maximum_amount,
  planner_amount_step,
  planner_default_amount
)
values
  ('evolv_reference', 'chicken-breast', 'Peito de frango', 'pt-BR', 'generic', 100, 'g', 165, 31, 0, 3.6, 0, false, array['protein_source'], array['omnivore','custom'], array['main'], array['ave'], '{}', 'minimally_processed', 50, 300, 10, 120),
  ('evolv_reference', 'lean-beef', 'Carne bovina magra', 'pt-BR', 'generic', 100, 'g', 219, 26, 0, 12, 0, false, array['protein_source'], array['omnivore','custom'], array['main'], array['carne'], '{}', 'minimally_processed', 50, 300, 10, 120),
  ('evolv_reference', 'salmon', 'Salmao', 'pt-BR', 'generic', 100, 'g', 208, 25, 0, 12, 0, false, array['protein_source'], array['omnivore','pescatarian','custom'], array['main'], array['peixe'], array['peixe'], 'in_natura', 50, 300, 10, 120),
  ('evolv_reference', 'tuna', 'Atum em agua', 'pt-BR', 'generic', 100, 'g', 116, 26, 0, 1, 0, false, array['protein_source'], array['omnivore','pescatarian','custom'], array['main','snack'], array['peixe'], array['peixe'], 'processed', 50, 250, 10, 100),
  ('evolv_reference', 'egg', 'Ovo', 'pt-BR', 'generic', 100, 'g', 143, 13, 0.7, 9.5, 0, false, array['protein_source'], array['omnivore','pescatarian','vegetarian','custom'], array['breakfast','main','snack'], array['ovo'], array['ovo'], 'minimally_processed', 50, 250, 25, 100),
  ('evolv_reference', 'plain-yogurt', 'Iogurte natural', 'pt-BR', 'generic', 100, 'g', 62, 5, 7, 1.5, 0, false, array['protein_source'], array['omnivore','pescatarian','vegetarian','custom'], array['breakfast','snack'], array['laticinio'], array['leite','lactose'], 'minimally_processed', 100, 300, 25, 170),
  ('evolv_reference', 'tofu', 'Tofu', 'pt-BR', 'generic', 100, 'g', 120, 12, 2, 7, 1, false, array['protein_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['any'], array['soja'], array['soja'], 'minimally_processed', 50, 350, 10, 150),
  ('evolv_reference', 'lentils', 'Lentilha cozida', 'pt-BR', 'generic', 100, 'g', 116, 9, 20, 0.4, 7.9, false, array['protein_source','carbohydrate_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['main'], array['leguminosa'], '{}', 'minimally_processed', 50, 350, 10, 150),
  ('evolv_reference', 'black-beans', 'Feijao preto cozido', 'pt-BR', 'generic', 100, 'g', 132, 8.9, 23.7, 0.5, 8.7, false, array['protein_source','carbohydrate_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['main'], array['leguminosa'], '{}', 'minimally_processed', 50, 350, 10, 120),
  ('evolv_reference', 'chickpeas', 'Grao-de-bico cozido', 'pt-BR', 'generic', 100, 'g', 164, 8.9, 27.4, 2.6, 7.6, false, array['protein_source','carbohydrate_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['main','snack'], array['leguminosa'], '{}', 'minimally_processed', 50, 350, 10, 120),
  ('evolv_reference', 'brown-rice', 'Arroz integral cozido', 'pt-BR', 'generic', 100, 'g', 124, 2.6, 25.8, 1, 2.7, false, array['carbohydrate_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['main'], array['cereal'], '{}', 'minimally_processed', 50, 400, 10, 150),
  ('evolv_reference', 'white-rice', 'Arroz branco cozido', 'pt-BR', 'generic', 100, 'g', 130, 2.7, 28.2, 0.3, 0.4, false, array['carbohydrate_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['main'], array['cereal'], '{}', 'minimally_processed', 50, 400, 10, 150),
  ('evolv_reference', 'potato', 'Batata cozida', 'pt-BR', 'generic', 100, 'g', 87, 1.9, 20, 0.1, 1.8, false, array['carbohydrate_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['main'], array['tuberculo'], '{}', 'minimally_processed', 50, 500, 10, 180),
  ('evolv_reference', 'sweet-potato', 'Batata-doce cozida', 'pt-BR', 'generic', 100, 'g', 90, 2, 20.7, 0.2, 3.3, false, array['carbohydrate_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['main'], array['tuberculo'], '{}', 'minimally_processed', 50, 500, 10, 180),
  ('evolv_reference', 'oats', 'Aveia', 'pt-BR', 'generic', 100, 'g', 389, 16.9, 66.3, 6.9, 10.6, false, array['carbohydrate_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['breakfast','snack'], array['cereal'], array['gluten'], 'minimally_processed', 20, 150, 5, 50),
  ('evolv_reference', 'whole-wheat-bread', 'Pao integral', 'pt-BR', 'generic', 100, 'g', 247, 13, 41, 4.2, 7, false, array['carbohydrate_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['breakfast','snack'], array['cereal'], array['gluten'], 'processed', 25, 200, 25, 50),
  ('evolv_reference', 'broccoli', 'Brocolis', 'pt-BR', 'generic', 100, 'g', 35, 2.4, 7.2, 0.4, 3.3, false, array['vegetable_or_fruit'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['main'], array['vegetal'], '{}', 'in_natura', 50, 300, 10, 120),
  ('evolv_reference', 'carrot', 'Cenoura', 'pt-BR', 'generic', 100, 'g', 41, 0.9, 9.6, 0.2, 2.8, false, array['vegetable_or_fruit'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['main','snack'], array['vegetal'], '{}', 'in_natura', 50, 300, 10, 100),
  ('evolv_reference', 'leafy-greens', 'Folhas verdes', 'pt-BR', 'generic', 100, 'g', 25, 2, 4, 0.4, 2.5, false, array['vegetable_or_fruit'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['main'], array['vegetal'], '{}', 'in_natura', 30, 250, 10, 80),
  ('evolv_reference', 'banana', 'Banana', 'pt-BR', 'generic', 100, 'g', 89, 1.1, 22.8, 0.3, 2.6, false, array['vegetable_or_fruit'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['breakfast','snack'], array['fruta'], '{}', 'in_natura', 50, 300, 10, 100),
  ('evolv_reference', 'apple', 'Maca', 'pt-BR', 'generic', 100, 'g', 52, 0.3, 13.8, 0.2, 2.4, false, array['vegetable_or_fruit'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['breakfast','snack'], array['fruta'], '{}', 'in_natura', 50, 300, 10, 130),
  ('evolv_reference', 'berries', 'Frutas vermelhas', 'pt-BR', 'generic', 100, 'g', 50, 0.7, 11, 0.3, 4.5, false, array['vegetable_or_fruit'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['breakfast','snack'], array['fruta'], '{}', 'in_natura', 50, 300, 10, 100),
  ('evolv_reference', 'olive-oil', 'Azeite de oliva', 'pt-BR', 'generic', 10, 'ml', 90, 0, 0, 10, 0, false, array['fat_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['any'], array['oleo'], '{}', 'processed', 5, 40, 5, 10),
  ('evolv_reference', 'avocado', 'Abacate', 'pt-BR', 'generic', 100, 'g', 160, 2, 8.5, 14.7, 6.7, false, array['fat_source','vegetable_or_fruit'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['any'], array['fruta'], '{}', 'in_natura', 30, 200, 10, 80),
  ('evolv_reference', 'peanut-butter', 'Pasta de amendoim', 'pt-BR', 'generic', 20, 'g', 118, 5, 4, 10, 1.2, false, array['fat_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['breakfast','snack'], array['oleaginosa'], array['amendoim'], 'processed', 10, 50, 5, 20),
  ('evolv_reference', 'mixed-nuts', 'Castanhas', 'pt-BR', 'generic', 30, 'g', 180, 5, 6, 16, 3, false, array['fat_source'], array['omnivore','pescatarian','vegetarian','vegan','custom'], array['breakfast','snack'], array['oleaginosa'], array['castanhas'], 'minimally_processed', 10, 60, 5, 30)
on conflict (source, external_id) where external_id is not null do update set
  name = excluded.name,
  base_amount = excluded.base_amount,
  base_unit = excluded.base_unit,
  calories_kcal = excluded.calories_kcal,
  protein_g = excluded.protein_g,
  carbohydrate_g = excluded.carbohydrate_g,
  fat_g = excluded.fat_g,
  fiber_g = excluded.fiber_g,
  nutrition_roles = excluded.nutrition_roles,
  compatible_food_styles = excluded.compatible_food_styles,
  planner_meal_types = excluded.planner_meal_types,
  planner_tags = excluded.planner_tags,
  allergens = excluded.allergens,
  processing_level = excluded.processing_level,
  planner_minimum_amount = excluded.planner_minimum_amount,
  planner_maximum_amount = excluded.planner_maximum_amount,
  planner_amount_step = excluded.planner_amount_step,
  planner_default_amount = excluded.planner_default_amount,
  updated_at = now();

create or replace function public.create_planner_diet_plan(p_plan jsonb)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_plan_id uuid;
  v_meal_id uuid;
  v_meal jsonb;
  v_item jsonb;
  v_food_id uuid;
  v_status public.plan_status;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  if nullif(p_plan ->> 'user_id', '')::uuid is distinct from v_user_id then
    raise exception 'The plan owner must match auth.uid()' using errcode = '42501';
  end if;

  if jsonb_typeof(coalesce(p_plan -> 'meals', '[]'::jsonb)) <> 'array'
     or jsonb_array_length(coalesce(p_plan -> 'meals', '[]'::jsonb)) = 0 then
    raise exception 'A generated diet plan must contain at least one meal' using errcode = '22023';
  end if;

  v_status := coalesce(nullif(p_plan ->> 'status', '')::public.plan_status, 'draft');

  if v_status = 'active' then
    update public.diet_plans
    set status = 'archived'
    where user_id = v_user_id
      and status = 'active';
  end if;

  insert into public.diet_plans (
    user_id,
    goal_id,
    name,
    status,
    daily_calories_target,
    daily_protein_target_g,
    daily_carbohydrate_target_g,
    daily_fat_target_g,
    daily_fiber_target_g,
    notes,
    planner_version,
    planner_input,
    nutrition_phase,
    macro_pattern,
    food_style,
    meal_schedule
  )
  values (
    v_user_id,
    nullif(p_plan ->> 'goal_id', '')::uuid,
    p_plan ->> 'name',
    v_status,
    (p_plan ->> 'daily_calories_target')::integer,
    (p_plan ->> 'daily_protein_target_g')::integer,
    (p_plan ->> 'daily_carbohydrate_target_g')::integer,
    (p_plan ->> 'daily_fat_target_g')::integer,
    (p_plan ->> 'daily_fiber_target_g')::integer,
    nullif(p_plan ->> 'notes', ''),
    nullif(p_plan ->> 'planner_version', ''),
    coalesce(p_plan -> 'planner_input', '{}'::jsonb),
    nullif(p_plan ->> 'nutrition_phase', ''),
    nullif(p_plan ->> 'macro_pattern', ''),
    nullif(p_plan ->> 'food_style', ''),
    nullif(p_plan ->> 'meal_schedule', '')
  )
  returning id into v_plan_id;

  for v_meal in
    select value
    from jsonb_array_elements(p_plan -> 'meals')
  loop
    insert into public.meals (
      diet_plan_id,
      name,
      meal_time,
      position,
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
          and (user_id is null or user_id = v_user_id)
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

  return v_plan_id;
end;
$$;

create or replace function public.set_diet_plan_status(
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
    from public.diet_plans
    where id = p_plan_id
      and user_id = v_user_id
  ) then
    raise exception 'Diet plan not found' using errcode = 'P0002';
  end if;

  if p_status = 'active' then
    update public.diet_plans
    set status = 'archived'
    where user_id = v_user_id
      and status = 'active'
      and id <> p_plan_id;
  end if;

  update public.diet_plans
  set status = p_status
  where id = p_plan_id
    and user_id = v_user_id;

  return p_plan_id;
end;
$$;

revoke all on function public.create_planner_diet_plan(jsonb) from public;
revoke all on function public.set_diet_plan_status(uuid, public.plan_status) from public;
grant execute on function public.create_planner_diet_plan(jsonb) to authenticated;
grant execute on function public.set_diet_plan_status(uuid, public.plan_status) to authenticated;

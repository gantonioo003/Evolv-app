-- Evolv - Expanded nutrition and exercise catalogs
-- Adds structured food composition, portions, daily logs, equipment,
-- muscles, training preferences, and richer exercise classification.

create table public.equipment (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  category text not null check (category in (
    'bodyweight', 'free_weight', 'machine', 'cable', 'functional', 'cardio', 'accessory'
  )),
  created_at timestamptz not null default now()
);

create table public.muscle_groups (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  body_region text not null check (body_region in ('upper', 'lower', 'core', 'full_body')),
  created_at timestamptz not null default now()
);

create table public.training_styles (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  created_at timestamptz not null default now()
);

alter table public.exercises
  add column source text not null default 'evolv',
  add column external_id text,
  add column aliases text[] not null default '{}',
  add column parent_exercise_id uuid references public.exercises(id) on delete set null,
  add column movement_pattern text,
  add column difficulty text check (difficulty is null or difficulty in ('beginner', 'intermediate', 'advanced')),
  add column is_compound boolean not null default false,
  add column instructions_source_url text,
  add column updated_at timestamptz not null default now();

create unique index exercises_source_external_id_idx
on public.exercises(source, external_id)
where external_id is not null;

create table public.exercise_equipment (
  exercise_id uuid not null references public.exercises(id) on delete cascade,
  equipment_id uuid not null references public.equipment(id) on delete cascade,
  is_required boolean not null default true,
  primary key (exercise_id, equipment_id)
);

create table public.exercise_muscles (
  exercise_id uuid not null references public.exercises(id) on delete cascade,
  muscle_group_id uuid not null references public.muscle_groups(id) on delete cascade,
  role text not null check (role in ('primary', 'secondary', 'stabilizer')),
  primary key (exercise_id, muscle_group_id, role)
);

create table public.exercise_training_styles (
  exercise_id uuid not null references public.exercises(id) on delete cascade,
  training_style_id uuid not null references public.training_styles(id) on delete cascade,
  primary key (exercise_id, training_style_id)
);

create table public.exercise_substitutions (
  exercise_id uuid not null references public.exercises(id) on delete cascade,
  substitute_exercise_id uuid not null references public.exercises(id) on delete cascade,
  compatibility smallint not null default 80 check (compatibility between 1 and 100),
  reason text,
  primary key (exercise_id, substitute_exercise_id),
  check (exercise_id <> substitute_exercise_id)
);

create table public.training_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  preferred_equipment_categories text[] not null default '{}'
    check (preferred_equipment_categories <@ array[
      'bodyweight', 'free_weight', 'machine', 'cable', 'functional', 'cardio', 'accessory'
    ]::text[]),
  avoided_exercises uuid[] not null default '{}',
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.user_preferred_training_styles (
  user_id uuid not null references auth.users(id) on delete cascade,
  training_style_id uuid not null references public.training_styles(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, training_style_id)
);

create table public.user_available_equipment (
  user_id uuid not null references auth.users(id) on delete cascade,
  equipment_id uuid not null references public.equipment(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, equipment_id)
);

create table public.nutrients (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null,
  unit text not null check (unit in ('kcal', 'g', 'mg', 'mcg', 'kj')),
  category text not null check (category in ('energy', 'macro', 'fat', 'carbohydrate', 'vitamin', 'mineral', 'other')),
  created_at timestamptz not null default now()
);

create table public.foods (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  source text not null default 'user',
  external_id text,
  name text not null,
  brand text,
  barcode text,
  locale text not null default 'pt-BR',
  data_type text check (data_type is null or data_type in (
    'generic', 'branded', 'restaurant', 'recipe', 'custom'
  )),
  base_amount numeric(9,3) not null default 100 check (base_amount > 0),
  base_unit text not null default 'g',
  calories_kcal numeric(9,3) check (calories_kcal is null or calories_kcal >= 0),
  protein_g numeric(9,3) check (protein_g is null or protein_g >= 0),
  carbohydrate_g numeric(9,3) check (carbohydrate_g is null or carbohydrate_g >= 0),
  fat_g numeric(9,3) check (fat_g is null or fat_g >= 0),
  fiber_g numeric(9,3) check (fiber_g is null or fiber_g >= 0),
  sugar_g numeric(9,3) check (sugar_g is null or sugar_g >= 0),
  saturated_fat_g numeric(9,3) check (saturated_fat_g is null or saturated_fat_g >= 0),
  sodium_mg numeric(9,3) check (sodium_mg is null or sodium_mg >= 0),
  is_verified boolean not null default false,
  last_synced_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index foods_source_external_id_idx
on public.foods(source, external_id)
where external_id is not null;

create index foods_name_search_idx on public.foods using gin (to_tsvector('simple', name));
create index foods_barcode_idx on public.foods(barcode) where barcode is not null;

create table public.food_nutrients (
  food_id uuid not null references public.foods(id) on delete cascade,
  nutrient_id uuid not null references public.nutrients(id) on delete cascade,
  amount numeric(12,4) not null check (amount >= 0),
  data_quality text check (data_quality is null or data_quality in ('analytical', 'label', 'calculated', 'estimated', 'user_entered')),
  primary key (food_id, nutrient_id)
);

create table public.food_portions (
  id uuid primary key default gen_random_uuid(),
  food_id uuid not null references public.foods(id) on delete cascade,
  name text not null,
  quantity numeric(9,3) not null default 1 check (quantity > 0),
  gram_weight numeric(9,3) check (gram_weight is null or gram_weight > 0),
  is_default boolean not null default false,
  created_at timestamptz not null default now()
);

alter table public.diet_plans
  add column daily_carbohydrate_target_g integer check (daily_carbohydrate_target_g is null or daily_carbohydrate_target_g between 0 and 1200),
  add column daily_fat_target_g integer check (daily_fat_target_g is null or daily_fat_target_g between 0 and 400),
  add column daily_fiber_target_g integer check (daily_fiber_target_g is null or daily_fiber_target_g between 0 and 150);

alter table public.meals
  add column carbohydrate_target_g integer check (carbohydrate_target_g is null or carbohydrate_target_g between 0 and 500),
  add column fat_target_g integer check (fat_target_g is null or fat_target_g between 0 and 200);

alter table public.meal_items
  add column food_id uuid references public.foods(id) on delete set null,
  add column quantity numeric(9,3) check (quantity is null or quantity > 0),
  add column unit text;

alter table public.food_logs alter column description drop not null;

create table public.food_log_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  food_log_id uuid not null references public.food_logs(id) on delete cascade,
  food_id uuid references public.foods(id) on delete set null,
  food_name text not null,
  quantity numeric(9,3) not null check (quantity > 0),
  unit text not null,
  amount_grams numeric(9,3) check (amount_grams is null or amount_grams > 0),
  calories_kcal numeric(9,3) not null default 0 check (calories_kcal >= 0),
  protein_g numeric(9,3) not null default 0 check (protein_g >= 0),
  carbohydrate_g numeric(9,3) not null default 0 check (carbohydrate_g >= 0),
  fat_g numeric(9,3) not null default 0 check (fat_g >= 0),
  fiber_g numeric(9,3) not null default 0 check (fiber_g >= 0),
  created_at timestamptz not null default now()
);

create table public.energy_expenditure_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source text not null check (source in ('basal_estimate', 'workout', 'steps', 'wearable', 'manual')),
  calories_kcal numeric(9,3) not null check (calories_kcal >= 0),
  occurred_at timestamptz not null default now(),
  description text,
  created_at timestamptz not null default now()
);

create index exercise_equipment_equipment_id_idx on public.exercise_equipment(equipment_id);
create index exercise_muscles_muscle_group_id_idx on public.exercise_muscles(muscle_group_id);
create index exercise_training_styles_style_id_idx on public.exercise_training_styles(training_style_id);
create index exercise_substitutions_substitute_id_idx on public.exercise_substitutions(substitute_exercise_id);
create index food_nutrients_nutrient_id_idx on public.food_nutrients(nutrient_id);
create index food_portions_food_id_idx on public.food_portions(food_id);
create index food_log_items_user_id_idx on public.food_log_items(user_id);
create index food_log_items_food_log_id_idx on public.food_log_items(food_log_id);
create index energy_expenditure_user_date_idx on public.energy_expenditure_logs(user_id, occurred_at desc);

create trigger exercises_set_updated_at
before update on public.exercises
for each row execute function public.set_updated_at();

create trigger training_preferences_set_updated_at
before update on public.training_preferences
for each row execute function public.set_updated_at();

create trigger foods_set_updated_at
before update on public.foods
for each row execute function public.set_updated_at();

alter table public.equipment enable row level security;
alter table public.muscle_groups enable row level security;
alter table public.training_styles enable row level security;
alter table public.exercise_equipment enable row level security;
alter table public.exercise_muscles enable row level security;
alter table public.exercise_training_styles enable row level security;
alter table public.exercise_substitutions enable row level security;
alter table public.training_preferences enable row level security;
alter table public.user_preferred_training_styles enable row level security;
alter table public.user_available_equipment enable row level security;
alter table public.nutrients enable row level security;
alter table public.foods enable row level security;
alter table public.food_nutrients enable row level security;
alter table public.food_portions enable row level security;
alter table public.food_log_items enable row level security;
alter table public.energy_expenditure_logs enable row level security;

create policy "Authenticated users can read equipment"
on public.equipment for select to authenticated using (true);

create policy "Authenticated users can read muscle groups"
on public.muscle_groups for select to authenticated using (true);

create policy "Authenticated users can read training styles"
on public.training_styles for select to authenticated using (true);

create policy "Authenticated users can read exercise equipment"
on public.exercise_equipment for select to authenticated using (true);

create policy "Authenticated users can read exercise muscles"
on public.exercise_muscles for select to authenticated using (true);

create policy "Authenticated users can read exercise training styles"
on public.exercise_training_styles for select to authenticated using (true);

create policy "Authenticated users can read exercise substitutions"
on public.exercise_substitutions for select to authenticated using (true);

create policy "Users can manage their own training preferences"
on public.training_preferences for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their preferred training styles"
on public.user_preferred_training_styles for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their available equipment"
on public.user_available_equipment for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Authenticated users can read nutrients"
on public.nutrients for select to authenticated using (true);

create policy "Users can read catalog and own foods"
on public.foods for select
using (user_id is null or auth.uid() = user_id);

create policy "Users can manage their own custom foods"
on public.foods for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can read nutrients from accessible foods"
on public.food_nutrients for select
using (
  exists (
    select 1 from public.foods f
    where f.id = food_nutrients.food_id
      and (f.user_id is null or f.user_id = auth.uid())
  )
);

create policy "Users can manage nutrients from their custom foods"
on public.food_nutrients for all
using (
  exists (select 1 from public.foods f where f.id = food_nutrients.food_id and f.user_id = auth.uid())
)
with check (
  exists (select 1 from public.foods f where f.id = food_nutrients.food_id and f.user_id = auth.uid())
);

create policy "Users can read portions from accessible foods"
on public.food_portions for select
using (
  exists (
    select 1 from public.foods f
    where f.id = food_portions.food_id
      and (f.user_id is null or f.user_id = auth.uid())
  )
);

create policy "Users can manage portions from their custom foods"
on public.food_portions for all
using (
  exists (select 1 from public.foods f where f.id = food_portions.food_id and f.user_id = auth.uid())
)
with check (
  exists (select 1 from public.foods f where f.id = food_portions.food_id and f.user_id = auth.uid())
);

create policy "Users can manage their own food log items"
on public.food_log_items for all
using (
  auth.uid() = user_id
  and exists (
    select 1 from public.food_logs fl
    where fl.id = food_log_items.food_log_id
      and fl.user_id = auth.uid()
  )
)
with check (
  auth.uid() = user_id
  and exists (
    select 1 from public.food_logs fl
    where fl.id = food_log_items.food_log_id
      and fl.user_id = auth.uid()
  )
);

create policy "Users can manage their own energy expenditure"
on public.energy_expenditure_logs for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

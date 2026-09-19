-- Evolv - Initial database schema
-- Target: Supabase PostgreSQL
-- Purpose: MVP data model for profile, goals, workout plan, diet plan,
-- coach conversations, optional memory, adjustments, and progress.

create extension if not exists pgcrypto;

create type public.goal_type as enum (
  'hypertrophy',
  'fat_loss',
  'strength',
  'health',
  'recomposition',
  'maintenance'
);

create type public.plan_status as enum (
  'draft',
  'active',
  'archived'
);

create type public.weekday as enum (
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday'
);

create type public.coach_message_role as enum (
  'user',
  'assistant',
  'system'
);

create type public.adjustment_status as enum (
  'pending',
  'applied',
  'rejected'
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  birth_date date,
  height_cm integer check (height_cm is null or height_cm between 80 and 260),
  current_weight_kg numeric(5,2) check (current_weight_kg is null or current_weight_kg between 25 and 350),
  training_level text check (training_level is null or training_level in ('beginner', 'intermediate', 'advanced')),
  preferred_training_time time,
  available_training_days public.weekday[] not null default '{}',
  disliked_foods text[] not null default '{}',
  food_restrictions text[] not null default '{}',
  injuries_or_limitations text[] not null default '{}',
  coach_memory_enabled boolean not null default false,
  notifications_enabled boolean not null default true,
  onboarding_status text not null default 'not_started'
    check (onboarding_status in ('not_started', 'in_progress', 'completed', 'skipped')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.goals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  type public.goal_type not null,
  title text not null,
  description text,
  target_weight_kg numeric(5,2) check (target_weight_kg is null or target_weight_kg between 25 and 350),
  target_date date,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.exercises (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  muscle_group text not null,
  equipment text,
  instructions text,
  is_system boolean not null default true,
  created_at timestamptz not null default now(),
  unique (name)
);

create table public.workout_plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  goal_id uuid references public.goals(id) on delete set null,
  name text not null,
  status public.plan_status not null default 'draft',
  start_date date not null,
  end_date date,
  weekly_frequency integer not null check (weekly_frequency between 1 and 7),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.workout_days (
  id uuid primary key default gen_random_uuid(),
  workout_plan_id uuid not null references public.workout_plans(id) on delete cascade,
  weekday public.weekday not null,
  title text not null,
  focus text not null,
  estimated_minutes integer check (estimated_minutes is null or estimated_minutes between 10 and 240),
  position integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workout_plan_id, weekday, position)
);

create table public.workout_day_exercises (
  id uuid primary key default gen_random_uuid(),
  workout_day_id uuid not null references public.workout_days(id) on delete cascade,
  exercise_id uuid not null references public.exercises(id) on delete restrict,
  position integer not null default 0,
  sets integer not null check (sets between 1 and 12),
  min_reps integer not null check (min_reps between 1 and 100),
  max_reps integer not null check (max_reps between min_reps and 100),
  rest_seconds integer check (rest_seconds is null or rest_seconds between 15 and 600),
  target_load_kg numeric(6,2) check (target_load_kg is null or target_load_kg >= 0),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workout_day_id, position)
);

create table public.workout_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  workout_day_id uuid references public.workout_days(id) on delete set null,
  performed_at timestamptz not null default now(),
  notes text,
  created_at timestamptz not null default now()
);

create table public.exercise_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  workout_log_id uuid references public.workout_logs(id) on delete cascade,
  exercise_id uuid not null references public.exercises(id) on delete restrict,
  performed_at timestamptz not null default now(),
  sets_completed integer check (sets_completed is null or sets_completed between 0 and 30),
  reps_summary text,
  load_kg numeric(6,2) check (load_kg is null or load_kg >= 0),
  notes text,
  created_at timestamptz not null default now()
);

create table public.exercise_progression_suggestions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  exercise_id uuid not null references public.exercises(id) on delete cascade,
  current_load_kg numeric(6,2) not null check (current_load_kg >= 0),
  suggested_load_kg numeric(6,2) not null check (suggested_load_kg >= current_load_kg),
  reason text not null,
  suggested_for date,
  accepted_at timestamptz,
  dismissed_at timestamptz,
  created_at timestamptz not null default now(),
  check (accepted_at is null or dismissed_at is null)
);

create table public.diet_plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  goal_id uuid references public.goals(id) on delete set null,
  name text not null,
  status public.plan_status not null default 'draft',
  daily_calories_target integer check (daily_calories_target is null or daily_calories_target between 800 and 8000),
  daily_protein_target_g integer check (daily_protein_target_g is null or daily_protein_target_g between 20 and 500),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.meals (
  id uuid primary key default gen_random_uuid(),
  diet_plan_id uuid not null references public.diet_plans(id) on delete cascade,
  name text not null,
  meal_time time,
  position integer not null default 0,
  calories_target integer check (calories_target is null or calories_target between 0 and 3000),
  protein_target_g integer check (protein_target_g is null or protein_target_g between 0 and 200),
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (diet_plan_id, position)
);

create table public.meal_items (
  id uuid primary key default gen_random_uuid(),
  meal_id uuid not null references public.meals(id) on delete cascade,
  name text not null,
  amount text,
  substitution_group text,
  notes text,
  created_at timestamptz not null default now()
);

create table public.food_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  logged_at timestamptz not null default now(),
  description text not null,
  meal_name text,
  notes text,
  created_at timestamptz not null default now()
);

create table public.coach_conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text,
  entry_context text check (entry_context is null or entry_context in ('today', 'workout', 'diet', 'account', 'general')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.coach_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.coach_conversations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role public.coach_message_role not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.coach_memory_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source_message_id uuid references public.coach_messages(id) on delete set null,
  category text not null check (category in ('preference', 'limitation', 'recurring_question', 'routine', 'adjustment')),
  content text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.planner_adjustments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  conversation_id uuid references public.coach_conversations(id) on delete set null,
  status public.adjustment_status not null default 'pending',
  reason text not null,
  requested_change jsonb not null default '{}'::jsonb,
  applied_change jsonb,
  applied_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.progress_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  measured_at date not null default current_date,
  weight_kg numeric(5,2) check (weight_kg is null or weight_kg between 25 and 350),
  waist_cm numeric(5,2) check (waist_cm is null or waist_cm between 30 and 250),
  chest_cm numeric(5,2) check (chest_cm is null or chest_cm between 30 and 250),
  arm_cm numeric(5,2) check (arm_cm is null or arm_cm between 10 and 100),
  leg_cm numeric(5,2) check (leg_cm is null or leg_cm between 20 and 150),
  notes text,
  created_at timestamptz not null default now()
);

create table public.progress_photos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  progress_entry_id uuid references public.progress_entries(id) on delete set null,
  storage_path text not null,
  photo_type text check (photo_type is null or photo_type in ('front', 'side', 'back', 'other')),
  created_at timestamptz not null default now()
);

create index goals_user_id_idx on public.goals(user_id);
create index workout_plans_user_id_idx on public.workout_plans(user_id);
create index workout_days_plan_id_idx on public.workout_days(workout_plan_id);
create index workout_day_exercises_day_id_idx on public.workout_day_exercises(workout_day_id);
create index workout_logs_user_id_performed_at_idx on public.workout_logs(user_id, performed_at desc);
create index exercise_logs_user_exercise_performed_at_idx on public.exercise_logs(user_id, exercise_id, performed_at desc);
create index progression_suggestions_user_exercise_idx on public.exercise_progression_suggestions(user_id, exercise_id, created_at desc);
create index diet_plans_user_id_idx on public.diet_plans(user_id);
create index meals_diet_plan_id_idx on public.meals(diet_plan_id);
create index food_logs_user_id_logged_at_idx on public.food_logs(user_id, logged_at desc);
create index coach_conversations_user_id_idx on public.coach_conversations(user_id);
create index coach_messages_conversation_id_idx on public.coach_messages(conversation_id, created_at);
create index coach_memory_items_user_id_idx on public.coach_memory_items(user_id);
create index planner_adjustments_user_id_idx on public.planner_adjustments(user_id);
create index progress_entries_user_id_measured_at_idx on public.progress_entries(user_id, measured_at desc);
create index progress_photos_user_id_idx on public.progress_photos(user_id);

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create trigger goals_set_updated_at
before update on public.goals
for each row execute function public.set_updated_at();

create trigger workout_plans_set_updated_at
before update on public.workout_plans
for each row execute function public.set_updated_at();

create trigger workout_days_set_updated_at
before update on public.workout_days
for each row execute function public.set_updated_at();

create trigger workout_day_exercises_set_updated_at
before update on public.workout_day_exercises
for each row execute function public.set_updated_at();

create trigger diet_plans_set_updated_at
before update on public.diet_plans
for each row execute function public.set_updated_at();

create trigger meals_set_updated_at
before update on public.meals
for each row execute function public.set_updated_at();

create trigger coach_conversations_set_updated_at
before update on public.coach_conversations
for each row execute function public.set_updated_at();

create trigger coach_memory_items_set_updated_at
before update on public.coach_memory_items
for each row execute function public.set_updated_at();

create trigger planner_adjustments_set_updated_at
before update on public.planner_adjustments
for each row execute function public.set_updated_at();

alter table public.profiles enable row level security;
alter table public.goals enable row level security;
alter table public.exercises enable row level security;
alter table public.workout_plans enable row level security;
alter table public.workout_days enable row level security;
alter table public.workout_day_exercises enable row level security;
alter table public.workout_logs enable row level security;
alter table public.exercise_logs enable row level security;
alter table public.exercise_progression_suggestions enable row level security;
alter table public.diet_plans enable row level security;
alter table public.meals enable row level security;
alter table public.meal_items enable row level security;
alter table public.food_logs enable row level security;
alter table public.coach_conversations enable row level security;
alter table public.coach_messages enable row level security;
alter table public.coach_memory_items enable row level security;
alter table public.planner_adjustments enable row level security;
alter table public.progress_entries enable row level security;
alter table public.progress_photos enable row level security;

create policy "Users can manage their own profile"
on public.profiles
for all
using (auth.uid() = id)
with check (auth.uid() = id);

create policy "Users can manage their own goals"
on public.goals
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Authenticated users can read system exercises"
on public.exercises
for select
to authenticated
using (true);

create policy "Users can manage their own workout plans"
on public.workout_plans
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can read workout days from their plans"
on public.workout_days
for select
using (
  exists (
    select 1
    from public.workout_plans wp
    where wp.id = workout_days.workout_plan_id
      and wp.user_id = auth.uid()
  )
);

create policy "Users can manage workout days from their plans"
on public.workout_days
for all
using (
  exists (
    select 1
    from public.workout_plans wp
    where wp.id = workout_days.workout_plan_id
      and wp.user_id = auth.uid()
  )
)
with check (
  exists (
    select 1
    from public.workout_plans wp
    where wp.id = workout_days.workout_plan_id
      and wp.user_id = auth.uid()
  )
);

create policy "Users can manage workout exercises from their plans"
on public.workout_day_exercises
for all
using (
  exists (
    select 1
    from public.workout_days wd
    join public.workout_plans wp on wp.id = wd.workout_plan_id
    where wd.id = workout_day_exercises.workout_day_id
      and wp.user_id = auth.uid()
  )
)
with check (
  exists (
    select 1
    from public.workout_days wd
    join public.workout_plans wp on wp.id = wd.workout_plan_id
    where wd.id = workout_day_exercises.workout_day_id
      and wp.user_id = auth.uid()
  )
);

create policy "Users can manage their own workout logs"
on public.workout_logs
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their own exercise logs"
on public.exercise_logs
for all
using (
  auth.uid() = user_id
  and (
    workout_log_id is null
    or exists (
      select 1 from public.workout_logs wl
      where wl.id = exercise_logs.workout_log_id
        and wl.user_id = auth.uid()
    )
  )
)
with check (
  auth.uid() = user_id
  and (
    workout_log_id is null
    or exists (
      select 1 from public.workout_logs wl
      where wl.id = exercise_logs.workout_log_id
        and wl.user_id = auth.uid()
    )
  )
);

create policy "Users can manage their own progression suggestions"
on public.exercise_progression_suggestions
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their own diet plans"
on public.diet_plans
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage meals from their diet plans"
on public.meals
for all
using (
  exists (
    select 1
    from public.diet_plans dp
    where dp.id = meals.diet_plan_id
      and dp.user_id = auth.uid()
  )
)
with check (
  exists (
    select 1
    from public.diet_plans dp
    where dp.id = meals.diet_plan_id
      and dp.user_id = auth.uid()
  )
);

create policy "Users can manage meal items from their diet plans"
on public.meal_items
for all
using (
  exists (
    select 1
    from public.meals m
    join public.diet_plans dp on dp.id = m.diet_plan_id
    where m.id = meal_items.meal_id
      and dp.user_id = auth.uid()
  )
)
with check (
  exists (
    select 1
    from public.meals m
    join public.diet_plans dp on dp.id = m.diet_plan_id
    where m.id = meal_items.meal_id
      and dp.user_id = auth.uid()
  )
);

create policy "Users can manage their own food logs"
on public.food_logs
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their own coach conversations"
on public.coach_conversations
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their own coach messages"
on public.coach_messages
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their own coach memory"
on public.coach_memory_items
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their own planner adjustments"
on public.planner_adjustments
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their own progress entries"
on public.progress_entries
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their own progress photos"
on public.progress_photos
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

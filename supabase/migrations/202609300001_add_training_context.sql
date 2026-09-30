-- Evolv - Training, nutrition phase and readiness context
-- Adds optional context for long-term planning without enabling automatic changes.

alter table public.workout_plans
  add column split_type text check (split_type is null or split_type in (
    'full_body', 'upper_lower', 'push_pull_legs', 'body_part', 'hybrid', 'custom'
  )),
  add column split_label text;

alter table public.exercise_logs
  add column rpe numeric(3,1) check (rpe is null or rpe between 1 and 10),
  add column reps_in_reserve numeric(3,1)
    check (reps_in_reserve is null or reps_in_reserve between 0 and 10);

alter table public.exercise_progression_suggestions
  add column suggestion_type text not null default 'increase_load'
    check (suggestion_type in (
      'increase_load', 'increase_reps', 'hold_load', 'review_recovery',
      'review_plan', 'consider_deload'
    )),
  add column evidence jsonb not null default '{}'::jsonb;

create table public.nutrition_phases (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  goal_id uuid references public.goals(id) on delete set null,
  parent_phase_id uuid references public.nutrition_phases(id) on delete set null,
  phase_type text not null check (phase_type in (
    'mass_gain', 'fat_loss', 'maintenance', 'recomposition', 'diet_break', 'custom'
  )),
  label text,
  status text not null default 'active'
    check (status in ('active', 'completed', 'cancelled')),
  started_on date not null default current_date,
  planned_end_on date,
  ended_on date,
  starting_weight_kg numeric(5,2)
    check (starting_weight_kg is null or starting_weight_kg between 25 and 350),
  target_weight_kg numeric(5,2)
    check (target_weight_kg is null or target_weight_kg between 25 and 350),
  calorie_target integer
    check (calorie_target is null or calorie_target between 800 and 8000),
  target_rate_percent_per_week numeric(4,2)
    check (target_rate_percent_per_week is null or target_rate_percent_per_week between 0 and 5),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (planned_end_on is null or planned_end_on >= started_on),
  check (ended_on is null or ended_on >= started_on)
);

create table public.readiness_check_ins (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  recorded_on date not null default current_date,
  motivation smallint check (motivation is null or motivation between 1 and 5),
  energy smallint check (energy is null or energy between 1 and 5),
  sleep_quality smallint check (sleep_quality is null or sleep_quality between 1 and 5),
  recovery smallint check (recovery is null or recovery between 1 and 5),
  hunger smallint check (hunger is null or hunger between 1 and 5),
  stress smallint check (stress is null or stress between 1 and 5),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, recorded_on),
  check (
    num_nonnulls(motivation, energy, sleep_quality, recovery, hunger, stress, notes) > 0
  )
);

create table public.insight_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  proactive_insights_enabled boolean not null default true,
  max_non_urgent_per_week smallint not null default 1
    check (max_non_urgent_per_week between 0 and 7),
  repeated_topic_cooldown_days smallint not null default 30
    check (repeated_topic_cooldown_days between 1 and 365),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index nutrition_phases_user_started_idx
on public.nutrition_phases(user_id, started_on desc);

create index nutrition_phases_user_status_idx
on public.nutrition_phases(user_id, status);

create index readiness_check_ins_user_date_idx
on public.readiness_check_ins(user_id, recorded_on desc);

create trigger nutrition_phases_set_updated_at
before update on public.nutrition_phases
for each row execute function public.set_updated_at();

create trigger readiness_check_ins_set_updated_at
before update on public.readiness_check_ins
for each row execute function public.set_updated_at();

create trigger insight_preferences_set_updated_at
before update on public.insight_preferences
for each row execute function public.set_updated_at();

create or replace function public.enforce_training_context_ownership()
returns trigger
language plpgsql
as $$
begin
  if new.goal_id is not null and not exists (
    select 1 from public.goals g
    where g.id = new.goal_id and g.user_id = new.user_id
  ) then
    raise sqlstate '23514' using message = 'The nutrition phase goal must belong to the same user.';
  end if;

  if new.parent_phase_id is not null and not exists (
    select 1 from public.nutrition_phases np
    where np.id = new.parent_phase_id and np.user_id = new.user_id
  ) then
    raise sqlstate '23514' using message = 'The parent nutrition phase must belong to the same user.';
  end if;

  return new;
end;
$$;

create trigger nutrition_phases_enforce_owned_references
before insert or update on public.nutrition_phases
for each row execute function public.enforce_training_context_ownership();

alter table public.nutrition_phases enable row level security;
alter table public.readiness_check_ins enable row level security;
alter table public.insight_preferences enable row level security;

create policy "Users can manage their own nutrition phases"
on public.nutrition_phases for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their own readiness check-ins"
on public.readiness_check_ins for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can manage their own insight preferences"
on public.insight_preferences for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

grant select, insert, update, delete on table
  public.nutrition_phases,
  public.readiness_check_ins,
  public.insight_preferences
to authenticated;


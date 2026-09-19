-- Evolv - Explicit Data API permissions
-- RLS decides which rows each authenticated user can access.
-- These grants only allow the authenticated role to reach the tables.

grant usage on schema public to authenticated;

grant select on table
  public.exercises,
  public.equipment,
  public.muscle_groups,
  public.training_styles,
  public.exercise_equipment,
  public.exercise_muscles,
  public.exercise_training_styles,
  public.exercise_substitutions,
  public.nutrients
to authenticated;

grant select, insert, update, delete on table
  public.profiles,
  public.goals,
  public.workout_plans,
  public.workout_days,
  public.workout_day_exercises,
  public.workout_logs,
  public.exercise_logs,
  public.exercise_progression_suggestions,
  public.training_preferences,
  public.user_preferred_training_styles,
  public.user_available_equipment,
  public.diet_plans,
  public.meals,
  public.meal_items,
  public.foods,
  public.food_nutrients,
  public.food_portions,
  public.food_logs,
  public.food_log_items,
  public.energy_expenditure_logs,
  public.coach_conversations,
  public.coach_messages,
  public.coach_memory_items,
  public.planner_adjustments,
  public.progress_entries,
  public.progress_photos
to authenticated;

grant usage on type
  public.goal_type,
  public.plan_status,
  public.weekday,
  public.coach_message_role,
  public.adjustment_status
to authenticated;

revoke all on all tables in schema public from anon;

export type GoalType =
  | "hypertrophy"
  | "fat_loss"
  | "strength"
  | "health"
  | "recomposition"
  | "maintenance";

export type ProfileApi = {
  id: string;
  full_name: string | null;
  birth_date: string | null;
  height_cm: number | null;
  current_weight_kg: number | null;
  training_level: string | null;
  preferred_training_time: string | null;
  available_training_days: string[];
  disliked_foods: string[];
  food_restrictions: string[];
  injuries_or_limitations: string[];
  coach_memory_enabled: boolean;
  notifications_enabled: boolean;
  onboarding_status: "not_started" | "in_progress" | "completed" | "skipped";
};

export type GoalApi = {
  id: string;
  user_id: string;
  type: GoalType;
  title: string;
  description: string | null;
  target_weight_kg: number | null;
  target_date: string | null;
  is_active: boolean;
};

export type ExerciseApi = {
  id: string;
  name: string;
  muscle_group: string;
  equipment: string | null;
  instructions: string | null;
};

export type ExerciseCatalogApi = ExerciseApi & {
  aliases?: string[];
  movement_pattern?: string | null;
  difficulty?: string | null;
  is_compound?: boolean | null;
};

export type WorkoutDayExerciseApi = {
  id: string;
  exercise_id: string;
  position: number;
  sets: number | null;
  min_reps: number | null;
  max_reps: number | null;
  rest_seconds: number | null;
  duration_minutes: number | null;
  prescription_kind: "repetitions" | "duration";
  planner_role: string | null;
  target_load_kg: number | null;
  notes: string | null;
  exercises: ExerciseApi;
};

export type WorkoutDayApi = {
  id: string;
  weekday: string;
  title: string;
  focus: string;
  estimated_minutes: number | null;
  position: number;
  workout_day_exercises: WorkoutDayExerciseApi[];
};

export type WorkoutPlanApi = {
  id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
  start_date: string;
  end_date: string | null;
  weekly_frequency: number;
  notes: string | null;
  split_type?: string | null;
  split_label?: string | null;
  planner_version?: string | null;
  goals: GoalApi | null;
  workout_days: WorkoutDayApi[];
};

export type WorkoutPlanSummaryApi = Pick<
  WorkoutPlanApi,
  | "id"
  | "name"
  | "status"
  | "start_date"
  | "end_date"
  | "weekly_frequency"
  | "split_type"
  | "split_label"
  | "planner_version"
> & {
  created_at: string;
  updated_at: string;
};

export type PlannerModality =
  | "full-gym"
  | "machines"
  | "free-weights"
  | "cables"
  | "calisthenics"
  | "bands"
  | "functional"
  | "suspension"
  | "bodyweight"
  | "cardio-equipment"
  | "running"
  | "walking"
  | "cycling"
  | "rowing"
  | "stairs"
  | "swimming"
  | "hiit"
  | "plyometrics"
  | "yoga-pilates"
  | "sports"
  | "mobility"
  | "stretching";

export type GenerateWorkoutPlanInput = {
  name?: string;
  goal?: GoalType;
  level?: "beginner" | "intermediate" | "advanced";
  available_days?: string[];
  session_minutes?: number;
  modalities?: PlannerModality[];
  desired_weekly_frequency?: number;
  start_date?: string;
  activate?: boolean;
};

export type NutritionPhase =
  | "mass_gain"
  | "fat_loss"
  | "maintenance"
  | "recomposition"
  | "diet_break"
  | "custom";

export type NutritionMacroPattern =
  "balanced" | "high_carb_performance" | "low_carb" | "ketogenic" | "custom";

export type NutritionFoodStyle =
  "omnivore" | "pescatarian" | "vegetarian" | "vegan" | "custom";

export type GenerateNutritionPlanInput = {
  name?: string;
  phase?: NutritionPhase;
  calorie_target_override?: number;
  estimated_maintenance_calories?: number;
  activity_level?:
    "sedentary" | "light" | "moderate" | "very_active" | "athlete";
  metabolic_equation_sex?: "female" | "male";
  macro_pattern?: NutritionMacroPattern;
  meals_per_day?: number;
  use_training_rest_variants?: boolean;
  training_day_meals?: number;
  rest_day_meals?: number;
  rotate_menus?: boolean;
  menu_rotation_size?: number;
  flexible_meal_frequency?: "none" | "weekly" | "fortnightly";
  flexible_meal_weekday?: string;
  alcohol_frequency?: "none" | "fortnightly" | "monthly";
  alcohol_preferred_weekday?: string;
  alcohol_max_servings?: number;
  meal_schedule?: "regular" | "time_restricted" | "custom";
  eating_window_hours?: number;
  eating_window_start_hour?: number;
  food_style?: NutritionFoodStyle;
  preferred_foods?: string[];
  disliked_foods?: string[];
  food_restrictions?: string[];
  allergen_exclusions?: string[];
  activate?: boolean;
};

export type PlannerAdjustmentKind =
  | "move_workout_day"
  | "replace_exercise"
  | "replace_meal_item"
  | "set_day_activity";

export type CreatePlannerAdjustmentInput = {
  kind: PlannerAdjustmentKind;
  reason: string;
  source?: "manual" | "coach";
  workout_plan_id?: string;
  diet_plan_id?: string;
  workout_day_id?: string;
  target_weekday?: string;
  workout_day_exercise_id?: string;
  replacement_exercise_id?: string;
  meal_item_id?: string;
  replacement_food_id?: string;
  activity_date?: string;
  activity_type?: "rest" | "resistance" | "cardio" | "mixed";
  intensity?: "light" | "moderate" | "hard";
  estimated_minutes?: number;
  nutrition_day_type?: "training_day" | "rest_day";
  note?: string;
};

export type PlannerDayContextApi = {
  activity_date: string;
  activity_type: "rest" | "resistance" | "cardio" | "mixed";
  intensity: "light" | "moderate" | "hard" | null;
  estimated_minutes: number | null;
  nutrition_day_type: "training_day" | "rest_day";
  source: "override" | "workout_plan" | "profile" | "default";
  workout_day_id: string | null;
  title: string;
  note: string | null;
};

export type PlannerAdjustmentPreviewApi = {
  title: string;
  summary: string;
  changes: string[];
  preserved: string[];
  warnings: string[];
};

export type PlannerAdjustmentApi = {
  id: string;
  status: "pending" | "applied" | "rejected";
  adjustment_kind: PlannerAdjustmentKind | null;
  source: "manual" | "coach" | "planner";
  reason: string;
  workout_plan_id: string | null;
  diet_plan_id: string | null;
  target_type: string | null;
  target_id: string | null;
  preview: PlannerAdjustmentPreviewApi;
  reversible: boolean;
  expires_at: string;
  confirmed_at: string | null;
  rejected_at: string | null;
  reverted_at: string | null;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
};

export type MealItemSubstitutionApi = {
  food_id: string;
  name: string;
  role: string;
  amount: number;
  unit: string;
  similarity_score: number;
};

export type MealItemApi = {
  id: string;
  position: number;
  name: string;
  amount: string | null;
  quantity: number | null;
  unit: string | null;
  nutrition_role: string | null;
  calories_kcal: number | null;
  protein_g: number | null;
  carbohydrate_g: number | null;
  fat_g: number | null;
  fiber_g: number | null;
  substitutions: MealItemSubstitutionApi[];
  notes: string | null;
};

export type MealApi = {
  id: string;
  name: string;
  meal_time: string | null;
  position: number;
  day_type: "every_day" | "training_day" | "rest_day";
  rotation_index: number;
  calories_target: number | null;
  protein_target_g: number | null;
  carbohydrate_target_g: number | null;
  fat_target_g: number | null;
  description: string | null;
  meal_items: MealItemApi[];
};

export type DietPlanApi = {
  id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
  daily_calories_target: number | null;
  daily_protein_target_g: number | null;
  daily_carbohydrate_target_g: number | null;
  daily_fat_target_g: number | null;
  daily_fiber_target_g: number | null;
  uses_day_variants: boolean;
  training_day_calories_target: number | null;
  rest_day_calories_target: number | null;
  menu_rotation_enabled: boolean;
  menu_rotation_size: number;
  flexible_meal_frequency: "none" | "weekly" | "fortnightly";
  flexible_meal_weekday: string | null;
  alcohol_frequency: "none" | "fortnightly" | "monthly";
  alcohol_preferred_weekday: string | null;
  alcohol_max_servings: number | null;
  nutrition_phase: NutritionPhase | null;
  macro_pattern: NutritionMacroPattern | null;
  food_style: NutritionFoodStyle | null;
  meal_schedule: "regular" | "time_restricted" | "custom" | null;
  planner_version: string | null;
  notes: string | null;
  goals: GoalApi | null;
  meals: MealApi[];
};

export type DietPlanSummaryApi = Pick<
  DietPlanApi,
  | "id"
  | "name"
  | "status"
  | "daily_calories_target"
  | "daily_protein_target_g"
  | "uses_day_variants"
  | "training_day_calories_target"
  | "rest_day_calories_target"
  | "menu_rotation_enabled"
  | "menu_rotation_size"
  | "flexible_meal_frequency"
  | "flexible_meal_weekday"
  | "alcohol_frequency"
  | "alcohol_preferred_weekday"
  | "alcohol_max_servings"
  | "nutrition_phase"
  | "macro_pattern"
  | "food_style"
  | "meal_schedule"
  | "planner_version"
  | "created_at"
  | "updated_at"
>;

export type ProgressEntryApi = {
  id: string;
  measured_at: string;
  weight_kg: number | null;
  waist_cm: number | null;
  chest_cm: number | null;
  arm_cm: number | null;
  leg_cm: number | null;
  notes: string | null;
};

export type ProgressionSuggestionApi = {
  id: string;
  current_load_kg: number;
  suggested_load_kg: number;
  reason: string;
  accepted_at: string | null;
  dismissed_at: string | null;
  exercises: Pick<ExerciseApi, "id" | "name" | "muscle_group" | "equipment">;
};

export type FoodLogApi = {
  id: string;
  logged_at: string;
  description: string;
  meal_name: string | null;
};

export type NutritionSummaryApi = {
  calories_kcal: number;
  protein_g: number;
  carbohydrate_g: number;
  fat_g: number;
  fiber_g: number;
};

export type UpdateProfileInput = Partial<
  Pick<
    ProfileApi,
    | "full_name"
    | "birth_date"
    | "height_cm"
    | "current_weight_kg"
    | "training_level"
    | "available_training_days"
    | "preferred_training_time"
    | "food_restrictions"
    | "disliked_foods"
    | "injuries_or_limitations"
    | "notifications_enabled"
    | "coach_memory_enabled"
    | "onboarding_status"
  >
>;

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

export type WorkoutDayExerciseApi = {
  id: string;
  exercise_id: string;
  position: number;
  sets: number;
  min_reps: number;
  max_reps: number;
  rest_seconds: number | null;
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
  start_date: string;
  end_date: string | null;
  weekly_frequency: number;
  notes: string | null;
  split_type?: string | null;
  split_label?: string | null;
  goals: GoalApi | null;
  workout_days: WorkoutDayApi[];
};

export type MealItemApi = {
  id: string;
  name: string;
  amount: string | null;
  notes: string | null;
};

export type MealApi = {
  id: string;
  name: string;
  meal_time: string | null;
  position: number;
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
  daily_calories_target: number | null;
  daily_protein_target_g: number | null;
  daily_carbohydrate_target_g: number | null;
  daily_fat_target_g: number | null;
  daily_fiber_target_g: number | null;
  notes: string | null;
  goals: GoalApi | null;
  meals: MealApi[];
};

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

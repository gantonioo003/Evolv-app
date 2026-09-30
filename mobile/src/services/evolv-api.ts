import { ApiClient } from "@/services/api-client";
import type {
  DietPlanApi,
  FoodLogApi,
  GoalApi,
  GoalType,
  NutritionSummaryApi,
  ProfileApi,
  ProgressEntryApi,
  ProgressionSuggestionApi,
  UpdateProfileInput,
  WorkoutPlanApi,
} from "@/types/api";

const dateOnly = (date: Date) => date.toISOString().slice(0, 10);

export class EvolvApi {
  private readonly client: ApiClient;

  constructor(accessToken: string) {
    this.client = new ApiClient(accessToken);
  }

  getProfile() {
    return this.client.get<ProfileApi>("/profiles/me");
  }

  updateProfile(input: UpdateProfileInput) {
    return this.client.patch<ProfileApi>("/profiles/me", input);
  }

  getActiveGoal() {
    return this.client.get<GoalApi | null>("/goals/active");
  }

  createGoal(input: { type: GoalType; title: string; description?: string }) {
    return this.client.post<GoalApi>("/goals", input);
  }

  getActiveWorkoutPlan() {
    return this.client.get<WorkoutPlanApi | null>("/workouts/active-plan");
  }

  getProgressionSuggestions() {
    return this.client.get<ProgressionSuggestionApi[]>(
      "/workouts/progression-suggestions?status=pending&limit=20",
    );
  }

  recordExerciseLoad(
    exerciseId: string,
    input: {
      load_kg: number;
      sets_completed?: number;
      reps_summary?: string;
      notes?: string;
    },
  ) {
    return this.client.post(`/workouts/exercises/${exerciseId}/logs`, input);
  }

  getActiveDietPlan() {
    return this.client.get<DietPlanApi | null>("/nutrition/active-plan");
  }

  getTodayFoodLogs() {
    const from = new Date();
    from.setHours(0, 0, 0, 0);
    const to = new Date(from);
    to.setDate(to.getDate() + 1);
    return this.client.get<FoodLogApi[]>(
      `/nutrition/logs?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}&limit=100`,
    );
  }

  getTodayNutritionSummary() {
    const from = new Date();
    from.setHours(0, 0, 0, 0);
    const to = new Date(from);
    to.setDate(to.getDate() + 1);
    return this.client.get<NutritionSummaryApi>(
      `/nutrition/summary?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}&limit=100`,
    );
  }

  createFoodLog(input: { description: string; meal_name?: string }) {
    return this.client.post<FoodLogApi>("/nutrition/logs", input);
  }

  removeFoodLog(foodLogId: string) {
    return this.client.delete<{ id: string }>(`/nutrition/logs/${foodLogId}`);
  }

  getProgress() {
    return this.client.get<ProgressEntryApi[]>("/progress?limit=100");
  }

  createProgressEntry(input: {
    measured_at?: string;
    weight_kg?: number;
    waist_cm?: number;
    chest_cm?: number;
    arm_cm?: number;
    leg_cm?: number;
    notes?: string;
  }) {
    return this.client.post<ProgressEntryApi>("/progress", {
      measured_at: input.measured_at ?? dateOnly(new Date()),
      ...input,
    });
  }
}

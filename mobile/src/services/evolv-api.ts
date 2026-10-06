import { ApiClient } from "@/services/api-client";
import type {
  DietPlanApi,
  DietPlanSummaryApi,
  ExerciseCatalogApi,
  FoodLogApi,
  GenerateNutritionPlanInput,
  GenerateWorkoutPlanInput,
  GoalApi,
  GoalType,
  NutritionSummaryApi,
  PlannerAdjustmentApi,
  PlannerDayContextApi,
  CreatePlannerAdjustmentInput,
  ProfileApi,
  ProgressEntryApi,
  ProgressionSuggestionApi,
  UpdateProfileInput,
  WorkoutPlanApi,
  WorkoutPlanSummaryApi,
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

  listWorkoutPlans() {
    return this.client.get<WorkoutPlanSummaryApi[]>("/planner/plans?limit=50");
  }

  getWorkoutPlan(planId: string) {
    return this.client.get<WorkoutPlanApi>(`/planner/plans/${planId}`);
  }

  generateWorkoutPlan(input: GenerateWorkoutPlanInput) {
    return this.client.post<WorkoutPlanApi>("/planner/plans/generate", input);
  }

  activateWorkoutPlan(planId: string) {
    return this.client.post<WorkoutPlanApi>(
      `/planner/plans/${planId}/activate`,
    );
  }

  archiveWorkoutPlan(planId: string) {
    return this.client.post<WorkoutPlanApi>(`/planner/plans/${planId}/archive`);
  }

  getPlannerDayContext(date = localDateOnly(new Date())) {
    return this.client.get<PlannerDayContextApi>(
      `/planner/day-context?date=${encodeURIComponent(date)}`,
    );
  }

  listExercises(filters?: { muscleGroup?: string; search?: string }) {
    const query = new URLSearchParams({ limit: "100" });
    if (filters?.muscleGroup) query.set("muscle_group", filters.muscleGroup);
    if (filters?.search) query.set("search", filters.search);
    return this.client.get<ExerciseCatalogApi[]>(
      `/workouts/exercises?${query.toString()}`,
    );
  }

  previewPlannerAdjustment(input: CreatePlannerAdjustmentInput) {
    return this.client.post<PlannerAdjustmentApi>(
      "/planner/adjustments/preview",
      input,
    );
  }

  listPlannerAdjustments() {
    return this.client.get<PlannerAdjustmentApi[]>(
      "/planner/adjustments?limit=100",
    );
  }

  getPlannerAdjustment(adjustmentId: string) {
    return this.client.get<PlannerAdjustmentApi>(
      `/planner/adjustments/${adjustmentId}`,
    );
  }

  applyPlannerAdjustment(adjustmentId: string) {
    return this.client.post<PlannerAdjustmentApi>(
      `/planner/adjustments/${adjustmentId}/apply`,
    );
  }

  rejectPlannerAdjustment(adjustmentId: string) {
    return this.client.post<PlannerAdjustmentApi>(
      `/planner/adjustments/${adjustmentId}/reject`,
    );
  }

  revertPlannerAdjustment(adjustmentId: string) {
    return this.client.post<PlannerAdjustmentApi>(
      `/planner/adjustments/${adjustmentId}/revert`,
    );
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

  listDietPlans() {
    return this.client.get<DietPlanSummaryApi[]>(
      "/planner/nutrition-plans?limit=50",
    );
  }

  getDietPlan(planId: string) {
    return this.client.get<DietPlanApi>(`/planner/nutrition-plans/${planId}`);
  }

  generateDietPlan(input: GenerateNutritionPlanInput) {
    return this.client.post<DietPlanApi>(
      "/planner/nutrition-plans/generate",
      input,
    );
  }

  activateDietPlan(planId: string) {
    return this.client.post<DietPlanApi>(
      `/planner/nutrition-plans/${planId}/activate`,
    );
  }

  archiveDietPlan(planId: string) {
    return this.client.post<DietPlanApi>(
      `/planner/nutrition-plans/${planId}/archive`,
    );
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

function localDateOnly(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { useAuth } from "@/context/auth-context";
import { EvolvApi } from "@/services/evolv-api";
import type {
  DietPlanApi,
  DietPlanSummaryApi,
  ExerciseCatalogApi,
  FoodLogApi,
  GenerateNutritionPlanInput,
  GenerateWorkoutPlanInput,
  GoalApi,
  GoalType,
  MealApi,
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

type EvolvDataContextValue = {
  profile: ProfileApi | null;
  activeGoal: GoalApi | null;
  workoutPlan: WorkoutPlanApi | null;
  workoutPlans: WorkoutPlanSummaryApi[];
  dietPlan: DietPlanApi | null;
  dietPlans: DietPlanSummaryApi[];
  progressEntries: ProgressEntryApi[];
  progressionSuggestions: ProgressionSuggestionApi[];
  todayFoodLogs: FoodLogApi[];
  nutritionSummary: NutritionSummaryApi | null;
  todayContext: PlannerDayContextApi | null;
  isLoading: boolean;
  hasLoaded: boolean;
  isMutating: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  updateProfile: (input: UpdateProfileInput) => Promise<ProfileApi>;
  createGoal: (input: {
    type: GoalType;
    title: string;
    description?: string;
  }) => Promise<GoalApi>;
  generateWorkoutPlan: (
    input: GenerateWorkoutPlanInput,
  ) => Promise<WorkoutPlanApi>;
  loadWorkoutPlan: (planId: string) => Promise<WorkoutPlanApi>;
  activateWorkoutPlan: (planId: string) => Promise<WorkoutPlanApi>;
  archiveWorkoutPlan: (planId: string) => Promise<WorkoutPlanApi>;
  generateDietPlan: (input: GenerateNutritionPlanInput) => Promise<DietPlanApi>;
  loadDietPlan: (planId: string) => Promise<DietPlanApi>;
  activateDietPlan: (planId: string) => Promise<DietPlanApi>;
  archiveDietPlan: (planId: string) => Promise<DietPlanApi>;
  findExerciseAlternatives: (
    muscleGroup: string,
  ) => Promise<ExerciseCatalogApi[]>;
  previewPlannerAdjustment: (
    input: CreatePlannerAdjustmentInput,
  ) => Promise<PlannerAdjustmentApi>;
  listPlannerAdjustments: () => Promise<PlannerAdjustmentApi[]>;
  loadPlannerAdjustment: (
    adjustmentId: string,
  ) => Promise<PlannerAdjustmentApi>;
  applyPlannerAdjustment: (
    adjustmentId: string,
  ) => Promise<PlannerAdjustmentApi>;
  rejectPlannerAdjustment: (
    adjustmentId: string,
  ) => Promise<PlannerAdjustmentApi>;
  revertPlannerAdjustment: (
    adjustmentId: string,
  ) => Promise<PlannerAdjustmentApi>;
  recordExerciseLoad: (
    exerciseId: string,
    input: {
      load_kg: number;
      sets_completed?: number;
      reps_summary?: string;
    },
  ) => Promise<void>;
  toggleMealRegistration: (meal: MealApi) => Promise<void>;
  addProgressEntry: (input: {
    weight_kg?: number;
    waist_cm?: number;
    chest_cm?: number;
    arm_cm?: number;
    leg_cm?: number;
    notes?: string;
  }) => Promise<ProgressEntryApi>;
};

const EvolvDataContext = createContext<EvolvDataContextValue | null>(null);

const emptySummary: NutritionSummaryApi = {
  calories_kcal: 0,
  protein_g: 0,
  carbohydrate_g: 0,
  fat_g: 0,
  fiber_g: 0,
};

const messageFromError = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Nao foi possivel atualizar os dados.";

const toPlanSummary = (plan: WorkoutPlanApi): WorkoutPlanSummaryApi => ({
  id: plan.id,
  name: plan.name,
  status: plan.status,
  start_date: plan.start_date,
  end_date: plan.end_date,
  weekly_frequency: plan.weekly_frequency,
  split_type: plan.split_type,
  split_label: plan.split_label,
  planner_version: plan.planner_version,
  created_at: plan.created_at,
  updated_at: plan.updated_at,
});

const replacePlanSummary = (
  plans: WorkoutPlanSummaryApi[],
  nextPlan: WorkoutPlanApi,
) => {
  const next = toPlanSummary(nextPlan);
  const normalized = plans.map((plan) => {
    if (plan.id === next.id) return next;
    if (next.status === "active" && plan.status === "active") {
      return { ...plan, status: "archived" };
    }
    return plan;
  });
  return normalized.some((plan) => plan.id === next.id)
    ? normalized
    : [next, ...normalized];
};

const toDietPlanSummary = (plan: DietPlanApi): DietPlanSummaryApi => ({
  id: plan.id,
  name: plan.name,
  status: plan.status,
  daily_calories_target: plan.daily_calories_target,
  daily_protein_target_g: plan.daily_protein_target_g,
  uses_day_variants: plan.uses_day_variants,
  training_day_calories_target: plan.training_day_calories_target,
  rest_day_calories_target: plan.rest_day_calories_target,
  menu_rotation_enabled: plan.menu_rotation_enabled,
  menu_rotation_size: plan.menu_rotation_size,
  flexible_meal_frequency: plan.flexible_meal_frequency,
  flexible_meal_weekday: plan.flexible_meal_weekday,
  alcohol_frequency: plan.alcohol_frequency,
  alcohol_preferred_weekday: plan.alcohol_preferred_weekday,
  alcohol_max_servings: plan.alcohol_max_servings,
  nutrition_phase: plan.nutrition_phase,
  macro_pattern: plan.macro_pattern,
  food_style: plan.food_style,
  meal_schedule: plan.meal_schedule,
  planner_version: plan.planner_version,
  created_at: plan.created_at,
  updated_at: plan.updated_at,
});

const replaceDietPlanSummary = (
  plans: DietPlanSummaryApi[],
  nextPlan: DietPlanApi,
) => {
  const next = toDietPlanSummary(nextPlan);
  const normalized = plans.map((plan) => {
    if (plan.id === next.id) return next;
    if (next.status === "active" && plan.status === "active") {
      return { ...plan, status: "archived" };
    }
    return plan;
  });
  return normalized.some((plan) => plan.id === next.id)
    ? normalized
    : [next, ...normalized];
};

export function EvolvDataProvider({ children }: PropsWithChildren) {
  const { session } = useAuth();
  const [profile, setProfile] = useState<ProfileApi | null>(null);
  const [activeGoal, setActiveGoal] = useState<GoalApi | null>(null);
  const [workoutPlan, setWorkoutPlan] = useState<WorkoutPlanApi | null>(null);
  const [workoutPlans, setWorkoutPlans] = useState<WorkoutPlanSummaryApi[]>([]);
  const [dietPlan, setDietPlan] = useState<DietPlanApi | null>(null);
  const [dietPlans, setDietPlans] = useState<DietPlanSummaryApi[]>([]);
  const [progressEntries, setProgressEntries] = useState<ProgressEntryApi[]>(
    [],
  );
  const [progressionSuggestions, setProgressionSuggestions] = useState<
    ProgressionSuggestionApi[]
  >([]);
  const [todayFoodLogs, setTodayFoodLogs] = useState<FoodLogApi[]>([]);
  const [nutritionSummary, setNutritionSummary] =
    useState<NutritionSummaryApi | null>(null);
  const [todayContext, setTodayContext] =
    useState<PlannerDayContextApi | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadedAccessToken, setLoadedAccessToken] = useState<string | null>(
    null,
  );
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const api = useMemo(
    () => (session?.access_token ? new EvolvApi(session.access_token) : null),
    [session],
  );
  const accessToken = session?.access_token ?? null;
  const hasLoaded = Boolean(accessToken && loadedAccessToken === accessToken);

  const refresh = useCallback(async () => {
    if (!api) return;
    setIsLoading(true);
    setError(null);

    try {
      const [
        nextProfile,
        nextGoal,
        nextWorkoutPlan,
        nextWorkoutPlans,
        nextDietPlan,
        nextDietPlans,
        nextProgress,
        nextSuggestions,
        nextFoodLogs,
        nextSummary,
        nextTodayContext,
      ] = await Promise.all([
        api.getProfile(),
        api.getActiveGoal(),
        api.getActiveWorkoutPlan(),
        api.listWorkoutPlans(),
        api.getActiveDietPlan(),
        api.listDietPlans(),
        api.getProgress(),
        api.getProgressionSuggestions(),
        api.getTodayFoodLogs(),
        api.getTodayNutritionSummary(),
        api.getPlannerDayContext(),
      ]);

      setProfile(nextProfile);
      setActiveGoal(nextGoal);
      setWorkoutPlan(nextWorkoutPlan);
      setWorkoutPlans(nextWorkoutPlans);
      setDietPlan(nextDietPlan);
      setDietPlans(nextDietPlans);
      setProgressEntries(nextProgress);
      setProgressionSuggestions(nextSuggestions);
      setTodayFoodLogs(nextFoodLogs);
      setNutritionSummary(nextSummary ?? emptySummary);
      setTodayContext(nextTodayContext);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setIsLoading(false);
      setLoadedAccessToken(accessToken);
    }
  }, [accessToken, api]);

  useEffect(() => {
    if (!api) return;
    const refreshTimer = setTimeout(() => void refresh(), 0);
    return () => clearTimeout(refreshTimer);
  }, [api, refresh]);

  const mutate = useCallback(async <T,>(operation: () => Promise<T>) => {
    setIsMutating(true);
    setError(null);
    try {
      return await operation();
    } catch (caught) {
      setError(messageFromError(caught));
      throw caught;
    } finally {
      setIsMutating(false);
    }
  }, []);

  const updateProfile = useCallback(
    (input: UpdateProfileInput) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const nextProfile = await api.updateProfile(input);
        setProfile(nextProfile);
        return nextProfile;
      });
    },
    [api, mutate],
  );

  const createGoal = useCallback(
    (input: { type: GoalType; title: string; description?: string }) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const nextGoal = await api.createGoal(input);
        setActiveGoal(nextGoal);
        return nextGoal;
      });
    },
    [api, mutate],
  );

  const generateWorkoutPlan = useCallback(
    (input: GenerateWorkoutPlanInput) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const nextPlan = await api.generateWorkoutPlan(input);
        setWorkoutPlans((current) => replacePlanSummary(current, nextPlan));
        if (nextPlan.status === "active") setWorkoutPlan(nextPlan);
        return nextPlan;
      });
    },
    [api, mutate],
  );

  const loadWorkoutPlan = useCallback(
    (planId: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return api.getWorkoutPlan(planId);
    },
    [api],
  );

  const activateWorkoutPlan = useCallback(
    (planId: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const nextPlan = await api.activateWorkoutPlan(planId);
        setWorkoutPlan(nextPlan);
        setWorkoutPlans((current) => replacePlanSummary(current, nextPlan));
        return nextPlan;
      });
    },
    [api, mutate],
  );

  const archiveWorkoutPlan = useCallback(
    (planId: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const nextPlan = await api.archiveWorkoutPlan(planId);
        setWorkoutPlan((current) => (current?.id === planId ? null : current));
        setWorkoutPlans((current) => replacePlanSummary(current, nextPlan));
        return nextPlan;
      });
    },
    [api, mutate],
  );

  const generateDietPlan = useCallback(
    (input: GenerateNutritionPlanInput) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const nextPlan = await api.generateDietPlan(input);
        setDietPlans((current) => replaceDietPlanSummary(current, nextPlan));
        if (nextPlan.status === "active") setDietPlan(nextPlan);
        return nextPlan;
      });
    },
    [api, mutate],
  );

  const loadDietPlan = useCallback(
    (planId: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return api.getDietPlan(planId);
    },
    [api],
  );

  const activateDietPlan = useCallback(
    (planId: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const nextPlan = await api.activateDietPlan(planId);
        setDietPlan(nextPlan);
        setDietPlans((current) => replaceDietPlanSummary(current, nextPlan));
        return nextPlan;
      });
    },
    [api, mutate],
  );

  const archiveDietPlan = useCallback(
    (planId: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const nextPlan = await api.archiveDietPlan(planId);
        setDietPlan((current) => (current?.id === planId ? null : current));
        setDietPlans((current) => replaceDietPlanSummary(current, nextPlan));
        return nextPlan;
      });
    },
    [api, mutate],
  );

  const findExerciseAlternatives = useCallback(
    (muscleGroup: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return api.listExercises({ muscleGroup });
    },
    [api],
  );

  const previewPlannerAdjustment = useCallback(
    (input: CreatePlannerAdjustmentInput) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(() => api.previewPlannerAdjustment(input));
    },
    [api, mutate],
  );

  const listPlannerAdjustments = useCallback(() => {
    if (!api) return Promise.reject(new Error("Entre na sua conta primeiro."));
    return api.listPlannerAdjustments();
  }, [api]);

  const loadPlannerAdjustment = useCallback(
    (adjustmentId: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return api.getPlannerAdjustment(adjustmentId);
    },
    [api],
  );

  const applyPlannerAdjustment = useCallback(
    (adjustmentId: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const adjustment = await api.applyPlannerAdjustment(adjustmentId);
        await refresh();
        return adjustment;
      });
    },
    [api, mutate, refresh],
  );

  const rejectPlannerAdjustment = useCallback(
    (adjustmentId: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(() => api.rejectPlannerAdjustment(adjustmentId));
    },
    [api, mutate],
  );

  const revertPlannerAdjustment = useCallback(
    (adjustmentId: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const adjustment = await api.revertPlannerAdjustment(adjustmentId);
        await refresh();
        return adjustment;
      });
    },
    [api, mutate, refresh],
  );

  const recordExerciseLoad = useCallback(
    (
      exerciseId: string,
      input: {
        load_kg: number;
        sets_completed?: number;
        reps_summary?: string;
      },
    ) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        await api.recordExerciseLoad(exerciseId, input);
      });
    },
    [api, mutate],
  );

  const toggleMealRegistration = useCallback(
    (meal: MealApi) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const existing = todayFoodLogs.find(
          (log) => log.meal_name === meal.name,
        );
        if (existing) {
          await api.removeFoodLog(existing.id);
          setTodayFoodLogs((current) =>
            current.filter((log) => log.id !== existing.id),
          );
          return;
        }

        const created = await api.createFoodLog({
          meal_name: meal.name,
          description:
            meal.description ||
            meal.meal_items.map((item) => item.name).join(", "),
        });
        setTodayFoodLogs((current) => [created, ...current]);
      });
    },
    [api, mutate, todayFoodLogs],
  );

  const addProgressEntry = useCallback(
    (input: {
      weight_kg?: number;
      waist_cm?: number;
      chest_cm?: number;
      arm_cm?: number;
      leg_cm?: number;
      notes?: string;
    }) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const created = await api.createProgressEntry(input);
        setProgressEntries((current) => [created, ...current]);
        if (created.weight_kg !== null) {
          setProfile((current) =>
            current
              ? { ...current, current_weight_kg: created.weight_kg }
              : current,
          );
        }
        return created;
      });
    },
    [api, mutate],
  );

  const value = useMemo<EvolvDataContextValue>(
    () => ({
      profile: api ? profile : null,
      activeGoal: api ? activeGoal : null,
      workoutPlan: api ? workoutPlan : null,
      workoutPlans: api ? workoutPlans : [],
      dietPlan: api ? dietPlan : null,
      dietPlans: api ? dietPlans : [],
      progressEntries: api ? progressEntries : [],
      progressionSuggestions: api ? progressionSuggestions : [],
      todayFoodLogs: api ? todayFoodLogs : [],
      nutritionSummary: api ? nutritionSummary : null,
      todayContext: api ? todayContext : null,
      isLoading,
      hasLoaded,
      isMutating,
      error,
      refresh,
      updateProfile,
      createGoal,
      generateWorkoutPlan,
      loadWorkoutPlan,
      activateWorkoutPlan,
      archiveWorkoutPlan,
      generateDietPlan,
      loadDietPlan,
      activateDietPlan,
      archiveDietPlan,
      findExerciseAlternatives,
      previewPlannerAdjustment,
      listPlannerAdjustments,
      loadPlannerAdjustment,
      applyPlannerAdjustment,
      rejectPlannerAdjustment,
      revertPlannerAdjustment,
      recordExerciseLoad,
      toggleMealRegistration,
      addProgressEntry,
    }),
    [
      activeGoal,
      activateWorkoutPlan,
      activateDietPlan,
      addProgressEntry,
      api,
      archiveWorkoutPlan,
      archiveDietPlan,
      findExerciseAlternatives,
      previewPlannerAdjustment,
      listPlannerAdjustments,
      loadPlannerAdjustment,
      applyPlannerAdjustment,
      rejectPlannerAdjustment,
      revertPlannerAdjustment,
      createGoal,
      dietPlan,
      dietPlans,
      error,
      hasLoaded,
      generateWorkoutPlan,
      generateDietPlan,
      isLoading,
      isMutating,
      nutritionSummary,
      profile,
      progressEntries,
      progressionSuggestions,
      recordExerciseLoad,
      refresh,
      loadWorkoutPlan,
      loadDietPlan,
      todayFoodLogs,
      todayContext,
      toggleMealRegistration,
      updateProfile,
      workoutPlan,
      workoutPlans,
    ],
  );

  return (
    <EvolvDataContext.Provider value={value}>
      {children}
    </EvolvDataContext.Provider>
  );
}

export function useEvolvData() {
  const context = useContext(EvolvDataContext);
  if (!context) {
    throw new Error("useEvolvData deve ser usado dentro de EvolvDataProvider.");
  }
  return context;
}

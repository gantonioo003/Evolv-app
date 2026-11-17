import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import { AppState } from "react-native";

import { useAuth } from "@/context/auth-context";
import { mapWorkoutPlanToDays } from "@/data/api-mappers";
import { getDailyDiet } from "@/data/daily-diet";
import { localDateOnly, mondayWeekDates, mondayWeekIndex, weekdaysFromSunday } from "@/lib/local-date";
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
  NutritionSummaryApi,
  PlannerAdjustmentApi,
  PlannerDayContextApi,
  PlannerWeekOverridesApi,
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
  today: Date;
  workoutWeek: ReturnType<typeof mapWorkoutPlanToDays>;
  nutritionDayType: PlannerDayContextApi["nutrition_day_type"];
  dailyDiet: ReturnType<typeof getDailyDiet>;
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
      load_kg?: number;
      sets_completed?: number;
      repetitions?: number;
      duration_seconds?: number;
      reps_summary?: string;
    },
  ) => Promise<void>;
  setMealRegistration: (mealId: string, registered: boolean) => Promise<void>;
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

const emptyFoodLogs: FoodLogApi[] = [];

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
  const [todayDate, setTodayDate] = useState(() => localDateOnly(new Date()));
  const today = useMemo(() => new Date(`${todayDate}T00:00:00`), [todayDate]);
  const [foodLogDay, setFoodLogDay] = useState<{ date: string; logs: FoodLogApi[] } | null>(null);
  const todayFoodLogs = foodLogDay?.date === todayDate ? foodLogDay.logs : emptyFoodLogs;
  const refreshRequest = useRef(0);
  const foodLogRequest = useRef(0);
  const registeringMeal = useRef(false);
  const nutritionSummary = useMemo(
    () =>
      todayFoodLogs.flatMap((log) => log.food_log_items).reduce(
        (sum, item) => ({
          calories_kcal: sum.calories_kcal + Number(item.calories_kcal),
          protein_g: sum.protein_g + Number(item.protein_g),
          carbohydrate_g: sum.carbohydrate_g + Number(item.carbohydrate_g),
          fat_g: sum.fat_g + Number(item.fat_g),
          fiber_g: sum.fiber_g + Number(item.fiber_g),
        }),
        emptySummary,
      ),
    [todayFoodLogs],
  );
  const [todayContext, setTodayContext] =
    useState<PlannerDayContextApi | null>(null);
  const [weekOverrides, setWeekOverrides] = useState<PlannerWeekOverridesApi | null>(null);
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

  const workoutWeek = useMemo(() => {
    if (!workoutPlan) return [];
    const calendar = weekOverrides?.dates.includes(todayDate)
      ? weekOverrides
      : { dates: mondayWeekDates(today), overrides: [] };
    return mapWorkoutPlanToDays(workoutPlan, calendar);
  }, [today, todayDate, weekOverrides, workoutPlan]);
  const scheduledTraining =
    workoutWeek[mondayWeekIndex(today)]?.status === "planned" ||
    profile?.available_training_days.includes(weekdaysFromSunday[today.getDay()]);
  const nutritionDayType = todayContext?.activity_date === todayDate
    ? todayContext.nutrition_day_type
    : scheduledTraining ? "training_day" : "rest_day";
  const dailyDiet = useMemo(
    () => getDailyDiet(dietPlan, nutritionDayType, today),
    [dietPlan, nutritionDayType, today],
  );

  const refresh = useCallback(async () => {
    if (!api) return;
    const request = ++refreshRequest.current;
    const now = new Date();
    const date = localDateOnly(now);
    const foodLogRead = ++foodLogRequest.current;
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
        nextTodayContext,
        nextWeekOverrides,
      ] = await Promise.all([
        api.getProfile(),
        api.getActiveGoal(),
        api.getActiveWorkoutPlan(),
        api.listWorkoutPlans(),
        api.getActiveDietPlan(),
        api.listDietPlans(),
        api.getProgress(),
        api.getProgressionSuggestions(),
        api.getTodayFoodLogs(now),
        api.getPlannerDayContext(date),
        api.getPlannerWeekOverrides(date).catch(() => null),
      ]);

      if (request !== refreshRequest.current) return;
      setProfile(nextProfile);
      setActiveGoal(nextGoal);
      setWorkoutPlan(nextWorkoutPlan);
      setWorkoutPlans(nextWorkoutPlans);
      setDietPlan(nextDietPlan);
      setDietPlans(nextDietPlans);
      setProgressEntries(nextProgress);
      setProgressionSuggestions(nextSuggestions);
      if (foodLogRead === foodLogRequest.current) {
        setFoodLogDay({ date, logs: nextFoodLogs });
      }
      setTodayContext(nextTodayContext);
      setWeekOverrides(nextWeekOverrides);
    } catch (caught) {
      if (request === refreshRequest.current) setError(messageFromError(caught));
    } finally {
      if (request === refreshRequest.current) {
        setIsLoading(false);
        setLoadedAccessToken(accessToken);
      }
    }
  }, [accessToken, api]);

  useEffect(() => {
    let midnightTimer: ReturnType<typeof setTimeout>;
    const syncDate = () => {
      const now = new Date();
      const midnight = new Date(now);
      midnight.setHours(24, 0, 0, 0);
      setTodayDate(localDateOnly(now));
      clearTimeout(midnightTimer);
      midnightTimer = setTimeout(syncDate, midnight.getTime() - now.getTime());
    };

    syncDate();
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") syncDate();
    });
    return () => {
      clearTimeout(midnightTimer);
      subscription.remove();
    };
  }, []);

  const invalidatePendingReads = useCallback(() => {
    refreshRequest.current++;
    foodLogRequest.current++;
  }, []);

  useEffect(() => {
    if (!api) return;
    const refreshTimer = setTimeout(() => void refresh(), 0);
    return () => {
      clearTimeout(refreshTimer);
      invalidatePendingReads();
    };
  }, [api, invalidatePendingReads, refresh, todayDate]);

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
        if (input.available_training_days !== undefined) await refresh();
        return nextProfile;
      });
    },
    [api, mutate, refresh],
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
        if (nextPlan.status === "active") {
          setWorkoutPlan(nextPlan);
          await refresh();
        }
        return nextPlan;
      });
    },
    [api, mutate, refresh],
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
        await refresh();
        return nextPlan;
      });
    },
    [api, mutate, refresh],
  );

  const archiveWorkoutPlan = useCallback(
    (planId: string) => {
      if (!api)
        return Promise.reject(new Error("Entre na sua conta primeiro."));
      return mutate(async () => {
        const nextPlan = await api.archiveWorkoutPlan(planId);
        setWorkoutPlan((current) => (current?.id === planId ? null : current));
        setWorkoutPlans((current) => replacePlanSummary(current, nextPlan));
        await refresh();
        return nextPlan;
      });
    },
    [api, mutate, refresh],
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
        load_kg?: number;
        sets_completed?: number;
        repetitions?: number;
        duration_seconds?: number;
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

  const setMealRegistration = useCallback(
    async (mealId: string, registered: boolean) => {
      if (!api) throw new Error("Entre na sua conta primeiro.");
      if (registeringMeal.current) return;
      const now = new Date();
      const date = localDateOnly(now);
      if (date !== todayDate) throw new Error("O dia mudou. Confira o cardápio de hoje.");
      registeringMeal.current = true;
      try {
        await mutate(async () => {
          await api.setPlannedMealRegistration(mealId, registered, now);
          if (date !== localDateOnly(new Date())) return;
          const foodLogRead = ++foodLogRequest.current;
          const logs = await api.getTodayFoodLogs(now);
          if (foodLogRead === foodLogRequest.current) setFoodLogDay({ date, logs });
        });
      } finally {
        registeringMeal.current = false;
      }
    },
    [api, mutate, todayDate],
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
      todayFoodLogs: hasLoaded ? todayFoodLogs : emptyFoodLogs,
      nutritionSummary: hasLoaded ? nutritionSummary : null,
      today,
      workoutWeek: hasLoaded ? workoutWeek : [],
      nutritionDayType,
      dailyDiet: hasLoaded ? dailyDiet : null,
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
      setMealRegistration,
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
      today,
      todayFoodLogs,
      workoutWeek,
      nutritionDayType,
      dailyDiet,
      setMealRegistration,
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

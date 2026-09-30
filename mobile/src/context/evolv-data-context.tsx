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
  FoodLogApi,
  GoalApi,
  GoalType,
  MealApi,
  NutritionSummaryApi,
  ProfileApi,
  ProgressEntryApi,
  ProgressionSuggestionApi,
  UpdateProfileInput,
  WorkoutPlanApi,
} from "@/types/api";

type EvolvDataContextValue = {
  profile: ProfileApi | null;
  activeGoal: GoalApi | null;
  workoutPlan: WorkoutPlanApi | null;
  dietPlan: DietPlanApi | null;
  progressEntries: ProgressEntryApi[];
  progressionSuggestions: ProgressionSuggestionApi[];
  todayFoodLogs: FoodLogApi[];
  nutritionSummary: NutritionSummaryApi | null;
  isLoading: boolean;
  isMutating: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  updateProfile: (input: UpdateProfileInput) => Promise<ProfileApi>;
  createGoal: (input: {
    type: GoalType;
    title: string;
    description?: string;
  }) => Promise<GoalApi>;
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

export function EvolvDataProvider({ children }: PropsWithChildren) {
  const { session } = useAuth();
  const [profile, setProfile] = useState<ProfileApi | null>(null);
  const [activeGoal, setActiveGoal] = useState<GoalApi | null>(null);
  const [workoutPlan, setWorkoutPlan] = useState<WorkoutPlanApi | null>(null);
  const [dietPlan, setDietPlan] = useState<DietPlanApi | null>(null);
  const [progressEntries, setProgressEntries] = useState<ProgressEntryApi[]>(
    [],
  );
  const [progressionSuggestions, setProgressionSuggestions] = useState<
    ProgressionSuggestionApi[]
  >([]);
  const [todayFoodLogs, setTodayFoodLogs] = useState<FoodLogApi[]>([]);
  const [nutritionSummary, setNutritionSummary] =
    useState<NutritionSummaryApi | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const api = useMemo(
    () => (session?.access_token ? new EvolvApi(session.access_token) : null),
    [session],
  );

  const refresh = useCallback(async () => {
    if (!api) return;
    setIsLoading(true);
    setError(null);

    try {
      const [
        nextProfile,
        nextGoal,
        nextWorkoutPlan,
        nextDietPlan,
        nextProgress,
        nextSuggestions,
        nextFoodLogs,
        nextSummary,
      ] = await Promise.all([
        api.getProfile(),
        api.getActiveGoal(),
        api.getActiveWorkoutPlan(),
        api.getActiveDietPlan(),
        api.getProgress(),
        api.getProgressionSuggestions(),
        api.getTodayFoodLogs(),
        api.getTodayNutritionSummary(),
      ]);

      setProfile(nextProfile);
      setActiveGoal(nextGoal);
      setWorkoutPlan(nextWorkoutPlan);
      setDietPlan(nextDietPlan);
      setProgressEntries(nextProgress);
      setProgressionSuggestions(nextSuggestions);
      setTodayFoodLogs(nextFoodLogs);
      setNutritionSummary(nextSummary ?? emptySummary);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setIsLoading(false);
    }
  }, [api]);

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
      dietPlan: api ? dietPlan : null,
      progressEntries: api ? progressEntries : [],
      progressionSuggestions: api ? progressionSuggestions : [],
      todayFoodLogs: api ? todayFoodLogs : [],
      nutritionSummary: api ? nutritionSummary : null,
      isLoading,
      isMutating,
      error,
      refresh,
      updateProfile,
      createGoal,
      recordExerciseLoad,
      toggleMealRegistration,
      addProgressEntry,
    }),
    [
      activeGoal,
      addProgressEntry,
      api,
      createGoal,
      dietPlan,
      error,
      isLoading,
      isMutating,
      nutritionSummary,
      profile,
      progressEntries,
      progressionSuggestions,
      recordExerciseLoad,
      refresh,
      todayFoodLogs,
      toggleMealRegistration,
      updateProfile,
      workoutPlan,
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

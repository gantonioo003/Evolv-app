import type { Meal, WorkoutDay } from "@/types/domain";
import type { DietPlanApi, WorkoutPlanApi } from "@/types/api";

const weekdays = [
  ["monday", "Segunda", "SEG"],
  ["tuesday", "Terça", "TER"],
  ["wednesday", "Quarta", "QUA"],
  ["thursday", "Quinta", "QUI"],
  ["friday", "Sexta", "SEX"],
  ["saturday", "Sábado", "SÁB"],
  ["sunday", "Domingo", "DOM"],
] as const;

export function mapWorkoutPlanToDays(plan: WorkoutPlanApi): WorkoutDay[] {
  return weekdays.map(([weekday, label, shortLabel]) => {
    const day = plan.workout_days.find((item) => item.weekday === weekday);
    if (!day) {
      return {
        id: weekday,
        weekday: label,
        shortLabel,
        title: "Descanso",
        durationMinutes: 0,
        status: "rest",
        exercises: [],
      };
    }

    return {
      id: day.id,
      weekday: label,
      shortLabel,
      title: day.title,
      durationMinutes: day.estimated_minutes ?? 0,
      status: "planned",
      exercises: day.workout_day_exercises.map((item) => ({
        id: item.exercise_id,
        name: item.exercises.name,
        sets: item.sets,
        reps:
          item.min_reps === item.max_reps
            ? String(item.min_reps)
            : `${item.min_reps}-${item.max_reps}`,
        restSeconds: item.rest_seconds ?? 0,
        load: item.target_load_kg ?? 0,
        unit: "kg",
        note: item.notes ?? undefined,
      })),
    };
  });
}

export function mapDietPlanToMeals(plan: DietPlanApi): Meal[] {
  return plan.meals.map((meal) => ({
    id: meal.id,
    label: meal.meal_time?.slice(0, 5) ?? `Refeição ${meal.position + 1}`,
    title: meal.name,
    description:
      meal.description || meal.meal_items.map((item) => item.name).join(", "),
    calories: meal.calories_target ?? 0,
    protein: meal.protein_target_g ?? 0,
    carbs: meal.carbohydrate_target_g ?? 0,
    fat: meal.fat_target_g ?? 0,
  }));
}

export function workoutImageCategoryFromText(value: string) {
  const normalized = value.toLocaleLowerCase("pt-BR");
  if (normalized.includes("costa") || normalized.includes("bíceps"))
    return "back";
  if (normalized.includes("peito") || normalized.includes("tríceps"))
    return "chest";
  if (normalized.includes("perna") || normalized.includes("glúte"))
    return "legs";
  if (normalized.includes("ombro")) return "shoulders";
  if (normalized.includes("cardio") || normalized.includes("corrida"))
    return "cardio";
  if (normalized.includes("mobilidade") || normalized.includes("recuper"))
    return "recovery";
  return "fullBody";
}

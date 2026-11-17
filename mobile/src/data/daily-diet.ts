import { calendarDayIndex } from "@/lib/local-date";
import type { DietPlanApi, PlannerDayContextApi } from "@/types/api";

export function getDailyDiet(
  plan: DietPlanApi | null,
  dayType: PlannerDayContextApi["nutrition_day_type"],
  date: Date,
) {
  if (!plan) return null;
  const rotationSize = plan.menu_rotation_enabled
    ? Math.max(1, plan.menu_rotation_size)
    : 1;
  const rotationIndex = calendarDayIndex(date) % rotationSize;
  const meals = plan.meals.filter(
    (meal) =>
      (!plan.uses_day_variants || meal.day_type === dayType) &&
      meal.rotation_index === rotationIndex,
  );
  const calorieTarget = plan.uses_day_variants
    ? dayType === "training_day"
      ? plan.training_day_calories_target
      : plan.rest_day_calories_target
    : plan.daily_calories_target;
  return {
    meals,
    calorieTarget: calorieTarget ?? 0,
    proteinTarget: plan.uses_day_variants
      ? Math.round(meals.reduce((sum, meal) => sum + (meal.protein_target_g ?? 0), 0))
      : (plan.daily_protein_target_g ?? 0),
  };
}

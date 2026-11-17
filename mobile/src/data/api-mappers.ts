import type { Meal, WorkoutDay } from "@/types/domain";
import type { DietPlanApi, PlannerWeekOverridesApi, WorkoutDayExerciseApi, WorkoutPlanApi } from "@/types/api";

function exerciseLogMetric(item: WorkoutDayExerciseApi) {
  const { name, movement_pattern, equipment: rawEquipment } = item.exercises;
  const equipment = rawEquipment ?? "";
  const normalizedName = name.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
  const assisted = /\b(?:assistid[ao]s?|assisted|graviton)\b/.test(normalizedName);
  const barPull = !assisted && /^(?:barra fixa|(?:chin|pull)[ -]?ups?)\b/.test(normalizedName);
  // These two catalogue exercises use a support bench, even though its slug says machine.
  const usesSupportBench = /^(?:glute ham raise|extensao lombar)$/.test(normalizedName);
  const bodyweight = !assisted && (barPull || usesSupportBench ||
    /^(bodyweight|pull_up_bar|dip_station|suspension_trainer)$/.test(equipment));
  const isHold = movement_pattern === "isometric" ||
    /^(?:prancha(?: lateral)?|l-sit)$/.test(normalizedName);
  const timed = item.prescription_kind === "duration" || isHold;
  const hasWeightTarget = (item.target_load_kg ?? 0) > 0;
  const weightedEquipment = /(?:_machine$|^leg_press)|^(cable_station|barbell|dumbbell|ez_bar|kettlebell|landmine|medicine_ball|pec_deck|sled)$/.test(equipment);
  const logMetric = timed ? "time" : barPull || hasWeightTarget || (weightedEquipment && !usesSupportBench)
    ? "load" : "reps";
  const canAddLoad = bodyweight && logMetric !== "load" &&
    (!timed || isHold) &&
    !["jump", "conditioning", "mobility", "stretching"].includes(movement_pattern ?? "");
  return { logMetric, canAddLoad, loadIsAdded: logMetric === "load" && bodyweight } as const;
}

const weekdays = [
  ["monday", "Segunda", "SEG"],
  ["tuesday", "Terça", "TER"],
  ["wednesday", "Quarta", "QUA"],
  ["thursday", "Quinta", "QUI"],
  ["friday", "Sexta", "SEX"],
  ["saturday", "Sábado", "SÁB"],
  ["sunday", "Domingo", "DOM"],
] as const;

export function mapWorkoutPlanToDays(plan: WorkoutPlanApi, calendar?: PlannerWeekOverridesApi | null): WorkoutDay[] {
  return weekdays.map(([weekday, label, shortLabel], index) => {
    const date = calendar?.dates[index];
    const override = calendar?.overrides.find((item) => item.activity_date === date);
    const active = !date || (date >= plan.start_date && (!plan.end_date || date <= plan.end_date));
    const day = active && plan.workout_days.find((item) => override
      ? override.activity_type !== "rest" && item.id === override.workout_day_id
      : item.weekday === weekday);
    if (!day) {
      return {
        id: weekday,
        weekday: label,
        shortLabel,
        title: override?.activity_type === "cardio" ? "Cardio" :
          override?.activity_type === "mixed" ? "Treino misto" :
          override?.activity_type === "resistance" ? "Musculação" : "Descanso",
        durationMinutes: 0,
        status: override && override.activity_type !== "rest" ? "planned" : "rest",
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
        planItemId: item.id,
        ...exerciseLogMetric(item),
        name: item.exercises.name,
        sets: item.sets ?? 0,
        reps:
          item.prescription_kind === "duration"
            ? `${item.duration_minutes ?? 0} min`
            : item.min_reps === item.max_reps
              ? String(item.min_reps ?? 0)
              : `${item.min_reps ?? 0}-${item.max_reps ?? 0}`,
        durationMinutes: item.duration_minutes ?? undefined,
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
  if (normalized.includes("descanso") || normalized.trim() === "livre")
    return "recovery";
  if (/costa|bíceps|superiore?s?|upper/.test(normalized))
    return "back";
  if (normalized.includes("peito") || normalized.includes("tríceps"))
    return "chest";
  if (/perna|glúte|inferiore?s?|lower/.test(normalized))
    return "legs";
  if (normalized.includes("ombro")) return "shoulders";
  if (/cardio|corrida|bicicleta/.test(normalized))
    return "cardio";
  if (normalized.includes("mobilidade") || normalized.includes("recuper"))
    return "recovery";
  return "fullBody";
}

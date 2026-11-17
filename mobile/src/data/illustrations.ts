import type { ImageSourcePropType } from "react-native";

import { workoutImageCategoryFromText } from "@/data/api-mappers";
import type { WorkoutDay } from "@/types/domain";

export type ThemeArtwork = {
  light: ImageSourcePropType;
  dark: ImageSourcePropType;
};

export const artwork = {
  today: {
    dark: require("@/assets/illustrations/blue/today.jpg"),
    light: require("@/assets/illustrations/light/today.jpg"),
  },
  workout: {
    dark: require("@/assets/illustrations/blue/workout.jpg"),
    light: require("@/assets/illustrations/light/workout.jpg"),
  },
  coach: {
    dark: require("@/assets/illustrations/blue/coach.jpg"),
    light: require("@/assets/illustrations/light/coach.jpg"),
  },
  diet: {
    dark: require("@/assets/illustrations/blue/diet.jpg"),
    light: require("@/assets/illustrations/light/diet.jpg"),
  },
  account: {
    dark: require("@/assets/illustrations/blue/account.jpg"),
    light: require("@/assets/illustrations/light/account.jpg"),
  },
  login: {
    dark: require("@/assets/illustrations/blue/login.jpg"),
    light: require("@/assets/illustrations/light/login.jpg"),
  },
  recovery: {
    dark: require("@/assets/illustrations/blue/recovery.jpg"),
    light: require("@/assets/illustrations/light/recovery.jpg"),
  },
  workoutPlan: {
    dark: require("@/assets/illustrations/blue/workout-plan.jpg"),
    light: require("@/assets/illustrations/light/workout-plan.jpg"),
  },
  upperBody: {
    dark: require("@/assets/illustrations/blue/upper-body.jpg"),
    light: require("@/assets/illustrations/light/upper-body.jpg"),
  },
  lowerBody: {
    dark: require("@/assets/illustrations/blue/lower-body.jpg"),
    light: require("@/assets/illustrations/light/lower-body.jpg"),
  },
  cardio: {
    dark: require("@/assets/illustrations/blue/cardio.jpg"),
    light: require("@/assets/illustrations/light/cardio.jpg"),
  },
  mobility: {
    dark: require("@/assets/illustrations/blue/mobility.jpg"),
    light: require("@/assets/illustrations/light/mobility.jpg"),
  },
  breakfast: {
    dark: require("@/assets/illustrations/blue/breakfast.jpg"),
    light: require("@/assets/illustrations/light/breakfast.jpg"),
  },
  lunch: {
    dark: require("@/assets/illustrations/blue/lunch.jpg"),
    light: require("@/assets/illustrations/light/lunch.jpg"),
  },
  snack: {
    dark: require("@/assets/illustrations/blue/snack.jpg"),
    light: require("@/assets/illustrations/light/snack.jpg"),
  },
  dinner: {
    dark: require("@/assets/illustrations/blue/dinner.jpg"),
    light: require("@/assets/illustrations/light/dinner.jpg"),
  },
  mealPlan: {
    dark: require("@/assets/illustrations/blue/meal-plan.jpg"),
    light: require("@/assets/illustrations/light/meal-plan.jpg"),
  },
  flexibleMeal: {
    dark: require("@/assets/illustrations/blue/flexible-meal.jpg"),
    light: require("@/assets/illustrations/light/flexible-meal.jpg"),
  },
  progress: {
    dark: require("@/assets/illustrations/blue/progress.jpg"),
    light: require("@/assets/illustrations/light/progress.jpg"),
  },
  onboarding: {
    dark: require("@/assets/illustrations/blue/onboarding.jpg"),
    light: require("@/assets/illustrations/light/onboarding.jpg"),
  },
  coachMemory: {
    dark: require("@/assets/illustrations/blue/coach-memory.jpg"),
    light: require("@/assets/illustrations/light/coach-memory.jpg"),
  },
  adjustments: {
    dark: require("@/assets/illustrations/blue/adjustments.jpg"),
    light: require("@/assets/illustrations/light/adjustments.jpg"),
  },
  trainingPreferences: {
    dark: require("@/assets/illustrations/blue/training-preferences.jpg"),
    light: require("@/assets/illustrations/light/training-preferences.jpg"),
  },
  privacy: {
    dark: require("@/assets/illustrations/blue/privacy.jpg"),
    light: require("@/assets/illustrations/light/privacy.jpg"),
  },
} satisfies Record<string, ThemeArtwork>;

const workoutArtwork = {
  back: artwork.upperBody,
  chest: artwork.upperBody,
  shoulders: artwork.upperBody,
  legs: artwork.lowerBody,
  cardio: artwork.cardio,
  recovery: artwork.mobility,
  fullBody: artwork.workout,
} satisfies Record<ReturnType<typeof workoutImageCategoryFromText>, ThemeArtwork>;

export function workoutIllustration(day: WorkoutDay, focus?: string): ThemeArtwork {
  if (day.status === "rest") return artwork.recovery;
  if (day.status === "free") return artwork.workoutPlan;
  return workoutArtwork[workoutImageCategoryFromText([day.title, focus].filter(Boolean).join(" "))];
}

export function mealIllustration(title: string): ThemeArtwork | undefined {
  const name = title.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase("pt-BR");
  if (/\b(lanche|ceia)\b/.test(name)) return artwork.snack;
  if (/\b(cafe|desjejum)\b/.test(name)) return artwork.breakfast;
  if (/\balmoco\b/.test(name)) return artwork.lunch;
  if (/\b(jantar|janta)\b/.test(name)) return artwork.dinner;
}

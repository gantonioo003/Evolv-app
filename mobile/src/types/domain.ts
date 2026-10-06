export type Exercise = {
  id: string;
  name: string;
  sets: number;
  reps: string;
  durationMinutes?: number;
  restSeconds: number;
  load: number;
  unit: "kg";
  note?: string;
};

export type WorkoutDay = {
  id: string;
  weekday: string;
  shortLabel: string;
  title: string;
  durationMinutes: number;
  status: "planned" | "free" | "rest";
  exercises: Exercise[];
};

export type Meal = {
  id: string;
  label: string;
  title: string;
  description: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
};

export type CoachMessage = {
  id: string;
  sender: "coach" | "user";
  text: string;
};

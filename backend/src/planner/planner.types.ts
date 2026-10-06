import type { Enums } from '../database/database.types.js';

export const plannerGoals = [
  'hypertrophy',
  'fat_loss',
  'strength',
  'health',
  'recomposition',
  'maintenance',
] as const;

export const plannerLevels = ['beginner', 'intermediate', 'advanced'] as const;

export const plannerModalities = [
  'full-gym',
  'machines',
  'free-weights',
  'cables',
  'calisthenics',
  'bands',
  'functional',
  'suspension',
  'bodyweight',
  'cardio-equipment',
  'running',
  'walking',
  'cycling',
  'rowing',
  'stairs',
  'swimming',
  'hiit',
  'plyometrics',
  'yoga-pilates',
  'sports',
  'mobility',
  'stretching',
] as const;

export const plannerSplitTypes = [
  'full_body',
  'upper_lower',
  'push_pull_legs',
  'body_part',
  'hybrid',
  'custom',
] as const;

export type PlannerGoal = (typeof plannerGoals)[number];
export type PlannerLevel = (typeof plannerLevels)[number];
export type PlannerModality = (typeof plannerModalities)[number];
export type PlannerSplitType = (typeof plannerSplitTypes)[number];
export type PlannerWeekday = Enums<'weekday'>;
export type PlannerSessionProfile = 'compact' | 'standard' | 'extended';
export type PlannerComposition =
  'resistance' | 'cardio' | 'mobility' | 'mixed' | 'unspecified';

export type PlannerInput = {
  goal?: PlannerGoal;
  level?: PlannerLevel;
  availableDays: PlannerWeekday[];
  sessionMinutes?: number;
  modalities?: PlannerModality[];
  desiredWeeklyFrequency?: number;
};

export type PlannerDayTemplate = {
  weekday: PlannerWeekday;
  position: number;
  title: string;
  focus: string;
  estimatedMinutes: number;
};

export const plannerStabilityPolicy = {
  deterministic: true,
  automaticMutations: false,
  requiresUserConfirmation: true,
  preserveUnchangedDays: true,
  minimumReviewWindowDays: 14,
} as const;

export type PlannerRecommendation = {
  goal: PlannerGoal;
  level: PlannerLevel;
  weeklyFrequency: number;
  splitType: PlannerSplitType;
  splitLabel: string;
  agendaLabel: string;
  sessionMinutes: number;
  sessionProfile: PlannerSessionProfile;
  composition: PlannerComposition;
  modalities: PlannerModality[];
  days: PlannerDayTemplate[];
  assumptions: string[];
  rationale: string[];
  warnings: string[];
  stabilityPolicy: typeof plannerStabilityPolicy;
};

export type PlannerExerciseKind = 'resistance' | 'cardio' | 'mobility';
export type PlannerExerciseRole =
  'primary' | 'secondary' | 'accessory' | 'core' | 'conditioning' | 'mobility';

export type PlannerExerciseCandidate = {
  id: string;
  name: string;
  muscleGroup: string;
  equipment?: string | null;
  equipmentCategory?: string | null;
  movementPattern?: string | null;
  difficulty?: PlannerLevel | null;
  isCompound: boolean;
  kind?: PlannerExerciseKind;
  modalities?: PlannerModality[];
};

export type PlannerGenerationConstraints = {
  avoidedExerciseIds?: string[];
  availableEquipment?: string[];
};

export type PlannerGenerationRequest = {
  input: PlannerInput;
  exercises: PlannerExerciseCandidate[];
  constraints?: PlannerGenerationConstraints;
};

export type PlannerRepetitionPrescription = {
  kind: 'repetitions';
  sets: number;
  minReps: number;
  maxReps: number;
  restSeconds: number;
};

export type PlannerDurationPrescription = {
  kind: 'duration';
  durationMinutes: number;
  restSeconds: number;
};

export type PlannerExercisePrescription =
  PlannerRepetitionPrescription | PlannerDurationPrescription;

export type PlannerGeneratedExercise = {
  exerciseId: string;
  name: string;
  position: number;
  muscleGroup: string;
  movementPattern: string | null;
  equipment: string | null;
  isCompound: boolean;
  role: PlannerExerciseRole;
  prescription: PlannerExercisePrescription;
};

export type PlannerGeneratedDay = PlannerDayTemplate & {
  exercises: PlannerGeneratedExercise[];
  totalWorkSets: number;
};

export type PlannerGenerationSummary = {
  ruleVersion: 'planner-rules-v1';
  catalogSize: number;
  eligibleCatalogSize: number;
  totalWeeklySets: number;
  weeklySetsByMuscle: Record<string, number>;
  weeklySetCapPerMuscle: number;
};

export type PlannerGeneratedPlan = Omit<PlannerRecommendation, 'days'> & {
  days: PlannerGeneratedDay[];
  generation: PlannerGenerationSummary;
};

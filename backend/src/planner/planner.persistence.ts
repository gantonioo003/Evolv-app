import type { Json } from '../database/database.types.js';
import type { PlannerGeneratedPlan } from './planner.types.js';

type BuildPlannerPayloadOptions = {
  generated: PlannerGeneratedPlan;
  userId: string;
  goalId: string | null;
  name: string;
  startDate: string;
  status: 'draft' | 'active';
};

export function buildPlannerPersistencePayload({
  generated,
  userId,
  goalId,
  name,
  startDate,
  status,
}: BuildPlannerPayloadOptions): Json {
  return {
    user_id: userId,
    goal_id: goalId,
    name,
    status,
    start_date: startDate,
    end_date: null,
    weekly_frequency: generated.weeklyFrequency,
    notes: generated.warnings.length ? generated.warnings.join(' ') : null,
    split_type: generated.splitType,
    split_label: generated.splitLabel,
    planner_version: generated.generation.ruleVersion,
    planner_input: {
      goal: generated.goal,
      level: generated.level,
      session_minutes: generated.sessionMinutes,
      modalities: generated.modalities,
      assumptions: generated.assumptions,
      weekly_set_cap_per_muscle: generated.generation.weeklySetCapPerMuscle,
    },
    days: generated.days.map((day) => ({
      weekday: day.weekday,
      position: day.position,
      title: day.title,
      focus: day.focus,
      estimated_minutes: day.estimatedMinutes,
      exercises: day.exercises.map((exercise) => {
        const common = {
          exercise_id: exercise.exerciseId,
          position: exercise.position,
          rest_seconds: exercise.prescription.restSeconds,
          planner_role: exercise.role,
          notes: null,
        };

        if (exercise.prescription.kind === 'duration') {
          return {
            ...common,
            prescription_kind: 'duration',
            sets: null,
            min_reps: null,
            max_reps: null,
            duration_minutes: exercise.prescription.durationMinutes,
          };
        }

        return {
          ...common,
          prescription_kind: 'repetitions',
          sets: exercise.prescription.sets,
          min_reps: exercise.prescription.minReps,
          max_reps: exercise.prescription.maxReps,
          duration_minutes: null,
        };
      }),
    })),
  };
}

import { Injectable, NotFoundException } from '@nestjs/common';
import type { SupabaseClient } from '@supabase/supabase-js';
import { throwDatabaseError } from '../common/errors/database.error.js';
import type { Database, Enums, Tables } from '../database/database.types.js';
import { SupabaseService } from '../supabase/supabase.service.js';
import type { GeneratePlannerPlanDto } from './dto/generate-planner-plan.dto.js';
import type { ListPlannerPlansQueryDto } from './dto/list-planner-plans-query.dto.js';
import { generateWorkoutPlan } from './planner.generator.js';
import { buildPlannerPersistencePayload } from './planner.persistence.js';
import { recommendPlannerStructure } from './planner.rules.js';
import type {
  PlannerExerciseCandidate,
  PlannerExerciseKind,
  PlannerGeneratedPlan,
  PlannerGenerationRequest,
  PlannerGoal,
  PlannerInput,
  PlannerLevel,
  PlannerModality,
  PlannerRecommendation,
  PlannerWeekday,
} from './planner.types.js';

type ExerciseRow = Pick<
  Tables<'exercises'>,
  | 'id'
  | 'name'
  | 'muscle_group'
  | 'equipment'
  | 'movement_pattern'
  | 'difficulty'
  | 'is_compound'
  | 'training_kind'
  | 'planner_modalities'
>;

const weekdays: PlannerWeekday[] = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
];

const plannerLevels = new Set<PlannerLevel>([
  'beginner',
  'intermediate',
  'advanced',
]);

const plannerExerciseKinds = new Set<PlannerExerciseKind>([
  'resistance',
  'cardio',
  'mobility',
]);

const plannerModalities = new Set<PlannerModality>([
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
]);

@Injectable()
export class PlannerService {
  constructor(private readonly supabase: SupabaseService) {}

  recommendStructure(input: PlannerInput): PlannerRecommendation {
    return recommendPlannerStructure(input);
  }

  generatePlan(request: PlannerGenerationRequest): PlannerGeneratedPlan {
    return generateWorkoutPlan(request);
  }

  async generateAndSave(
    userId: string,
    accessToken: string,
    dto: GeneratePlannerPlanDto,
  ) {
    const client = this.supabase.forUser(accessToken);
    const context = await this.loadGenerationContext(userId, client);
    const availableDays = resolveAvailableDays(
      dto.available_days,
      context.profile?.available_training_days,
      dto.desired_weekly_frequency,
    );
    const generated = generateWorkoutPlan({
      input: {
        goal: dto.goal ?? (context.goal?.type as PlannerGoal | undefined),
        level: dto.level ?? normalizeLevel(context.profile?.training_level),
        availableDays,
        sessionMinutes: dto.session_minutes,
        modalities: dto.modalities,
        desiredWeeklyFrequency: dto.desired_weekly_frequency,
      },
      exercises: context.exercises.map(toPlannerCandidate),
      constraints: {
        avoidedExerciseIds: context.preferences?.avoided_exercises,
        availableEquipment: context.availableEquipment.length
          ? context.availableEquipment
          : undefined,
      },
    });
    const startDate = (dto.start_date ?? new Date().toISOString()).slice(0, 10);
    const payload = buildPlannerPersistencePayload({
      generated,
      userId,
      goalId: context.goal?.id ?? null,
      name: dto.name?.trim() || `${generated.splitLabel} - Evolv`,
      startDate,
      status: dto.activate === false ? 'draft' : 'active',
    });
    const { data: planId, error } = await client.rpc(
      'create_planner_workout_plan',
      { p_plan: payload },
    );

    if (error) {
      throwDatabaseError(
        'PlannerService.generateAndSave',
        error,
        'Nao foi possivel salvar o plano gerado.',
      );
    }

    return this.getPlan(userId, accessToken, planId);
  }

  async listPlans(
    userId: string,
    accessToken: string,
    queryDto: ListPlannerPlansQueryDto,
  ) {
    let query = this.supabase
      .forUser(accessToken)
      .from('workout_plans')
      .select(
        'id, name, status, start_date, end_date, weekly_frequency, split_type, split_label, planner_version, created_at, updated_at',
      )
      .eq('user_id', userId)
      .order('updated_at', { ascending: false })
      .limit(queryDto.limit);

    if (queryDto.status) query = query.eq('status', queryDto.status);

    const { data, error } = await query;
    if (error) {
      throwDatabaseError(
        'PlannerService.listPlans',
        error,
        'Nao foi possivel listar os planos.',
      );
    }
    return data;
  }

  async getPlan(userId: string, accessToken: string, planId: string) {
    const client = this.supabase.forUser(accessToken);
    const { data, error } = await client
      .from('workout_plans')
      .select(
        `
        *,
        goals (*),
        workout_days (
          *,
          workout_day_exercises (
            *,
            exercises (*)
          )
        )
      `,
      )
      .eq('id', planId)
      .eq('user_id', userId)
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'PlannerService.getPlan',
        error,
        'Nao foi possivel buscar o plano.',
      );
    }
    if (!data) throwPlanNotFound();

    data.workout_days.sort((left, right) => left.position - right.position);
    for (const day of data.workout_days) {
      day.workout_day_exercises.sort(
        (left, right) => left.position - right.position,
      );
    }
    return data;
  }

  async setPlanStatus(
    userId: string,
    accessToken: string,
    planId: string,
    status: Extract<Enums<'plan_status'>, 'active' | 'archived'>,
  ) {
    const client = this.supabase.forUser(accessToken);
    const { error } = await client.rpc('set_workout_plan_status', {
      p_plan_id: planId,
      p_status: status,
    });

    if (error?.code === 'P0002') throwPlanNotFound();
    if (error) {
      throwDatabaseError(
        'PlannerService.setPlanStatus',
        error,
        'Nao foi possivel atualizar o plano.',
      );
    }
    return this.getPlan(userId, accessToken, planId);
  }

  private async loadGenerationContext(
    userId: string,
    client: SupabaseClient<Database>,
  ) {
    const [profile, goal, exercises, preferences, equipment] =
      await Promise.all([
        client
          .from('profiles')
          .select('training_level, available_training_days')
          .eq('id', userId)
          .maybeSingle(),
        client
          .from('goals')
          .select('id, type')
          .eq('user_id', userId)
          .eq('is_active', true)
          .order('updated_at', { ascending: false })
          .limit(1)
          .maybeSingle(),
        client
          .from('exercises')
          .select(
            'id, name, muscle_group, equipment, movement_pattern, difficulty, is_compound, training_kind, planner_modalities',
          )
          .order('name', { ascending: true }),
        client
          .from('training_preferences')
          .select('avoided_exercises')
          .eq('user_id', userId)
          .maybeSingle(),
        client
          .from('user_available_equipment')
          .select('equipment (slug)')
          .eq('user_id', userId),
      ]);

    const firstError =
      profile.error ??
      goal.error ??
      exercises.error ??
      preferences.error ??
      equipment.error;
    if (firstError) {
      throwDatabaseError(
        'PlannerService.loadGenerationContext',
        firstError,
        'Nao foi possivel preparar os dados do Planner.',
      );
    }

    const availableEquipment = (equipment.data ?? [])
      .map((item) => item.equipment?.slug)
      .filter((slug): slug is string => Boolean(slug));

    return {
      profile: profile.data,
      goal: goal.data,
      exercises: (exercises.data ?? []) as ExerciseRow[],
      preferences: preferences.data,
      availableEquipment,
    };
  }
}

function resolveAvailableDays(
  requested: PlannerWeekday[] | undefined,
  saved: PlannerWeekday[] | undefined,
  desiredFrequency: number | undefined,
) {
  if (requested?.length) return requested;
  if (saved?.length) return saved;
  if (desiredFrequency) return weekdays;
  return ['monday', 'wednesday', 'friday'] satisfies PlannerWeekday[];
}

function normalizeLevel(value: string | null | undefined) {
  return value && plannerLevels.has(value as PlannerLevel)
    ? (value as PlannerLevel)
    : undefined;
}

function toPlannerCandidate(exercise: ExerciseRow): PlannerExerciseCandidate {
  const difficulty = normalizeLevel(exercise.difficulty);
  const kind = plannerExerciseKinds.has(
    exercise.training_kind as PlannerExerciseKind,
  )
    ? (exercise.training_kind as PlannerExerciseKind)
    : 'resistance';
  const modalities = exercise.planner_modalities.filter((modality) =>
    plannerModalities.has(modality as PlannerModality),
  ) as PlannerModality[];

  return {
    id: exercise.id,
    name: exercise.name,
    muscleGroup: exercise.muscle_group,
    equipment: exercise.equipment,
    movementPattern: exercise.movement_pattern,
    difficulty,
    isCompound: exercise.is_compound,
    kind,
    modalities,
  };
}

function throwPlanNotFound(): never {
  throw new NotFoundException({
    code: 'WORKOUT_PLAN_NOT_FOUND',
    message: 'Plano de treino nao encontrado.',
  });
}

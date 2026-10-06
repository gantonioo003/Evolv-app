import {
  BadRequestException,
  ConflictException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import type { PostgrestError } from '@supabase/supabase-js';
import type { Json, Tables, TablesInsert } from '../database/database.types.js';
import { throwDatabaseError } from '../common/errors/database.error.js';
import { SupabaseService } from '../supabase/supabase.service.js';
import type { CreatePlannerAdjustmentDto } from './dto/create-planner-adjustment.dto.js';

type ExerciseSummary = Pick<
  Tables<'exercises'>,
  | 'id'
  | 'name'
  | 'muscle_group'
  | 'movement_pattern'
  | 'training_kind'
  | 'equipment'
>;

type Substitution = {
  food_id: string;
  name: string;
  role: string;
  amount: number;
  unit: string;
  nutrition: {
    calories: number;
    proteinG: number;
    carbohydrateG: number;
    fatG: number;
    fiberG: number;
  };
  similarity_score: number;
};

@Injectable()
export class PlannerAdjustmentsService {
  constructor(private readonly supabase: SupabaseService) {}

  preview(
    userId: string,
    accessToken: string,
    dto: CreatePlannerAdjustmentDto,
  ) {
    const reason = dto.reason.trim();
    if (!reason) {
      throw new BadRequestException({
        code: 'ADJUSTMENT_REASON_REQUIRED',
        message: 'Explique brevemente por que deseja fazer a alteracao.',
      });
    }

    switch (dto.kind) {
      case 'move_workout_day':
        return this.previewWorkoutDayMove(userId, accessToken, dto, reason);
      case 'replace_exercise':
        return this.previewExerciseReplacement(
          userId,
          accessToken,
          dto,
          reason,
        );
      case 'replace_meal_item':
        return this.previewMealItemReplacement(
          userId,
          accessToken,
          dto,
          reason,
        );
      case 'set_day_activity':
        return this.previewDayActivity(userId, accessToken, dto, reason);
    }
  }

  async list(userId: string, accessToken: string, limit: number) {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('planner_adjustments')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })
      .limit(limit);

    if (error) {
      throwDatabaseError(
        'PlannerAdjustmentsService.list',
        error,
        'Nao foi possivel carregar o historico de ajustes.',
      );
    }
    return data;
  }

  async get(userId: string, accessToken: string, adjustmentId: string) {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('planner_adjustments')
      .select('*')
      .eq('id', adjustmentId)
      .eq('user_id', userId)
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'PlannerAdjustmentsService.get',
        error,
        'Nao foi possivel carregar o ajuste.',
      );
    }
    if (!data) throwAdjustmentNotFound();
    return data;
  }

  async apply(userId: string, accessToken: string, adjustmentId: string) {
    const adjustment = await this.get(userId, accessToken, adjustmentId);
    await this.runMutation(
      accessToken,
      adjustment.adjustment_kind === 'set_day_activity'
        ? 'apply_day_activity_adjustment'
        : 'apply_planner_adjustment',
      adjustmentId,
    );
    return this.get(userId, accessToken, adjustmentId);
  }

  async reject(userId: string, accessToken: string, adjustmentId: string) {
    await this.runMutation(
      accessToken,
      'reject_planner_adjustment',
      adjustmentId,
    );
    return this.get(userId, accessToken, adjustmentId);
  }

  async revert(userId: string, accessToken: string, adjustmentId: string) {
    const adjustment = await this.get(userId, accessToken, adjustmentId);
    await this.runMutation(
      accessToken,
      adjustment.adjustment_kind === 'set_day_activity'
        ? 'revert_day_activity_adjustment'
        : 'revert_planner_adjustment',
      adjustmentId,
    );
    return this.get(userId, accessToken, adjustmentId);
  }

  private async previewDayActivity(
    userId: string,
    accessToken: string,
    dto: CreatePlannerAdjustmentDto,
    reason: string,
  ) {
    requireFields(dto, ['activity_date', 'activity_type']);
    const client = this.supabase.forUser(accessToken);
    const { data: current, error } = await client
      .from('daily_activity_overrides')
      .select('*')
      .eq('user_id', userId)
      .eq('activity_date', dto.activity_date as string)
      .maybeSingle();
    if (error) throwAdjustmentDatabaseError(error);

    const nutritionDayType = resolveNutritionDayType({
      activityType: dto.activity_type as DayActivityType,
      intensity: dto.intensity,
      estimatedMinutes: dto.estimated_minutes,
      explicitDayType: dto.nutrition_day_type,
    });
    const before = current
      ? { existed: true, ...current }
      : { existed: false, activity_date: dto.activity_date as string };
    const after = {
      activity_date: dto.activity_date as string,
      activity_type: dto.activity_type as DayActivityType,
      intensity:
        dto.activity_type === 'rest' ? null : (dto.intensity ?? 'moderate'),
      estimated_minutes:
        dto.activity_type === 'rest' ? 0 : (dto.estimated_minutes ?? null),
      workout_day_id: dto.workout_day_id ?? null,
      nutrition_day_type: nutritionDayType,
      note: dto.note?.trim() || null,
    };
    const activityLabel = dayActivityLabel(after.activity_type);
    const menuLabel =
      nutritionDayType === 'training_day' ? 'dia de treino' : 'dia de descanso';
    const warnings =
      after.activity_type === 'cardio' && nutritionDayType === 'rest_day'
        ? [
            'Cardio leve ou moderado usa o menu de descanso por padrao. Nenhum carboidrato extra sera inventado sem confirmacao.',
          ]
        : [];
    const preview = {
      title: 'Ajustar atividade do dia',
      summary: `${dto.activity_date}: ${activityLabel}, com o menu de ${menuLabel}.`,
      changes: [
        `Atividade: ${current ? dayActivityLabel(current.activity_type as DayActivityType) : 'planejamento semanal'} -> ${activityLabel}`,
        `Dieta exibida: ${menuLabel}`,
      ],
      preserved: [
        'Plano semanal, outros dias, exercicios e menus alimentares',
      ],
      warnings,
    };

    return this.createAdjustment(userId, accessToken, {
      dto,
      reason,
      targetType: 'daily_activity_override',
      targetId: current?.id,
      preview,
      before,
      after,
    });
  }

  private async previewWorkoutDayMove(
    userId: string,
    accessToken: string,
    dto: CreatePlannerAdjustmentDto,
    reason: string,
  ) {
    requireFields(dto, ['workout_plan_id', 'workout_day_id', 'target_weekday']);
    const targetWeekday =
      dto.target_weekday as Tables<'workout_days'>['weekday'];
    const client = this.supabase.forUser(accessToken);
    const { data: day, error } = await client
      .from('workout_days')
      .select('id, workout_plan_id, weekday, title, focus')
      .eq('id', dto.workout_day_id as string)
      .eq('workout_plan_id', dto.workout_plan_id as string)
      .maybeSingle();

    if (error) throwAdjustmentDatabaseError(error);
    if (!day) throwTargetNotFound('Dia de treino nao encontrado.');
    await this.assertWorkoutPlanOwner(
      userId,
      accessToken,
      dto.workout_plan_id as string,
    );

    if (day.weekday === targetWeekday) {
      throw new BadRequestException({
        code: 'WORKOUT_DAY_ALREADY_SCHEDULED',
        message: 'Esse treino ja esta marcado para o dia escolhido.',
      });
    }

    const { data: swapDay, error: swapError } = await client
      .from('workout_days')
      .select('id, weekday, title')
      .eq('workout_plan_id', dto.workout_plan_id as string)
      .eq('weekday', targetWeekday)
      .limit(1)
      .maybeSingle();
    if (swapError) throwAdjustmentDatabaseError(swapError);

    const before = {
      day_id: day.id,
      weekday: day.weekday,
      swap_day_id: swapDay?.id ?? null,
      swap_weekday: swapDay?.weekday ?? null,
    };
    const after = {
      day_id: day.id,
      weekday: targetWeekday,
      swap_day_id: swapDay?.id ?? null,
      swap_weekday: swapDay ? day.weekday : null,
    };
    const preview = {
      title: swapDay ? 'Trocar dias de treino' : 'Mover treino',
      summary: swapDay
        ? `${day.title} vai para ${weekdayLabel(targetWeekday)} e ${swapDay.title} vai para ${weekdayLabel(day.weekday)}.`
        : `${day.title} vai de ${weekdayLabel(day.weekday)} para ${weekdayLabel(targetWeekday)}.`,
      changes: swapDay
        ? [
            `${day.title}: ${weekdayLabel(day.weekday)} -> ${weekdayLabel(targetWeekday)}`,
            `${swapDay.title}: ${weekdayLabel(swapDay.weekday)} -> ${weekdayLabel(day.weekday)}`,
          ]
        : [
            `${day.title}: ${weekdayLabel(day.weekday)} -> ${weekdayLabel(targetWeekday)}`,
          ],
      preserved: ['Exercicios, series, repeticoes, cargas e ordem'],
      warnings: [],
    };

    return this.createAdjustment(userId, accessToken, {
      dto,
      reason,
      targetType: 'workout_day',
      targetId: day.id,
      workoutPlanId: day.workout_plan_id,
      preview,
      before,
      after,
    });
  }

  private async previewExerciseReplacement(
    userId: string,
    accessToken: string,
    dto: CreatePlannerAdjustmentDto,
    reason: string,
  ) {
    requireFields(dto, [
      'workout_plan_id',
      'workout_day_exercise_id',
      'replacement_exercise_id',
    ]);
    const client = this.supabase.forUser(accessToken);
    await this.assertWorkoutPlanOwner(
      userId,
      accessToken,
      dto.workout_plan_id as string,
    );

    const { data: item, error } = await client
      .from('workout_day_exercises')
      .select(
        '*, exercises (id, name, muscle_group, movement_pattern, training_kind, equipment), workout_days!inner(workout_plan_id)',
      )
      .eq('id', dto.workout_day_exercise_id as string)
      .eq('workout_days.workout_plan_id', dto.workout_plan_id as string)
      .maybeSingle();
    if (error) throwAdjustmentDatabaseError(error);
    if (!item || !item.exercises)
      throwTargetNotFound('Exercicio do plano nao encontrado.');

    const { data: replacement, error: replacementError } = await client
      .from('exercises')
      .select(
        'id, name, muscle_group, movement_pattern, training_kind, equipment',
      )
      .eq('id', dto.replacement_exercise_id as string)
      .maybeSingle();
    if (replacementError) throwAdjustmentDatabaseError(replacementError);
    if (!replacement)
      throwTargetNotFound('Exercicio substituto nao encontrado.');

    const current = item.exercises as ExerciseSummary;
    if (!isCompatibleExerciseReplacement(current, replacement)) {
      throw new BadRequestException({
        code: 'INCOMPATIBLE_EXERCISE_REPLACEMENT',
        message:
          'Escolha um exercicio do mesmo tipo, musculo ou padrao de movimento.',
      });
    }

    const { count, error: duplicateError } = await client
      .from('workout_day_exercises')
      .select('id', { count: 'exact', head: true })
      .eq('workout_day_id', item.workout_day_id)
      .eq('exercise_id', replacement.id)
      .neq('id', item.id);
    if (duplicateError) throwAdjustmentDatabaseError(duplicateError);
    if (count) {
      throw new BadRequestException({
        code: 'DUPLICATE_EXERCISE_IN_DAY',
        message: 'O exercicio substituto ja esta neste dia.',
      });
    }

    const before = {
      workout_day_exercise_id: item.id,
      exercise_id: current.id,
      exercise_name: current.name,
    };
    const after = {
      workout_day_exercise_id: item.id,
      exercise_id: replacement.id,
      exercise_name: replacement.name,
    };
    const preview = {
      title: 'Trocar exercicio',
      summary: `${current.name} sera substituido por ${replacement.name}.`,
      changes: [`${current.name} -> ${replacement.name}`],
      preserved: [
        'Dia, posicao, series, repeticoes, descanso e carga registrada',
      ],
      warnings:
        current.muscle_group === replacement.muscle_group
          ? []
          : [
              'O padrao de movimento foi preservado, mas o musculo principal cadastrado difere.',
            ],
    };

    return this.createAdjustment(userId, accessToken, {
      dto,
      reason,
      targetType: 'workout_day_exercise',
      targetId: item.id,
      workoutPlanId: dto.workout_plan_id as string,
      preview,
      before,
      after,
    });
  }

  private async previewMealItemReplacement(
    userId: string,
    accessToken: string,
    dto: CreatePlannerAdjustmentDto,
    reason: string,
  ) {
    requireFields(dto, ['diet_plan_id', 'meal_item_id', 'replacement_food_id']);
    const client = this.supabase.forUser(accessToken);
    await this.assertDietPlanOwner(
      userId,
      accessToken,
      dto.diet_plan_id as string,
    );

    const { data: item, error } = await client
      .from('meal_items')
      .select('*, meals!inner(diet_plan_id)')
      .eq('id', dto.meal_item_id as string)
      .eq('meals.diet_plan_id', dto.diet_plan_id as string)
      .maybeSingle();
    if (error) throwAdjustmentDatabaseError(error);
    if (!item) throwTargetNotFound('Alimento do plano nao encontrado.');

    const substitutions = parseSubstitutions(item.substitutions);
    const replacement = substitutions.find(
      (candidate) => candidate.food_id === dto.replacement_food_id,
    );
    if (!replacement) {
      throw new BadRequestException({
        code: 'FOOD_NOT_APPROVED_SUBSTITUTION',
        message: 'Escolha uma das substituicoes calculadas para este alimento.',
      });
    }

    const before = mealItemSnapshot(item);
    const after = buildMealReplacementSnapshot(item, replacement);
    const preview = {
      title: 'Trocar alimento',
      summary: `${item.name} sera substituido por ${replacement.name} em quantidade equivalente.`,
      changes: [
        `${item.amount ?? item.name} -> ${replacement.amount} ${replacement.unit} de ${replacement.name}`,
      ],
      preserved: ['Refeicao, papel nutricional e restante do plano'],
      warnings: [
        `Similaridade nutricional estimada: ${Math.round(replacement.similarity_score * 100)}%.`,
      ],
    };

    return this.createAdjustment(userId, accessToken, {
      dto,
      reason,
      targetType: 'meal_item',
      targetId: item.id,
      dietPlanId: dto.diet_plan_id as string,
      preview,
      before,
      after,
    });
  }

  private async createAdjustment(
    userId: string,
    accessToken: string,
    input: {
      dto: CreatePlannerAdjustmentDto;
      reason: string;
      targetType:
        | 'workout_day'
        | 'workout_day_exercise'
        | 'meal_item'
        | 'daily_activity_override';
      targetId?: string;
      workoutPlanId?: string;
      dietPlanId?: string;
      preview: Record<string, Json>;
      before: Record<string, Json>;
      after: Record<string, Json>;
    },
  ) {
    const row: TablesInsert<'planner_adjustments'> = {
      user_id: userId,
      reason: input.reason,
      adjustment_kind: input.dto.kind,
      source: input.dto.source ?? 'manual',
      workout_plan_id: input.workoutPlanId,
      diet_plan_id: input.dietPlanId,
      target_type: input.targetType,
      target_id: input.targetId,
      requested_change: input.dto as unknown as Json,
      preview: input.preview,
      before_snapshot: input.before,
      after_snapshot: input.after,
    };
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('planner_adjustments')
      .insert(row)
      .select('*')
      .single();
    if (error) throwAdjustmentDatabaseError(error);
    return data;
  }

  private async assertWorkoutPlanOwner(
    userId: string,
    accessToken: string,
    planId: string,
  ) {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('workout_plans')
      .select('id')
      .eq('id', planId)
      .eq('user_id', userId)
      .maybeSingle();
    if (error) throwAdjustmentDatabaseError(error);
    if (!data) throwTargetNotFound('Plano de treino nao encontrado.');
  }

  private async assertDietPlanOwner(
    userId: string,
    accessToken: string,
    planId: string,
  ) {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('diet_plans')
      .select('id')
      .eq('id', planId)
      .eq('user_id', userId)
      .maybeSingle();
    if (error) throwAdjustmentDatabaseError(error);
    if (!data) throwTargetNotFound('Plano alimentar nao encontrado.');
  }

  private async runMutation(
    accessToken: string,
    functionName:
      | 'apply_planner_adjustment'
      | 'apply_day_activity_adjustment'
      | 'reject_planner_adjustment'
      | 'revert_planner_adjustment'
      | 'revert_day_activity_adjustment',
    adjustmentId: string,
  ) {
    const { error } = await this.supabase
      .forUser(accessToken)
      .rpc(functionName, {
        p_adjustment_id: adjustmentId,
      });
    if (!error) return;
    if (error.code === 'P0002') throwAdjustmentNotFound();
    if (error.code === '40001') {
      throw new ConflictException({
        code: 'ADJUSTMENT_STALE',
        message:
          'O plano mudou depois da previa. Crie uma nova previa antes de confirmar.',
      });
    }
    if (error.code === '22023') {
      throw new BadRequestException({
        code: 'ADJUSTMENT_NOT_ALLOWED',
        message: error.message,
      });
    }
    throwAdjustmentDatabaseError(error);
  }
}

type DayActivityType = 'rest' | 'resistance' | 'cardio' | 'mixed';

export function resolveNutritionDayType(input: {
  activityType: DayActivityType;
  intensity?: 'light' | 'moderate' | 'hard';
  estimatedMinutes?: number;
  explicitDayType?: 'training_day' | 'rest_day';
}) {
  if (input.explicitDayType) return input.explicitDayType;
  if (input.activityType === 'rest') return 'rest_day' as const;
  if (input.activityType === 'resistance' || input.activityType === 'mixed') {
    return 'training_day' as const;
  }
  return input.intensity === 'hard' || (input.estimatedMinutes ?? 0) >= 60
    ? ('training_day' as const)
    : ('rest_day' as const);
}

function dayActivityLabel(activityType: DayActivityType) {
  const labels: Record<DayActivityType, string> = {
    rest: 'descanso',
    resistance: 'treino de forca',
    cardio: 'cardio',
    mixed: 'treino misto',
  };
  return labels[activityType];
}

export function isCompatibleExerciseReplacement(
  current: ExerciseSummary,
  replacement: ExerciseSummary,
) {
  if (current.id === replacement.id) return false;
  if (current.training_kind !== replacement.training_kind) return false;
  if (current.training_kind !== 'resistance') return true;
  return (
    current.muscle_group === replacement.muscle_group ||
    Boolean(
      current.movement_pattern &&
      current.movement_pattern === replacement.movement_pattern,
    )
  );
}

export function buildMealReplacementSnapshot(
  current: Tables<'meal_items'>,
  replacement: Substitution,
) {
  const oldAsSubstitution: Substitution | null = current.food_id
    ? {
        food_id: current.food_id,
        name: current.name,
        role: current.nutrition_role ?? replacement.role,
        amount: current.quantity ?? replacement.amount,
        unit: current.unit ?? replacement.unit,
        nutrition: {
          calories: current.calories_kcal ?? 0,
          proteinG: current.protein_g ?? 0,
          carbohydrateG: current.carbohydrate_g ?? 0,
          fatG: current.fat_g ?? 0,
          fiberG: current.fiber_g ?? 0,
        },
        similarity_score: replacement.similarity_score,
      }
    : null;
  const remaining = parseSubstitutions(current.substitutions).filter(
    (candidate) => candidate.food_id !== replacement.food_id,
  );
  if (oldAsSubstitution) remaining.unshift(oldAsSubstitution);

  return {
    meal_item_id: current.id,
    food_id: replacement.food_id,
    name: replacement.name,
    amount: `${replacement.amount} ${replacement.unit}`,
    quantity: replacement.amount,
    unit: replacement.unit,
    nutrition_role: replacement.role,
    calories_kcal: replacement.nutrition.calories,
    protein_g: replacement.nutrition.proteinG,
    carbohydrate_g: replacement.nutrition.carbohydrateG,
    fat_g: replacement.nutrition.fatG,
    fiber_g: replacement.nutrition.fiberG,
    substitutions: remaining as unknown as Json,
  };
}

function mealItemSnapshot(item: Tables<'meal_items'>) {
  return {
    meal_item_id: item.id,
    food_id: item.food_id,
    name: item.name,
    amount: item.amount,
    quantity: item.quantity,
    unit: item.unit,
    nutrition_role: item.nutrition_role,
    calories_kcal: item.calories_kcal,
    protein_g: item.protein_g,
    carbohydrate_g: item.carbohydrate_g,
    fat_g: item.fat_g,
    fiber_g: item.fiber_g,
    substitutions: item.substitutions,
  };
}

function parseSubstitutions(value: Json): Substitution[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isSubstitution) as unknown as Substitution[];
}

function isSubstitution(value: Json): boolean {
  return Boolean(
    value &&
    typeof value === 'object' &&
    !Array.isArray(value) &&
    typeof value.food_id === 'string' &&
    typeof value.name === 'string' &&
    typeof value.amount === 'number' &&
    typeof value.unit === 'string' &&
    value.nutrition &&
    typeof value.nutrition === 'object' &&
    !Array.isArray(value.nutrition),
  );
}

function requireFields(
  dto: CreatePlannerAdjustmentDto,
  fields: (keyof CreatePlannerAdjustmentDto)[],
) {
  const missing = fields.filter((field) => !dto[field]);
  if (!missing.length) return;
  throw new BadRequestException({
    code: 'ADJUSTMENT_FIELDS_REQUIRED',
    message: `Campos obrigatorios ausentes: ${missing.join(', ')}.`,
  });
}

function weekdayLabel(value: string | undefined) {
  const labels: Record<string, string> = {
    monday: 'segunda',
    tuesday: 'terca',
    wednesday: 'quarta',
    thursday: 'quinta',
    friday: 'sexta',
    saturday: 'sabado',
    sunday: 'domingo',
  };
  return value ? (labels[value] ?? value) : '';
}

function throwAdjustmentNotFound(): never {
  throw new NotFoundException({
    code: 'PLANNER_ADJUSTMENT_NOT_FOUND',
    message: 'Ajuste do Planner nao encontrado.',
  });
}

function throwTargetNotFound(message: string): never {
  throw new NotFoundException({ code: 'ADJUSTMENT_TARGET_NOT_FOUND', message });
}

function throwAdjustmentDatabaseError(error: PostgrestError): never {
  throwDatabaseError(
    'PlannerAdjustmentsService',
    error,
    'Nao foi possivel preparar o ajuste do Planner.',
  );
}

import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import type { SupabaseClient } from '@supabase/supabase-js';
import { throwDatabaseError } from '../common/errors/database.error.js';
import type { Database, Enums, Tables } from '../database/database.types.js';
import { SupabaseService } from '../supabase/supabase.service.js';
import type { GenerateNutritionPlanDto } from './dto/generate-nutrition-plan.dto.js';
import type { ListPlannerPlansQueryDto } from './dto/list-planner-plans-query.dto.js';
import {
  generateNutritionPlan,
  NutritionFoodGeneratorError,
} from './nutrition-planner.generator.js';
import { buildNutritionPlannerPersistencePayload } from './nutrition-planner.persistence.js';
import {
  NutritionPlannerInputError,
  recommendNutritionPlan,
} from './nutrition-planner.rules.js';
import type {
  NutritionFoodCandidate,
  NutritionFoodMealType,
  NutritionFoodProcessingLevel,
  NutritionFoodRole,
  NutritionFoodStyle,
  NutritionPlannerInput,
  NutritionPhaseType,
} from './nutrition-planner.types.js';

type FoodRow = Pick<
  Tables<'foods'>,
  | 'id'
  | 'name'
  | 'base_amount'
  | 'base_unit'
  | 'calories_kcal'
  | 'protein_g'
  | 'carbohydrate_g'
  | 'fat_g'
  | 'fiber_g'
  | 'nutrition_roles'
  | 'compatible_food_styles'
  | 'planner_meal_types'
  | 'planner_tags'
  | 'allergens'
  | 'processing_level'
  | 'planner_minimum_amount'
  | 'planner_maximum_amount'
  | 'planner_amount_step'
  | 'planner_default_amount'
>;

@Injectable()
export class NutritionPlannerService {
  constructor(private readonly supabase: SupabaseService) {}

  async generateAndSave(
    userId: string,
    accessToken: string,
    dto: GenerateNutritionPlanDto,
  ) {
    const client = this.supabase.forUser(accessToken);
    const context = await this.loadGenerationContext(userId, client);

    try {
      const plannerInput: NutritionPlannerInput = {
        phase: dto.phase ?? phaseFromGoal(context.goal?.type),
        currentWeightKg: context.profile?.current_weight_kg ?? undefined,
        heightCm: context.profile?.height_cm ?? undefined,
        ageYears: ageFromBirthDate(context.profile?.birth_date),
        metabolicEquationSex: dto.metabolic_equation_sex,
        activityLevel: dto.activity_level,
        estimatedMaintenanceCalories: dto.estimated_maintenance_calories,
        calorieTargetOverride: dto.calorie_target_override,
        macroPattern: dto.macro_pattern,
        customMacroPercentages: dto.custom_macro_percentages,
        mealsPerDay: dto.meals_per_day,
        mealSchedule: dto.meal_schedule,
        eatingWindowHours: dto.eating_window_hours,
        eatingWindowStartHour: dto.eating_window_start_hour,
        foodStyle: dto.food_style,
        preferredFoods: dto.preferred_foods,
        dislikedFoods: uniqueStrings([
          ...(context.profile?.disliked_foods ?? []),
          ...(dto.disliked_foods ?? []),
        ]),
        foodRestrictions: uniqueStrings([
          ...(context.profile?.food_restrictions ?? []),
          ...(dto.food_restrictions ?? []),
        ]),
        allergenExclusions: dto.allergen_exclusions,
        healthFlags: dto.health_flags,
      };
      const recommendation = recommendNutritionPlan(plannerInput);
      const generated = generateNutritionPlan({
        recommendation,
        foods: context.foods.map(toNutritionFoodCandidate),
      });
      const menuRotationSize =
        dto.rotate_menus === false ? 1 : (dto.menu_rotation_size ?? 3);
      const variants = createNutritionMealVariants({
        plannerInput,
        generated,
        foods: context.foods.map(toNutritionFoodCandidate),
        useTrainingRestVariants: dto.use_training_rest_variants === true,
        trainingDaysPerWeek: normalizedTrainingDays(
          context.profile?.available_training_days.length,
        ),
        trainingMeals: dto.training_day_meals ?? dto.meals_per_day ?? 5,
        restMeals:
          dto.rest_day_meals ??
          Math.max(1, (dto.training_day_meals ?? dto.meals_per_day ?? 5) - 1),
        menuRotationSize,
      });
      const payload = buildNutritionPlannerPersistencePayload({
        generated,
        variants,
        menuRotationEnabled: menuRotationSize > 1,
        menuRotationSize,
        flexibleMealFrequency: dto.flexible_meal_frequency,
        flexibleMealWeekday: dto.flexible_meal_weekday,
        alcoholFrequency: dto.alcohol_frequency,
        alcoholPreferredWeekday: dto.alcohol_preferred_weekday,
        alcoholMaxServings: dto.alcohol_max_servings,
        userId,
        goalId: context.goal?.id ?? null,
        name:
          dto.name?.trim() ||
          `${nutritionPhaseLabel(recommendation.phase)} - Evolv`,
        status: dto.activate === false ? 'draft' : 'active',
      });
      const { data: planId, error } = await client.rpc(
        'create_planner_diet_plan_v3',
        { p_plan: payload },
      );

      if (error) {
        throwDatabaseError(
          'NutritionPlannerService.generateAndSave',
          error,
          'Nao foi possivel salvar o plano alimentar gerado.',
        );
      }
      return this.getPlan(userId, accessToken, planId);
    } catch (error) {
      if (
        error instanceof NutritionPlannerInputError ||
        error instanceof NutritionFoodGeneratorError
      ) {
        throw new BadRequestException({
          code: error.code,
          message: error.message,
        });
      }
      throw error;
    }
  }

  async listPlans(
    userId: string,
    accessToken: string,
    queryDto: ListPlannerPlansQueryDto,
  ) {
    let query = this.supabase
      .forUser(accessToken)
      .from('diet_plans')
      .select(
        'id, name, status, daily_calories_target, daily_protein_target_g, nutrition_phase, macro_pattern, food_style, meal_schedule, planner_version, uses_day_variants, training_day_calories_target, rest_day_calories_target, menu_rotation_enabled, menu_rotation_size, flexible_meal_frequency, flexible_meal_weekday, alcohol_frequency, alcohol_preferred_weekday, alcohol_max_servings, created_at, updated_at',
      )
      .eq('user_id', userId)
      .order('updated_at', { ascending: false })
      .limit(queryDto.limit);

    if (queryDto.status) query = query.eq('status', queryDto.status);
    const { data, error } = await query;
    if (error) {
      throwDatabaseError(
        'NutritionPlannerService.listPlans',
        error,
        'Nao foi possivel listar os planos alimentares.',
      );
    }
    return data;
  }

  async getPlan(userId: string, accessToken: string, planId: string) {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('diet_plans')
      .select(
        `
        *,
        goals (*),
        meals (
          *,
          meal_items (
            *,
            foods (id, name, brand, calories_kcal, protein_g, carbohydrate_g, fat_g, fiber_g)
          )
        )
      `,
      )
      .eq('id', planId)
      .eq('user_id', userId)
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'NutritionPlannerService.getPlan',
        error,
        'Nao foi possivel buscar o plano alimentar.',
      );
    }
    if (!data) throwNutritionPlanNotFound();

    data.meals.sort(
      (left, right) =>
        left.day_type.localeCompare(right.day_type) ||
        left.rotation_index - right.rotation_index ||
        left.position - right.position,
    );
    data.meals.forEach((meal) => {
      meal.meal_items.sort((left, right) => left.position - right.position);
    });
    return data;
  }

  async setPlanStatus(
    userId: string,
    accessToken: string,
    planId: string,
    status: Extract<Enums<'plan_status'>, 'active' | 'archived'>,
  ) {
    const { error } = await this.supabase
      .forUser(accessToken)
      .rpc('set_diet_plan_status', {
        p_plan_id: planId,
        p_status: status,
      });
    if (error?.code === 'P0002') throwNutritionPlanNotFound();
    if (error) {
      throwDatabaseError(
        'NutritionPlannerService.setPlanStatus',
        error,
        'Nao foi possivel atualizar o plano alimentar.',
      );
    }
    return this.getPlan(userId, accessToken, planId);
  }

  private async loadGenerationContext(
    userId: string,
    client: SupabaseClient<Database>,
  ) {
    const [profile, goal, foods] = await Promise.all([
      client
        .from('profiles')
        .select(
          'birth_date, height_cm, current_weight_kg, available_training_days, disliked_foods, food_restrictions',
        )
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
        .from('foods')
        .select(
          'id, name, base_amount, base_unit, calories_kcal, protein_g, carbohydrate_g, fat_g, fiber_g, nutrition_roles, compatible_food_styles, planner_meal_types, planner_tags, allergens, processing_level, planner_minimum_amount, planner_maximum_amount, planner_amount_step, planner_default_amount',
        )
        .not('calories_kcal', 'is', null)
        .not('protein_g', 'is', null)
        .not('carbohydrate_g', 'is', null)
        .not('fat_g', 'is', null)
        .not('fiber_g', 'is', null)
        .order('name', { ascending: true }),
    ]);
    const firstError = profile.error ?? goal.error ?? foods.error;
    if (firstError) {
      throwDatabaseError(
        'NutritionPlannerService.loadGenerationContext',
        firstError,
        'Nao foi possivel preparar os dados do Planner nutricional.',
      );
    }
    return {
      profile: profile.data,
      goal: goal.data,
      foods: (foods.data ?? []) as FoodRow[],
    };
  }
}

function createNutritionMealVariants({
  plannerInput,
  generated,
  foods,
  useTrainingRestVariants,
  trainingDaysPerWeek,
  trainingMeals,
  restMeals,
  menuRotationSize,
}: {
  plannerInput: NutritionPlannerInput;
  generated: ReturnType<typeof generateNutritionPlan>;
  foods: NutritionFoodCandidate[];
  useTrainingRestVariants: boolean;
  trainingDaysPerWeek: number;
  trainingMeals: number;
  restMeals: number;
  menuRotationSize: number;
}) {
  const base = generated.recommendation;
  const targets = calculateDayVariantCalories(
    base.targets.calories,
    trainingDaysPerWeek,
  );
  const dayDefinitions = useTrainingRestVariants
    ? [
        {
          dayType: 'training_day' as const,
          recommendation: recommendNutritionPlan({
            ...plannerInput,
            calorieTargetOverride: targets.training,
            mealsPerDay: trainingMeals,
          }),
          seedOffset: 0,
        },
        {
          dayType: 'rest_day' as const,
          recommendation: recommendNutritionPlan({
            ...plannerInput,
            calorieTargetOverride: targets.rest,
            mealsPerDay: restMeals,
          }),
          seedOffset: 11,
        },
      ]
    : [
        {
          dayType: 'every_day' as const,
          recommendation: base,
          seedOffset: 0,
        },
      ];

  return dayDefinitions.flatMap((definition) =>
    Array.from({ length: menuRotationSize }, (_, rotationIndex) => ({
      dayType: definition.dayType,
      rotationIndex,
      generated:
        definition.dayType === 'every_day' && rotationIndex === 0
          ? generated
          : generateNutritionPlan({
              recommendation: definition.recommendation,
              foods,
              varietySeed: definition.seedOffset + rotationIndex,
            }),
    })),
  );
}

export function calculateDayVariantCalories(
  averageCalories: number,
  trainingDaysPerWeek: number,
) {
  const trainingDays = normalizedTrainingDays(trainingDaysPerWeek);
  const restDays = 7 - trainingDays;
  const maximumTrainingCalories = Math.floor(
    (averageCalories * 7 - 800 * restDays) / trainingDays,
  );
  const desiredTrainingCalories = roundToTen(averageCalories * 1.05);
  const training = Math.max(
    800,
    Math.min(8000, desiredTrainingCalories, maximumTrainingCalories),
  );
  const rest = Math.max(
    800,
    Math.min(
      8000,
      roundToTen((averageCalories * 7 - training * trainingDays) / restDays),
    ),
  );
  return { training, rest };
}

function normalizedTrainingDays(value: number | null | undefined) {
  if (!value) return 4;
  return Math.max(1, Math.min(6, value));
}

function roundToTen(value: number) {
  return Math.round(value / 10) * 10;
}

function toNutritionFoodCandidate(food: FoodRow): NutritionFoodCandidate {
  return {
    id: food.id,
    name: food.name,
    baseAmount: food.base_amount,
    baseUnit: food.base_unit,
    nutrition: {
      calories: food.calories_kcal as number,
      proteinG: food.protein_g as number,
      carbohydrateG: food.carbohydrate_g as number,
      fatG: food.fat_g as number,
      fiberG: food.fiber_g as number,
    },
    roles: food.nutrition_roles as NutritionFoodRole[],
    compatibleFoodStyles: food.compatible_food_styles as NutritionFoodStyle[],
    mealTypes: food.planner_meal_types as NutritionFoodMealType[],
    tags: food.planner_tags,
    allergens: food.allergens,
    processingLevel: food.processing_level as NutritionFoodProcessingLevel,
    minimumAmount: food.planner_minimum_amount ?? undefined,
    maximumAmount: food.planner_maximum_amount ?? undefined,
    amountStep: food.planner_amount_step ?? undefined,
    defaultAmount: food.planner_default_amount ?? undefined,
  };
}

function phaseFromGoal(goal: string | undefined): NutritionPhaseType {
  if (goal === 'hypertrophy') return 'mass_gain';
  if (goal === 'fat_loss') return 'fat_loss';
  if (goal === 'recomposition') return 'recomposition';
  return 'maintenance';
}

function ageFromBirthDate(value: string | null | undefined) {
  if (!value) return undefined;
  const birthDate = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(birthDate.getTime())) return undefined;
  const today = new Date();
  let age = today.getUTCFullYear() - birthDate.getUTCFullYear();
  const beforeBirthday =
    today.getUTCMonth() < birthDate.getUTCMonth() ||
    (today.getUTCMonth() === birthDate.getUTCMonth() &&
      today.getUTCDate() < birthDate.getUTCDate());
  if (beforeBirthday) age -= 1;
  return age;
}

function uniqueStrings(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function nutritionPhaseLabel(phase: NutritionPhaseType) {
  const labels: Record<NutritionPhaseType, string> = {
    mass_gain: 'Ganho de massa',
    fat_loss: 'Perda de gordura',
    maintenance: 'Manutencao',
    recomposition: 'Recomposicao',
    diet_break: 'Pausa de dieta',
    custom: 'Plano personalizado',
  };
  return labels[phase];
}

function throwNutritionPlanNotFound(): never {
  throw new NotFoundException({
    code: 'DIET_PLAN_NOT_FOUND',
    message: 'Plano alimentar nao encontrado.',
  });
}

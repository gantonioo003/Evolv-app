import type { Json } from '../database/database.types.js';
import type { NutritionGeneratedPlan } from './nutrition-planner.types.js';

type BuildNutritionPlannerPayloadOptions = {
  generated: NutritionGeneratedPlan;
  variants?: Array<{
    dayType: 'every_day' | 'training_day' | 'rest_day';
    rotationIndex: number;
    generated: NutritionGeneratedPlan;
  }>;
  menuRotationEnabled?: boolean;
  menuRotationSize?: number;
  flexibleMealFrequency?: 'none' | 'weekly' | 'fortnightly';
  flexibleMealWeekday?: string;
  alcoholFrequency?: 'none' | 'fortnightly' | 'monthly';
  alcoholPreferredWeekday?: string;
  alcoholMaxServings?: number;
  userId: string;
  goalId: string | null;
  name: string;
  status: 'draft' | 'active';
};

export function buildNutritionPlannerPersistencePayload({
  generated,
  variants,
  menuRotationEnabled = false,
  menuRotationSize = 1,
  flexibleMealFrequency = 'none',
  flexibleMealWeekday,
  alcoholFrequency = 'none',
  alcoholPreferredWeekday,
  alcoholMaxServings,
  userId,
  goalId,
  name,
  status,
}: BuildNutritionPlannerPayloadOptions): Json {
  const { recommendation } = generated;
  const generatedPlans = variants?.map((variant) => variant.generated) ?? [
    generated,
  ];
  const warnings = [
    ...recommendation.warnings,
    ...generated.warnings,
    ...generatedPlans.flatMap((plan) => [
      ...plan.recommendation.warnings,
      ...plan.warnings,
    ]),
  ].filter((warning, index, values) => values.indexOf(warning) === index);
  const trainingVariant = variants?.find(
    (variant) => variant.dayType === 'training_day',
  );
  const restVariant = variants?.find(
    (variant) => variant.dayType === 'rest_day',
  );

  return {
    user_id: userId,
    goal_id: goalId,
    name,
    status,
    daily_calories_target: recommendation.targets.calories,
    daily_protein_target_g: recommendation.targets.proteinG,
    daily_carbohydrate_target_g: recommendation.targets.carbohydrateG,
    daily_fat_target_g: recommendation.targets.fatG,
    daily_fiber_target_g: recommendation.targets.fiberG,
    notes: warnings.length ? warnings.join(' ') : null,
    planner_version: generated.generatorVersion,
    nutrition_phase: recommendation.phase,
    macro_pattern: recommendation.macroPattern,
    food_style: recommendation.foodStyle,
    meal_schedule: recommendation.mealSchedule,
    uses_day_variants: Boolean(
      variants?.some((variant) => variant.dayType !== 'every_day'),
    ),
    menu_rotation_enabled: menuRotationEnabled,
    menu_rotation_size: menuRotationSize,
    flexible_meal_frequency: flexibleMealFrequency,
    flexible_meal_weekday:
      flexibleMealFrequency === 'none' ? null : (flexibleMealWeekday ?? null),
    alcohol_frequency: alcoholFrequency,
    alcohol_preferred_weekday:
      alcoholFrequency === 'none' ? null : (alcoholPreferredWeekday ?? null),
    alcohol_max_servings:
      alcoholFrequency === 'none' ? null : (alcoholMaxServings ?? 1),
    training_day_calories_target:
      trainingVariant?.generated.recommendation.targets.calories ?? null,
    rest_day_calories_target:
      restVariant?.generated.recommendation.targets.calories ?? null,
    planner_input: {
      rule_version: recommendation.ruleVersion,
      energy: recommendation.energy,
      assumptions: recommendation.assumptions,
      exclusions: recommendation.exclusions,
      target_deviation_percent: generated.deviationPercent,
      review_recommended: recommendation.reviewRecommended,
      day_variants:
        variants?.map((variant) => ({
          day_type: variant.dayType,
          rotation_index: variant.rotationIndex,
          calories: variant.generated.recommendation.targets.calories,
          meals: variant.generated.meals.length,
        })) ?? null,
      planned_flexibility: {
        flexible_meal_frequency: flexibleMealFrequency,
        flexible_meal_weekday: flexibleMealWeekday ?? null,
        alcohol_frequency: alcoholFrequency,
        alcohol_preferred_weekday: alcoholPreferredWeekday ?? null,
        alcohol_max_servings: alcoholMaxServings ?? null,
      },
    },
    meals: (
      variants ?? [
        { dayType: 'every_day' as const, rotationIndex: 0, generated },
      ]
    ).flatMap((variant) =>
      variant.generated.meals.map((meal) => ({
        name: meal.name,
        meal_time: meal.suggestedTime,
        position: meal.position,
        day_type: variant.dayType,
        rotation_index: variant.rotationIndex,
        calories_target: meal.target.calories,
        protein_target_g: meal.target.proteinG,
        carbohydrate_target_g: meal.target.carbohydrateG,
        fat_target_g: meal.target.fatG,
        description: meal.items.map((item) => item.name).join(', '),
        actual_calories: meal.actual.calories,
        actual_protein_g: meal.actual.proteinG,
        actual_carbohydrate_g: meal.actual.carbohydrateG,
        actual_fat_g: meal.actual.fatG,
        actual_fiber_g: meal.actual.fiberG,
        items: meal.items.map((item, position) => ({
          position,
          food_id: item.foodId,
          name: item.name,
          amount: `${item.amount} ${item.unit}`,
          quantity: item.amount,
          unit: item.unit,
          substitution_group: item.role,
          nutrition_role: item.role,
          calories_kcal: item.nutrition.calories,
          protein_g: item.nutrition.proteinG,
          carbohydrate_g: item.nutrition.carbohydrateG,
          fat_g: item.nutrition.fatG,
          fiber_g: item.nutrition.fiberG,
          substitutions: item.substitutions.map((substitution) => ({
            food_id: substitution.foodId,
            name: substitution.name,
            role: substitution.role,
            amount: substitution.amount,
            unit: substitution.unit,
            nutrition: substitution.nutrition,
            similarity_score: substitution.similarityScore,
          })),
          notes: null,
        })),
      })),
    ),
  };
}

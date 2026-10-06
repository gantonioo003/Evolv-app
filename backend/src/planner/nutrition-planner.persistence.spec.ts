import { generateNutritionPlan } from './nutrition-planner.generator.js';
import { buildNutritionPlannerPersistencePayload } from './nutrition-planner.persistence.js';
import { recommendNutritionPlan } from './nutrition-planner.rules.js';
import type { NutritionFoodCandidate } from './nutrition-planner.types.js';

const foods: NutritionFoodCandidate[] = [
  {
    id: '11111111-1111-4111-8111-111111111111',
    name: 'Tofu',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 120,
      proteinG: 12,
      carbohydrateG: 2,
      fatG: 7,
      fiberG: 1,
    },
    roles: ['protein_source'],
    compatibleFoodStyles: ['vegan'],
    mealTypes: ['any'],
    minimumAmount: 50,
    maximumAmount: 350,
    amountStep: 10,
  },
  {
    id: '22222222-2222-4222-8222-222222222222',
    name: 'Arroz',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 130,
      proteinG: 2.7,
      carbohydrateG: 28,
      fatG: 0.3,
      fiberG: 0.4,
    },
    roles: ['carbohydrate_source'],
    compatibleFoodStyles: ['vegan'],
    mealTypes: ['any'],
    minimumAmount: 50,
    maximumAmount: 400,
    amountStep: 10,
  },
  {
    id: '33333333-3333-4333-8333-333333333333',
    name: 'Brocolis',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 35,
      proteinG: 2.4,
      carbohydrateG: 7,
      fatG: 0.4,
      fiberG: 3.3,
    },
    roles: ['vegetable_or_fruit'],
    compatibleFoodStyles: ['vegan'],
    mealTypes: ['any'],
    minimumAmount: 50,
    maximumAmount: 300,
    amountStep: 10,
  },
  {
    id: '44444444-4444-4444-8444-444444444444',
    name: 'Azeite',
    baseAmount: 10,
    baseUnit: 'ml',
    nutrition: {
      calories: 90,
      proteinG: 0,
      carbohydrateG: 0,
      fatG: 10,
      fiberG: 0,
    },
    roles: ['fat_source'],
    compatibleFoodStyles: ['vegan'],
    mealTypes: ['any'],
    minimumAmount: 5,
    maximumAmount: 40,
    amountStep: 5,
  },
];

describe('buildNutritionPlannerPersistencePayload', () => {
  it('preserva metas, porcoes e substituicoes para a transacao', () => {
    const recommendation = recommendNutritionPlan({
      calorieTargetOverride: 1800,
      currentWeightKg: 70,
      mealsPerDay: 2,
      foodStyle: 'vegan',
    });
    const generated = generateNutritionPlan({ recommendation, foods });
    const payload = buildNutritionPlannerPersistencePayload({
      generated,
      userId: '55555555-5555-4555-8555-555555555555',
      goalId: null,
      name: 'Plano vegano',
      status: 'active',
    });

    expect(payload).toMatchObject({
      status: 'active',
      planner_version: 'nutrition-food-generator-v1',
      food_style: 'vegan',
      daily_calories_target: 1800,
      meals: expect.arrayContaining([
        expect.objectContaining({
          items: expect.arrayContaining([
            expect.objectContaining({
              food_id: expect.any(String),
              nutrition_role: 'protein_source',
              quantity: expect.any(Number),
              substitutions: expect.any(Array),
            }),
          ]),
        }),
      ]),
    });
  });

  it('guarda as entradas necessarias para auditar a recomendacao', () => {
    const recommendation = recommendNutritionPlan({
      phase: 'fat_loss',
      calorieTargetOverride: 1700,
      currentWeightKg: 75,
      mealsPerDay: 1,
      foodStyle: 'vegan',
    });
    const generated = generateNutritionPlan({ recommendation, foods });
    const payload = buildNutritionPlannerPersistencePayload({
      generated,
      userId: '55555555-5555-4555-8555-555555555555',
      goalId: '66666666-6666-4666-8666-666666666666',
      name: 'Plano auditavel',
      status: 'draft',
    });

    expect(payload).toMatchObject({
      goal_id: '66666666-6666-4666-8666-666666666666',
      nutrition_phase: 'fat_loss',
      planner_input: {
        rule_version: 'nutrition-planner-rules-v1',
        energy: { method: 'calorie_target_override' },
        assumptions: expect.any(Array),
      },
    });
  });

  it('persiste refeicoes diferentes para treino e descanso', () => {
    const baseRecommendation = recommendNutritionPlan({
      calorieTargetOverride: 2000,
      currentWeightKg: 70,
      mealsPerDay: 4,
      foodStyle: 'vegan',
    });
    const trainingRecommendation = recommendNutritionPlan({
      calorieTargetOverride: 2100,
      currentWeightKg: 70,
      mealsPerDay: 5,
      foodStyle: 'vegan',
    });
    const restRecommendation = recommendNutritionPlan({
      calorieTargetOverride: 1920,
      currentWeightKg: 70,
      mealsPerDay: 4,
      foodStyle: 'vegan',
    });
    const generated = generateNutritionPlan({
      recommendation: baseRecommendation,
      foods,
    });
    const payload = buildNutritionPlannerPersistencePayload({
      generated,
      variants: [
        {
          dayType: 'training_day',
          rotationIndex: 0,
          generated: generateNutritionPlan({
            recommendation: trainingRecommendation,
            foods,
          }),
        },
        {
          dayType: 'rest_day',
          rotationIndex: 0,
          generated: generateNutritionPlan({
            recommendation: restRecommendation,
            foods,
          }),
        },
      ],
      userId: '55555555-5555-4555-8555-555555555555',
      goalId: null,
      name: 'Plano com variacoes',
      status: 'active',
      flexibleMealFrequency: 'weekly',
      flexibleMealWeekday: 'saturday',
      alcoholFrequency: 'fortnightly',
      alcoholPreferredWeekday: 'saturday',
      alcoholMaxServings: 1,
    });

    expect(payload).toMatchObject({
      uses_day_variants: true,
      menu_rotation_enabled: false,
      menu_rotation_size: 1,
      flexible_meal_frequency: 'weekly',
      flexible_meal_weekday: 'saturday',
      alcohol_frequency: 'fortnightly',
      alcohol_preferred_weekday: 'saturday',
      alcohol_max_servings: 1,
      training_day_calories_target: 2100,
      rest_day_calories_target: 1920,
      planner_input: {
        day_variants: [
          { day_type: 'training_day', meals: 5 },
          { day_type: 'rest_day', meals: 4 },
        ],
      },
    });
    expect(payload).toHaveProperty('meals');
    expect((payload as { meals: Array<{ day_type: string }> }).meals).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ day_type: 'training_day' }),
        expect.objectContaining({ day_type: 'rest_day' }),
      ]),
    );
  });
});

import { describe, expect, it } from 'vitest';
import {
  generateNutritionPlan,
  NutritionFoodGeneratorError,
} from './nutrition-planner.generator.js';
import { recommendNutritionPlan } from './nutrition-planner.rules.js';
import type {
  NutritionFoodCandidate,
  NutritionFoodStyle,
  NutritionPlannerInput,
} from './nutrition-planner.types.js';

const allStyles: NutritionFoodStyle[] = [
  'omnivore',
  'pescatarian',
  'vegetarian',
  'vegan',
  'custom',
];

const catalog: NutritionFoodCandidate[] = [
  {
    id: 'chicken',
    name: 'Peito de frango',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 165,
      proteinG: 31,
      carbohydrateG: 0,
      fatG: 3.6,
      fiberG: 0,
    },
    roles: ['protein_source'],
    compatibleFoodStyles: ['omnivore', 'custom'],
    mealTypes: ['main'],
    processingLevel: 'minimally_processed',
    minimumAmount: 50,
    maximumAmount: 300,
    amountStep: 10,
  },
  {
    id: 'salmon',
    name: 'Salmao',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 208,
      proteinG: 25,
      carbohydrateG: 0,
      fatG: 12,
      fiberG: 0,
    },
    roles: ['protein_source'],
    compatibleFoodStyles: ['omnivore', 'pescatarian', 'custom'],
    mealTypes: ['main'],
    processingLevel: 'in_natura',
    minimumAmount: 50,
    maximumAmount: 300,
    amountStep: 10,
  },
  {
    id: 'egg',
    name: 'Ovo',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 143,
      proteinG: 13,
      carbohydrateG: 0.7,
      fatG: 9.5,
      fiberG: 0,
    },
    roles: ['protein_source'],
    compatibleFoodStyles: ['omnivore', 'pescatarian', 'vegetarian', 'custom'],
    mealTypes: ['breakfast', 'snack'],
    processingLevel: 'minimally_processed',
    minimumAmount: 50,
    maximumAmount: 250,
    amountStep: 25,
  },
  {
    id: 'tofu',
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
    compatibleFoodStyles: allStyles,
    mealTypes: ['any'],
    processingLevel: 'minimally_processed',
    minimumAmount: 50,
    maximumAmount: 350,
    amountStep: 10,
  },
  {
    id: 'yogurt',
    name: 'Iogurte natural',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 62,
      proteinG: 5,
      carbohydrateG: 7,
      fatG: 1.5,
      fiberG: 0,
    },
    roles: ['protein_source'],
    compatibleFoodStyles: ['omnivore', 'pescatarian', 'vegetarian', 'custom'],
    mealTypes: ['breakfast', 'snack'],
    allergens: ['leite', 'lactose'],
    processingLevel: 'minimally_processed',
    minimumAmount: 100,
    maximumAmount: 300,
    amountStep: 25,
  },
  {
    id: 'rice',
    name: 'Arroz integral cozido',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 124,
      proteinG: 2.6,
      carbohydrateG: 25.8,
      fatG: 1,
      fiberG: 2.7,
    },
    roles: ['carbohydrate_source'],
    compatibleFoodStyles: allStyles,
    mealTypes: ['main'],
    processingLevel: 'minimally_processed',
    minimumAmount: 50,
    maximumAmount: 400,
    amountStep: 10,
  },
  {
    id: 'potato',
    name: 'Batata cozida',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 87,
      proteinG: 1.9,
      carbohydrateG: 20,
      fatG: 0.1,
      fiberG: 1.8,
    },
    roles: ['carbohydrate_source'],
    compatibleFoodStyles: allStyles,
    mealTypes: ['main'],
    processingLevel: 'minimally_processed',
    minimumAmount: 50,
    maximumAmount: 500,
    amountStep: 10,
  },
  {
    id: 'oats',
    name: 'Aveia',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 389,
      proteinG: 16.9,
      carbohydrateG: 66.3,
      fatG: 6.9,
      fiberG: 10.6,
    },
    roles: ['carbohydrate_source'],
    compatibleFoodStyles: allStyles,
    mealTypes: ['breakfast', 'snack'],
    processingLevel: 'minimally_processed',
    minimumAmount: 20,
    maximumAmount: 150,
    amountStep: 5,
  },
  {
    id: 'broccoli',
    name: 'Brocolis',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 35,
      proteinG: 2.4,
      carbohydrateG: 7.2,
      fatG: 0.4,
      fiberG: 3.3,
    },
    roles: ['vegetable_or_fruit'],
    compatibleFoodStyles: allStyles,
    mealTypes: ['main'],
    processingLevel: 'in_natura',
    minimumAmount: 50,
    maximumAmount: 300,
    amountStep: 10,
  },
  {
    id: 'berries',
    name: 'Frutas vermelhas',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 50,
      proteinG: 0.7,
      carbohydrateG: 11,
      fatG: 0.3,
      fiberG: 4.5,
    },
    roles: ['vegetable_or_fruit'],
    compatibleFoodStyles: allStyles,
    mealTypes: ['breakfast', 'snack'],
    processingLevel: 'in_natura',
    minimumAmount: 50,
    maximumAmount: 300,
    amountStep: 10,
  },
  {
    id: 'banana',
    name: 'Banana',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 89,
      proteinG: 1.1,
      carbohydrateG: 22.8,
      fatG: 0.3,
      fiberG: 2.6,
    },
    roles: ['vegetable_or_fruit'],
    compatibleFoodStyles: allStyles,
    mealTypes: ['breakfast', 'snack'],
    processingLevel: 'in_natura',
    minimumAmount: 50,
    maximumAmount: 300,
    amountStep: 10,
  },
  {
    id: 'olive-oil',
    name: 'Azeite de oliva',
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
    compatibleFoodStyles: allStyles,
    mealTypes: ['main'],
    processingLevel: 'processed',
    minimumAmount: 5,
    maximumAmount: 40,
    amountStep: 5,
  },
  {
    id: 'avocado',
    name: 'Abacate',
    baseAmount: 100,
    baseUnit: 'g',
    nutrition: {
      calories: 160,
      proteinG: 2,
      carbohydrateG: 8.5,
      fatG: 14.7,
      fiberG: 6.7,
    },
    roles: ['fat_source', 'vegetable_or_fruit'],
    compatibleFoodStyles: allStyles,
    mealTypes: ['breakfast', 'snack', 'main'],
    processingLevel: 'in_natura',
    minimumAmount: 30,
    maximumAmount: 200,
    amountStep: 10,
  },
  {
    id: 'peanut-butter',
    name: 'Pasta de amendoim',
    baseAmount: 20,
    baseUnit: 'g',
    nutrition: {
      calories: 118,
      proteinG: 5,
      carbohydrateG: 4,
      fatG: 10,
      fiberG: 1.2,
    },
    roles: ['fat_source'],
    compatibleFoodStyles: allStyles,
    mealTypes: ['breakfast', 'snack'],
    allergens: ['amendoim'],
    processingLevel: 'processed',
    minimumAmount: 10,
    maximumAmount: 50,
    amountStep: 5,
  },
];

const baseInput: NutritionPlannerInput = {
  phase: 'maintenance',
  calorieTargetOverride: 2200,
  currentWeightKg: 80,
  activityLevel: 'moderate',
  macroPattern: 'balanced',
  mealsPerDay: 4,
  foodStyle: 'omnivore',
};

function generate(input: NutritionPlannerInput = baseInput, foods = catalog) {
  return generateNutritionPlan({
    recommendation: recommendNutritionPlan(input),
    foods,
  });
}

describe('generateNutritionPlan', () => {
  it('monta todas as refeicoes com porcoes e totais calculados', () => {
    const result = generate();

    expect(result.meals).toHaveLength(4);
    expect(result.meals.every((meal) => meal.items.length >= 3)).toBe(true);
    expect(result.actual.calories).toBeGreaterThan(0);
    expect(Math.abs(result.deviationPercent.calories)).toBeLessThan(15);
  });

  it('aplica alergias e alimentos rejeitados antes da selecao', () => {
    const result = generate({
      ...baseInput,
      allergenExclusions: ['amendoim', 'lactose'],
      dislikedFoods: ['brocolis'],
    });
    const names = result.meals.flatMap((meal) =>
      meal.items.flatMap((item) => [
        item.name,
        ...item.substitutions.map((substitution) => substitution.name),
      ]),
    );

    expect(names).not.toContain('Pasta de amendoim');
    expect(names).not.toContain('Iogurte natural');
    expect(names).not.toContain('Brocolis');
  });

  it('prioriza um alimento preferido quando ele e compativel', () => {
    const result = generate({
      ...baseInput,
      mealsPerDay: 1,
      preferredFoods: ['salmao'],
    });

    expect(result.meals[0].items.map((item) => item.foodId)).toContain(
      'salmon',
    );
  });

  it('respeita o estilo vegano', () => {
    const result = generate({ ...baseInput, foodStyle: 'vegan' });
    const selectedIds = result.meals.flatMap((meal) =>
      meal.items.map((item) => item.foodId),
    );

    expect(selectedIds).not.toContain('chicken');
    expect(selectedIds).not.toContain('salmon');
    expect(selectedIds).not.toContain('egg');
    expect(selectedIds).not.toContain('yogurt');
    expect(selectedIds).toContain('tofu');
  });

  it('na cetogenica nao inclui fonte dedicada de carboidrato nem fruta rica em carboidrato', () => {
    const result = generate({
      ...baseInput,
      macroPattern: 'ketogenic',
      mealsPerDay: 3,
    });
    const items = result.meals.flatMap((meal) => meal.items);

    expect(items.map((item) => item.role)).not.toContain('carbohydrate_source');
    expect(items.map((item) => item.foodId)).not.toContain('banana');
  });

  it('oferece substituicoes do mesmo papel nutricional', () => {
    const result = generate({ ...baseInput, mealsPerDay: 1 });

    for (const item of result.meals[0].items) {
      expect(
        item.substitutions.every(
          (substitution) => substitution.role === item.role,
        ),
      ).toBe(true);
      expect(
        item.substitutions.every((substitution) => substitution.amount > 0),
      ).toBe(true);
    }
  });

  it('mantem porcoes dentro dos limites e nos passos do catalogo', () => {
    const result = generate();
    const byId = new Map(catalog.map((food) => [food.id, food]));

    for (const item of result.meals.flatMap((meal) => meal.items)) {
      const food = byId.get(item.foodId)!;
      expect(item.amount).toBeGreaterThanOrEqual(food.minimumAmount!);
      expect(item.amount).toBeLessThanOrEqual(food.maximumAmount!);
      expect(item.amount % food.amountStep!).toBe(0);
    }
  });

  it('reduz repeticao quando existem alternativas equivalentes', () => {
    const proteins: NutritionFoodCandidate[] = ['a', 'b', 'c'].map((id) => ({
      id: `protein-${id}`,
      name: `Proteina ${id}`,
      baseAmount: 100,
      baseUnit: 'g',
      nutrition: {
        calories: 150,
        proteinG: 25,
        carbohydrateG: 2,
        fatG: 5,
        fiberG: 0,
      },
      roles: ['protein_source'],
      compatibleFoodStyles: allStyles,
      mealTypes: ['any'],
      processingLevel: 'minimally_processed',
      minimumAmount: 50,
      maximumAmount: 300,
      amountStep: 10,
    }));
    const result = generate({ ...baseInput, mealsPerDay: 3 }, [
      ...proteins,
      catalog.find((food) => food.id === 'rice')!,
      catalog.find((food) => food.id === 'oats')!,
      catalog.find((food) => food.id === 'broccoli')!,
      catalog.find((food) => food.id === 'berries')!,
      catalog.find((food) => food.id === 'olive-oil')!,
      catalog.find((food) => food.id === 'avocado')!,
    ]);
    const selectedProteins = result.meals.map(
      (meal) =>
        meal.items.find((item) => item.role === 'protein_source')!.foodId,
    );

    expect(new Set(selectedProteins).size).toBe(3);
  });

  it('prefere alimento menos processado quando os demais criterios empatam', () => {
    const natural: NutritionFoodCandidate = {
      ...catalog.find((food) => food.id === 'tofu')!,
      id: 'natural-protein',
      name: 'Proteina natural',
      processingLevel: 'in_natura',
    };
    const ultraProcessed: NutritionFoodCandidate = {
      ...natural,
      id: 'ultra-protein',
      name: 'Proteina ultraprocessada',
      processingLevel: 'ultra_processed',
    };
    const result = generate(
      { ...baseInput, mealsPerDay: 1, foodStyle: 'vegan' },
      [
        natural,
        ultraProcessed,
        catalog.find((food) => food.id === 'rice')!,
        catalog.find((food) => food.id === 'broccoli')!,
        catalog.find((food) => food.id === 'avocado')!,
      ],
    );

    expect(result.meals[0].items[0].foodId).toBe('natural-protein');
  });

  it('avisa quando o catalogo nao possui um papel obrigatorio', () => {
    const result = generate(
      { ...baseInput, mealsPerDay: 1, foodStyle: 'vegan' },
      [catalog.find((food) => food.id === 'rice')!],
    );

    expect(result.meals[0].warnings.join(' ')).toContain('fonte de proteina');
    expect(result.meals[0].warnings.join(' ')).toContain('vegetal ou fruta');
  });

  it('bloqueia catalogo vazio e contexto que exige revisao', () => {
    expect(() => generate(baseInput, [])).toThrow(NutritionFoodGeneratorError);
    expect(() =>
      generate({ ...baseInput, healthFlags: ['kidney_disease'] }),
    ).toThrowError('exige revisao');
  });

  it('rejeita dados nutricionais invalidos', () => {
    const invalid = {
      ...catalog[0],
      nutrition: { ...catalog[0].nutrition, calories: -1 },
    };

    expect(() => generate(baseInput, [invalid])).toThrowError(
      'Alimento invalido',
    );
  });

  it('e deterministico para a mesma recomendacao e catalogo', () => {
    expect(generate()).toEqual(generate());
  });

  it('gera cardapios variados e ainda deterministicos por semente', () => {
    const recommendation = recommendNutritionPlan(baseInput);
    const first = generateNutritionPlan({
      recommendation,
      foods: catalog,
      varietySeed: 0,
    });
    const second = generateNutritionPlan({
      recommendation,
      foods: catalog,
      varietySeed: 1,
    });
    const repeatedFirst = generateNutritionPlan({
      recommendation,
      foods: catalog,
      varietySeed: 0,
    });
    const selectedIds = (plan: typeof first) =>
      plan.meals.flatMap((meal) => meal.items.map((item) => item.foodId));

    expect(selectedIds(first)).not.toEqual(selectedIds(second));
    expect(first).toEqual(repeatedFirst);
  });
});

import { describe, expect, it } from 'vitest';
import {
  NutritionPlannerInputError,
  recommendNutritionPlan,
} from './nutrition-planner.rules.js';
import type { NutritionPlannerInput } from './nutrition-planner.types.js';

const baseInput: NutritionPlannerInput = {
  phase: 'maintenance',
  currentWeightKg: 80,
  heightCm: 180,
  ageYears: 28,
  metabolicEquationSex: 'male',
  activityLevel: 'moderate',
  macroPattern: 'balanced',
  mealsPerDay: 4,
};

describe('recommendNutritionPlan', () => {
  it('calcula manutencao e uma distribuicao equilibrada', () => {
    const result = recommendNutritionPlan(baseInput);

    expect(result.phase).toBe('maintenance');
    expect(result.energy.method).toBe('mifflin_st_jeor');
    expect(result.energy.targetCalories).toBe(
      result.energy.maintenanceCalories,
    );
    expect(result.targets.percentages.carbohydrate).toBeGreaterThanOrEqual(45);
    expect(result.meals).toHaveLength(4);
  });

  it('aplica deficit moderado no cutting', () => {
    const result = recommendNutritionPlan({ ...baseInput, phase: 'fat_loss' });

    expect(result.energy.phaseAdjustmentPercent).toBe(-15);
    expect(result.energy.targetCalories).toBeLessThan(
      result.energy.maintenanceCalories,
    );
    expect(result.targets.proteinG).toBeGreaterThanOrEqual(144);
  });

  it('aplica superavit pequeno no ganho de massa', () => {
    const result = recommendNutritionPlan({ ...baseInput, phase: 'mass_gain' });

    expect(result.energy.phaseAdjustmentPercent).toBe(10);
    expect(result.energy.targetCalories).toBeGreaterThan(
      result.energy.maintenanceCalories,
    );
  });

  it('trata diet break como manutencao', () => {
    const result = recommendNutritionPlan({
      ...baseInput,
      phase: 'diet_break',
    });

    expect(result.energy.phaseAdjustmentPercent).toBe(0);
    expect(result.energy.targetCalories).toBe(
      result.energy.maintenanceCalories,
    );
  });

  it('mantem cetogenica abaixo de 50 g de carboidrato e recomenda revisao', () => {
    const result = recommendNutritionPlan({
      ...baseInput,
      macroPattern: 'ketogenic',
    });

    expect(result.targets.carbohydrateG).toBeLessThanOrEqual(50);
    expect(result.reviewRecommended).toBe(true);
    expect(result.mealBuildingBlocks.map((item) => item.role)).not.toContain(
      'carbohydrate_source',
    );
  });

  it('cria low carb sem confundir com cetogenica', () => {
    const result = recommendNutritionPlan({
      ...baseInput,
      macroPattern: 'low_carb',
    });

    expect(result.targets.percentages.carbohydrate).toBeCloseTo(30, 0);
    expect(result.targets.carbohydrateG).toBeGreaterThan(50);
  });

  it('jejum altera os horarios mas nao as metas do dia', () => {
    const regular = recommendNutritionPlan(baseInput);
    const restricted = recommendNutritionPlan({
      ...baseInput,
      mealSchedule: 'time_restricted',
      eatingWindowHours: 8,
      mealsPerDay: 3,
    });

    expect(restricted.targets).toEqual(regular.targets);
    expect(restricted.meals).toHaveLength(3);
    expect(restricted.meals[0].suggestedTime).toBe('10:00');
    expect(restricted.meals[2].suggestedTime).toBe('18:00');
  });

  it('preserva estilo alimentar e normaliza gostos e exclusoes', () => {
    const result = recommendNutritionPlan({
      ...baseInput,
      foodStyle: 'vegetarian',
      preferredFoods: [' Arroz ', 'Feijao', 'arroz'],
      dislikedFoods: ['Brocolis'],
      foodRestrictions: ['Lactose'],
      allergenExclusions: ['AMENDOIM'],
    });

    expect(result.foodStyle).toBe('vegetarian');
    expect(result.exclusions.preferredFoods).toEqual(['arroz', 'feijao']);
    expect(result.exclusions.preferenceExclusions).toEqual(['brocolis']);
    expect(result.exclusions.hardExclusions).toEqual(['amendoim', 'lactose']);
  });

  it('usa meta calorica explicita sem aplicar outro ajuste', () => {
    const result = recommendNutritionPlan({
      phase: 'fat_loss',
      calorieTargetOverride: 2100,
      currentWeightKg: 80,
    });

    expect(result.energy.method).toBe('calorie_target_override');
    expect(result.energy.phaseAdjustmentPercent).toBe(0);
    expect(result.targets.calories).toBe(2100);
  });

  it('aceita macros personalizados somente quando somam 100%', () => {
    const result = recommendNutritionPlan({
      ...baseInput,
      macroPattern: 'custom',
      customMacroPercentages: {
        protein: 30,
        carbohydrate: 45,
        fat: 25,
      },
    });

    expect(result.targets.percentages).toEqual({
      protein: 30,
      carbohydrate: 45,
      fat: 25,
    });
    expect(() =>
      recommendNutritionPlan({
        ...baseInput,
        macroPattern: 'custom',
        customMacroPercentages: {
          protein: 30,
          carbohydrate: 30,
          fat: 30,
        },
      }),
    ).toThrow(NutritionPlannerInputError);
  });

  it('faz a soma das refeicoes bater com a meta do dia', () => {
    const result = recommendNutritionPlan({ ...baseInput, mealsPerDay: 7 });
    const sum = (field: 'calories' | 'proteinG' | 'carbohydrateG' | 'fatG') =>
      result.meals.reduce((total, meal) => total + meal[field], 0);

    expect(sum('calories')).toBe(result.targets.calories);
    expect(sum('proteinG')).toBe(result.targets.proteinG);
    expect(sum('carbohydrateG')).toBe(result.targets.carbohydrateG);
    expect(sum('fatG')).toBe(result.targets.fatG);
  });

  it('bloqueia geracao automatica quando existe contexto clinico', () => {
    const result = recommendNutritionPlan({
      ...baseInput,
      healthFlags: ['kidney_disease'],
    });

    expect(result.automaticGenerationAllowed).toBe(false);
    expect(result.reviewRecommended).toBe(true);
  });

  it('nao inventa calorias quando faltam dados suficientes', () => {
    expect(() => recommendNutritionPlan({ phase: 'maintenance' })).toThrowError(
      'Informe uma meta calorica',
    );
  });

  it('e deterministico para a mesma entrada', () => {
    expect(recommendNutritionPlan(baseInput)).toEqual(
      recommendNutritionPlan(baseInput),
    );
  });
});

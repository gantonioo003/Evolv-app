import { describe, expect, it } from 'vitest';
import type { Tables } from '../database/database.types.js';
import {
  buildMealReplacementSnapshot,
  isCompatibleExerciseReplacement,
  resolveNutritionDayType,
} from './planner-adjustments.service.js';

const exercise = {
  id: 'current',
  name: 'Supino reto',
  muscle_group: 'chest',
  movement_pattern: 'horizontal_push',
  training_kind: 'resistance',
  equipment: 'barbell',
};

describe('Planner adjustments', () => {
  it('aceita troca pelo mesmo musculo', () => {
    expect(
      isCompatibleExerciseReplacement(exercise, {
        ...exercise,
        id: 'replacement',
        name: 'Supino com halteres',
        equipment: 'dumbbell',
      }),
    ).toBe(true);
  });

  it('aceita o mesmo padrao de movimento quando o musculo cadastrado difere', () => {
    expect(
      isCompatibleExerciseReplacement(exercise, {
        ...exercise,
        id: 'replacement',
        muscle_group: 'front_deltoid',
      }),
    ).toBe(true);
  });

  it('recusa cardio no lugar de exercicio resistido', () => {
    expect(
      isCompatibleExerciseReplacement(exercise, {
        ...exercise,
        id: 'replacement',
        training_kind: 'cardio',
      }),
    ).toBe(false);
  });

  it('mantem o alimento anterior como opcao ao fazer uma troca', () => {
    const current = {
      id: 'item',
      food_id: 'rice',
      name: 'Arroz',
      amount: '200 g',
      quantity: 200,
      unit: 'g',
      nutrition_role: 'carbohydrate_source',
      calories_kcal: 260,
      protein_g: 5.4,
      carbohydrate_g: 56.4,
      fat_g: 0.6,
      fiber_g: 0.8,
      substitutions: [],
    } as unknown as Tables<'meal_items'>;

    const next = buildMealReplacementSnapshot(current, {
      food_id: 'potato',
      name: 'Batata',
      role: 'carbohydrate_source',
      amount: 300,
      unit: 'g',
      nutrition: {
        calories: 261,
        proteinG: 5.7,
        carbohydrateG: 60,
        fatG: 0.3,
        fiberG: 5.4,
      },
      similarity_score: 0.92,
    });

    expect(next.name).toBe('Batata');
    expect(next.amount).toBe('300 g');
    expect(next.substitutions).toEqual([
      expect.objectContaining({ food_id: 'rice', name: 'Arroz' }),
    ]);
  });

  it('liga o contexto alimentar ao tipo de atividade sem inventar ajuste', () => {
    expect(
      resolveNutritionDayType({
        activityType: 'cardio',
        intensity: 'moderate',
        estimatedMinutes: 35,
      }),
    ).toBe('rest_day');
    expect(
      resolveNutritionDayType({
        activityType: 'cardio',
        intensity: 'hard',
        estimatedMinutes: 60,
      }),
    ).toBe('training_day');
    expect(
      resolveNutritionDayType({
        activityType: 'rest',
        explicitDayType: 'training_day',
      }),
    ).toBe('training_day');
  });
});

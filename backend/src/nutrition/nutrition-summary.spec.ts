import { calculateNutritionSummary } from './nutrition-summary.js';

describe('calculateNutritionSummary', () => {
  it('soma calorias e macronutrientes dos itens', () => {
    const result = calculateNutritionSummary([
      {
        calories_kcal: 300,
        protein_g: 25,
        carbohydrate_g: 40,
        fat_g: 5,
        fiber_g: 4,
      },
      {
        calories_kcal: 200,
        protein_g: 15,
        carbohydrate_g: 20,
        fat_g: 7,
        fiber_g: 2,
      },
    ]);

    expect(result).toEqual({
      items: 2,
      calories_kcal: 500,
      protein_g: 40,
      carbohydrate_g: 60,
      fat_g: 12,
      fiber_g: 6,
    });
  });
});

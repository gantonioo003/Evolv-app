type NutritionItem = {
  calories_kcal: number;
  protein_g: number;
  carbohydrate_g: number;
  fat_g: number;
  fiber_g: number;
};

export type NutritionSummary = NutritionItem & { items: number };

export function calculateNutritionSummary(
  items: NutritionItem[],
): NutritionSummary {
  return items.reduce<NutritionSummary>(
    (total, item) => ({
      items: total.items + 1,
      calories_kcal: total.calories_kcal + Number(item.calories_kcal),
      protein_g: total.protein_g + Number(item.protein_g),
      carbohydrate_g: total.carbohydrate_g + Number(item.carbohydrate_g),
      fat_g: total.fat_g + Number(item.fat_g),
      fiber_g: total.fiber_g + Number(item.fiber_g),
    }),
    {
      items: 0,
      calories_kcal: 0,
      protein_g: 0,
      carbohydrate_g: 0,
      fat_g: 0,
      fiber_g: 0,
    },
  );
}

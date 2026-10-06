import type {
  NutritionFoodCandidate,
  NutritionFoodGeneratorRequest,
  NutritionFoodMealType,
  NutritionFoodRole,
  NutritionGeneratedFood,
  NutritionGeneratedMeal,
  NutritionGeneratedPlan,
  NutritionGeneratedSubstitution,
  NutritionMealTarget,
  NutritionPlannerRecommendation,
  NutritionTargetDeviation,
  NutritionValues,
} from './nutrition-planner.types.js';

export type NutritionFoodGeneratorErrorCode =
  | 'EMPTY_CATALOG'
  | 'INVALID_FOOD_CANDIDATE'
  | 'NO_ELIGIBLE_FOODS'
  | 'AUTOMATIC_GENERATION_BLOCKED';

export class NutritionFoodGeneratorError extends Error {
  constructor(
    readonly code: NutritionFoodGeneratorErrorCode,
    message: string,
  ) {
    super(message);
    this.name = 'NutritionFoodGeneratorError';
  }
}

type SelectedFood = {
  food: NutritionFoodCandidate;
  role: NutritionFoodRole;
  amount: number;
};

const zeroNutrition = (): NutritionValues => ({
  calories: 0,
  proteinG: 0,
  carbohydrateG: 0,
  fatG: 0,
  fiberG: 0,
});

export function generateNutritionPlan(
  request: NutritionFoodGeneratorRequest,
): NutritionGeneratedPlan {
  const { recommendation } = request;
  if (!recommendation.automaticGenerationAllowed) {
    throw new NutritionFoodGeneratorError(
      'AUTOMATIC_GENERATION_BLOCKED',
      'A recomendacao exige revisao antes da montagem automatica das refeicoes.',
    );
  }
  if (!request.foods.length) {
    throw new NutritionFoodGeneratorError(
      'EMPTY_CATALOG',
      'O catalogo de alimentos esta vazio.',
    );
  }

  const catalog = prepareCatalog(request.foods);
  const eligibleCatalog = catalog.filter((food) =>
    isFoodEligible(food, recommendation),
  );
  if (!eligibleCatalog.length) {
    throw new NutritionFoodGeneratorError(
      'NO_ELIGIBLE_FOODS',
      'Nenhum alimento atende ao estilo, restricoes e preferencias informados.',
    );
  }

  const usage = new Map<string, number>();
  const maxSubstitutions = clampInteger(
    request.maxSubstitutionsPerItem ?? 3,
    0,
    10,
  );
  const meals = recommendation.meals.map((target) => {
    const meal = generateMeal(
      target,
      recommendation,
      eligibleCatalog,
      usage,
      maxSubstitutions,
      request.varietySeed,
    );
    for (const item of meal.items) {
      usage.set(item.foodId, (usage.get(item.foodId) ?? 0) + 1);
    }
    return meal;
  });
  const actual = sumNutrition(meals.map((meal) => meal.actual));
  const target = recommendation.targets;
  const deviationPercent = calculateDeviation(actual, {
    calories: target.calories,
    proteinG: target.proteinG,
    carbohydrateG: target.carbohydrateG,
    fatG: target.fatG,
  });
  const warnings = meals.flatMap((meal) =>
    meal.warnings.map((warning) => `${meal.name}: ${warning}`),
  );

  if (Math.abs(deviationPercent.calories) > 12) {
    warnings.push(
      'O catalogo nao permitiu aproximar o total diario de calorias dentro de 12%.',
    );
  }
  if (Math.abs(deviationPercent.protein) > 15) {
    warnings.push(
      'O catalogo nao permitiu aproximar a proteina diaria dentro de 15%.',
    );
  }

  return {
    generatorVersion: 'nutrition-food-generator-v1',
    recommendation,
    meals,
    actual,
    deviationPercent,
    warnings: [...new Set(warnings)],
  };
}

function generateMeal(
  target: NutritionMealTarget,
  recommendation: NutritionPlannerRecommendation,
  catalog: NutritionFoodCandidate[],
  usage: Map<string, number>,
  maxSubstitutions: number,
  varietySeed?: number,
): NutritionGeneratedMeal {
  const warnings: string[] = [];
  const mealType = identifyMealType(target);
  const selected: SelectedFood[] = [];
  const roles = rolesForMeal(recommendation, target);

  for (const [roleIndex, { role, required }] of roles.entries()) {
    const candidates = catalog
      .filter((food) => food.roles.includes(role))
      .filter((food) => matchesMealType(food, mealType))
      .filter((food) => !selected.some((item) => item.food.id === food.id))
      .sort((left, right) =>
        compareCandidates(left, right, role, mealType, recommendation, usage),
      );
    const choiceWindow = Math.min(3, candidates.length);
    const food =
      candidates[
        varietySeed === undefined
          ? 0
          : (varietySeed + target.position + roleIndex) % choiceWindow
      ];
    if (!food) {
      if (required) {
        warnings.push(
          `Falta alimento elegivel para o papel ${roleLabel(role)}.`,
        );
      }
      continue;
    }
    selected.push({
      food,
      role,
      amount: initialAmount(food),
    });
  }

  const optimized = optimizeAmounts(selected, target);
  const items = optimized.map((item) =>
    createGeneratedFood(item, catalog, mealType, maxSubstitutions),
  );
  const actual = sumNutrition(items.map((item) => item.nutrition));
  const deviationPercent = calculateDeviation(actual, target);

  if (!items.length) {
    warnings.push('Nenhum alimento pode ser montado para esta refeicao.');
  } else {
    if (Math.abs(deviationPercent.calories) > 15) {
      warnings.push('Calorias ficaram mais de 15% distantes da meta.');
    }
    if (Math.abs(deviationPercent.protein) > 20) {
      warnings.push('Proteina ficou mais de 20% distante da meta.');
    }
  }

  return {
    position: target.position,
    name: target.name,
    suggestedTime: target.suggestedTime,
    target,
    items,
    actual,
    deviationPercent,
    warnings,
  };
}

function prepareCatalog(foods: NutritionFoodCandidate[]) {
  const byId = new Map<string, NutritionFoodCandidate>();
  for (const food of foods) {
    validateFood(food);
    if (!byId.has(food.id)) byId.set(food.id, food);
  }
  return [...byId.values()].sort((left, right) =>
    left.id.localeCompare(right.id),
  );
}

function validateFood(food: NutritionFoodCandidate) {
  const values = [
    food.baseAmount,
    food.nutrition.calories,
    food.nutrition.proteinG,
    food.nutrition.carbohydrateG,
    food.nutrition.fatG,
    food.nutrition.fiberG,
    food.minimumAmount,
    food.maximumAmount,
    food.amountStep,
    food.defaultAmount,
  ].filter((value): value is number => value !== undefined);
  if (
    !food.id.trim() ||
    !food.name.trim() ||
    !food.baseUnit.trim() ||
    !food.roles.length ||
    !food.compatibleFoodStyles.length ||
    !Number.isFinite(food.baseAmount) ||
    food.baseAmount <= 0 ||
    values.some((value) => !Number.isFinite(value) || value < 0) ||
    (food.maximumAmount !== undefined &&
      food.minimumAmount !== undefined &&
      food.maximumAmount < food.minimumAmount)
  ) {
    throw new NutritionFoodGeneratorError(
      'INVALID_FOOD_CANDIDATE',
      `Alimento invalido no catalogo: ${food.id || food.name || 'sem identificador'}.`,
    );
  }
}

function isFoodEligible(
  food: NutritionFoodCandidate,
  recommendation: NutritionPlannerRecommendation,
) {
  if (!food.compatibleFoodStyles.includes(recommendation.foodStyle)) {
    return false;
  }
  const searchable = searchableTerms(food);
  if (
    recommendation.exclusions.hardExclusions.some((term) =>
      containsTerm(searchable, term),
    ) ||
    recommendation.exclusions.preferenceExclusions.some((term) =>
      containsTerm(searchable, term),
    )
  ) {
    return false;
  }
  if (
    recommendation.macroPattern === 'ketogenic' &&
    food.roles.includes('vegetable_or_fruit') &&
    nutrientPerHundred(food, 'carbohydrateG') > 12
  ) {
    return false;
  }
  return true;
}

function rolesForMeal(
  recommendation: NutritionPlannerRecommendation,
  target: NutritionMealTarget,
) {
  return recommendation.mealBuildingBlocks.filter((block) => {
    if (block.required) return true;
    if (block.role === 'carbohydrate_source') {
      return (
        recommendation.macroPattern !== 'ketogenic' &&
        target.carbohydrateG >= 12
      );
    }
    if (block.role === 'fat_source') return target.fatG >= 6;
    return false;
  });
}

function identifyMealType(target: NutritionMealTarget): NutritionFoodMealType {
  const name = normalizeText(target.name);
  if (name.includes('cafe') || name.includes('primeira')) return 'breakfast';
  if (name.includes('lanche') || name.includes('ceia')) return 'snack';
  return 'main';
}

function matchesMealType(
  food: NutritionFoodCandidate,
  mealType: NutritionFoodMealType,
) {
  return (
    !food.mealTypes?.length ||
    food.mealTypes.includes('any') ||
    food.mealTypes.includes(mealType)
  );
}

function compareCandidates(
  left: NutritionFoodCandidate,
  right: NutritionFoodCandidate,
  role: NutritionFoodRole,
  mealType: NutritionFoodMealType,
  recommendation: NutritionPlannerRecommendation,
  usage: Map<string, number>,
) {
  const difference =
    candidateScore(right, role, mealType, recommendation, usage) -
    candidateScore(left, role, mealType, recommendation, usage);
  return difference || left.id.localeCompare(right.id);
}

function candidateScore(
  food: NutritionFoodCandidate,
  role: NutritionFoodRole,
  mealType: NutritionFoodMealType,
  recommendation: NutritionPlannerRecommendation,
  usage: Map<string, number>,
) {
  let score = 0;
  const searchable = searchableTerms(food);
  if (
    recommendation.exclusions.preferredFoods.some((term) =>
      containsTerm(searchable, term),
    )
  ) {
    score += 100;
  }
  if (food.mealTypes?.includes(mealType)) score += 12;
  score += processingScore(food.processingLevel);
  score += roleDensity(food, role) * 2;
  score -= (usage.get(food.id) ?? 0) * 35;
  return score;
}

function processingScore(level: NutritionFoodCandidate['processingLevel']) {
  const scores = {
    in_natura: 18,
    minimally_processed: 15,
    processed: 5,
    ultra_processed: -8,
    unknown: 0,
  };
  return scores[level ?? 'unknown'];
}

function roleDensity(food: NutritionFoodCandidate, role: NutritionFoodRole) {
  if (role === 'protein_source') return nutrientPerHundred(food, 'proteinG');
  if (role === 'carbohydrate_source')
    return nutrientPerHundred(food, 'carbohydrateG');
  if (role === 'fat_source') return nutrientPerHundred(food, 'fatG');
  if (role === 'vegetable_or_fruit')
    return nutrientPerHundred(food, 'fiberG') * 2;
  return nutrientPerHundred(food, 'calories') / 10;
}

function optimizeAmounts(
  selected: SelectedFood[],
  target: NutritionMealTarget,
) {
  const current = selected.map((item) => ({ ...item }));
  let currentScore = objective(current, target);

  for (let iteration = 0; iteration < 300; iteration += 1) {
    let bestScore = currentScore;
    let bestIndex = -1;
    let bestAmount = 0;

    for (let index = 0; index < current.length; index += 1) {
      const item = current[index];
      const step = amountStep(item.food);
      for (const direction of [-1, 1]) {
        const amount = normalizeAmount(
          item.food,
          item.amount + step * direction,
        );
        if (amount === item.amount) continue;
        const proposal = current.map((value, proposalIndex) =>
          proposalIndex === index ? { ...value, amount } : value,
        );
        const score = objective(proposal, target);
        if (
          score < bestScore - 0.000001 ||
          (Math.abs(score - bestScore) <= 0.000001 &&
            (bestIndex < 0 || index < bestIndex))
        ) {
          bestScore = score;
          bestIndex = index;
          bestAmount = amount;
        }
      }
    }

    if (bestIndex < 0) break;
    current[bestIndex].amount = bestAmount;
    currentScore = bestScore;
  }
  return current;
}

function objective(items: SelectedFood[], target: NutritionMealTarget) {
  const actual = sumNutrition(
    items.map((item) => nutritionForAmount(item.food, item.amount)),
  );
  return (
    relativeError(actual.calories, target.calories) * 1.4 +
    relativeError(actual.proteinG, target.proteinG) * 2.2 +
    relativeError(actual.carbohydrateG, target.carbohydrateG) * 1.2 +
    relativeError(actual.fatG, target.fatG) * 1.4
  );
}

function createGeneratedFood(
  item: SelectedFood,
  catalog: NutritionFoodCandidate[],
  mealType: NutritionFoodMealType,
  maxSubstitutions: number,
): NutritionGeneratedFood {
  const nutrition = nutritionForAmount(item.food, item.amount);
  const substitutions = catalog
    .filter((food) => food.id !== item.food.id)
    .filter((food) => food.roles.includes(item.role))
    .filter((food) => matchesMealType(food, mealType))
    .map((food) => createSubstitution(item, food, nutrition))
    .sort(
      (left, right) =>
        right.similarityScore - left.similarityScore ||
        left.foodId.localeCompare(right.foodId),
    )
    .slice(0, maxSubstitutions);

  return {
    foodId: item.food.id,
    name: item.food.name,
    role: item.role,
    amount: item.amount,
    unit: item.food.baseUnit,
    nutrition,
    substitutions,
  };
}

function createSubstitution(
  original: SelectedFood,
  candidate: NutritionFoodCandidate,
  originalNutrition: NutritionValues,
): NutritionGeneratedSubstitution {
  const nutrient = primaryNutrient(original.role, originalNutrition);
  const candidatePerBase = candidate.nutrition[nutrient];
  const originalValue = originalNutrition[nutrient];
  const rawAmount =
    candidatePerBase > 0
      ? (originalValue / candidatePerBase) * candidate.baseAmount
      : (candidate.defaultAmount ?? candidate.baseAmount);
  const amount = normalizeAmount(candidate, rawAmount);
  const nutrition = nutritionForAmount(candidate, amount);
  const distance = substitutionDistance(originalNutrition, nutrition);

  return {
    foodId: candidate.id,
    name: candidate.name,
    role: original.role,
    amount,
    unit: candidate.baseUnit,
    nutrition,
    similarityScore: roundOneDecimal(Math.max(0, 100 - distance * 100)),
  };
}

function primaryNutrient(
  role: NutritionFoodRole,
  nutrition: NutritionValues,
): keyof NutritionValues {
  if (role === 'protein_source') return 'proteinG';
  if (role === 'carbohydrate_source') return 'carbohydrateG';
  if (role === 'fat_source') return 'fatG';
  if (role === 'vegetable_or_fruit' && nutrition.fiberG > 0) return 'fiberG';
  return 'calories';
}

function substitutionDistance(
  original: NutritionValues,
  candidate: NutritionValues,
) {
  return (
    relativeError(candidate.calories, original.calories) * 0.35 +
    relativeError(candidate.proteinG, original.proteinG) * 0.25 +
    relativeError(candidate.carbohydrateG, original.carbohydrateG) * 0.2 +
    relativeError(candidate.fatG, original.fatG) * 0.2
  );
}

function initialAmount(food: NutritionFoodCandidate) {
  return normalizeAmount(food, food.defaultAmount ?? food.baseAmount);
}

function amountStep(food: NutritionFoodCandidate) {
  if (food.amountStep !== undefined && food.amountStep > 0) {
    return food.amountStep;
  }
  if (normalizeText(food.baseUnit).includes('un')) return 0.5;
  return food.baseAmount <= 20 ? 5 : 10;
}

function minimumAmount(food: NutritionFoodCandidate) {
  return food.minimumAmount ?? amountStep(food);
}

function maximumAmount(food: NutritionFoodCandidate) {
  return food.maximumAmount ?? food.baseAmount * 4;
}

function normalizeAmount(food: NutritionFoodCandidate, amount: number) {
  const minimum = minimumAmount(food);
  const maximum = maximumAmount(food);
  const step = amountStep(food);
  const clamped = Math.min(maximum, Math.max(minimum, amount));
  const stepped = Math.round(clamped / step) * step;
  return roundOneDecimal(Math.min(maximum, Math.max(minimum, stepped)));
}

function nutritionForAmount(
  food: NutritionFoodCandidate,
  amount: number,
): NutritionValues {
  const multiplier = amount / food.baseAmount;
  return {
    calories: roundOneDecimal(food.nutrition.calories * multiplier),
    proteinG: roundOneDecimal(food.nutrition.proteinG * multiplier),
    carbohydrateG: roundOneDecimal(food.nutrition.carbohydrateG * multiplier),
    fatG: roundOneDecimal(food.nutrition.fatG * multiplier),
    fiberG: roundOneDecimal(food.nutrition.fiberG * multiplier),
  };
}

function nutrientPerHundred(
  food: NutritionFoodCandidate,
  nutrient: keyof NutritionValues,
) {
  return (food.nutrition[nutrient] * 100) / food.baseAmount;
}

function sumNutrition(values: NutritionValues[]): NutritionValues {
  const total = values.reduce((sum, value) => {
    sum.calories += value.calories;
    sum.proteinG += value.proteinG;
    sum.carbohydrateG += value.carbohydrateG;
    sum.fatG += value.fatG;
    sum.fiberG += value.fiberG;
    return sum;
  }, zeroNutrition());
  return {
    calories: roundOneDecimal(total.calories),
    proteinG: roundOneDecimal(total.proteinG),
    carbohydrateG: roundOneDecimal(total.carbohydrateG),
    fatG: roundOneDecimal(total.fatG),
    fiberG: roundOneDecimal(total.fiberG),
  };
}

function calculateDeviation(
  actual: NutritionValues,
  target: Pick<
    NutritionMealTarget,
    'calories' | 'proteinG' | 'carbohydrateG' | 'fatG'
  >,
): NutritionTargetDeviation {
  return {
    calories: signedPercent(actual.calories, target.calories),
    protein: signedPercent(actual.proteinG, target.proteinG),
    carbohydrate: signedPercent(actual.carbohydrateG, target.carbohydrateG),
    fat: signedPercent(actual.fatG, target.fatG),
  };
}

function signedPercent(actual: number, target: number) {
  if (target === 0) return actual === 0 ? 0 : 100;
  return roundOneDecimal(((actual - target) / target) * 100);
}

function relativeError(actual: number, target: number) {
  if (target === 0) return actual === 0 ? 0 : actual;
  return Math.abs(actual - target) / target;
}

function searchableTerms(food: NutritionFoodCandidate) {
  return [food.name, ...(food.tags ?? []), ...(food.allergens ?? [])]
    .map(normalizeText)
    .join(' | ');
}

function containsTerm(searchable: string, term: string) {
  const normalized = normalizeText(term);
  return normalized.length > 0 && searchable.includes(normalized);
}

function normalizeText(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLowerCase();
}

function roleLabel(role: NutritionFoodRole) {
  const labels: Record<NutritionFoodRole, string> = {
    protein_source: 'fonte de proteina',
    carbohydrate_source: 'fonte de carboidrato',
    vegetable_or_fruit: 'vegetal ou fruta',
    fat_source: 'fonte de gordura',
    optional_extra: 'complemento opcional',
  };
  return labels[role];
}

function roundOneDecimal(value: number) {
  return Math.round(value * 10) / 10;
}

function clampInteger(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, Math.round(value)));
}

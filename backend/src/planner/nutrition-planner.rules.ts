import type {
  NutritionActivityLevel,
  NutritionEnergyEstimate,
  NutritionMacroPattern,
  NutritionMacroPercentages,
  NutritionMacroTargets,
  NutritionMealBuildingBlock,
  NutritionMealSchedule,
  NutritionMealTarget,
  NutritionPhaseType,
  NutritionPlannerInput,
  NutritionPlannerRecommendation,
} from './nutrition-planner.types.js';

const activityMultipliers: Record<NutritionActivityLevel, number> = {
  sedentary: 1.2,
  light: 1.375,
  moderate: 1.55,
  very_active: 1.725,
  athlete: 1.9,
};

const phaseAdjustments: Record<NutritionPhaseType, number> = {
  mass_gain: 10,
  fat_loss: -15,
  maintenance: 0,
  recomposition: -5,
  diet_break: 0,
  custom: 0,
};

export type NutritionPlannerInputErrorCode =
  | 'MISSING_ENERGY_DATA'
  | 'INVALID_ANTHROPOMETRICS'
  | 'INVALID_CALORIE_TARGET'
  | 'INVALID_MEAL_SCHEDULE'
  | 'INVALID_CUSTOM_MACROS';

export class NutritionPlannerInputError extends Error {
  constructor(
    readonly code: NutritionPlannerInputErrorCode,
    message: string,
  ) {
    super(message);
    this.name = 'NutritionPlannerInputError';
  }
}

export function recommendNutritionPlan(
  input: NutritionPlannerInput,
): NutritionPlannerRecommendation {
  validateInput(input);

  const assumptions: string[] = [];
  const warnings: string[] = [];
  const phase = input.phase ?? 'maintenance';
  const macroPattern = input.macroPattern ?? 'balanced';
  const foodStyle = input.foodStyle ?? 'omnivore';
  const mealSchedule = input.mealSchedule ?? 'regular';
  const activityLevel = input.activityLevel ?? 'light';

  if (!input.phase)
    assumptions.push('Fase nao informada: manutencao usada como base.');
  if (!input.macroPattern)
    assumptions.push('Distribuicao nao informada: padrao equilibrado usado.');
  if (!input.foodStyle)
    assumptions.push(
      'Estilo alimentar nao informado: onivoro usado como base.',
    );
  if (!input.activityLevel)
    assumptions.push(
      'Atividade nao informada: nivel leve usado na estimativa.',
    );

  const energy = estimateEnergy(input, phase, activityLevel, assumptions);
  const targets = createMacroTargets(
    energy.targetCalories,
    input.currentWeightKg,
    activityLevel,
    phase,
    macroPattern,
    input.customMacroPercentages,
    warnings,
  );
  const meals = createMealTargets(
    targets,
    input.mealsPerDay,
    mealSchedule,
    input.eatingWindowHours,
    input.eatingWindowStartHour,
    assumptions,
    warnings,
  );
  const healthFlags = [...new Set(input.healthFlags ?? [])];
  const automaticGenerationAllowed = healthFlags.length === 0;

  if (healthFlags.length) {
    warnings.push(
      'O contexto informado exige revisao profissional antes de gerar um cardapio automatico.',
    );
  }
  if (macroPattern === 'ketogenic') {
    warnings.push(
      'Cetogenica e um protocolo restritivo; efeitos, tolerancia e seguranca precisam de acompanhamento adequado.',
    );
  }
  if (mealSchedule === 'time_restricted') {
    warnings.push(
      'A janela alimentar organiza horarios, mas nao substitui calorias, nutrientes nem aderencia.',
    );
  }
  if (targets.calories < 1200 || targets.calories > 5000) {
    warnings.push(
      'A meta energetica esta fora da faixa comum do aplicativo e deve ser revisada.',
    );
  }

  return {
    ruleVersion: 'nutrition-planner-rules-v1',
    phase,
    macroPattern,
    foodStyle,
    mealSchedule,
    energy,
    targets,
    meals,
    mealBuildingBlocks: createMealBuildingBlocks(macroPattern),
    exclusions: {
      hardExclusions: normalizeFoodList([
        ...(input.foodRestrictions ?? []),
        ...(input.allergenExclusions ?? []),
      ]),
      preferenceExclusions: normalizeFoodList(input.dislikedFoods ?? []),
      preferredFoods: normalizeFoodList(input.preferredFoods ?? []),
    },
    assumptions,
    warnings,
    reviewRecommended:
      healthFlags.length > 0 ||
      macroPattern === 'ketogenic' ||
      targets.calories < 1200 ||
      targets.calories > 5000,
    automaticGenerationAllowed,
  };
}

function validateInput(input: NutritionPlannerInput) {
  const numbers = [
    input.currentWeightKg,
    input.heightCm,
    input.ageYears,
    input.estimatedMaintenanceCalories,
    input.calorieTargetOverride,
  ].filter((value): value is number => value !== undefined);

  if (numbers.some((value) => !Number.isFinite(value) || value <= 0)) {
    throw new NutritionPlannerInputError(
      'INVALID_ANTHROPOMETRICS',
      'Peso, altura, idade e calorias devem ser numeros positivos.',
    );
  }
  if (
    input.calorieTargetOverride !== undefined &&
    (input.calorieTargetOverride < 800 || input.calorieTargetOverride > 8000)
  ) {
    throw new NutritionPlannerInputError(
      'INVALID_CALORIE_TARGET',
      'A meta calorica deve ficar entre 800 e 8000 kcal.',
    );
  }
  if (
    input.estimatedMaintenanceCalories !== undefined &&
    (input.estimatedMaintenanceCalories < 800 ||
      input.estimatedMaintenanceCalories > 8000)
  ) {
    throw new NutritionPlannerInputError(
      'INVALID_CALORIE_TARGET',
      'A manutencao estimada deve ficar entre 800 e 8000 kcal.',
    );
  }

  const canEstimate =
    input.currentWeightKg !== undefined &&
    input.heightCm !== undefined &&
    input.ageYears !== undefined;
  if (
    input.calorieTargetOverride === undefined &&
    input.estimatedMaintenanceCalories === undefined &&
    !canEstimate
  ) {
    throw new NutritionPlannerInputError(
      'MISSING_ENERGY_DATA',
      'Informe uma meta calorica, uma manutencao estimada ou peso, altura e idade.',
    );
  }
  if (input.currentWeightKg !== undefined && input.currentWeightKg > 400) {
    throw new NutritionPlannerInputError(
      'INVALID_ANTHROPOMETRICS',
      'Peso fora da faixa aceita pelo Planner.',
    );
  }
  if (
    input.heightCm !== undefined &&
    (input.heightCm < 100 || input.heightCm > 250)
  ) {
    throw new NutritionPlannerInputError(
      'INVALID_ANTHROPOMETRICS',
      'Altura fora da faixa aceita pelo Planner.',
    );
  }
  if (
    input.ageYears !== undefined &&
    (input.ageYears < 18 || input.ageYears > 100)
  ) {
    throw new NutritionPlannerInputError(
      'INVALID_ANTHROPOMETRICS',
      'A estimativa automatica atual atende adultos entre 18 e 100 anos.',
    );
  }
  if (
    input.mealsPerDay !== undefined &&
    (!Number.isInteger(input.mealsPerDay) ||
      input.mealsPerDay < 1 ||
      input.mealsPerDay > 8)
  ) {
    throw new NutritionPlannerInputError(
      'INVALID_MEAL_SCHEDULE',
      'A quantidade de refeicoes deve ficar entre 1 e 8.',
    );
  }
  if (
    input.eatingWindowHours !== undefined &&
    (input.eatingWindowHours < 4 || input.eatingWindowHours > 16)
  ) {
    throw new NutritionPlannerInputError(
      'INVALID_MEAL_SCHEDULE',
      'A janela alimentar deve ficar entre 4 e 16 horas.',
    );
  }
  if (
    input.eatingWindowStartHour !== undefined &&
    (input.eatingWindowStartHour < 0 || input.eatingWindowStartHour >= 24)
  ) {
    throw new NutritionPlannerInputError(
      'INVALID_MEAL_SCHEDULE',
      'O inicio da janela deve ser uma hora entre 0 e 23.',
    );
  }
  if (input.macroPattern === 'custom') {
    validateCustomMacros(input.customMacroPercentages);
  }
}

function validateCustomMacros(percentages?: NutritionMacroPercentages) {
  if (!percentages) {
    throw new NutritionPlannerInputError(
      'INVALID_CUSTOM_MACROS',
      'Informe os percentuais para usar uma distribuicao personalizada.',
    );
  }
  const values = [
    percentages.protein,
    percentages.carbohydrate,
    percentages.fat,
  ];
  const total = values.reduce((sum, value) => sum + value, 0);
  if (
    values.some(
      (value) => !Number.isFinite(value) || value < 0 || value > 100,
    ) ||
    Math.abs(total - 100) > 0.01
  ) {
    throw new NutritionPlannerInputError(
      'INVALID_CUSTOM_MACROS',
      'Proteina, carboidrato e gordura devem somar 100%.',
    );
  }
}

function estimateEnergy(
  input: NutritionPlannerInput,
  phase: NutritionPhaseType,
  activityLevel: NutritionActivityLevel,
  assumptions: string[],
): NutritionEnergyEstimate {
  if (input.calorieTargetOverride !== undefined) {
    return {
      method: 'calorie_target_override',
      confidence: 'high',
      restingCalories: null,
      maintenanceCalories: Math.round(input.calorieTargetOverride),
      phaseAdjustmentPercent: 0,
      targetCalories: Math.round(input.calorieTargetOverride),
    };
  }

  const adjustment = phaseAdjustments[phase];
  if (input.estimatedMaintenanceCalories !== undefined) {
    const maintenanceCalories = roundToTen(input.estimatedMaintenanceCalories);
    return {
      method: 'provided_maintenance_estimate',
      confidence: 'medium',
      restingCalories: null,
      maintenanceCalories,
      phaseAdjustmentPercent: adjustment,
      targetCalories: applyEnergyAdjustment(maintenanceCalories, adjustment),
    };
  }

  const weight = input.currentWeightKg as number;
  const height = input.heightCm as number;
  const age = input.ageYears as number;
  let sexConstant: number;
  let confidence: NutritionEnergyEstimate['confidence'];

  if (input.metabolicEquationSex === 'male') {
    sexConstant = 5;
    confidence = 'medium';
  } else if (input.metabolicEquationSex === 'female') {
    sexConstant = -161;
    confidence = 'medium';
  } else {
    sexConstant = -78;
    confidence = 'low';
    assumptions.push(
      'Parametro metabolico de sexo nao informado: usado o ponto medio da equacao apenas como estimativa inicial.',
    );
  }

  const restingCalories = Math.round(
    10 * weight + 6.25 * height - 5 * age + sexConstant,
  );
  const maintenanceCalories = roundToTen(
    restingCalories * activityMultipliers[activityLevel],
  );

  assumptions.push(
    'Gasto estimado por equacao populacional; o valor real pode variar e deve ser ajustado pela evolucao registrada.',
  );

  return {
    method: 'mifflin_st_jeor',
    confidence,
    restingCalories,
    maintenanceCalories,
    phaseAdjustmentPercent: adjustment,
    targetCalories: applyEnergyAdjustment(maintenanceCalories, adjustment),
  };
}

function applyEnergyAdjustment(calories: number, adjustmentPercent: number) {
  return roundToTen(calories * (1 + adjustmentPercent / 100));
}

function createMacroTargets(
  calories: number,
  weightKg: number | undefined,
  activityLevel: NutritionActivityLevel,
  phase: NutritionPhaseType,
  pattern: NutritionMacroPattern,
  custom: NutritionMacroPercentages | undefined,
  warnings: string[],
): NutritionMacroTargets {
  if (pattern === 'custom') {
    const percentages = custom as NutritionMacroPercentages;
    return targetsFromPercentages(calories, percentages);
  }

  const proteinG = calculateProteinTarget(
    calories,
    weightKg,
    activityLevel,
    phase,
    warnings,
  );
  const proteinCalories = proteinG * 4;
  let carbohydrateG: number;
  let fatG: number;

  if (pattern === 'ketogenic') {
    carbohydrateG = Math.min(50, Math.round((calories * 0.08) / 4));
    fatG = Math.max(
      0,
      Math.round((calories - proteinCalories - carbohydrateG * 4) / 9),
    );
  } else if (pattern === 'low_carb') {
    carbohydrateG = Math.round((calories * 0.3) / 4);
    fatG = Math.max(
      0,
      Math.round((calories - proteinCalories - carbohydrateG * 4) / 9),
    );
  } else {
    const fatPercent = pattern === 'high_carb_performance' ? 20 : 30;
    fatG = Math.round((calories * (fatPercent / 100)) / 9);
    carbohydrateG = Math.max(
      0,
      Math.round((calories - proteinCalories - fatG * 9) / 4),
    );
  }

  const percentages = calculateMacroPercentages(
    calories,
    proteinG,
    carbohydrateG,
    fatG,
  );
  if (
    pattern === 'balanced' &&
    (percentages.carbohydrate < 45 ||
      percentages.carbohydrate > 65 ||
      percentages.fat < 20 ||
      percentages.fat > 35 ||
      percentages.protein < 10 ||
      percentages.protein > 35)
  ) {
    warnings.push(
      'A distribuicao calculada saiu da faixa equilibrada; revise calorias, peso ou proteina.',
    );
  }

  return {
    calories,
    proteinG,
    carbohydrateG,
    fatG,
    fiberG: Math.round((calories / 1000) * 14),
    percentages,
  };
}

function calculateProteinTarget(
  calories: number,
  weightKg: number | undefined,
  activityLevel: NutritionActivityLevel,
  phase: NutritionPhaseType,
  warnings: string[],
) {
  if (!weightKg) {
    warnings.push(
      'Peso nao informado: proteina estimada como 20% das calorias.',
    );
    return Math.round((calories * 0.2) / 4);
  }

  const activityProtein: Record<NutritionActivityLevel, number> = {
    sedentary: 0.8,
    light: 1.2,
    moderate: 1.6,
    very_active: 1.8,
    athlete: 2,
  };
  const phaseMinimum: Record<NutritionPhaseType, number> = {
    mass_gain: 1.6,
    fat_loss: 1.8,
    maintenance: 1.2,
    recomposition: 1.8,
    diet_break: 1.6,
    custom: 1.2,
  };
  const gramsPerKg = Math.min(
    2,
    Math.max(activityProtein[activityLevel], phaseMinimum[phase]),
  );
  const desired = Math.round(weightKg * gramsPerKg);
  const energyCap = Math.floor((calories * 0.35) / 4);

  if (desired > energyCap) {
    warnings.push(
      'Proteina limitada a 35% das calorias; uma meta maior exigiria revisar a energia total.',
    );
  }
  return Math.min(desired, energyCap);
}

function targetsFromPercentages(
  calories: number,
  percentages: NutritionMacroPercentages,
): NutritionMacroTargets {
  return {
    calories,
    proteinG: Math.round((calories * (percentages.protein / 100)) / 4),
    carbohydrateG: Math.round(
      (calories * (percentages.carbohydrate / 100)) / 4,
    ),
    fatG: Math.round((calories * (percentages.fat / 100)) / 9),
    fiberG: Math.round((calories / 1000) * 14),
    percentages: { ...percentages },
  };
}

function calculateMacroPercentages(
  calories: number,
  proteinG: number,
  carbohydrateG: number,
  fatG: number,
): NutritionMacroPercentages {
  return {
    protein: roundOneDecimal((proteinG * 4 * 100) / calories),
    carbohydrate: roundOneDecimal((carbohydrateG * 4 * 100) / calories),
    fat: roundOneDecimal((fatG * 9 * 100) / calories),
  };
}

function createMealTargets(
  targets: NutritionMacroTargets,
  requestedMeals: number | undefined,
  schedule: NutritionMealSchedule,
  requestedWindowHours: number | undefined,
  requestedStartHour: number | undefined,
  assumptions: string[],
  warnings: string[],
): NutritionMealTarget[] {
  const mealCount = requestedMeals ?? (schedule === 'time_restricted' ? 3 : 4);
  if (!requestedMeals) {
    assumptions.push(
      `${mealCount} refeicoes usadas como distribuicao inicial.`,
    );
  }

  const shares = createMealShares(mealCount);
  const calories = splitInteger(targets.calories, shares);
  const protein = splitInteger(targets.proteinG, shares);
  const carbohydrate = splitInteger(targets.carbohydrateG, shares);
  const fat = splitInteger(targets.fatG, shares);
  const times = createMealTimes(
    mealCount,
    schedule,
    requestedWindowHours,
    requestedStartHour,
  );

  if (schedule === 'time_restricted' && (requestedWindowHours ?? 10) < 8) {
    warnings.push(
      'Janelas menores que 8 horas sao mais restritivas e merecem revisao de aderencia e seguranca.',
    );
  }

  return shares.map((share, index) => ({
    position: index,
    name: createMealName(index, mealCount),
    suggestedTime: times[index] ?? null,
    calorieShare: roundOneDecimal(share * 100),
    calories: calories[index],
    proteinG: protein[index],
    carbohydrateG: carbohydrate[index],
    fatG: fat[index],
  }));
}

function createMealShares(count: number) {
  const presets: Record<number, number[]> = {
    1: [1],
    2: [0.45, 0.55],
    3: [0.3, 0.4, 0.3],
    4: [0.25, 0.35, 0.15, 0.25],
    5: [0.2, 0.3, 0.1, 0.15, 0.25],
    6: [0.17, 0.23, 0.1, 0.2, 0.1, 0.2],
    7: [0.14, 0.18, 0.1, 0.18, 0.1, 0.16, 0.14],
    8: [0.12, 0.16, 0.1, 0.15, 0.1, 0.14, 0.1, 0.13],
  };
  return presets[count];
}

function splitInteger(total: number, shares: number[]) {
  const values = shares.map((share) => Math.round(total * share));
  const difference = total - values.reduce((sum, value) => sum + value, 0);
  values[values.length - 1] += difference;
  return values;
}

function createMealTimes(
  count: number,
  schedule: NutritionMealSchedule,
  requestedWindowHours?: number,
  requestedStartHour?: number,
) {
  if (schedule === 'custom') return Array<string | null>(count).fill(null);

  const start = requestedStartHour ?? (schedule === 'time_restricted' ? 10 : 8);
  const windowHours =
    schedule === 'time_restricted' ? (requestedWindowHours ?? 10) : 12;
  if (count === 1) return [formatHour(start + windowHours / 2)];

  return Array.from({ length: count }, (_, index) =>
    formatHour(start + (windowHours * index) / (count - 1)),
  );
}

function formatHour(value: number) {
  const wrapped = ((value % 24) + 24) % 24;
  const hour = Math.floor(wrapped);
  const minutes = Math.round((wrapped - hour) * 60);
  const normalizedHour = minutes === 60 ? (hour + 1) % 24 : hour;
  const normalizedMinutes = minutes === 60 ? 0 : minutes;
  return `${String(normalizedHour).padStart(2, '0')}:${String(normalizedMinutes).padStart(2, '0')}`;
}

function createMealName(index: number, count: number) {
  const presets: Record<number, string[]> = {
    1: ['Refeicao principal'],
    2: ['Primeira refeicao', 'Segunda refeicao'],
    3: ['Primeira refeicao', 'Refeicao principal', 'Ultima refeicao'],
    4: ['Cafe da manha', 'Almoco', 'Lanche', 'Jantar'],
    5: ['Cafe da manha', 'Almoco', 'Lanche 1', 'Lanche 2', 'Jantar'],
    6: ['Cafe da manha', 'Lanche 1', 'Almoco', 'Lanche 2', 'Jantar', 'Ceia'],
  };
  return presets[count]?.[index] ?? `Refeicao ${index + 1}`;
}

function createMealBuildingBlocks(
  pattern: NutritionMacroPattern,
): NutritionMealBuildingBlock[] {
  if (pattern === 'ketogenic') {
    return [
      {
        role: 'protein_source',
        required: true,
        guidance:
          'Fonte proteica compativel com as restricoes e o estilo alimentar.',
      },
      {
        role: 'vegetable_or_fruit',
        required: true,
        guidance:
          'Vegetal com baixo teor de carboidrato e boa densidade nutricional.',
      },
      {
        role: 'fat_source',
        required: true,
        guidance:
          'Fonte de gordura dimensionada para completar a meta da refeicao.',
      },
    ];
  }

  return [
    {
      role: 'protein_source',
      required: true,
      guidance:
        'Fonte principal de proteina compativel com o estilo alimentar.',
    },
    {
      role: 'vegetable_or_fruit',
      required: true,
      guidance: 'Vegetal ou fruta para variedade, fibras e micronutrientes.',
    },
    {
      role: 'carbohydrate_source',
      required: pattern !== 'low_carb',
      guidance: 'Fonte de carboidrato ajustada ao padrao e ao restante do dia.',
    },
    {
      role: 'fat_source',
      required: false,
      guidance: 'Fonte de gordura usada quando necessaria para fechar a meta.',
    },
  ];
}

function normalizeFoodList(values: string[]) {
  return [...new Set(values.map((value) => value.trim().toLowerCase()))]
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right, 'pt-BR'));
}

function roundOneDecimal(value: number) {
  return Math.round(value * 10) / 10;
}

function roundToTen(value: number) {
  return Math.round(value / 10) * 10;
}

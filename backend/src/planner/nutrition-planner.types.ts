export const nutritionPhaseTypes = [
  'mass_gain',
  'fat_loss',
  'maintenance',
  'recomposition',
  'diet_break',
  'custom',
] as const;

export const nutritionMacroPatterns = [
  'balanced',
  'high_carb_performance',
  'low_carb',
  'ketogenic',
  'custom',
] as const;

export const nutritionFoodStyles = [
  'omnivore',
  'pescatarian',
  'vegetarian',
  'vegan',
  'custom',
] as const;

export const nutritionMealSchedules = [
  'regular',
  'time_restricted',
  'custom',
] as const;

export const nutritionActivityLevels = [
  'sedentary',
  'light',
  'moderate',
  'very_active',
  'athlete',
] as const;

export const nutritionHealthFlags = [
  'pregnant_or_breastfeeding',
  'under_18',
  'eating_disorder_history',
  'kidney_disease',
  'glucose_lowering_medication',
  'other_clinical_condition',
] as const;

export type NutritionPhaseType = (typeof nutritionPhaseTypes)[number];
export type NutritionMacroPattern = (typeof nutritionMacroPatterns)[number];
export type NutritionFoodStyle = (typeof nutritionFoodStyles)[number];
export type NutritionMealSchedule = (typeof nutritionMealSchedules)[number];
export type NutritionActivityLevel = (typeof nutritionActivityLevels)[number];
export type NutritionHealthFlag = (typeof nutritionHealthFlags)[number];
export type NutritionMetabolicEquationSex = 'female' | 'male';

export type NutritionMacroPercentages = {
  protein: number;
  carbohydrate: number;
  fat: number;
};

export type NutritionPlannerInput = {
  phase?: NutritionPhaseType;
  currentWeightKg?: number;
  heightCm?: number;
  ageYears?: number;
  metabolicEquationSex?: NutritionMetabolicEquationSex;
  activityLevel?: NutritionActivityLevel;
  estimatedMaintenanceCalories?: number;
  calorieTargetOverride?: number;
  macroPattern?: NutritionMacroPattern;
  customMacroPercentages?: NutritionMacroPercentages;
  mealsPerDay?: number;
  mealSchedule?: NutritionMealSchedule;
  eatingWindowHours?: number;
  eatingWindowStartHour?: number;
  foodStyle?: NutritionFoodStyle;
  preferredFoods?: string[];
  dislikedFoods?: string[];
  foodRestrictions?: string[];
  allergenExclusions?: string[];
  healthFlags?: NutritionHealthFlag[];
};

export type NutritionEnergyEstimate = {
  method:
    | 'calorie_target_override'
    | 'provided_maintenance_estimate'
    | 'mifflin_st_jeor';
  confidence: 'low' | 'medium' | 'high';
  restingCalories: number | null;
  maintenanceCalories: number;
  phaseAdjustmentPercent: number;
  targetCalories: number;
};

export type NutritionMacroTargets = {
  calories: number;
  proteinG: number;
  carbohydrateG: number;
  fatG: number;
  fiberG: number;
  percentages: NutritionMacroPercentages;
};

export type NutritionMealTarget = {
  position: number;
  name: string;
  suggestedTime: string | null;
  calorieShare: number;
  calories: number;
  proteinG: number;
  carbohydrateG: number;
  fatG: number;
};

export type NutritionFoodRole =
  | 'protein_source'
  | 'carbohydrate_source'
  | 'vegetable_or_fruit'
  | 'fat_source'
  | 'optional_extra';

export type NutritionMealBuildingBlock = {
  role: NutritionFoodRole;
  required: boolean;
  guidance: string;
};

export type NutritionExclusionPolicy = {
  hardExclusions: string[];
  preferenceExclusions: string[];
  preferredFoods: string[];
};

export type NutritionPlannerRecommendation = {
  ruleVersion: 'nutrition-planner-rules-v1';
  phase: NutritionPhaseType;
  macroPattern: NutritionMacroPattern;
  foodStyle: NutritionFoodStyle;
  mealSchedule: NutritionMealSchedule;
  energy: NutritionEnergyEstimate;
  targets: NutritionMacroTargets;
  meals: NutritionMealTarget[];
  mealBuildingBlocks: NutritionMealBuildingBlock[];
  exclusions: NutritionExclusionPolicy;
  assumptions: string[];
  warnings: string[];
  reviewRecommended: boolean;
  automaticGenerationAllowed: boolean;
};

export const nutritionFoodProcessingLevels = [
  'in_natura',
  'minimally_processed',
  'processed',
  'ultra_processed',
  'unknown',
] as const;

export const nutritionFoodMealTypes = [
  'breakfast',
  'main',
  'snack',
  'any',
] as const;

export type NutritionFoodProcessingLevel =
  (typeof nutritionFoodProcessingLevels)[number];
export type NutritionFoodMealType = (typeof nutritionFoodMealTypes)[number];

export type NutritionValues = {
  calories: number;
  proteinG: number;
  carbohydrateG: number;
  fatG: number;
  fiberG: number;
};

export type NutritionFoodCandidate = {
  id: string;
  name: string;
  baseAmount: number;
  baseUnit: string;
  nutrition: NutritionValues;
  roles: NutritionFoodRole[];
  compatibleFoodStyles: NutritionFoodStyle[];
  mealTypes?: NutritionFoodMealType[];
  tags?: string[];
  allergens?: string[];
  processingLevel?: NutritionFoodProcessingLevel;
  minimumAmount?: number;
  maximumAmount?: number;
  amountStep?: number;
  defaultAmount?: number;
};

export type NutritionFoodGeneratorRequest = {
  recommendation: NutritionPlannerRecommendation;
  foods: NutritionFoodCandidate[];
  maxSubstitutionsPerItem?: number;
  varietySeed?: number;
};

export type NutritionGeneratedSubstitution = {
  foodId: string;
  name: string;
  role: NutritionFoodRole;
  amount: number;
  unit: string;
  nutrition: NutritionValues;
  similarityScore: number;
};

export type NutritionGeneratedFood = {
  foodId: string;
  name: string;
  role: NutritionFoodRole;
  amount: number;
  unit: string;
  nutrition: NutritionValues;
  substitutions: NutritionGeneratedSubstitution[];
};

export type NutritionTargetDeviation = {
  calories: number;
  protein: number;
  carbohydrate: number;
  fat: number;
};

export type NutritionGeneratedMeal = {
  position: number;
  name: string;
  suggestedTime: string | null;
  target: NutritionMealTarget;
  items: NutritionGeneratedFood[];
  actual: NutritionValues;
  deviationPercent: NutritionTargetDeviation;
  warnings: string[];
};

export type NutritionGeneratedPlan = {
  generatorVersion: 'nutrition-food-generator-v1';
  recommendation: NutritionPlannerRecommendation;
  meals: NutritionGeneratedMeal[];
  actual: NutritionValues;
  deviationPercent: NutritionTargetDeviation;
  warnings: string[];
};

import { Type } from 'class-transformer';
import {
  ArrayMaxSize,
  ArrayUnique,
  IsArray,
  IsBoolean,
  IsIn,
  IsInt,
  IsNumber,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
  ValidateNested,
} from 'class-validator';
import {
  nutritionActivityLevels,
  nutritionFoodStyles,
  nutritionHealthFlags,
  nutritionMacroPatterns,
  nutritionMealSchedules,
  nutritionPhaseTypes,
  type NutritionActivityLevel,
  type NutritionFoodStyle,
  type NutritionHealthFlag,
  type NutritionMacroPattern,
  type NutritionMealSchedule,
  type NutritionMetabolicEquationSex,
  type NutritionPhaseType,
} from '../nutrition-planner.types.js';

const plannerWeekdays = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const;

class CustomMacroPercentagesDto {
  @IsNumber()
  @Min(0)
  @Max(100)
  protein: number;

  @IsNumber()
  @Min(0)
  @Max(100)
  carbohydrate: number;

  @IsNumber()
  @Min(0)
  @Max(100)
  fat: number;
}

export class GenerateNutritionPlanDto {
  @IsOptional()
  @IsString()
  @MaxLength(120)
  name?: string;

  @IsOptional()
  @IsIn(nutritionPhaseTypes)
  phase?: NutritionPhaseType;

  @IsOptional()
  @IsNumber()
  @Min(800)
  @Max(8000)
  calorie_target_override?: number;

  @IsOptional()
  @IsNumber()
  @Min(800)
  @Max(8000)
  estimated_maintenance_calories?: number;

  @IsOptional()
  @IsIn(nutritionActivityLevels)
  activity_level?: NutritionActivityLevel;

  @IsOptional()
  @IsIn(['female', 'male'])
  metabolic_equation_sex?: NutritionMetabolicEquationSex;

  @IsOptional()
  @IsIn(nutritionMacroPatterns)
  macro_pattern?: NutritionMacroPattern;

  @IsOptional()
  @ValidateNested()
  @Type(() => CustomMacroPercentagesDto)
  custom_macro_percentages?: CustomMacroPercentagesDto;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(8)
  meals_per_day?: number;

  @IsOptional()
  @IsBoolean()
  use_training_rest_variants?: boolean;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(8)
  training_day_meals?: number;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(8)
  rest_day_meals?: number;

  @IsOptional()
  @IsBoolean()
  rotate_menus?: boolean;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(7)
  menu_rotation_size?: number;

  @IsOptional()
  @IsIn(['none', 'weekly', 'fortnightly'])
  flexible_meal_frequency?: 'none' | 'weekly' | 'fortnightly';

  @IsOptional()
  @IsIn(plannerWeekdays)
  flexible_meal_weekday?: (typeof plannerWeekdays)[number];

  @IsOptional()
  @IsIn(['none', 'fortnightly', 'monthly'])
  alcohol_frequency?: 'none' | 'fortnightly' | 'monthly';

  @IsOptional()
  @IsIn(plannerWeekdays)
  alcohol_preferred_weekday?: (typeof plannerWeekdays)[number];

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(4)
  alcohol_max_servings?: number;

  @IsOptional()
  @IsIn(nutritionMealSchedules)
  meal_schedule?: NutritionMealSchedule;

  @IsOptional()
  @IsNumber()
  @Min(4)
  @Max(16)
  eating_window_hours?: number;

  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(23.99)
  eating_window_start_hour?: number;

  @IsOptional()
  @IsIn(nutritionFoodStyles)
  food_style?: NutritionFoodStyle;

  @IsOptional()
  @IsArray()
  @ArrayUnique()
  @ArrayMaxSize(50)
  @IsString({ each: true })
  @MaxLength(120, { each: true })
  preferred_foods?: string[];

  @IsOptional()
  @IsArray()
  @ArrayUnique()
  @ArrayMaxSize(50)
  @IsString({ each: true })
  @MaxLength(120, { each: true })
  disliked_foods?: string[];

  @IsOptional()
  @IsArray()
  @ArrayUnique()
  @ArrayMaxSize(50)
  @IsString({ each: true })
  @MaxLength(120, { each: true })
  food_restrictions?: string[];

  @IsOptional()
  @IsArray()
  @ArrayUnique()
  @ArrayMaxSize(30)
  @IsString({ each: true })
  @MaxLength(120, { each: true })
  allergen_exclusions?: string[];

  @IsOptional()
  @IsArray()
  @ArrayUnique()
  @ArrayMaxSize(nutritionHealthFlags.length)
  @IsIn(nutritionHealthFlags, { each: true })
  health_flags?: NutritionHealthFlag[];

  @IsOptional()
  @IsBoolean()
  activate?: boolean;
}

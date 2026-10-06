import {
  IsIn,
  IsInt,
  IsOptional,
  IsString,
  IsUUID,
  Matches,
  Max,
  MaxLength,
  Min,
} from 'class-validator';
import type { Enums } from '../../database/database.types.js';

export const plannerAdjustmentKinds = [
  'move_workout_day',
  'replace_exercise',
  'replace_meal_item',
  'set_day_activity',
] as const;

export type PlannerAdjustmentKind = (typeof plannerAdjustmentKinds)[number];

export class CreatePlannerAdjustmentDto {
  @IsIn(plannerAdjustmentKinds)
  kind: PlannerAdjustmentKind;

  @IsString()
  @MaxLength(500)
  reason: string;

  @IsOptional()
  @IsIn(['manual', 'coach'])
  source?: 'manual' | 'coach';

  @IsOptional()
  @IsUUID()
  workout_plan_id?: string;

  @IsOptional()
  @IsUUID()
  diet_plan_id?: string;

  @IsOptional()
  @IsUUID()
  workout_day_id?: string;

  @IsOptional()
  @IsIn([
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday',
    'saturday',
    'sunday',
  ])
  target_weekday?: Enums<'weekday'>;

  @IsOptional()
  @IsUUID()
  workout_day_exercise_id?: string;

  @IsOptional()
  @IsUUID()
  replacement_exercise_id?: string;

  @IsOptional()
  @IsUUID()
  meal_item_id?: string;

  @IsOptional()
  @IsUUID()
  replacement_food_id?: string;

  @IsOptional()
  @Matches(/^\d{4}-\d{2}-\d{2}$/)
  activity_date?: string;

  @IsOptional()
  @IsIn(['rest', 'resistance', 'cardio', 'mixed'])
  activity_type?: 'rest' | 'resistance' | 'cardio' | 'mixed';

  @IsOptional()
  @IsIn(['light', 'moderate', 'hard'])
  intensity?: 'light' | 'moderate' | 'hard';

  @IsOptional()
  @IsInt()
  @Min(0)
  @Max(360)
  estimated_minutes?: number;

  @IsOptional()
  @IsIn(['training_day', 'rest_day'])
  nutrition_day_type?: 'training_day' | 'rest_day';

  @IsOptional()
  @IsString()
  @MaxLength(500)
  note?: string;
}

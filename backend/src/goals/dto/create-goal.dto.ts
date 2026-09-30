import {
  IsBoolean,
  IsDateString,
  IsIn,
  IsNumber,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
} from 'class-validator';
import type { Enums } from '../../database/database.types.js';

export const goalTypes: Enums<'goal_type'>[] = [
  'hypertrophy',
  'fat_loss',
  'strength',
  'health',
  'recomposition',
  'maintenance',
];

export class CreateGoalDto {
  @IsIn(goalTypes)
  type: Enums<'goal_type'>;

  @IsString()
  @MaxLength(120)
  title: string;

  @IsOptional()
  @IsString()
  @MaxLength(1000)
  description?: string;

  @IsOptional()
  @IsNumber({ maxDecimalPlaces: 2 })
  @Min(25)
  @Max(350)
  target_weight_kg?: number;

  @IsOptional()
  @IsDateString()
  target_date?: string;

  @IsOptional()
  @IsBoolean()
  is_active?: boolean;
}

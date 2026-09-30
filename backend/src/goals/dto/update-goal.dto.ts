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
import { goalTypes } from './create-goal.dto.js';

export class UpdateGoalDto {
  @IsOptional()
  @IsIn(goalTypes)
  type?: Enums<'goal_type'>;

  @IsOptional()
  @IsString()
  @MaxLength(120)
  title?: string;

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

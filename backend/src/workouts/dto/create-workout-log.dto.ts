import {
  IsDateString,
  IsOptional,
  IsString,
  IsUUID,
  MaxLength,
} from 'class-validator';

export class CreateWorkoutLogDto {
  @IsOptional()
  @IsUUID()
  workout_day_id?: string;

  @IsOptional()
  @IsDateString()
  performed_at?: string;

  @IsOptional()
  @IsString()
  @MaxLength(1000)
  notes?: string;
}

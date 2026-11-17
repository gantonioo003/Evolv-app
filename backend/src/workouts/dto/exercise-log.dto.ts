import {
  IsDateString,
  IsInt,
  IsNumber,
  IsOptional,
  IsString,
  IsUUID,
  Max,
  MaxLength,
  Min,
} from 'class-validator';

class ExerciseMeasurementsDto {
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(1000)
  repetitions?: number;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(86400)
  duration_seconds?: number;
}

export class CreateExerciseLogDto extends ExerciseMeasurementsDto {
  @IsOptional()
  @IsUUID()
  workout_log_id?: string;

  @IsOptional()
  @IsDateString()
  performed_at?: string;

  @IsOptional()
  @IsInt()
  @Min(0)
  @Max(30)
  sets_completed?: number;

  @IsOptional()
  @IsString()
  @MaxLength(300)
  reps_summary?: string;

  @IsOptional()
  @IsNumber({ maxDecimalPlaces: 2 })
  @Min(0)
  @Max(2000)
  load_kg?: number;

  @IsOptional()
  @IsString()
  @MaxLength(1000)
  notes?: string;
}

export class UpdateExerciseLogDto extends ExerciseMeasurementsDto {
  @IsOptional()
  @IsDateString()
  performed_at?: string;

  @IsOptional()
  @IsInt()
  @Min(0)
  @Max(30)
  sets_completed?: number;

  @IsOptional()
  @IsString()
  @MaxLength(300)
  reps_summary?: string;

  @IsOptional()
  @IsNumber({ maxDecimalPlaces: 2 })
  @Min(0)
  @Max(2000)
  load_kg?: number;

  @IsOptional()
  @IsString()
  @MaxLength(1000)
  notes?: string;
}

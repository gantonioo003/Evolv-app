import {
  IsDateString,
  IsNumber,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
} from 'class-validator';

export class CreateProgressEntryDto {
  @IsOptional()
  @IsDateString()
  measured_at?: string;

  @IsOptional()
  @IsNumber({ maxDecimalPlaces: 2 })
  @Min(25)
  @Max(350)
  weight_kg?: number;

  @IsOptional()
  @IsNumber({ maxDecimalPlaces: 2 })
  @Min(30)
  @Max(250)
  waist_cm?: number;

  @IsOptional()
  @IsNumber({ maxDecimalPlaces: 2 })
  @Min(30)
  @Max(250)
  chest_cm?: number;

  @IsOptional()
  @IsNumber({ maxDecimalPlaces: 2 })
  @Min(10)
  @Max(100)
  arm_cm?: number;

  @IsOptional()
  @IsNumber({ maxDecimalPlaces: 2 })
  @Min(20)
  @Max(150)
  leg_cm?: number;

  @IsOptional()
  @IsString()
  @MaxLength(1000)
  notes?: string;
}

export class UpdateProgressEntryDto extends CreateProgressEntryDto {}

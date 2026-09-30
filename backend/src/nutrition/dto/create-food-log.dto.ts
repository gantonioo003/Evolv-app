import { IsDateString, IsOptional, IsString, MaxLength } from 'class-validator';

export class CreateFoodLogDto {
  @IsOptional()
  @IsDateString()
  logged_at?: string;

  @IsOptional()
  @IsString()
  @MaxLength(500)
  description?: string;

  @IsOptional()
  @IsString()
  @MaxLength(80)
  meal_name?: string;

  @IsOptional()
  @IsString()
  @MaxLength(1000)
  notes?: string;
}

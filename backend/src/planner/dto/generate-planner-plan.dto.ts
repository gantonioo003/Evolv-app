import {
  ArrayMaxSize,
  ArrayUnique,
  IsArray,
  IsBoolean,
  IsDateString,
  IsIn,
  IsInt,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
} from 'class-validator';
import {
  plannerGoals,
  plannerLevels,
  plannerModalities,
  type PlannerGoal,
  type PlannerLevel,
  type PlannerModality,
  type PlannerWeekday,
} from '../planner.types.js';

const weekdays: PlannerWeekday[] = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
];

export class GeneratePlannerPlanDto {
  @IsOptional()
  @IsString()
  @MaxLength(120)
  name?: string;

  @IsOptional()
  @IsIn(plannerGoals)
  goal?: PlannerGoal;

  @IsOptional()
  @IsIn(plannerLevels)
  level?: PlannerLevel;

  @IsOptional()
  @IsArray()
  @ArrayUnique()
  @ArrayMaxSize(7)
  @IsIn(weekdays, { each: true })
  available_days?: PlannerWeekday[];

  @IsOptional()
  @IsInt()
  @Min(20)
  @Max(180)
  session_minutes?: number;

  @IsOptional()
  @IsArray()
  @ArrayUnique()
  @ArrayMaxSize(plannerModalities.length)
  @IsIn(plannerModalities, { each: true })
  modalities?: PlannerModality[];

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(6)
  desired_weekly_frequency?: number;

  @IsOptional()
  @IsDateString()
  start_date?: string;

  @IsOptional()
  @IsBoolean()
  activate?: boolean;
}

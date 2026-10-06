import { Type } from 'class-transformer';
import { IsIn, IsInt, IsOptional, Max, Min } from 'class-validator';
import type { Enums } from '../../database/database.types.js';

export class ListPlannerPlansQueryDto {
  @IsOptional()
  @IsIn(['draft', 'active', 'archived'])
  status?: Enums<'plan_status'>;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit = 30;
}

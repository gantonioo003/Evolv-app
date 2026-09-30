import { IsIn, IsOptional } from 'class-validator';
import { PaginationQueryDto } from '../../common/dto/pagination-query.dto.js';

const statuses = ['pending', 'accepted', 'dismissed', 'all'] as const;
export type ProgressionStatus = (typeof statuses)[number];

export class ProgressionQueryDto extends PaginationQueryDto {
  @IsOptional()
  @IsIn(statuses)
  status: ProgressionStatus = 'pending';
}

export class UpdateProgressionSuggestionDto {
  @IsIn(['accept', 'dismiss'])
  action: 'accept' | 'dismiss';
}

import {
  Equals,
  IsBoolean,
  IsOptional,
  IsString,
  IsUUID,
  MaxLength,
  MinLength,
  Matches,
} from 'class-validator';
import { Type } from 'class-transformer';
import { IsInt, Min, Max } from 'class-validator';
export class CreateCoachSessionDto {
  @IsOptional() @IsUUID() workout_plan_id?: string;
  @IsOptional() @IsUUID() diet_plan_id?: string;
}
export class CoachMessageDto {
  @IsUUID() request_id: string;
  @IsString() @MinLength(1) @MaxLength(8000) @Matches(/\S/) text: string;
  @IsOptional() @IsUUID() proposal_id?: string;
}
export class ConfirmCoachAdjustmentDto {
  @IsBoolean() @Equals(true) confirmed: boolean;
}
export class CoachHistoryQueryDto {
  @IsOptional() @Type(() => Number) @IsInt() @Min(1) @Max(100) limit = 30;
  @IsOptional() @Type(() => Number) @IsInt() @Min(0) @Max(100000) offset = 0;
}
export class RenameCoachConversationDto {
  @IsString() @MinLength(1) @MaxLength(80) @Matches(/\S/) title: string;
}

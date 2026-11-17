import { IsBoolean, IsDateString, Matches } from 'class-validator';

export class SetPlannedMealRegistrationDto {
  @IsDateString({ strict: true })
  @Matches(/^\d{4}-\d{2}-\d{2}$/)
  local_date: string;

  @IsDateString({ strict: true })
  logged_at: string;

  @IsBoolean()
  registered: boolean;
}

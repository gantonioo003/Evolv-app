import { BadRequestException, Injectable } from '@nestjs/common';
import { throwDatabaseError } from '../common/errors/database.error.js';
import { SupabaseService } from '../supabase/supabase.service.js';

export type PlannerDayContext = {
  activity_date: string;
  activity_type: 'rest' | 'resistance' | 'cardio' | 'mixed';
  intensity: 'light' | 'moderate' | 'hard' | null;
  estimated_minutes: number | null;
  nutrition_day_type: 'training_day' | 'rest_day';
  source: 'override' | 'workout_plan' | 'profile' | 'default';
  workout_day_id: string | null;
  title: string;
  note: string | null;
};

export function weekDates(date: string): string[] {
  const start = new Date(date + 'T00:00:00Z');
  if (!Number.isFinite(start.getTime()) || start.toISOString().slice(0, 10) !== date)
    throw new BadRequestException('Data inválida.');
  start.setUTCDate(start.getUTCDate() - (start.getUTCDay() + 6) % 7);
  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(start);
    day.setUTCDate(day.getUTCDate() + index);
    return day.toISOString().slice(0, 10);
  });
}

export async function weekOverrides(supabase: SupabaseService, token: string, user: string, dates: string[]) {
  const { data, error } = await supabase.forUser(token).from('daily_activity_overrides')
    .select('activity_date, activity_type, workout_day_id')
    .eq('user_id', user)
    .in('activity_date', dates);
  if (error) throwDatabaseError('weekOverrides', error, 'Não foi possível carregar o calendário da semana.');
  return data ?? [];
}

@Injectable()
export class PlannerDayContextService {
  constructor(private readonly supabase: SupabaseService) {}

  async overrides(user: string, token: string, date: string) {
    const dates = weekDates(date);
    return { dates, overrides: await weekOverrides(this.supabase, token, user, dates) };
  }

  async get(accessToken: string, date: string) {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .rpc('get_daily_activity_context', { p_activity_date: date });

    if (error) {
      throwDatabaseError(
        'PlannerDayContextService.get',
        error,
        'Nao foi possivel decidir o contexto deste dia.',
      );
    }
    return data as PlannerDayContext;
  }
}

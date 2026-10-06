import { Injectable } from '@nestjs/common';
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

@Injectable()
export class PlannerDayContextService {
  constructor(private readonly supabase: SupabaseService) {}

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

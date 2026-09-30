import { Injectable, NotFoundException } from '@nestjs/common';
import type {
  Tables,
  TablesInsert,
  TablesUpdate,
} from '../database/database.types.js';
import { throwDatabaseError } from '../common/errors/database.error.js';
import { SupabaseService } from '../supabase/supabase.service.js';
import type {
  CreateExerciseLogDto,
  UpdateExerciseLogDto,
} from './dto/exercise-log.dto.js';
import type { ExerciseCatalogQueryDto } from './dto/exercise-catalog-query.dto.js';
import type { CreateWorkoutLogDto } from './dto/create-workout-log.dto.js';
import type {
  ProgressionQueryDto,
  UpdateProgressionSuggestionDto,
} from './dto/progression-query.dto.js';

type WorkoutLog = Tables<'workout_logs'>;
type ExerciseLog = Tables<'exercise_logs'>;
type ProgressionSuggestion = Tables<'exercise_progression_suggestions'>;

@Injectable()
export class WorkoutsService {
  constructor(private readonly supabase: SupabaseService) {}

  async getActivePlan(userId: string, accessToken: string) {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('workout_plans')
      .select(
        `
        *,
        goals (*),
        workout_days (
          *,
          workout_day_exercises (
            *,
            exercises (*)
          )
        )
      `,
      )
      .eq('user_id', userId)
      .eq('status', 'active')
      .order('updated_at', { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'WorkoutsService.getActivePlan',
        error,
        'Nao foi possivel buscar o plano de treino.',
      );
    }
    if (!data) return null;

    data.workout_days.sort((a, b) => a.position - b.position);
    for (const day of data.workout_days) {
      day.workout_day_exercises.sort((a, b) => a.position - b.position);
    }
    return data;
  }

  async listExercises(accessToken: string, queryDto: ExerciseCatalogQueryDto) {
    let query = this.supabase
      .forUser(accessToken)
      .from('exercises')
      .select(
        'id, name, aliases, muscle_group, equipment, movement_pattern, difficulty, is_compound, instructions',
      )
      .order('name', { ascending: true })
      .limit(queryDto.limit);

    if (queryDto.search) query = query.ilike('name', `%${queryDto.search}%`);
    if (queryDto.muscle_group)
      query = query.eq('muscle_group', queryDto.muscle_group);
    if (queryDto.equipment) query = query.eq('equipment', queryDto.equipment);
    if (queryDto.difficulty)
      query = query.eq('difficulty', queryDto.difficulty);

    const { data, error } = await query;
    if (error) {
      throwDatabaseError(
        'WorkoutsService.listExercises',
        error,
        'Nao foi possivel buscar os exercicios.',
      );
    }
    return data;
  }

  async listWorkoutLogs(userId: string, accessToken: string, limit: number) {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('workout_logs')
      .select('*, workout_days (id, title, focus, weekday)')
      .eq('user_id', userId)
      .order('performed_at', { ascending: false })
      .limit(limit);

    if (error) {
      throwDatabaseError(
        'WorkoutsService.listWorkoutLogs',
        error,
        'Nao foi possivel buscar os treinos registrados.',
      );
    }
    return data;
  }

  async createWorkoutLog(
    userId: string,
    accessToken: string,
    dto: CreateWorkoutLogDto,
  ): Promise<WorkoutLog> {
    const input: TablesInsert<'workout_logs'> = {
      user_id: userId,
      workout_day_id: dto.workout_day_id,
      performed_at: dto.performed_at,
      notes: dto.notes,
    };
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('workout_logs')
      .insert(input)
      .select('*')
      .single();

    if (error) {
      throwDatabaseError(
        'WorkoutsService.createWorkoutLog',
        error,
        'Nao foi possivel registrar o treino.',
      );
    }
    return data;
  }

  async getExerciseHistory(
    userId: string,
    accessToken: string,
    exerciseId: string,
    limit: number,
  ) {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('exercise_logs')
      .select('*, exercises (id, name, muscle_group, equipment)')
      .eq('user_id', userId)
      .eq('exercise_id', exerciseId)
      .order('performed_at', { ascending: false })
      .limit(limit);

    if (error) {
      throwDatabaseError(
        'WorkoutsService.getExerciseHistory',
        error,
        'Nao foi possivel buscar o historico de carga.',
      );
    }
    return data;
  }

  async createExerciseLog(
    userId: string,
    accessToken: string,
    exerciseId: string,
    dto: CreateExerciseLogDto,
  ): Promise<ExerciseLog> {
    const input: TablesInsert<'exercise_logs'> = {
      exercise_id: exerciseId,
      user_id: userId,
      workout_log_id: dto.workout_log_id,
      performed_at: dto.performed_at,
      sets_completed: dto.sets_completed,
      reps_summary: dto.reps_summary,
      load_kg: dto.load_kg,
      notes: dto.notes,
    };
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('exercise_logs')
      .insert(input)
      .select('*')
      .single();

    if (error) {
      throwDatabaseError(
        'WorkoutsService.createExerciseLog',
        error,
        'Nao foi possivel registrar a carga.',
      );
    }
    return data;
  }

  async updateExerciseLog(
    userId: string,
    accessToken: string,
    logId: string,
    dto: UpdateExerciseLogDto,
  ): Promise<ExerciseLog> {
    const changes: TablesUpdate<'exercise_logs'> = dto;
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('exercise_logs')
      .update(changes)
      .eq('id', logId)
      .eq('user_id', userId)
      .select('*')
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'WorkoutsService.updateExerciseLog',
        error,
        'Nao foi possivel atualizar a carga.',
      );
    }
    if (!data) {
      throw new NotFoundException({
        code: 'EXERCISE_LOG_NOT_FOUND',
        message: 'Registro de carga nao encontrado.',
      });
    }
    return data;
  }

  async listProgressionSuggestions(
    userId: string,
    accessToken: string,
    queryDto: ProgressionQueryDto,
  ) {
    let query = this.supabase
      .forUser(accessToken)
      .from('exercise_progression_suggestions')
      .select('*, exercises (id, name, muscle_group, equipment)')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })
      .limit(queryDto.limit);

    if (queryDto.status === 'pending') {
      query = query.is('accepted_at', null).is('dismissed_at', null);
    } else if (queryDto.status === 'accepted') {
      query = query.not('accepted_at', 'is', null);
    } else if (queryDto.status === 'dismissed') {
      query = query.not('dismissed_at', 'is', null);
    }

    const { data, error } = await query;
    if (error) {
      throwDatabaseError(
        'WorkoutsService.listProgressionSuggestions',
        error,
        'Nao foi possivel buscar as sugestoes.',
      );
    }
    return data;
  }

  async updateProgressionSuggestion(
    userId: string,
    accessToken: string,
    suggestionId: string,
    dto: UpdateProgressionSuggestionDto,
  ): Promise<ProgressionSuggestion> {
    const now = new Date().toISOString();
    const changes: TablesUpdate<'exercise_progression_suggestions'> =
      dto.action === 'accept'
        ? { accepted_at: now, dismissed_at: null }
        : { accepted_at: null, dismissed_at: now };
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('exercise_progression_suggestions')
      .update(changes)
      .eq('id', suggestionId)
      .eq('user_id', userId)
      .select('*')
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'WorkoutsService.updateProgressionSuggestion',
        error,
        'Nao foi possivel atualizar a sugestao.',
      );
    }
    if (!data) {
      throw new NotFoundException({
        code: 'SUGGESTION_NOT_FOUND',
        message: 'Sugestao nao encontrada.',
      });
    }
    return data;
  }
}

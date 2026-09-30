import { Injectable, NotFoundException } from '@nestjs/common';
import type {
  Tables,
  TablesInsert,
  TablesUpdate,
} from '../database/database.types.js';
import { throwDatabaseError } from '../common/errors/database.error.js';
import { SupabaseService } from '../supabase/supabase.service.js';
import type { CreateGoalDto } from './dto/create-goal.dto.js';
import type { UpdateGoalDto } from './dto/update-goal.dto.js';

type Goal = Tables<'goals'>;

@Injectable()
export class GoalsService {
  constructor(private readonly supabase: SupabaseService) {}

  async list(userId: string, accessToken: string): Promise<Goal[]> {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('goals')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false });

    if (error) {
      throwDatabaseError(
        'GoalsService.list',
        error,
        'Nao foi possivel buscar os objetivos.',
      );
    }
    return data;
  }

  async getActive(userId: string, accessToken: string): Promise<Goal | null> {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('goals')
      .select('*')
      .eq('user_id', userId)
      .eq('is_active', true)
      .order('updated_at', { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'GoalsService.getActive',
        error,
        'Nao foi possivel buscar o objetivo atual.',
      );
    }
    return data;
  }

  async create(
    userId: string,
    accessToken: string,
    dto: CreateGoalDto,
  ): Promise<Goal> {
    const input: TablesInsert<'goals'> = {
      user_id: userId,
      type: dto.type,
      title: dto.title,
      description: dto.description,
      target_weight_kg: dto.target_weight_kg,
      target_date: dto.target_date,
      is_active: dto.is_active,
    };
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('goals')
      .insert(input)
      .select('*')
      .single();

    if (error) {
      throwDatabaseError(
        'GoalsService.create',
        error,
        'Nao foi possivel criar o objetivo.',
      );
    }
    return data;
  }

  async update(
    userId: string,
    accessToken: string,
    goalId: string,
    dto: UpdateGoalDto,
  ): Promise<Goal> {
    const changes: TablesUpdate<'goals'> = dto;
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('goals')
      .update(changes)
      .eq('id', goalId)
      .eq('user_id', userId)
      .select('*')
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'GoalsService.update',
        error,
        'Nao foi possivel atualizar o objetivo.',
      );
    }
    if (!data) {
      throw new NotFoundException({
        code: 'GOAL_NOT_FOUND',
        message: 'Objetivo nao encontrado.',
      });
    }
    return data;
  }
}

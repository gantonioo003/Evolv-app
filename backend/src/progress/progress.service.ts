import { Injectable, NotFoundException } from '@nestjs/common';
import type {
  Tables,
  TablesInsert,
  TablesUpdate,
} from '../database/database.types.js';
import { throwDatabaseError } from '../common/errors/database.error.js';
import { SupabaseService } from '../supabase/supabase.service.js';
import type {
  CreateProgressEntryDto,
  UpdateProgressEntryDto,
} from './dto/progress-entry.dto.js';

type ProgressEntry = Tables<'progress_entries'>;

@Injectable()
export class ProgressService {
  constructor(private readonly supabase: SupabaseService) {}

  async list(
    userId: string,
    accessToken: string,
    limit: number,
  ): Promise<ProgressEntry[]> {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('progress_entries')
      .select('*')
      .eq('user_id', userId)
      .order('measured_at', { ascending: false })
      .limit(limit);

    if (error) {
      throwDatabaseError(
        'ProgressService.list',
        error,
        'Nao foi possivel buscar o progresso.',
      );
    }
    return data;
  }

  async create(
    userId: string,
    accessToken: string,
    dto: CreateProgressEntryDto,
  ): Promise<ProgressEntry> {
    const input: TablesInsert<'progress_entries'> = {
      user_id: userId,
      measured_at: dto.measured_at,
      weight_kg: dto.weight_kg,
      waist_cm: dto.waist_cm,
      chest_cm: dto.chest_cm,
      arm_cm: dto.arm_cm,
      leg_cm: dto.leg_cm,
      notes: dto.notes,
    };
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('progress_entries')
      .insert(input)
      .select('*')
      .single();

    if (error) {
      throwDatabaseError(
        'ProgressService.create',
        error,
        'Nao foi possivel registrar o progresso.',
      );
    }
    return data;
  }

  async update(
    userId: string,
    accessToken: string,
    entryId: string,
    dto: UpdateProgressEntryDto,
  ): Promise<ProgressEntry> {
    const changes: TablesUpdate<'progress_entries'> = dto;
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('progress_entries')
      .update(changes)
      .eq('id', entryId)
      .eq('user_id', userId)
      .select('*')
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'ProgressService.update',
        error,
        'Nao foi possivel atualizar o progresso.',
      );
    }
    if (!data) {
      throw new NotFoundException({
        code: 'PROGRESS_NOT_FOUND',
        message: 'Registro de progresso nao encontrado.',
      });
    }
    return data;
  }

  async remove(
    userId: string,
    accessToken: string,
    entryId: string,
  ): Promise<{ id: string }> {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('progress_entries')
      .delete()
      .eq('id', entryId)
      .eq('user_id', userId)
      .select('id')
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'ProgressService.remove',
        error,
        'Nao foi possivel remover o progresso.',
      );
    }
    if (!data) {
      throw new NotFoundException({
        code: 'PROGRESS_NOT_FOUND',
        message: 'Registro de progresso nao encontrado.',
      });
    }
    return data;
  }
}

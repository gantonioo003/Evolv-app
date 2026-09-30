import { Injectable, InternalServerErrorException } from '@nestjs/common';
import type {
  Tables,
  TablesInsert,
  TablesUpdate,
} from '../database/database.types.js';
import { SupabaseService } from '../supabase/supabase.service.js';
import type { UpdateProfileDto } from './dto/update-profile.dto.js';

type Profile = Tables<'profiles'>;

@Injectable()
export class ProfilesService {
  constructor(private readonly supabase: SupabaseService) {}

  async getMine(userId: string, accessToken: string): Promise<Profile> {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('profiles')
      .select('*')
      .eq('id', userId)
      .maybeSingle();

    if (error) this.throwDatabaseError();
    if (!data) return this.upsertProfile(userId, accessToken);

    return data;
  }

  async updateMine(
    userId: string,
    accessToken: string,
    dto: UpdateProfileDto,
  ): Promise<Profile> {
    const changes: TablesUpdate<'profiles'> = dto;
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('profiles')
      .update(changes)
      .eq('id', userId)
      .select('*')
      .maybeSingle();

    if (error) this.throwDatabaseError();
    if (!data) return this.upsertProfile(userId, accessToken, changes);

    return data;
  }

  private throwDatabaseError(): never {
    throw new InternalServerErrorException({
      code: 'DATABASE_ERROR',
      message: 'Nao foi possivel acessar o perfil agora.',
    });
  }

  private async upsertProfile(
    userId: string,
    accessToken: string,
    changes: TablesUpdate<'profiles'> = {},
  ): Promise<Profile> {
    const input: TablesInsert<'profiles'> = { id: userId, ...changes };
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('profiles')
      .upsert(input, { onConflict: 'id' })
      .select('*')
      .single();

    if (error) this.throwDatabaseError();
    return data;
  }
}

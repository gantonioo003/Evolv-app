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

  async getMine(
    userId: string,
    accessToken: string,
    signupMetadata: Record<string, unknown> = {},
  ): Promise<Profile> {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('profiles')
      .select('*')
      .eq('id', userId)
      .maybeSingle();

    if (error) this.throwDatabaseError();
    const signupProfile = profileFromSignup(signupMetadata);
    if (!data) return this.upsertProfile(userId, accessToken, signupProfile);

    // Email confirmation may happen long after signup; metadata survives it.
    if (
      data.onboarding_status === 'not_started' &&
      data.birth_date === null &&
      signupProfile.birth_date
    ) {
      const { data: hydrated, error: hydrationError } = await this.supabase
        .forUser(accessToken)
        .from('profiles')
        .update({ birth_date: signupProfile.birth_date })
        .eq('id', userId)
        .is('birth_date', null)
        .eq('onboarding_status', 'not_started')
        .select('*')
        .maybeSingle();
      if (hydrationError) this.throwDatabaseError();
      return hydrated ?? data;
    }

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

function profileFromSignup(
  metadata: Record<string, unknown>,
): TablesUpdate<'profiles'> {
  const profile: TablesUpdate<'profiles'> = {};
  if (typeof metadata.full_name === 'string') {
    const name = metadata.full_name.trim();
    if (name.length >= 2 && name.length <= 120) profile.full_name = name;
  }
  if (
    typeof metadata.birth_date === 'string' &&
    /^\d{4}-\d{2}-\d{2}$/.test(metadata.birth_date)
  ) {
    const date = new Date(`${metadata.birth_date}T00:00:00Z`);
    if (
      !Number.isNaN(date.getTime()) &&
      date.toISOString().slice(0, 10) === metadata.birth_date &&
      metadata.birth_date >= '1900-01-01' &&
      metadata.birth_date <= new Date().toISOString().slice(0, 10)
    )
      profile.birth_date = metadata.birth_date;
  }
  return profile;
}

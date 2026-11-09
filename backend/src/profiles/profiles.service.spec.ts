import { describe, expect, it, vi } from 'vitest';
import { ProfilesService } from './profiles.service.js';
import type { SupabaseService } from '../supabase/supabase.service.js';

function setup(profile: Record<string, unknown> | null) {
  const query = {
    select: vi.fn().mockReturnThis(),
    eq: vi.fn().mockReturnThis(),
    is: vi.fn().mockReturnThis(),
    update: vi.fn().mockReturnThis(),
    upsert: vi.fn().mockReturnThis(),
    maybeSingle: vi.fn().mockResolvedValue({ data: profile, error: null }),
    single: vi.fn().mockResolvedValue({ data: { id: 'user-1' }, error: null }),
  };
  const supabase = {
    forUser: vi.fn().mockReturnValue({ from: vi.fn().mockReturnValue(query) }),
  };
  return {
    query,
    service: new ProfilesService(supabase as unknown as SupabaseService),
  };
}

describe('signup profile data', () => {
  it('seeds a missing profile using validated signup metadata', async () => {
    const { service, query } = setup(null);
    await service.getMine('user-1', 'token', {
      full_name: ' Ana ',
      birth_date: '2000-02-29',
    });
    expect(query.upsert).toHaveBeenCalledWith(
      { id: 'user-1', full_name: 'Ana', birth_date: '2000-02-29' },
      { onConflict: 'id' },
    );
  });

  it('fills an empty birthday after email confirmation, scoped to a new profile', async () => {
    const original = {
      id: 'user-1',
      full_name: 'Ana',
      birth_date: null,
      onboarding_status: 'not_started',
    };
    const { service, query } = setup(original);
    query.maybeSingle
      .mockResolvedValueOnce({ data: original, error: null })
      .mockResolvedValueOnce({
        data: { ...original, birth_date: '2000-02-29' },
        error: null,
      });
    const result = await service.getMine('user-1', 'token', {
      birth_date: '2000-02-29',
    });
    expect(result.birth_date).toBe('2000-02-29');
    expect(query.update).toHaveBeenCalledWith({ birth_date: '2000-02-29' });
    expect(query.is).toHaveBeenCalledWith('birth_date', null);
    expect(query.eq).toHaveBeenCalledWith('onboarding_status', 'not_started');
  });

  it.each(['completed', 'skipped', 'in_progress'])(
    'does not change an existing %s profile',
    async (status) => {
      const { service, query } = setup({
        id: 'user-1',
        birth_date: null,
        onboarding_status: status,
      });
      await service.getMine('user-1', 'token', { birth_date: '2000-02-29' });
      expect(query.update).not.toHaveBeenCalled();
    },
  );

  it('does not overwrite a birthday edited by the user', async () => {
    const { service, query } = setup({
      birth_date: '1999-01-01',
      onboarding_status: 'not_started',
    });
    await service.getMine('user-1', 'token', { birth_date: '2000-02-29' });
    expect(query.update).not.toHaveBeenCalled();
  });

  it.each([
    '2001-02-29',
    '2000-04-31',
    '2999-01-01',
    '1899-01-01',
    'tomorrow',
    123,
  ])('ignores invalid signup birthdays: %s', async (birthDate) => {
    const { service, query } = setup(null);
    await service.getMine('user-1', 'token', {
      full_name: {},
      birth_date: birthDate,
    });
    expect(query.upsert).toHaveBeenCalledWith(
      { id: 'user-1' },
      { onConflict: 'id' },
    );
  });
});

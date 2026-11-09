import { randomUUID } from 'node:crypto';
import type { SupabaseService } from '../supabase/supabase.service.js';
import {
  CoachHistoryService,
  messageId,
  minimizeHistoryText,
} from './coach-history.service.js';
import { coachDatabase } from '../../test/fixtures/coach-postgres.js';

describe('Coach history on PostgreSQL with original RLS policies', () => {
  let fixture: Awaited<ReturnType<typeof coachDatabase>>;
  let service: CoachHistoryService;
  const a = randomUUID(),
    b = randomUUID();
  beforeAll(async () => {
    fixture = await coachDatabase();
    await fixture.user(a);
    await fixture.user(b);
    service = new CoachHistoryService(
      fixture.supabase as unknown as SupabaseService,
    );
  }, 30000);
  afterAll(async () => fixture?.db.close());
  it('persiste configuracao, lista e renomeia sem runtime de IA', async () => {
    const c = await service.create(a, a, { workout_plan_id: randomUUID() });
    expect(
      (await service.get(a, a, c.id)).selected.workout_plan_id,
    ).toBeDefined();
    expect((await service.list(a, a)).some((r) => r.id === c.id)).toBe(true);
    expect((await service.rename(a, a, c.id, 'Meu treino'))?.title).toBe(
      'Meu treino',
    );
    expect(await service.list(b, b)).toEqual([]);
    await expect(service.get(b, b, c.id)).rejects.toMatchObject({
      status: 404,
    });
  });
  it('grava par atomicamente e repete sem duplicar', async () => {
    const c = await service.create(a, a, {}),
      request = randomUUID();
    const response = {
      session_id: c.id,
      result: { answer: 'Resposta', actions: [] },
    };
    const first = await service.commit(
      a,
      a,
      c.id,
      request,
      'hash',
      'Email pessoa@example.com',
      response,
    );
    const second = await service.commit(
      a,
      a,
      c.id,
      request,
      'hash',
      'Email pessoa@example.com',
      response,
    );
    expect(second).toEqual(first);
    expect(await service.messages(a, a, c.id)).toHaveLength(2);
    expect((await service.recent(a, a, c.id))[0]?.content).not.toContain(
      'pessoa@example.com',
    );
    await expect(
      service.cached(a, a, c.id, request, 'other'),
    ).rejects.toMatchObject({ status: 409 });
  });
  it('RLS bloqueia acesso direto e trigger impede referencia a conversa alheia', async () => {
    const c = await service.create(a, a, {});
    const foreign = fixture.supabase.forUser(b);
    const rows = await foreign
      .from('coach_conversations')
      .select('*')
      .eq('id', c.id);
    expect((rows as { data: unknown[] }).data).toEqual([]);
    const inserted = (await foreign
      .from('coach_messages')
      .insert({
        id: randomUUID(),
        conversation_id: c.id,
        user_id: b,
        role: 'user',
        content: 'not allowed',
        metadata: {},
      })) as { error: unknown };
    expect(inserted.error).toBeTruthy();
  });
  it('restaura quatro pares e exclusao remove mensagens em cascata', async () => {
    const c = await service.create(a, a, {});
    for (let i = 0; i < 5; i++)
      await service.commit(a, a, c.id, randomUUID(), 'h' + i, 'user' + i, {
        result: { answer: 'answer' + i },
      });
    const history = await service.recent(a, a, c.id);
    expect(history).toHaveLength(8);
    expect(history.map((r) => r.role)).toEqual([
      'user',
      'assistant',
      'user',
      'assistant',
      'user',
      'assistant',
      'user',
      'assistant',
    ]);
    await service.remove(a, a, c.id);
    expect(
      (
        await fixture.db.query(
          'select * from coach_messages where conversation_id=$1',
          [c.id],
        )
      ).rows,
    ).toEqual([]);
    await expect(service.get(a, a, c.id)).rejects.toMatchObject({
      status: 404,
    });
  });
  it('ids deterministas isolam conversa, usuario e papel', () => {
    const request = randomUUID(),
      c = randomUUID();
    expect(messageId(a, c, request, 'user')).toBe(
      messageId(a, c, request, 'user'),
    );
    expect(messageId(a, c, request, 'user')).not.toBe(
      messageId(a, c, request, 'assistant'),
    );
    expect(messageId(a, c, request, 'user')).not.toBe(
      messageId(b, c, request, 'user'),
    );
    expect(minimizeHistoryText('email foo@example.com')).not.toContain(
      'foo@example.com',
    );
  });
});

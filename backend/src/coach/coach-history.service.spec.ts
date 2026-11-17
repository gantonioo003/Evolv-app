import { randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
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
  const legacy = randomUUID(), legacyCustom = randomUUID();
  const legacyStamp = '2026-11-01T12:00:00.000Z';
  beforeAll(async () => {
    fixture = await coachDatabase();
    await fixture.user(a);
    await fixture.user(b);
    const schema = readFileSync(resolve('../supabase/migrations/202609150001_initial_schema.sql'), 'utf8');
    await fixture.db.exec(
      schema.match(/create or replace function public\.set_updated_at\(\)[\s\S]*?\$\$;/)![0] +
      schema.match(/create trigger coach_conversations_set_updated_at[\s\S]*?;/)![0],
    );
    await fixture.db.query(
      'insert into coach_conversations (id, user_id, title, updated_at) values ($1,$2,$3,$4),($5,$2,$6,$4)',
      [legacy, a, 'Nova conversa', legacyStamp, legacyCustom, 'Meu nome antigo'],
    );
    await fixture.db.query(
      "insert into coach_messages (conversation_id, user_id, role, content, created_at) values ($1,$2,'user','Oi!', '2026-11-01T09:00:00Z'),($1,$2,'user','Me mostra meu almoço de hoje', '2026-11-01T10:00:00Z'),($3,$2,'user','Outro assunto', '2026-11-01T10:00:00Z')",
      [legacy, a, legacyCustom],
    );
    await fixture.db.exec(readFileSync(
      resolve('../supabase/migrations/202611160001_coach_conversation_titles.sql'), 'utf8',
    ));
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
  it('recupera o primeiro assunto das conversas antigas e mantém a data e nomes editados', async () => {
    const rows = await service.list(a, a);
    const named = rows.find((row) => row.id === legacy);
    expect(named?.title).toBe('Almoço de hoje');
    expect(new Date(named!.updated_at).toISOString()).toBe(legacyStamp);
    expect(rows.find((row) => row.id === legacyCustom)?.title).toBe('Meu nome antigo');
  });

  it('nomeia após o primeiro pedido útil e preserva o título escolhido depois', async () => {
    const conversation = await service.create(a, a, {});
    const send = (input: string) => service.commit(a, a, conversation.id, randomUUID(), 'hash', input, {
      session_id: conversation.id,
      result: { answer: 'Resposta', actions: [] },
    });
    expect(conversation.title).toBeNull();
    await send('Oii! Tudo bem?');
    expect((await service.get(a, a, conversation.id)).title).toBeNull();
    await send('Oi, qual é o meu treino de hoje?');
    expect((await service.get(a, a, conversation.id)).title).toBe('Treino de hoje');
    await send('O que tenho no almoço?');
    expect((await service.get(a, a, conversation.id)).title).toBe('Treino de hoje');
    await service.rename(a, a, conversation.id, 'Nova conversa');
    await send('Quero ver o treino de amanhã');
    expect((await service.get(a, a, conversation.id)).title).toBe('Nova conversa');
  });

  it('mantém títulos curtos sem incluir dados pessoais ou links', async () => {
    const titleQuery = async (input: string) => (await fixture.db.query<{ title: string | null }>(
      'select public.coach_opening_title($1) as title', [input],
    )).rows[0]?.title;
    expect(await titleQuery('Oi, pessoa@example.com')).toBeNull();
    expect(await titleQuery('Qual meu treino de hoje? https://example.com/perfil')).toBe('Treino de hoje');
    const long = await titleQuery('Quero rever meus treinos de superiores e inferiores nesta semana porque mudei de rotina');
    expect(long).toMatch(/…$/);
    expect(long?.length).toBeLessThanOrEqual(60);
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
  it('restaura pares pelo orcamento e exclusao remove mensagens em cascata', async () => {
    const c = await service.create(a, a, {});
    const context = {
      topics: [
        {
          topic: 'daily_hydration',
          anchor: 'Quanta água por dia?',
          details: ['Dias comuns'],
        },
      ],
    };
    for (let i = 0; i < 5; i++)
      await service.commit(a, a, c.id, randomUUID(), 'h' + i, i === 0 ? 'Faço supino com halteres.' : 'user' + i, {
        result: { answer: 'answer' + i, dialogue_context: context },
      });
    const history = await service.recent(a, a, c.id);
    expect(history).toHaveLength(10);
    expect(history.map((row) => row.content)).toContain('Faço supino com halteres.');
    expect(await service.recall(a, a, c.id, 'O que eu falei sobre supino?')).toEqual(['Faço supino com halteres.']);
    expect(await service.recall(b, b, c.id, 'O que eu falei sobre supino?')).toEqual([]);
    expect(history.filter((row) => row.dialogue_context)).toEqual([
      { role: 'assistant', content: 'answer4', dialogue_context: context },
    ]);
    expect(history.map((r) => r.role)).toEqual([
      'user',
      'assistant',
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
  it('recupera retorno citado num chat sem misturar outras conversas', async () => {
    const main = await service.create(a, a, {});
    const other = await service.create(a, a, {});
    const response = { result: { answer: 'Entendi.', actions: [] } };
    await service.commit(a, a, main.id, randomUUID(), 'r1', 'Volto na terça à noite.', response);
    await service.commit(a, a, main.id, randomUUID(), 'r2', 'Tomei um café.', response);
    await service.commit(a, a, other.id, randomUUID(), 'r3', 'Volto no sábado cedo.', response);
    const query = 'Que dia mesmo eu disse que volto?';
    expect(await service.recall(a, a, main.id, query)).toEqual(['Volto na terça à noite.']);
    expect(await service.recall(a, a, other.id, query)).toEqual(['Volto no sábado cedo.']);
    expect(await service.recall(b, b, main.id, query)).toEqual([]);
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

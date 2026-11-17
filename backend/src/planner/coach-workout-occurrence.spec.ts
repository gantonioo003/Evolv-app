import { randomUUID } from 'node:crypto';
import { coachDatabase } from '../../test/fixtures/coach-postgres.js';
import type { SupabaseService } from '../supabase/supabase.service.js';
import { PlannerAdjustmentsService } from './planner-adjustments.service.js';
import { PlannerDayContextService } from './planner-day-context.service.js';

it('moves only the dated session, restores it, and preserves changes made after preview', async () => {
  const { db, supabase, user } = await coachDatabase({ product: true });
  try {
    const owner = randomUUID();
    const other = randomUUID();
    await user(owner);
    await user(other);
    const insert = async (sql: string, parameters: string[]) =>
      (await db.query<{ id: string }>(sql + ' returning id', parameters)).rows[0]!.id;
    const plan = await insert(
      "insert into workout_plans(user_id,name,status,start_date,weekly_frequency) values ($1,'Treino','active','2026-11-09',1)",
      [owner],
    );
    const day = await insert(
      "insert into workout_days(workout_plan_id,weekday,title,focus) values ($1,'thursday','Superiores','Peito')",
      [plan],
    );
    const chat = await insert('insert into coach_conversations(user_id) values ($1)', [owner]);
    const client = supabase as unknown as SupabaseService;
    const service = new PlannerAdjustmentsService(client);
    const calendar = new PlannerDayContextService(client);
    const source = '2026-11-12';
    const target = '2026-11-13';
    const weekLater = '2026-11-19';
    const preview = () => service.preview(owner, owner, {
      kind: 'move_workout_occurrence', reason: 'Mover só nesta semana', source: 'coach',
      workout_plan_id: plan, workout_day_id: day, source_date: source, target_date: target,
    }, {
      adjustmentId: randomUUID(), conversationId: chat, proposalId: randomUUID(),
      expiresAt: new Date(Date.now() + 600_000).toISOString(),
    });

    const change = await preview();
    expect(change.status).toBe('pending');
    expect((await calendar.get(owner, source)).workout_day_id).toBe(day);
    expect((await calendar.get(owner, target)).activity_type).toBe('rest');
    await expect(service.apply(other, other, change.id, chat)).rejects.toMatchObject({ status: 404 });
    expect((await service.apply(owner, owner, change.id, chat)).status).toBe('applied');
    expect((await calendar.get(owner, source)).activity_type).toBe('rest');
    expect((await calendar.get(owner, target)).workout_day_id).toBe(day);
    expect((await calendar.get(owner, weekLater)).workout_day_id).toBe(day);
    await expect(service.apply(owner, owner, change.id, chat)).rejects.toMatchObject({ status: 400 });
    expect((await service.revert(owner, owner, change.id, chat)).reverted_at).toBeTruthy();
    expect((await calendar.get(owner, source)).workout_day_id).toBe(day);
    expect((await calendar.get(owner, target)).activity_type).toBe('rest');

    const stale = await preview();
    await db.query(
      "insert into daily_activity_overrides(user_id,activity_date,activity_type,nutrition_day_type) values ($1,$2,'cardio','rest_day')",
      [owner, target],
    );
    await expect(service.apply(owner, owner, stale.id, chat)).rejects.toMatchObject({ status: 409 });
    expect((await calendar.get(owner, source)).workout_day_id).toBe(day);
    expect((await calendar.get(owner, target)).activity_type).toBe('cardio');
  } finally {
    await db.close();
  }
});

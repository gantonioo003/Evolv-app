import { randomUUID } from 'node:crypto';
import { coachDatabase } from '../../test/fixtures/coach-postgres.js';
import { PlannerAdjustmentsService } from '../planner/planner-adjustments.service.js';
import type { SupabaseService } from '../supabase/supabase.service.js';
import type { CoachAiClient } from './coach-ai.client.js';
import type { CoachAccountService } from './coach-account.service.js';
import type { CoachContextService } from './coach-context.service.js';
import { CoachHistoryService } from './coach-history.service.js';
import { CoachController } from './coach.controller.js';
import type { User } from '@supabase/supabase-js';
import { CoachService } from './coach.service.js';

it('bloqueia aplicação por texto e recupera confirmação cuja resposta se perdeu', async () => {
  const { db, supabase, user } = await coachDatabase({ product: true });
  try {
    const owner = randomUUID();
    const foreign = randomUUID();
    await user(owner);
    await user(foreign);
    const plan = randomUUID();
    const session = randomUUID();
    await db.query(
      "insert into workout_plans(id,user_id,name,status,start_date,weekly_frequency) values ($1,$2,'Treino','active','2026-11-09',2)",
      [plan, owner],
    );
    await db.query(
      "insert into workout_days(id,workout_plan_id,weekday,title,focus) values ($1,$2,'saturday','Inferiores B','Pernas'), ($3,$2,'wednesday','Superiores','Costas')",
      [session, plan, randomUUID()],
    );
    const client = supabase as unknown as SupabaseService;
    const history = new CoachHistoryService(client);
    const planner = new PlannerAdjustmentsService(client);
    const runtime = randomUUID();
    const fingerprint = 'a'.repeat(64);
    let target = 'wednesday';
    let dietChange: Record<string, string> | null = null;
    let route = 'apply_requested_change';
    const proposal = randomUUID();
    let nextProposal = proposal;
    const request = vi.fn(async (_owner: string, path: string, _method: string, body?: unknown) => {
      if (path === '/v1/sessions') return { session_id: runtime };
      if (path.endsWith('/planner-context')) return { snapshot_fingerprint: fingerprint };
      if (!path.endsWith('/messages')) return {};
      return {
        session_id: runtime,
        request_id: (body as { request_id: string }).request_id,
        result: {
          answer: 'Vou conferir com o Planner.',
          analysis: { interpreter: 'qwen', route, risk: { labels: [] } },
          actions: [{
            id: nextProposal,
            status: route,
            snapshot_fingerprint: fingerprint,
            expires_at: new Date(Date.now() + 600_000).toISOString(),
            payload: dietChange ?? {
              kind: 'move_workout_day', source: 'coach', reason: 'Pedido direto',
              workout_plan_id: plan, workout_day_id: session, target_weekday: target,
            },
          }],
        },
      };
    });
    const coach = new CoachService(
      { request } as unknown as CoachAiClient,
      { build: async () => ({}) } as unknown as CoachContextService,
      planner, history,
      { context: async () => ({ memory_enabled: false }) } as unknown as CoachAccountService,
    );
    const { conversation_id: chat } = await coach.create(owner, owner, {});
    const weekday = async () => (await db.query<{ weekday: string }>(
      'select weekday from workout_days where id = $1', [session],
    )).rows[0]!.weekday;
    const controller = new CoachController(coach, history, {} as CoachAccountService);
    const principal = { id: owner } as User;
    const send = (text: string, proposal_id?: string) =>
      coach.message(owner, owner, chat, { request_id: randomUUID(), text, proposal_id });
    const purportedChange = await send('Qual treino ficou na quarta?');
    expect(purportedChange).toMatchObject({ result: { actions: [] }, planner_previews: [] });
    expect(await weekday()).toBe('saturday');
    expect((await db.query('select id from planner_adjustments')).rows).toHaveLength(0);

    target = 'friday';
    route = 'pending_user_confirmation';
    const proposalReply = await send('Muda sábado para sexta');
    expect(proposalReply).toMatchObject({ planner_previews: [] });
    route = 'confirmed_for_planner_preview';
    const previewReply = await send('confirmo', proposal);
    expect(previewReply).toMatchObject({ planner_previews: [{ status: 'pending' }] });
    expect(await weekday()).toBe('saturday');
    const adjustmentId = (await db.query<{ id: string }>('select id from planner_adjustments')).rows[0]!.id;
    expect(() => controller.apply(principal, owner, chat, adjustmentId, { confirmed: false }))
      .toThrow('COACH_EXPLICIT_CONFIRMATION_REQUIRED');
    await db.exec(`
      create table bench_workout_writes (id uuid);
      create function bench_count_workout_update() returns trigger language plpgsql security definer set search_path = public as $$
      begin
        insert into bench_workout_writes values (new.id);
        return new;
      end; $$;
      create trigger bench_count_workout_write after update on workout_days
      for each row when (old.weekday is distinct from new.weekday)
      execute function bench_count_workout_update();
    `);
    const confirm = () => controller.apply(principal, owner, chat, adjustmentId, { confirmed: true });
    // The server commits, but the transport loses the response before delivery.
    await confirm();
    expect(await weekday()).toBe('friday');
    const replay = await confirm();
    expect(replay).toMatchObject({ id: adjustmentId, status: 'applied' });
    expect((await db.query('select id from bench_workout_writes')).rows).toHaveLength(1);
    await expect(coach.decide(foreign, foreign, chat, adjustmentId, 'revert')).rejects.toMatchObject({ status: 404 });
    await coach.decide(owner, owner, chat, adjustmentId, 'revert');
    const retryRevert = await coach.decide(owner, owner, chat, adjustmentId, 'revert');
    expect(retryRevert.reverted_at).toBeTruthy();
    expect(await weekday()).toBe('saturday');
    expect((await db.query('select id from bench_workout_writes')).rows).toHaveLength(2);
    await expect(confirm()).rejects.toMatchObject({ status: 400 });

    const diet = randomUUID();
    const meal = randomUUID();
    const item = randomUUID();
    const food = randomUUID();
    const replacement = randomUUID();
    await db.query("insert into diet_plans(id,user_id,name,status) values ($1,$2,'Dieta','active')", [diet, owner]);
    await db.query("insert into meals(id,diet_plan_id,name,position) values ($1,$2,'Jantar',0)", [meal, diet]);
    await db.query("insert into foods(id,name) values ($1,'Proteína da ficha'),($2,'Opção equivalente')", [food, replacement]);
    const substitutions = [{
      food_id: replacement, name: 'Opção equivalente', role: 'protein_source', amount: 120, unit: 'g',
      similarity_score: 0.92,
      nutrition: { calories: 144, proteinG: 14.4, carbohydrateG: 2.4, fatG: 8.4, fiberG: 1.2 },
    }];
    await db.query(
      "insert into meal_items(id,meal_id,food_id,name,amount,quantity,unit,substitution_group,nutrition_role,calories_kcal,protein_g,carbohydrate_g,fat_g,fiber_g,substitutions) values ($1,$2,$3,'Proteína da ficha','100 g',100,'g','protein_source','protein_source',143,13,.7,9.5,0,$4::jsonb)",
      [item, meal, food, JSON.stringify(substitutions)],
    );
    dietChange = {
      kind: 'replace_meal_item', source: 'coach', reason: 'Troca no jantar',
      diet_plan_id: diet, meal_item_id: item, replacement_food_id: replacement,
    };
    route = 'apply_requested_change';
    const dietReply = await send('Troca pela opção equivalente no jantar');
    expect(dietReply).toMatchObject({ result: { actions: [] }, planner_previews: [] });
    expect((await db.query('select food_id from meal_items where id = $1', [item])).rows[0])
      .toMatchObject({ food_id: food });
    route = 'confirmed_for_planner_preview';
    const dietPreview = randomUUID();
    nextProposal = dietPreview;
    await send('confirmo', dietPreview);
    const dietAdjustment = (await db.query<{ id: string }>(
      'select id from planner_adjustments where diet_plan_id = $1', [diet],
    )).rows[0]!.id;
    await controller.apply(principal, owner, chat, dietAdjustment, { confirmed: true });
    const storedItem = (await db.query('select food_id, quantity from meal_items where id = $1', [item])).rows[0];
    expect(storedItem).toMatchObject({ food_id: replacement, quantity: expect.anything() });
    expect(Number((storedItem as { quantity: unknown }).quantity)).toBe(120);
  } finally {
    await db.close();
  }
}, 30_000);

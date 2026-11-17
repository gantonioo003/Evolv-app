import { HttpException } from '@nestjs/common';
import type { User } from '@supabase/supabase-js';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { createInterface } from 'node:readline';
import { coachDatabase } from '../../test/fixtures/coach-postgres.js';
import { PlannerAdjustmentsService } from '../planner/planner-adjustments.service.js';
import { PlannerDayContextService } from '../planner/planner-day-context.service.js';
import { NutritionPlannerService } from '../planner/nutrition-planner.service.js';
import { PlannerService } from '../planner/planner.service.js';
import type { SupabaseService } from '../supabase/supabase.service.js';
import type { CoachAiClient } from './coach-ai.client.js';
import { CoachAccountService } from './coach-account.service.js';
import { CoachContextService } from './coach-context.service.js';
import { CoachController } from './coach.controller.js';
import { CoachHistoryService } from './coach-history.service.js';
import { CoachService } from './coach.service.js';

type Proposal = {
  id: string;
  status: string;
  expires_at: string;
  payload: { kind: string };
};
type Preview = { id: string; conversation_id: string; expires_at: string };
type Reply = { result: { actions: Proposal[] }; planner_previews: Preview[] };
const python = process.env.EVOLV_TEST_PYTHON;
const nlp = process.env.EVOLV_TEST_NLP ?? '1.9.0';
const lmMode = process.env.EVOLV_TEST_LM_MODE ?? 'analyze';

function openRuntime(executable: string) {
  const child = spawn(
    executable,
    ['-u', '-B', resolve('../ai/tests/planner_security_runtime.py'), nlp],
    {
      cwd: resolve('..'),
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        HF_HUB_OFFLINE: '1',
        TRANSFORMERS_OFFLINE: '1',
      },
    },
  );
  let diagnostics = '';
  child.stderr.setEncoding('utf8').on('data', (text: string) => {
    diagnostics = (diagnostics + text).slice(-4000);
  });
  const lines = createInterface({ input: child.stdout });
  const iterator = lines[Symbol.asyncIterator]();
  async function packet() {
    for (;;) {
      const next = await iterator.next();
      if (next.done) throw new Error('Planner runtime exited: ' + diagnostics);
      if (next.value.startsWith('RESULT '))
        return JSON.parse(next.value.slice(7));
    }
  }
  async function call(input: object) {
    child.stdin.write(JSON.stringify(input) + '\n');
    const response = await packet();
    if (response.status)
      throw new HttpException(response.detail, response.status);
    return response.result as unknown;
  }
  return {
    ready: packet,
    stats: () => call({ stats: true }) as Promise<{ lm_calls: Record<string, number> }>,
    advance: (seconds: number) => call({ advance: seconds }),
    request: (user: string, path: string, method: string, body?: unknown) =>
      call({ user, path, method, body }),
    close: () => {
      child.stdin.end();
      child.kill();
      lines.close();
    },
  };
}

it.skipIf(!python)(
  'confere cada etapa de troca real do Coach em PostgreSQL',
  async () => {
    const { db, supabase, user } = await coachDatabase({ product: true });
    const runtime = openRuntime(python!);
    const checks: { name: string; passed: boolean; unchanged?: boolean }[] = [];
    const counts = { unintended: 0, authorized: 0 };
    let lmCalls: Record<string, number> = {};
    try {
      await runtime.ready();
      const owner = randomUUID(),
        foreign = randomUUID();
      await user(owner);
      await user(foreign);
      const insert = async (sql: string, args: unknown[]) =>
        (await db.query<{ id: string }>(sql + ' returning id', args)).rows[0]!
          .id;
      const plan = await insert(
        "insert into workout_plans(user_id,name,status,start_date,weekly_frequency) values ($1,'Treino','active','2026-11-10',1)",
        [owner],
      );
      const day = await insert(
        "insert into workout_days(workout_plan_id,weekday,title,focus) values ($1,'tuesday','Treino','Peito')",
        [plan],
      );
      const exercise = async (name: string) => {
        const existing = await db.query<{ id: string }>(
          'select id from exercises where lower(name)=lower($1)',
          [name],
        );
        return (
          existing.rows[0]?.id ??
          insert(
            "insert into exercises(name,muscle_group,equipment,movement_pattern,training_kind) values ($1,'chest','bodyweight','horizontal_push','resistance')",
            [name],
          )
        );
      };
      const press = await exercise('Supino reto');
      const pushup = await exercise('Flexao de bracos');
      const workoutItem = await insert(
        'insert into workout_day_exercises(workout_day_id,exercise_id,sets,min_reps,max_reps,rest_seconds,target_load_kg) values ($1,$2,3,8,12,90,32.5)',
        [day, press],
      );
      const diet = await insert(
        "insert into diet_plans(user_id,name,status) values ($1,'Dieta','active')",
        [owner],
      );
      const meal = await insert(
        "insert into meals(diet_plan_id,name) values ($1,'Cafe da manha')",
        [diet],
      );
      const food = async (name: string) => {
        const existing = await db.query<{ id: string }>(
          'select id from foods where lower(name)=lower($1) limit 1',
          [name],
        );
        return (
          existing.rows[0]?.id ??
          insert('insert into foods(name) values ($1)', [name])
        );
      };
      const egg = await food('Ovo'),
        tofu = await food('Tofu');
      const options = [
        {
          food_id: tofu,
          name: 'Tofu',
          role: 'protein_source',
          amount: 120,
          unit: 'g',
          nutrition: {
            calories: 144,
            proteinG: 14.4,
            carbohydrateG: 2.4,
            fatG: 8.4,
            fiberG: 1.2,
          },
          similarity_score: 0.92,
        },
      ];
      const mealItem = await insert(
        "insert into meal_items(meal_id,food_id,name,amount,quantity,unit,substitution_group,nutrition_role,calories_kcal,protein_g,carbohydrate_g,fat_g,fiber_g,substitutions) values ($1,$2,'Ovo','100 g',100,'g','legado','protein_source',143,13,.7,9.5,0,$3::jsonb)",
        [meal, egg, JSON.stringify(options)],
      );
      const client = supabase as unknown as SupabaseService;
      const history = new CoachHistoryService(client);
      const account = new CoachAccountService(
        client,
        new PlannerDayContextService(client),
      );
      const planner = new PlannerAdjustmentsService(client);
      const context = new CoachContextService(
        new PlannerService(client),
        new NutritionPlannerService(client),
        client,
      );
      const service = new CoachService(
        runtime as unknown as CoachAiClient,
        context,
        planner,
        history,
        account,
      );
      const controller = new CoachController(service, history, account);
      const sid = (await service.create(owner, owner, {})).session_id;
      const otherChat = (await service.create(owner, owner, {})).session_id;
      const principal = { id: owner } as User;
      const state = async () =>
        (
          await db.query(
            "select (select to_jsonb(w) - 'updated_at' from workout_day_exercises w where id=$1) as workout, " +
              "(select to_jsonb(m) - 'updated_at' from meal_items m where id=$2) as diet",
            [workoutItem, mealItem],
          )
        ).rows[0];
      const check = (name: string, passed: boolean, unchanged?: boolean) => {
        if (unchanged === false) counts.unintended++;
        checks.push({
          name,
          passed,
          ...(unchanged === undefined ? {} : { unchanged }),
        });
      };
      async function readOnly(name: string, fn: () => Promise<boolean>) {
        const before = await state();
        let passed = false;
        try {
          passed = await fn();
        } finally {
          const unchanged =
            JSON.stringify(await state()) === JSON.stringify(before);
          check(name, passed && unchanged, unchanged);
        }
      }
      const refuses = async (promise: Promise<unknown>, status: number) => {
        try {
          await promise;
          return false;
        } catch (error) {
          return error instanceof HttpException && error.getStatus() === status;
        }
      };
      const send = async (
        text: string,
        proposal_id?: string,
        chat = sid,
        actor = owner,
        request_id = randomUUID(),
      ) => {
        const reply = await service.message(actor, actor, chat, {
          request_id,
          text,
          proposal_id,
        }) as unknown as Reply;
        return reply;
      };
      async function propose(text: string, kind: string) {
        let proposal: Proposal | undefined;
        await readOnly(kind + ' proposta', async () => {
          const reply = await send(text);
          proposal = reply.result.actions[0];
          return (
            reply.planner_previews.length === 0 &&
            proposal?.status === 'pending_user_confirmation' &&
            proposal?.payload.kind === kind
          );
        });
        expect(proposal, text).toBeDefined();
        return proposal!;
      }
      async function preview(text: string, kind: string) {
        const p = await propose(text, kind);
        const request = randomUUID();
        let item: Preview | undefined;
        await readOnly(kind + ' prévia e reenvio', async () => {
          const reply = await send('confirmo', p.id, sid, owner, request);
          item = reply.planner_previews[0];
          const retry = await send('confirmo', p.id, sid, owner, request);
          return Boolean(
            item &&
            item.conversation_id === sid &&
            Date.parse(item.expires_at) === Date.parse(p.expires_at) &&
            retry.planner_previews[0]?.id === item.id,
          );
        });
        expect(item, text).toBeDefined();
        return item!;
      }
      const workoutText = 'Troque supino reto por flexão de braços.';
      const dietText = 'Troque o ovo do café da manhã por tofu.';
      const rpc = supabase.forUser(owner).rpc;
      await readOnly('saudação não altera nem propõe mudanças', async () => {
        const reply = await send('Oi, tudo bem?', undefined, otherChat);
        return reply.result.actions.length === 0 && reply.planner_previews.length === 0;
      });
      // A consultation is not consent. Use separate conversations so each case
      // starts without a pending action from the previous one.
      for (const [name, text] of [
        ['consulta sobre treino', 'Posso trocar supino reto por flexão de braços?'],
        ['consulta sobre dieta', 'Posso trocar o ovo do café da manhã por tofu?'],
        ['negação de troca', 'Não troque supino reto por flexão de braços.'],
        ['hipótese de troca', 'Se eu trocasse supino reto por flexão, seria melhor?'],
        ['relato de outra pessoa', 'Meu amigo quer trocar supino reto por flexão.'],
        ['substituição alimentar não aprovada', 'Troque o ovo do café da manhã por chocolate.'],
      ] as const) {
        const consultation = (await service.create(owner, owner, {})).session_id;
        await readOnly(name + ' não cria proposta nem prévia', async () => {
          const reply = await send(text, undefined, consultation);
          const stored = await db.query<{ count: number }>(
            'select count(*)::int as count from planner_adjustments where conversation_id=$1',
            [consultation],
          );
          return reply.result.actions.length === 0 &&
            reply.planner_previews.length === 0 && stored.rows[0]!.count === 0;
        });
      }
      const proposal = await propose(workoutText, 'replace_exercise');
      await readOnly(
        'confirmar sem identificador',
        async () => !(await send('confirmo')).planner_previews.length,
      );
      await readOnly(
        'identificador incorreto',
        async () =>
          !(await send('confirmo', randomUUID())).planner_previews.length,
      );
      await readOnly(
        'texto ambíguo com identificador',
        async () =>
          !(await send('talvez, vou pensar', proposal.id)).planner_previews
            .length,
      );
      await readOnly(
        'proposta em outra conversa da mesma conta',
        async () =>
          !(await send('confirmo', proposal.id, otherChat)).planner_previews
            .length,
      );
      await readOnly('proposta em sessão alheia', () =>
        refuses(send('confirmo', proposal.id, sid, foreign), 404),
      );
      await readOnly('recusar proposta por texto', async () => {
        const result = await send('rejeito', proposal.id);
        return (
          !result.planner_previews.length &&
          result.result.actions[0]?.status === 'rejected'
        );
      });
      await readOnly(
        'proposta recusada fica inutilizável',
        async () =>
          !(await send('confirmo', proposal.id)).planner_previews.length,
      );

      const staleProposal = await propose(workoutText, 'replace_exercise');
      await runtime.advance(601);
      await readOnly(
        'proposta vencida antes da prévia',
        async () =>
          !(await send('confirmo', staleProposal.id)).planner_previews.length,
      );
      await runtime.advance(-601);
      const changedPlan = await propose(workoutText, 'replace_exercise');
      await db.query('update workout_day_exercises set sets=4 where id=$1', [
        workoutItem,
      ]);
      await readOnly(
        'plano alterado antes de criar prévia',
        async () =>
          !(await send('confirmo', changedPlan.id)).planner_previews.length,
      );
      await db.query('update workout_day_exercises set sets=3 where id=$1', [
        workoutItem,
      ]);

      for (const [text, kind, expectedId] of [
        [workoutText, 'replace_exercise', pushup],
        [dietText, 'replace_meal_item', tofu],
      ] as const) {
        const denied = await preview(text, kind);
        const apply = (id: string, chat = sid, confirmed: unknown = true) =>
          Promise.resolve().then(() =>
            controller.apply(principal, owner, chat, id, {
              confirmed: confirmed as boolean,
            }),
          );
        for (const flag of [false, undefined, 'true']) {
          await readOnly(kind + ' confirmação indevida ' + String(flag), () =>
            refuses(
              apply(denied.id, sid, flag === undefined ? null : flag),
              400,
            ),
          );
        }
        await readOnly(kind + ' prévia em outra conversa', () =>
          refuses(apply(denied.id, otherChat), 404),
        );
        await readOnly(kind + ' prévia de outra conta', () =>
          refuses(
            service.decide(foreign, foreign, sid, denied.id, 'apply'),
            404,
          ),
        );
        await readOnly(kind + ' atalho HTTP do Planner', () =>
          refuses(planner.apply(owner, owner, denied.id), 400),
        );
        await readOnly(kind + ' atalho SQL antigo', async () => {
          const { error } = await rpc('apply_planner_adjustment', {
            p_adjustment_id: denied.id,
          });
          return (error as { code?: string } | null)?.code === '42501';
        });
        await readOnly(kind + ' RPC sem confirmação', async () => {
          const { error } = await rpc('mutate_coach_adjustment', {
            p_adjustment_id: denied.id,
            p_conversation_id: sid,
            p_operation: 'apply',
            p_confirmed: false,
          });
          return (error as { code?: string } | null)?.code === '22023';
        });
        await readOnly(kind + ' RPC em outra conversa', async () => {
          const { error } = await rpc('mutate_coach_adjustment', {
            p_adjustment_id: denied.id,
            p_conversation_id: otherChat,
            p_operation: 'apply',
            p_confirmed: true,
          });
          return (error as { code?: string } | null)?.code === 'P0002';
        });
        await readOnly(kind + ' bloqueio de mudança do vínculo', async () => {
          const { error } = (await supabase
            .forUser(owner)
            .from('planner_adjustments')
            .update({ conversation_id: otherChat })
            .eq('id', denied.id)) as { error: { code?: string } | null };
          return (error as { code?: string } | null)?.code === '42501';
        });
        await readOnly(
          kind + ' rejeição da prévia',
          async () =>
            (
              await controller.reject(principal, owner, sid, denied.id, {
                confirmed: true,
              })
            ).status === 'rejected',
        );
        await readOnly(kind + ' confirmar prévia rejeitada', () =>
          refuses(apply(denied.id), 400),
        );

        const expired = await preview(text, kind);
        await db.query(
          "update planner_adjustments set expires_at=now()-interval '1 second' where id=$1",
          [expired.id],
        );
        await readOnly(kind + ' confirmar prévia vencida', () =>
          refuses(apply(expired.id), 409),
        );

        const good = await preview(text, kind);
        const original = (await state()) as {
          workout: Record<string, unknown>;
          diet: Record<string, unknown>;
        };
        const concurrent = await Promise.allSettled([
          apply(good.id),
          apply(good.id),
        ]);
        const successful = concurrent.filter(
          (result) => result.status === 'fulfilled',
        );
        check(
          kind + ' confirmações simultâneas aplicam uma vez',
          successful.length === 1 &&
            concurrent.some(
              (result) =>
                result.status === 'rejected' &&
                result.reason instanceof HttpException &&
                [400, 429].includes(result.reason.getStatus()),
            ),
        );
        const applied = successful[0]!.value;
        const after = (await state()) as typeof original;
        const expected =
          kind === 'replace_exercise'
            ? {
                ...original,
                workout: { ...original.workout, exercise_id: expectedId },
              }
            : {
                ...original,
                diet: {
                  ...original.diet,
                  ...Object.fromEntries(
                    Object.entries(
                      applied.after_snapshot as Record<string, unknown>,
                    ).filter(([key]) => key !== 'meal_item_id'),
                  ),
                },
              };
        check(
          kind + ' aplica apenas os campos da prévia',
          applied.status === 'applied' &&
            after[kind === 'replace_exercise' ? 'workout' : 'diet'][
              kind === 'replace_exercise' ? 'exercise_id' : 'food_id'
            ] === expectedId &&
            JSON.stringify(after) === JSON.stringify(expected),
        );
        counts.authorized++;
        await readOnly(kind + ' confirmação repetida', async () =>
          (await apply(good.id)).status === 'applied',
        );
        await readOnly(kind + ' desfazer pela rota geral', () =>
          refuses(planner.revert(owner, owner, good.id), 400),
        );
        await readOnly(kind + ' desfazer pelo RPC antigo', async () => {
          const { error } = await rpc('revert_planner_adjustment', {
            p_adjustment_id: good.id,
          });
          return (error as { code?: string } | null)?.code === '42501';
        });
        await readOnly(kind + ' desfazer em outro chat', () =>
          refuses(
            service.decide(owner, owner, otherChat, good.id, 'revert'),
            404,
          ),
        );
        const reverted = await controller.revert(
          principal,
          owner,
          sid,
          good.id,
          { confirmed: true },
        );
        check(
          kind + ' desfazer restaura a linha inteira',
          Boolean(reverted.reverted_at) &&
            JSON.stringify(await state()) === JSON.stringify(original),
        );
        counts.authorized++;
        await readOnly(kind + ' desfazer repetido', async () =>
          Boolean((await service.decide(owner, owner, sid, good.id, 'revert')).reverted_at),
        );
      }

      const staleMeal = await preview(dietText, 'replace_meal_item');
      await db.query('update meal_items set quantity=95 where id=$1', [
        mealItem,
      ]);
      await readOnly('porção alterada entre prévia e confirmação', () =>
        refuses(service.decide(owner, owner, sid, staleMeal.id, 'apply'), 409),
      );
      await db.query('update meal_items set quantity=100 where id=$1', [
        mealItem,
      ]);
      const changedLater = await preview(dietText, 'replace_meal_item');
      await service.decide(owner, owner, sid, changedLater.id, 'apply');
      counts.authorized++;
      await db.query('update meal_items set quantity=125 where id=$1', [
        mealItem,
      ]);
      await readOnly('desfazer preserva edição posterior de porção', () =>
        refuses(
          service.decide(owner, owner, sid, changedLater.id, 'revert'),
          409,
        ),
      );
      await db.query('update meal_items set quantity=120 where id=$1', [
        mealItem,
      ]);
      await service.decide(owner, owner, sid, changedLater.id, 'revert');
      counts.authorized++;
      const orphan = await preview(workoutText, 'replace_exercise');
      await readOnly('apagar conversa não altera o plano', async () => {
        await service.remove(owner, owner, sid);
        const stored = await planner.get(owner, owner, orphan.id);
        return stored.conversation_id === null && stored.status === 'pending';
      });
      await readOnly(
        'prévia de conversa apagada não pode ser aplicada',
        async () => {
          return (
            (await refuses(
              service.decide(owner, owner, sid, orphan.id, 'apply'),
              404,
            )) && (await refuses(planner.apply(owner, owner, orphan.id), 400))
          );
        },
      );
      const manual = await planner.preview(owner, owner, {
        kind: 'replace_exercise',
        reason: 'Teste de ajuste manual',
        workout_plan_id: plan,
        workout_day_exercise_id: workoutItem,
        replacement_exercise_id: pushup,
      });
      const manualOriginal = await state();
      await planner.apply(owner, owner, manual.id);
      counts.authorized++;
      check(
        'ajuste manual mantém sua rota e aplica',
        ((await state()) as { workout: { exercise_id: string } }).workout
          .exercise_id === pushup,
      );
      await planner.revert(owner, owner, manual.id);
      counts.authorized++;
      check(
        'desfazer ajuste manual restaura o plano',
        JSON.stringify(await state()) === JSON.stringify(manualOriginal),
      );
      lmCalls = (await runtime.stats()).lm_calls;
      if (lmMode === 'generate') {
        check('Qwen executado durante a bateria', (lmCalls.write ?? 0) > 0);
      }
      await service.onModuleDestroy();
    } finally {
      runtime.close();
      await db.close();
      const output = process.env.EVOLV_PLANNER_SECURITY_OUTPUT;
      if (output) {
        mkdirSync(dirname(output), { recursive: true });
        writeFileSync(
          output,
          JSON.stringify(
            {
              phase: 'task-06-planner',
              lm_mode: lmMode,
              lm_calls: lmCalls,
              nlp,
              passed: checks.filter((item) => item.passed).length,
              total: checks.length,
              authorized_writes: counts.authorized,
              unintended_writes: counts.unintended,
              checks,
            },
            null,
            2,
          ) + '\n',
        );
      }
    }
    expect(checks.filter((item) => !item.passed)).toEqual([]);
  },
  lmMode === 'generate' ? 600_000 : 180_000,
);

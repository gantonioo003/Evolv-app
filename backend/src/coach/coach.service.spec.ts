import { randomUUID } from 'node:crypto';
import type { CoachAiClient } from './coach-ai.client.js';
import type { CoachContextService } from './coach-context.service.js';
import type { PlannerAdjustmentsService } from '../planner/planner-adjustments.service.js';
import { CoachService } from './coach.service.js';
import { CoachHistoryService } from './coach-history.service.js';
import { NotFoundException } from '@nestjs/common';

describe('CoachService', () => {
  const user = randomUUID(),
    sid = randomUUID(),
    proposal = randomUUID(),
    adjustment = randomUUID();
  const fp = 'a'.repeat(64);
  function setup() {
    const payload = {
      kind: 'move_workout_day',
      reason: 'Pedido do usuario',
      source: 'coach',
      workout_plan_id: randomUUID(),
      workout_day_id: randomUUID(),
      target_weekday: 'thursday',
    };
    const action = {
      id: proposal,
      status: 'confirmed_for_planner_preview',
      payload,
      snapshot_fingerprint: fp,
      expires_at: new Date(Date.now() + 600000).toISOString(),
    };
    const message = {
      request_id: randomUUID(),
      text: 'confirmo',
      proposal_id: proposal,
    };
    const response = {
      session_id: sid,
      request_id: message.request_id,
      result: { answer: 'Proposta', actions: [action] },
    };
    const request = vi.fn(async (_user: string, path: string) => {
      if (path === '/v1/sessions') return { session_id: sid };
      if (path.endsWith('/planner-context'))
        return { snapshot_fingerprint: fp };
      return response;
    });
    const planner = {
      preview: vi.fn().mockResolvedValue({ id: adjustment }),
      get: vi.fn().mockResolvedValue({ id: adjustment }),
      apply: vi.fn().mockResolvedValue({ id: adjustment, status: 'applied' }),
      reject: vi.fn(),
      revert: vi.fn(),
    };
    const saved = new Map<string, Record<string, unknown>>();
    const links = new Map<string, string>();
    const history = {
      create: vi.fn().mockResolvedValue({ id: sid }),
      get: vi.fn(async (owner: string) => {
        if (owner !== user) throw new NotFoundException();
        return { id: sid, selected: {} };
      }),
      recent: vi.fn().mockResolvedValue([]),
      cached: vi.fn(
        async (_u: string, _t: string, _s: string, r: string) =>
          saved.get(r) ?? null,
      ),
      commit: vi.fn(
        async (
          _u: string,
          _t: string,
          _s: string,
          r: string,
          _h: string,
          _i: string,
          out: Record<string, unknown>,
        ) => {
          saved.set(r, out);
          return out;
        },
      ),
      linked: vi.fn(async (_u: string, _t: string, _s: string, p: string) =>
        links.has(p) ? { id: links.get(p) } : null,
      ),
      link: vi.fn(
        async (_u: string, _t: string, _s: string, p: string, a: string) => {
          links.set(p, a);
        },
      ),
      adjustment: vi.fn(
        async (_u: string, _t: string, _s: string, a: string) => {
          if (![...links.values()].includes(a)) throw new NotFoundException();
        },
      ),
    };
    const service = new CoachService(
      { request } as unknown as CoachAiClient,
      {
        build: vi.fn().mockResolvedValue({}),
      } as unknown as CoachContextService,
      planner as unknown as PlannerAdjustmentsService,
      history as unknown as CoachHistoryService,
    );
    return { service, planner, action, message, response, request, history };
  }
  it('previa e aplicacao sao operacoes distintas, deduplica previa', async () => {
    const t = setup();
    await t.service.create(user, 'jwt', {});
    await t.service.message(user, 'jwt', sid, t.message);
    await t.service.message(user, 'jwt', sid, t.message);
    expect(t.planner.preview).toHaveBeenCalledTimes(1);
    expect(t.planner.apply).not.toHaveBeenCalled();
    await t.service.decide(user, 'jwt', sid, adjustment, 'apply');
    expect(t.planner.apply).toHaveBeenCalledWith(user, 'jwt', adjustment);
  });
  it('rejeita sessao de outra pessoa e ajuste nao associado', async () => {
    const t = setup();
    await t.service.create(user, 'jwt', {});
    await expect(
      t.service.message(randomUUID(), 'jwt', sid, t.message),
    ).rejects.toMatchObject({ status: 404 });
    await expect(
      t.service.decide(user, 'jwt', sid, adjustment, 'apply'),
    ).rejects.toMatchObject({ status: 404 });
  });
  it('nao cria previa de proposta nao confirmada', async () => {
    const t = setup();
    t.action.status = 'pending_user_confirmation';
    await t.service.create(user, 'jwt', {});
    await t.service.message(user, 'jwt', sid, t.message);
    expect(t.planner.preview).not.toHaveBeenCalled();
  });
  it('descreve a persistencia real sem inventar exclusao ou consentimento', async () => {
    const t = setup();
    Object.assign(t.response.result, {
      actions: [],
      analysis: { route: 'privacy_information' },
      answer: 'Historico somente em memoria',
    });
    const out = await t.service.message(user, 'jwt', sid, t.message);
    const result = out.result as Record<string, unknown>;
    expect(result.privacy).toEqual({
      history: 'supabase_user_scoped', automatic_training: false,
    });
    expect(result.planner).toEqual({ connected: true, writes_allowed: false });
    expect(result.answer).toContain('salvas na sua conta');
    expect(result.answer).toContain('não apaga dados');
    expect(t.planner.apply).not.toHaveBeenCalled();
  });
  it('recusa SQL, campos adicionais e falta de parametros', async () => {
    for (const mutate of [
      (a: ReturnType<typeof setup>['action']) =>
        Object.assign(a.payload, { sql: 'delete' }),
      (a: ReturnType<typeof setup>['action']) => {
        a.payload.kind = 'toString';
      },
      (a: ReturnType<typeof setup>['action']) => {
        a.payload.workout_day_id = 'invalid';
      },
    ]) {
      const t = setup();
      mutate(t.action);
      await t.service.create(user, 'jwt', {});
      await expect(
        t.service.message(user, 'jwt', sid, t.message),
      ).rejects.toMatchObject({ status: 502 });
      expect(t.planner.preview).not.toHaveBeenCalled();
    }
  });
  it('recusa contexto alterado e proposta vencida', async () => {
    for (const stale of [true, false]) {
      const t = setup();
      if (stale) t.action.snapshot_fingerprint = 'b'.repeat(64);
      else t.action.expires_at = new Date(0).toISOString();
      await t.service.create(user, 'jwt', {});
      await expect(
        t.service.message(user, 'jwt', sid, t.message),
      ).rejects.toMatchObject({ status: 409 });
      expect(t.planner.preview).not.toHaveBeenCalled();
    }
  });
  it('recupera falha temporaria ao vincular previa sem criar outra', async () => {
    const t = setup();
    await t.service.create(user, 'jwt', {});
    t.history.link.mockRejectedValueOnce(new Error('temporary'));
    await expect(
      t.service.message(user, 'jwt', sid, t.message),
    ).rejects.toThrow('temporary');
    await t.service.message(user, 'jwt', sid, t.message);
    expect(t.planner.preview).toHaveBeenCalledTimes(1);
    expect(t.history.link).toHaveBeenCalledTimes(2);
  });
  it('repeticao apos reinicio usa resposta persistida e dispensa runtime', async () => {
    const t = setup();
    await t.service.create(user, 'jwt', {});
    await t.service.message(user, 'jwt', sid, t.message);
    t.request.mockClear();
    const restarted = new CoachService(
      { request: t.request } as unknown as CoachAiClient,
      { build: vi.fn() } as unknown as CoachContextService,
      t.planner as unknown as PlannerAdjustmentsService,
      t.history as unknown as CoachHistoryService,
    );
    await restarted.message(user, 'jwt', sid, t.message);
    expect(t.request).not.toHaveBeenCalled();
    await restarted.decide(user, 'jwt', sid, adjustment, 'apply');
    expect(t.planner.apply).toHaveBeenCalledTimes(1);
  });
});

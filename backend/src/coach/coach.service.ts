import {
  BadGatewayException,
  ConflictException,
  HttpException,
  Injectable,
} from '@nestjs/common';
import { plainToInstance } from 'class-transformer';
import { isUUID, validate } from 'class-validator';
import { CreatePlannerAdjustmentDto } from '../planner/dto/create-planner-adjustment.dto.js';
import { PlannerAdjustmentsService } from '../planner/planner-adjustments.service.js';
import { CoachAiClient } from './coach-ai.client.js';
import { CoachContextService } from './coach-context.service.js';
import { CoachHistoryService } from './coach-history.service.js';
import { createHash } from 'node:crypto';
import type {
  CoachMessageDto,
  CreateCoachSessionDto,
} from './dto/coach.dto.js';

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new BadGatewayException('COACH_INVALID_CONTRACT');
  return value as Record<string, unknown>;
}
type Session = {
  owner: string;
  selected: CreateCoachSessionDto;
  touched: number;
  previews: Map<string, string>;
  runtimeId: string;
};
const required: Record<string, string[]> = {
  move_workout_day: ['workout_plan_id', 'workout_day_id', 'target_weekday'],
  replace_exercise: [
    'workout_plan_id',
    'workout_day_exercise_id',
    'replacement_exercise_id',
  ],
  replace_meal_item: ['diet_plan_id', 'meal_item_id', 'replacement_food_id'],
  set_day_activity: ['activity_date', 'activity_type'],
};

@Injectable()
export class CoachService {
  private readonly sessions = new Map<string, Session>();
  private readonly busy = new Set<string>();
  constructor(
    private readonly ai: CoachAiClient,
    private readonly context: CoachContextService,
    private readonly planner: PlannerAdjustmentsService,
    private readonly history: CoachHistoryService,
  ) {}
  async onModuleDestroy() {
    for (const [id, s] of this.sessions) {
      await this.ai
        .request(s.owner, '/v1/sessions/' + s.runtimeId, 'DELETE')
        .catch(() => undefined);
      this.sessions.delete(id);
    }
  }
  private async runtime(user: string, token: string, sid: string) {
    const conversation = await this.history.get(user, token, sid);
    const cached = this.sessions.get(sid);
    if (
      cached &&
      cached.owner === user &&
      Date.now() - cached.touched < 1800000
    )
      return cached;
    for (const [id, s] of this.sessions)
      if (Date.now() - s.touched >= 1800000) this.sessions.delete(id);
    if (this.sessions.size >= 32)
      throw new HttpException('COACH_SESSION_CAPACITY', 429);
    const response = record(
      await this.ai.request(user, '/v1/sessions', 'POST', {}),
    );
    const runtimeId = response.session_id;
    if (typeof runtimeId !== 'string' || !isUUID(runtimeId))
      throw new BadGatewayException('COACH_INVALID_SESSION');
    try {
      await this.ai.request(
        user,
        '/v1/sessions/' + runtimeId + '/history',
        'PUT',
        { messages: await this.history.recent(user, token, sid) },
      );
    } catch (error) {
      await this.ai
        .request(user, '/v1/sessions/' + runtimeId, 'DELETE')
        .catch(() => undefined);
      throw error;
    }
    const session: Session = {
      owner: user,
      selected: conversation.selected,
      touched: Date.now(),
      previews: new Map(),
      runtimeId,
    };
    this.sessions.set(sid, session);
    return session;
  }
  private async serial<T>(sid: string, fn: () => Promise<T>) {
    if (this.busy.has(sid)) throw new HttpException('COACH_SESSION_BUSY', 429);
    this.busy.add(sid);
    try {
      return await fn();
    } finally {
      this.busy.delete(sid);
    }
  }
  async create(user: string, token: string, dto: CreateCoachSessionDto) {
    await this.context.build(user, token, dto);
    const conversation = await this.history.create(user, token, dto);
    return {
      session_id: conversation.id,
      conversation_id: conversation.id,
      persistence: 'supabase',
    };
  }
  async remove(user: string, token: string, sid: string) {
    await this.history.get(user, token, sid);
    return this.serial(sid, async () => {
      await this.history.remove(user, token, sid);
      const cached = this.sessions.get(sid);
      if (cached)
        await this.ai
          .request(user, '/v1/sessions/' + cached.runtimeId, 'DELETE')
          .catch(() => undefined);
      this.sessions.delete(sid);
    });
  }
  async message(
    user: string,
    token: string,
    sid: string,
    dto: CoachMessageDto,
  ) {
    await this.history.get(user, token, sid);
    return this.serial(sid, async () => {
      const inputHash = createHash('sha256')
        .update(JSON.stringify([dto.text, dto.proposal_id ?? null]))
        .digest('hex');
      const saved = await this.history.cached(
        user,
        token,
        sid,
        dto.request_id,
        inputHash,
      );
      if (saved) return saved;
      let session = await this.runtime(user, token, sid);
      const snapshot = await this.context.build(user, token, session.selected);
      let refreshed: Record<string, unknown>;
      try {
        refreshed = record(
          await this.ai.request(
            user,
            '/v1/sessions/' + session.runtimeId + '/planner-context',
            'PUT',
            snapshot,
          ),
        );
      } catch (error) {
        if (!(error instanceof HttpException) || error.getStatus() !== 404)
          throw error;
        this.sessions.delete(sid);
        session = await this.runtime(user, token, sid);
        refreshed = record(
          await this.ai.request(
            user,
            '/v1/sessions/' + session.runtimeId + '/planner-context',
            'PUT',
            snapshot,
          ),
        );
      }
      const response = record(
        await this.ai.request(
          user,
          '/v1/sessions/' + session.runtimeId + '/messages',
          'POST',
          dto,
        ),
      );
      if (
        response.session_id !== session.runtimeId ||
        response.request_id !== dto.request_id
      )
        throw new BadGatewayException('COACH_RESPONSE_ID_MISMATCH');
      const result = record(response.result);
      if (
        typeof result.answer !== 'string' ||
        !Array.isArray(result.actions) ||
        result.actions.length > 1
      )
        throw new BadGatewayException('COACH_INVALID_RESULT');
      // The Python runtime describes local memory; this authenticated boundary
      // owns durable persistence and must describe the actual app behavior.
      result.privacy = {
        history: 'supabase_user_scoped',
        automatic_training: false,
      };
      result.planner = { connected: true, writes_allowed: false };
      if (
        result.analysis &&
        typeof result.analysis === 'object' &&
        (result.analysis as Record<string, unknown>).route === 'privacy_information'
      ) {
        result.answer =
          'No aplicativo, suas conversas são salvas na sua conta para você retomar o histórico. ' +
          'Elas não entram automaticamente no treinamento do modelo. ' +
          'Você pode excluir conversas pelo histórico; pedir exclusão no chat não apaga dados nem confirma consentimento.';
      }
      const previews: unknown[] = [];
      for (const raw of result.actions) {
        const action = record(raw);
        if (action.status !== 'confirmed_for_planner_preview') continue;
        if (
          typeof action.id !== 'string' ||
          !isUUID(action.id) ||
          action.id !== dto.proposal_id
        )
          throw new BadGatewayException('COACH_INVALID_PROPOSAL');
        if (
          typeof refreshed.snapshot_fingerprint !== 'string' ||
          !/^[a-f0-9]{64}$/.test(refreshed.snapshot_fingerprint) ||
          action.snapshot_fingerprint !== refreshed.snapshot_fingerprint
        )
          throw new ConflictException('COACH_PLAN_CONTEXT_CHANGED');
        if (
          typeof action.expires_at !== 'string' ||
          !Number.isFinite(Date.parse(action.expires_at)) ||
          Date.parse(action.expires_at) <= Date.now()
        )
          throw new ConflictException('COACH_PROPOSAL_EXPIRED');
        const payload = record(action.payload);
        if (
          typeof payload.kind !== 'string' ||
          !Object.hasOwn(required, payload.kind) ||
          payload.source !== 'coach' ||
          Object.keys(payload).some(
            (k) =>
              ![
                'kind',
                'reason',
                'source',
                ...required[payload.kind as string]!,
              ].includes(k),
          ) ||
          required[payload.kind].some(
            (k) => payload[k] === undefined || payload[k] === null,
          )
        )
          throw new BadGatewayException('COACH_INVALID_ACTION');
        const typed = plainToInstance(CreatePlannerAdjustmentDto, payload);
        if (
          (
            await validate(typed, {
              whitelist: true,
              forbidNonWhitelisted: true,
            })
          ).length
        )
          throw new BadGatewayException('COACH_INVALID_ACTION');
        const durable = await this.history.linked(user, token, sid, action.id);
        const existing = durable?.id ?? session.previews.get(action.id);
        if (existing) {
          if (!durable)
            await this.history.link(
              user,
              token,
              sid,
              action.id,
              existing,
              payload,
            );
          previews.push(await this.planner.get(user, token, existing));
          continue;
        }
        if (session.previews.size >= 32)
          throw new HttpException('COACH_PREVIEW_CAPACITY', 429);
        const preview = await this.planner.preview(user, token, typed);
        if (!preview || typeof preview.id !== 'string' || !isUUID(preview.id))
          throw new BadGatewayException('COACH_INVALID_PREVIEW');
        session.previews.set(action.id, preview.id);
        await this.history.link(
          user,
          token,
          sid,
          action.id,
          preview.id,
          payload,
        );
        previews.push(preview);
      }
      session.touched = Date.now();
      return this.history.commit(
        user,
        token,
        sid,
        dto.request_id,
        inputHash,
        dto.text,
        {
          ...response,
          session_id: sid,
          conversation_id: sid,
          planner_previews: previews,
        },
      );
    });
  }
  async decide(
    user: string,
    token: string,
    sid: string,
    adjustment: string,
    operation: 'apply' | 'reject' | 'revert',
  ) {
    await this.history.get(user, token, sid);
    await this.history.adjustment(user, token, sid, adjustment);
    return this.serial(sid, () =>
      this.planner[operation](user, token, adjustment),
    );
  }
}

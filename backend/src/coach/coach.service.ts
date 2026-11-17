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
import { CoachHistoryService, coachContextBudget, contextUnits, messageId } from './coach-history.service.js';
import { CoachAccountService } from './coach-account.service.js';
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
  previews: Set<string>;
  runtimeId: string;
};
const confirmations = new Set(['sim', 'confirmo', 'pode confirmar', 'confirmar', 'confirmo a proposta', 'confirmo essa proposta']);

const required: Record<string, string[]> = {
  move_workout_day: ['workout_plan_id', 'workout_day_id', 'target_weekday'],
  move_workout_occurrence: ['workout_plan_id', 'workout_day_id', 'source_date', 'target_date'],
  replace_exercise: [
    'workout_plan_id',
    'workout_day_exercise_id',
    'replacement_exercise_id',
  ],
  replace_meal_item: ['diet_plan_id', 'meal_item_id', 'replacement_food_id'],
  set_day_activity: ['activity_date', 'activity_type'],
};

const plannerAlternatives: Record<string, string> = {
  INCOMPATIBLE_EXERCISE_REPLACEMENT: 'O substituto não cumpre o mesmo papel nesse treino. Qual equipamento você tem disponível? Posso procurar outra opção.',
  DUPLICATE_EXERCISE_IN_DAY: 'O substituto já está nesse treino. Quer escolher outro exercício?',
  FOOD_NOT_APPROVED_SUBSTITUTION: 'Essa troca não está entre as opções equivalentes dessa refeição. Quer conferir o que o cardápio oferece?',
  WORKOUT_DAY_ALREADY_SCHEDULED: 'Esse treino já está no dia escolhido. Quer conferir a programação?',
  COACH_WORKOUT_DESTINATION_OCCUPIED: 'O dia de destino já tem um treino. Posso conferir quais dias estão livres.',
  ADJUSTMENT_EXPIRED: 'O prazo para aplicar a mudança passou. Peça a troca novamente para eu conferir o plano atual.',
  ADJUSTMENT_STALE: 'Seu plano mudou enquanto eu conferia a troca. Quer que eu consulte a versão atual?',
  ADJUSTMENT_TARGET_NOT_FOUND: 'O item já não está disponível no plano. Quer conferir a ficha atual comigo?',
};

function plannerReply(error: unknown) {
  if (!(error instanceof HttpException) || ![400, 404, 409].includes(error.getStatus())) {
    throw error;
  }
  const details = error.getResponse();
  const code = typeof details === 'object' && details && 'code' in details
    ? String(details.code) : '';
  if (code === 'INCOMPATIBLE_EXERCISE_REPLACEMENT' && typeof details === 'object'
      && details && 'alternatives' in details && Array.isArray(details.alternatives)) {
    const names = details.alternatives.filter((name): name is string => typeof name === 'string');
    if (names.length)
      return 'Esse substituto não cumpre o mesmo papel no treino. Posso trocar por ' +
        names.join(', ') + '. Algum desses funciona para você?';
  }
  if (Object.hasOwn(plannerAlternatives, code)) return plannerAlternatives[code]!;
  return error.getStatus() === 409
    ? 'O calendário mudou ou o dia de destino está ocupado. Quer conferir os próximos dias livres?'
    : 'A troca não passou na validação do plano. Quer que eu procure uma alternativa para esse dia ou item?';
}

@Injectable()
export class CoachService {
  private readonly sessions = new Map<string, Session>();
  private readonly busy = new Set<string>();
  constructor(
    private readonly ai: CoachAiClient,
    private readonly context: CoachContextService,
    private readonly planner: PlannerAdjustmentsService,
    private readonly history: CoachHistoryService,
    private readonly account: CoachAccountService,
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
      previews: new Set(),
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
      const used = await this.history.contextUsed(user, token, sid);
      const nextUsage = used + contextUnits(dto.text);
      if (nextUsage > coachContextBudget)
        throw new ConflictException({
          code: 'COACH_CONVERSATION_LIMIT',
          message: 'Esta conversa chegou ao limite. Abra uma nova para continuar.',
        });
      const { local_date, ...message } = dto;
      const normalized = dto.text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
      const asksAboutHistory = !dto.proposal_id && /\b(?:historico|registr\w*|ultim[oa])\b/.test(normalized);
      const [accountContext, recalled] = await Promise.all([
        this.account.context(user, token, local_date, asksAboutHistory),
        dto.proposal_id ? null : this.history.recall(user, token, sid, dto.text),
      ]);
      let session = await this.runtime(user, token, sid);
      const snapshot = await this.context.build(user, token, session.selected, accountContext.day?.date ?? local_date);
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
          { ...message, account_context: accountContext, recalled_messages: recalled },
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
      result.conversation_memory = { used: nextUsage, limit: coachContextBudget };
      if (coachContextBudget - nextUsage < contextUnits('confirmo') &&
          result.actions.some((action) => record(action).status === 'pending_user_confirmation')) {
        result.actions.length = 0;
        result.answer = 'Esta conversa chegou ao limite. Faça esse pedido em uma nova conversa para poder revisar e confirmar a proposta.';
      }
      const memoryItem = result.memory_item;
      delete result.memory_item;
      if (typeof memoryItem === 'string' && accountContext.memory_enabled &&
          !dto.proposal_id && result.actions.length === 0 &&
          record(result.analysis).route === 'conversation' &&
          /^\s*(?:lembre|lembra|guarde|guarda|salve|salva|anote|anota)(?: na mem[oó]ria)? que /i.test(dto.text)) {
        result.answer = await this.account.save(user, token, memoryItem);
      }
      result.planner = { connected: true, writes_allowed: false };
      if (
        result.analysis &&
        typeof result.analysis === 'object' &&
        (result.analysis as Record<string, unknown>).route === 'privacy_information'
      ) {
        result.answer =
          'No aplicativo, suas conversas são salvas na sua conta para você retomar o histórico. ' +
          'Elas não entram automaticamente no treinamento do modelo. ' +
          'Pedir exclusão no chat não apaga dados. Use o histórico para excluir conversas e Conta → Memória do Coach para remover preferências.';
      }
      const previews: unknown[] = [];
      for (const raw of result.actions) {
        const action = record(raw);
        if (action.status === 'apply_requested_change') {
          result.actions = [];
          result.answer = 'Para mudar sua ficha, primeiro peça uma prévia para conferir o item e confirmar.';
          break;
        }
        if (action.status !== 'confirmed_for_planner_preview') continue;
        if (
          typeof action.id !== 'string' ||
          !isUUID(action.id) ||
          action.id !== dto.proposal_id ||
          !confirmations.has(normalized.replace(/[^\w]+/g, ' ').trim())
        ) {
          throw new BadGatewayException('COACH_INVALID_PROPOSAL');
        }
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
        const proposalId = action.id as string;
        const existing = await this.history.linked(user, token, sid, proposalId);
        if (existing) {
          previews.push(existing);
          continue;
        }
        if (session.previews.size >= 32)
          throw new HttpException('COACH_PREVIEW_CAPACITY', 429);
        const preview = await this.planner.preview(user, token, typed, {
          adjustmentId: messageId(user, sid, proposalId, 'planner-preview'),
          conversationId: sid,
          proposalId,
          expiresAt: action.expires_at,
        });
        if (!preview || typeof preview.id !== 'string' || !isUUID(preview.id))
          throw new BadGatewayException('COACH_INVALID_PREVIEW');
        session.previews.add(proposalId);
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
    return this.serial(sid, async () => {
      try {
        return await this.planner[operation](user, token, adjustment, sid);
      } catch (error) {
        if (!(error instanceof HttpException) || error.getStatus() !== 400) throw error;
        const details = error.getResponse();
        if (!details || typeof details !== 'object' || !('code' in details)
            || details.code !== 'ADJUSTMENT_NOT_ALLOWED') throw error;
        const stored = await this.planner.get(user, token, adjustment);
        if ((operation === 'apply' && stored.status === 'applied' && !stored.reverted_at) ||
            (operation === 'reject' && stored.status === 'rejected') ||
            (operation === 'revert' && stored.reverted_at)) return stored;
        throw error;
      }
    });
  }
}

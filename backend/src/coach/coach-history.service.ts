import {
  ConflictException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
  BadRequestException,
} from '@nestjs/common';
import { createHash } from 'node:crypto';
import { isUUID } from 'class-validator';
import type { Json, TablesInsert } from '../database/database.types.js';
import { SupabaseService } from '../supabase/supabase.service.js';
import type { CreateCoachSessionDto } from './dto/coach.dto.js';

export const coachContextBudget = 9_000;

export function contextUnits(text: string) {
  return Math.max(1, Math.ceil(text.trim().length / 4));
}

function words(text: string) {
  return text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
}

export function messageId(
  user: string,
  conversation: string,
  request: string,
  role: string,
) {
  const hex = createHash('sha256')
    .update(JSON.stringify([user, conversation, request, role]))
    .digest('hex')
    .slice(0, 32)
    .split('');
  hex[12] = '5';
  hex[16] = ((parseInt(hex[16]!, 16) & 3) | 8).toString(16);
  const s = hex.join('');
  return [
    s.slice(0, 8),
    s.slice(8, 12),
    s.slice(12, 16),
    s.slice(16, 20),
    s.slice(20),
  ].join('-');
}
export function minimizeHistoryText(text: string) {
  return text
    .replace(/[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}/g, '[EMAIL]')
    .replace(/\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b/g, '[CPF]')
    .replace(/https?:\/\/[^\s<>]+/g, '[LINK]')
    .replace(
      /(?:\+55\s*)?\(?[1-9]\d\)?[ .-]?9?\d{4}[ .-]?\d{4}\b/g,
      '[TELEFONE]',
    );
}
function object(value: Json | undefined): Record<string, Json | undefined> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value
    : {};
}
function db(error: unknown) {
  if (error) throw new ServiceUnavailableException('COACH_HISTORY_UNAVAILABLE');
}

@Injectable()
export class CoachHistoryService {
  constructor(private readonly supabase: SupabaseService) {}
  async create(user: string, token: string, selected: CreateCoachSessionDto) {
    const client = this.supabase.forUser(token);
    const { data, error } = await client
      .from('coach_conversations')
      .insert({
        user_id: user,
        entry_context: 'general',
      })
      .select('*')
      .single();
    db(error);
    if (!data)
      throw new ServiceUnavailableException('COACH_HISTORY_UNAVAILABLE');
    const configured = await client.from('coach_messages').insert({
      conversation_id: data.id,
      user_id: user,
      role: 'system',
      content: 'Configuração da conversa',
      metadata: {
        kind: 'conversation_config',
        selected: {
          workout_plan_id: selected.workout_plan_id ?? null,
          diet_plan_id: selected.diet_plan_id ?? null,
        },
      },
    });
    if (configured.error) {
      await client
        .from('coach_conversations')
        .delete()
        .eq('user_id', user)
        .eq('id', data.id);
      db(configured.error);
    }
    return data;
  }
  async get(user: string, token: string, id: string) {
    const client = this.supabase.forUser(token);
    const { data, error } = await client
      .from('coach_conversations')
      .select('*')
      .eq('user_id', user)
      .eq('id', id)
      .maybeSingle();
    db(error);
    if (!data) throw new NotFoundException('COACH_CONVERSATION_NOT_FOUND');
    const config = await client
      .from('coach_messages')
      .select('metadata')
      .eq('user_id', user)
      .eq('conversation_id', id)
      .eq('role', 'system')
      .contains('metadata', { kind: 'conversation_config' })
      .order('created_at')
      .limit(1)
      .maybeSingle();
    db(config.error);
    const raw = object(object(config.data?.metadata).selected);
    const selected: CreateCoachSessionDto = {};
    if (typeof raw.workout_plan_id === 'string' && isUUID(raw.workout_plan_id))
      selected.workout_plan_id = raw.workout_plan_id;
    if (typeof raw.diet_plan_id === 'string' && isUUID(raw.diet_plan_id))
      selected.diet_plan_id = raw.diet_plan_id;
    return { ...data, selected };
  }
  async list(user: string, token: string, limit = 30, offset = 0) {
    const { data, error } = await this.supabase
      .forUser(token)
      .from('coach_conversations')
      .select('*')
      .eq('user_id', user)
      .order('updated_at', { ascending: false })
      .order('id', { ascending: false })
      .range(offset, offset + limit - 1);
    db(error);
    return data ?? [];
  }
  async messages(
    user: string,
    token: string,
    id: string,
    limit = 50,
    offset = 0,
  ) {
    await this.get(user, token, id);
    const { data, error } = await this.supabase
      .forUser(token)
      .from('coach_messages')
      .select('id, conversation_id, role, content, created_at, metadata')
      .eq('user_id', user)
      .eq('conversation_id', id)
      .in('role', ['user', 'assistant'])
      .order('created_at', { ascending: false })
      .order('id', { ascending: false })
      .range(offset, offset + limit - 1);
    db(error);
    return data ?? [];
  }
  async recent(user: string, token: string, id: string) {
    const rows = await this.messages(user, token, id, 64);
    // Reconstruct complete pairs; never pass system config or executable proposals into the LM.
    const groups = new Map<string, typeof rows>();
    for (const row of rows) {
      const request = object(row.metadata).request_id;
      if (typeof request === 'string')
        groups.set(request, [...(groups.get(request) ?? []), row]);
    }
    let remaining = 24000;
    return [...groups.values()]
      .filter(
        (g) =>
          g.some((r) => r.role === 'user') &&
          g.some((r) => r.role === 'assistant'),
      )
      .filter((group) => {
        const size = group.reduce((total, row) => total + Math.min(row.content.length, 8000), 0);
        if (size > remaining) {
          remaining = 0;
          return false;
        }
        remaining -= size;
        return true;
      })
      .reverse()
      .flatMap((g, index, pairs) =>
        ['user', 'assistant'].map((role) => {
          const row = g.find((r) => r.role === role)!;
          const result = object(object(object(row.metadata).response).result);
          return {
            role,
            content: row.content.slice(0, 8000),
            ...(role === 'assistant' && index === pairs.length - 1
              ? { dialogue_context: result.dialogue_context }
              : {}),
          };
        }),
      );
  }

  async contextUsed(user: string, token: string, id: string) {
    const { data, error } = await this.supabase.forUser(token).from('coach_messages')
      .select('metadata').eq('user_id', user).eq('conversation_id', id).eq('role', 'assistant')
      .order('created_at', { ascending: false }).order('id', { ascending: false }).limit(1).maybeSingle();
    db(error);
    const result = object(object(object(data?.metadata).response).result);
    const usage = object(result.conversation_memory);
    if (usage.limit === coachContextBudget && typeof usage.used === 'number' &&
        Number.isSafeInteger(usage.used) && usage.used >= 0 && usage.used <= coachContextBudget)
      return usage.used;
    let used = 0;
    for await (const content of this.userTexts(user, token, id)) {
      used += contextUnits(content);
      if (used >= coachContextBudget) return coachContextBudget;
    }
    return used;
  }

  private async *userTexts(user: string, token: string, id: string) {
    const pageSize = 200;
    for (let offset = 0; ; offset += pageSize) {
      const { data, error } = await this.supabase.forUser(token).from('coach_messages')
        .select('content').eq('user_id', user).eq('conversation_id', id).eq('role', 'user')
        .order('created_at').order('id').range(offset, offset + pageSize - 1);
      db(error);
      for (const row of data ?? []) yield row.content;
      if ((data?.length ?? 0) < pageSize) return;
    }
  }

  async recall(user: string, token: string, id: string, text: string) {
    const normalized = words(text);
    const explicitRecall = /^(?:(?:lembra|lembre|me diga|me diz) )?o que (?:eu )?(?:te )?(?:falei|disse|comentei)\b/.test(normalized)
      || /^(?:me lembra|o que (?:voce )?lembra)\b.{0,60}\b(?:no|do) comeco d[oa] (?:chat|conversa)\b/.test(normalized);
    const factQuestion = /^(?:qual|quais|que dia|me lembra)\b.{0,85}\b(?:falei|disse|comentei)\b/.test(normalized);
    const field = factQuestion
      ? [
          [/\b(?:volto|voltar|retorno)\b/, /\b(?:volto|voltar|retorno)\b/],
          [/\b(?:equipamento|equipamentos)\b/, /\b(?:halter\w*|elastico\w*|faixa|esteira|barra)\b/],
          [/\b(?:horario|horarios|dias de treino|dias de academia)\b/, /\b(?:treino|academia)\b/],
        ].find(([question]) => question!.test(normalized))?.[1]
      : undefined;
    if (!explicitRecall && !field) return null;
    const subject = normalized.match(/\bsobre\s+(.+)/)?.[1] ?? '';
    const keywords = subject.match(/[a-z0-9]{3,}/g)?.filter((word) =>
      !['que', 'meu', 'minha', 'nosso', 'para', 'mesmo', 'essa', 'esse'].includes(word)) ?? [];
    const fromStart = !keywords.length && /\b(?:no|do) comeco\b/.test(normalized);
    const relevant: string[] = [];
    for await (const row of this.userTexts(user, token, id)) {
      const content = words(row);
      if (field ? field.test(content) : (!keywords.length || keywords.some((word) => content.includes(word)) ||
          (keywords.includes('objetivo') && /\b(?:meu objetivo|minha meta|quero (?:ganhar|perder|melhorar))\b/.test(content)))) {
        relevant.push(minimizeHistoryText(row).slice(0, 300));
        if (fromStart && relevant.length === 3) break;
        if (relevant.length > 3) relevant.shift();
      }
    }
    return relevant;
  }
  async cached(
    user: string,
    token: string,
    id: string,
    request: string,
    hash: string,
  ) {
    const { data, error } = await this.supabase
      .forUser(token)
      .from('coach_messages')
      .select('metadata')
      .eq('user_id', user)
      .eq('conversation_id', id)
      .eq('id', messageId(user, id, request, 'assistant'))
      .maybeSingle();
    db(error);
    if (!data) return null;
    const meta = object(data.metadata);
    if (meta.input_hash !== hash)
      throw new ConflictException('COACH_REQUEST_ID_CONFLICT');
    return meta.response as Record<string, unknown>;
  }
  async commit(
    user: string,
    token: string,
    id: string,
    request: string,
    hash: string,
    input: string,
    response: Record<string, unknown>,
  ) {
    const result = response.result as Record<string, unknown>;
    const answer = minimizeHistoryText(String(result.answer));
    const stored = { ...response, result: { ...result, answer } };
    const stamp = Date.now();
    const rows: TablesInsert<'coach_messages'>[] = [
      {
        id: messageId(user, id, request, 'user'),
        user_id: user,
        conversation_id: id,
        role: 'user',
        content: minimizeHistoryText(input),
        created_at: new Date(stamp).toISOString(),
        metadata: { request_id: request, input_hash: hash },
      },
      {
        id: messageId(user, id, request, 'assistant'),
        user_id: user,
        conversation_id: id,
        role: 'assistant',
        content: answer,
        created_at: new Date(stamp + 1).toISOString(),
        metadata: {
          request_id: request,
          input_hash: hash,
          response: stored as unknown as Json,
        },
      },
    ];
    // One PostgREST INSERT/upsert statement: either the batch succeeds or it rolls back.
    const { error } = await this.supabase
      .forUser(token)
      .from('coach_messages')
      .upsert(rows, { onConflict: 'id', ignoreDuplicates: true });
    db(error);
    const touched = await this.supabase
      .forUser(token)
      .from('coach_conversations')
      .update({ updated_at: new Date(stamp + 1).toISOString() })
      .eq('id', id)
      .eq('user_id', user);
    db(touched.error);
    const saved = await this.cached(user, token, id, request, hash);
    if (!saved)
      throw new ServiceUnavailableException('COACH_HISTORY_NOT_COMMITTED');
    return saved;
  }
  async remove(user: string, token: string, id: string) {
    await this.get(user, token, id);
    const { error } = await this.supabase
      .forUser(token)
      .from('coach_conversations')
      .delete()
      .eq('id', id)
      .eq('user_id', user);
    db(error);
  }
  async rename(user: string, token: string, id: string, title: string) {
    await this.get(user, token, id);
    const clean = minimizeHistoryText(title).trim();
    if (!clean) throw new BadRequestException('COACH_TITLE_REQUIRED');
    const { data, error } = await this.supabase
      .forUser(token)
      .from('coach_conversations')
      .update({ title: clean })
      .eq('id', id)
      .eq('user_id', user)
      .select('*')
      .single();
    db(error);
    return data;
  }
  async linked(user: string, token: string, id: string, proposal: string) {
    const { data, error } = await this.supabase
      .forUser(token)
      .from('planner_adjustments')
      .select('*')
      .eq('user_id', user)
      .eq('conversation_id', id)
      .eq('source', 'coach')
      .contains('requested_change', { coach_proposal_id: proposal })
      .limit(2);
    db(error);
    if ((data?.length ?? 0) > 1)
      throw new ConflictException('COACH_DUPLICATE_PREVIEWS');
    return data?.[0] ?? null;
  }
  async adjustment(
    user: string,
    token: string,
    id: string,
    adjustment: string,
  ) {
    const { data, error } = await this.supabase
      .forUser(token)
      .from('planner_adjustments')
      .select('id')
      .eq('id', adjustment)
      .eq('user_id', user)
      .eq('conversation_id', id)
      .eq('source', 'coach')
      .maybeSingle();
    db(error);
    if (!data) throw new NotFoundException('COACH_ADJUSTMENT_NOT_FOUND');
  }
}

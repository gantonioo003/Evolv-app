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
        title: 'Nova conversa',
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
    const rows = await this.messages(user, token, id, 16);
    // Reconstruct complete pairs; never pass system config or executable proposals into the LM.
    const groups = new Map<string, typeof rows>();
    for (const row of rows) {
      const request = object(row.metadata).request_id;
      if (typeof request === 'string')
        groups.set(request, [...(groups.get(request) ?? []), row]);
    }
    return [...groups.values()]
      .filter(
        (g) =>
          g.some((r) => r.role === 'user') &&
          g.some((r) => r.role === 'assistant'),
      )
      .slice(0, 4)
      .reverse()
      .flatMap((g) =>
        ['user', 'assistant'].map((role) => ({
          role,
          content: g.find((r) => r.role === role)!.content.slice(0, 8000),
        })),
      );
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
      .contains('requested_change', { coach_proposal_id: proposal })
      .limit(2);
    db(error);
    if ((data?.length ?? 0) > 1)
      throw new ConflictException('COACH_DUPLICATE_PREVIEWS');
    return data?.[0] ?? null;
  }
  async link(
    user: string,
    token: string,
    id: string,
    proposal: string,
    adjustment: string,
    payload: Record<string, unknown>,
  ) {
    const { data, error } = await this.supabase
      .forUser(token)
      .from('planner_adjustments')
      .update({
        conversation_id: id,
        requested_change: { ...payload, coach_proposal_id: proposal } as Json,
      })
      .eq('id', adjustment)
      .eq('user_id', user)
      .eq('source', 'coach')
      .select('*')
      .single();
    db(error);
    return data;
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
      .maybeSingle();
    db(error);
    if (!data) throw new NotFoundException('COACH_ADJUSTMENT_NOT_FOUND');
  }
}

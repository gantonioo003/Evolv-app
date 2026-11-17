import { Injectable, ServiceUnavailableException } from '@nestjs/common';
import { SupabaseService } from '../supabase/supabase.service.js';
import { PlannerDayContextService } from '../planner/planner-day-context.service.js';
import { messageId, minimizeHistoryText } from './coach-history.service.js';

const memoryLimit = 100;

@Injectable()
export class CoachAccountService {
  constructor(
    private readonly supabase: SupabaseService,
    private readonly plannerDay: PlannerDayContextService,
  ) {}

  async context(user: string, token: string, localDate?: string, includeExerciseLogs = false) {
    const today = localDate ?? new Date().toISOString().slice(0, 10);
    const client = this.supabase.forUser(token);
    const [profile, goal, day, logs] = await Promise.all([
      client
        .from('profiles')
        .select(
          'birth_date, height_cm, current_weight_kg, training_level, available_training_days, preferred_training_time, disliked_foods, coach_memory_enabled',
        )
        .eq('id', user)
        .maybeSingle(),
      client
        .from('goals')
        .select('type')
        .eq('user_id', user)
        .eq('is_active', true)
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle(),
      this.plannerDay.get(token, today),
      includeExerciseLogs ? client
        .from('exercise_logs')
        .select('performed_at, load_kg, sets_completed, reps_summary, exercises(name)')
        .eq('user_id', user)
        .order('performed_at', { ascending: false })
        .order('created_at', { ascending: false })
        .order('id', { ascending: false })
        .limit(60) : { data: [], error: null },
    ]);
    if (profile.error || goal.error || logs.error) this.unavailable();
    const p = profile.data;
    const enabled = p?.coach_memory_enabled ?? false;
    const birth = p?.birth_date;
    const age =
      birth && birth <= today
        ? Number(today.slice(0, 4)) -
          Number(birth.slice(0, 4)) -
          Number(today.slice(5) < birth.slice(5))
        : null;
    return {
      memory_enabled: enabled,
      memories: enabled
        ? (await this.list(user, token)).map(({ content }) =>
            minimizeHistoryText(content).slice(0, 180),
          )
        : [],
      age,
      height_cm: p?.height_cm ?? null,
      weight_kg: p?.current_weight_kg ?? null,
      level: p?.training_level ?? null,
      training_days: p?.available_training_days ?? [],
      training_time: p?.preferred_training_time?.slice(0, 5) ?? null,
      disliked_foods: (p?.disliked_foods ?? [])
        .slice(0, 20)
        .map((s) => minimizeHistoryText(s).slice(0, 120)),
      goal: goal.data?.type ?? null,
      day: {
        date: day.activity_date,
        source: day.source,
        activity_type: day.activity_type,
        nutrition_day_type: day.nutrition_day_type,
        workout_day_id: day.workout_day_id,
      },
      exercise_logs: (logs.data ?? []).flatMap((log) => {
        if (!log.exercises?.name) return [];
        const summary = log.reps_summary?.trim();
        const repetitions = summary?.match(/^([1-9]\d{0,3})(?:\s+(?:reps|repetiç(?:ão|ões)))?$/i);
        const duration = summary?.match(/^([1-9]\d{0,4})\s*(?:s|segundos?)$/i);
        const reps = repetitions ? Number(repetitions[1]) : null;
        const seconds = duration ? Number(duration[1]) : null;
        return [{
          exercise: log.exercises.name.slice(0, 200),
          date: log.performed_at.slice(0, 10),
          repetitions: reps && reps <= 1000 ? reps : null,
          duration_seconds: seconds && seconds <= 86400 ? seconds : null,
          load_kg: log.load_kg,
          sets_completed: log.sets_completed,
        }];
      }),
    };
  }

  async list(user: string, token: string) {
    const { data, error } = await this.supabase
      .forUser(token)
      .from('coach_memory_items')
      .select('id, category, content')
      .eq('user_id', user)
      .eq('is_active', true)
      .order('updated_at', { ascending: false })
      .limit(memoryLimit);
    if (error) this.unavailable();
    return data ?? [];
  }

  async save(user: string, token: string, input: string) {
    const content = input.trim().replace(/\s+/g, ' ');
    if (
      content.length < 8 ||
      content.length > 180 ||
      minimizeHistoryText(content) !== content
    )
      return 'Consigo guardar preferências e hábitos de treino ou alimentação. Tente resumir em uma frase.';
    const category = /^(treino|pratico|costumo)\b/i.test(content)
      ? 'routine'
      : 'preference';
    const id = messageId(
      user,
      'account-memory',
      content.toLowerCase(),
      category,
    );
    const items = await this.list(user, token);
    if (items.some((item) => item.id === id))
      return 'Essa informação já está na sua memória do Coach.';
    if (items.length >= memoryLimit)
      return 'Sua memória entre conversas está cheia. Você pode remover um item em Conta → Memória do Coach.';
    const { error } = await this.supabase
      .forUser(token)
      .from('coach_memory_items')
      .upsert(
        {
          id,
          user_id: user,
          category,
          content,
          is_active: true,
        },
        { onConflict: 'id' },
      );
    if (error) this.unavailable();
    return 'Guardei isso na memória do Coach para usar em outras conversas.';
  }

  async remove(user: string, token: string, id: string) {
    const { error } = await this.supabase
      .forUser(token)
      .from('coach_memory_items')
      .delete()
      .eq('user_id', user)
      .eq('id', id);
    if (error) this.unavailable();
    return { removed: true };
  }

  private unavailable(): never {
    throw new ServiceUnavailableException('COACH_ACCOUNT_CONTEXT_UNAVAILABLE');
  }
}

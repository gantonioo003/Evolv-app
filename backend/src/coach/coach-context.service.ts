import {
  BadRequestException,
  Injectable,
  ServiceUnavailableException,
} from '@nestjs/common';
import { createHash } from 'node:crypto';
import { weekDates, weekOverrides } from '../planner/planner-day-context.service.js';
import { PlannerService } from '../planner/planner.service.js';
import { NutritionPlannerService } from '../planner/nutrition-planner.service.js';
import { parseSubstitutions } from '../planner/planner-adjustments.service.js';
import { SupabaseService } from '../supabase/supabase.service.js';
import type { CreateCoachSessionDto } from './dto/coach.dto.js';
@Injectable()
export class CoachContextService {
  constructor(
    private readonly workouts: PlannerService,
    private readonly nutrition: NutritionPlannerService,
    private readonly supabase: SupabaseService,
  ) {}
  async build(userId: string, token: string, selected: CreateCoachSessionDto, localDate?: string) {
    const activeWorkouts = selected.workout_plan_id
      ? []
      : await this.workouts.listPlans(userId, token, {
          status: 'active',
          limit: 2,
        });
    const activeDiets = selected.diet_plan_id
      ? []
      : await this.nutrition.listPlans(userId, token, {
          status: 'active',
          limit: 2,
        });
    if ((activeWorkouts?.length ?? 0) > 1 || (activeDiets?.length ?? 0) > 1)
      throw new BadRequestException('COACH_PLAN_SELECTION_REQUIRED');
    const workoutId = selected.workout_plan_id ?? activeWorkouts?.[0]?.id;
    const dietId = selected.diet_plan_id ?? activeDiets?.[0]?.id;
    const workout = workoutId
      ? await this.workouts.getPlan(userId, token, workoutId)
      : null;
    const diet = dietId
      ? await this.nutrition.getPlan(userId, token, dietId)
      : null;
    if (
      (workout && workout.status !== 'active') ||
      (diet && diet.status !== 'active')
    )
      throw new BadRequestException('COACH_ACTIVE_PLAN_REQUIRED');
    const client = this.supabase.forUser(token);
    const exercises = workout
      ? await client
          .from('exercises')
          .select('id, name')
          .order('id')
          .limit(1000)
      : { data: [], error: null };
    const foods = diet
      ? await client.from('foods').select('id, name').order('id').limit(1000)
      : { data: [], error: null };
    if (exercises.error || foods.error)
      throw new ServiceUnavailableException('COACH_CONTEXT_UNAVAILABLE');
    if (
      (exercises.data?.length ?? 0) >= 1000 ||
      (foods.data?.length ?? 0) >= 1000
    )
      throw new BadRequestException('COACH_CATALOG_REQUIRES_PAGINATION');
    const dates = localDate && workout ? weekDates(localDate) : [];
    if (localDate && dates[6] === localDate) {
      const nextDay = new Date(localDate + 'T00:00:00Z');
      nextDay.setUTCDate(nextDay.getUTCDate() + 1);
      dates.push(nextDay.toISOString().slice(0, 10));
    }
    const overrides = dates.length ? await weekOverrides(this.supabase, token, userId, dates) : [];
    const weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    const titles: Record<string, string> = { rest: 'Descanso', resistance: 'Musculação', cardio: 'Cardio', mixed: 'Treino misto' };
    const week = dates.map((date, index) => {
      const override = overrides.find((item) => item.activity_date === date);
      const active = workout && date >= workout.start_date && (!workout.end_date || date <= workout.end_date);
      const day = active && workout.workout_days.find((item) => override
        ? item.id === override.workout_day_id : item.weekday === weekdays[index % weekdays.length]);
      const activity = override?.activity_type ?? (day ? 'resistance' : 'rest');
      return {
        date, activity_type: activity,
        workout_day_id: activity !== 'rest' && day ? day.id : null,
        title: activity === 'rest' ? titles.rest : (day ? day.title : (titles[activity] ?? 'Treino')),
      };
    });
    const named = (row: { id: string; name: string }) => ({
      id: row.id,
      canonical: row.name,
    });
    return {
      actor_id: userId,
      revision: createHash('sha256')
        .update(
          JSON.stringify({
            workout,
            week,
            diet,
            exercises: exercises.data,
            foods: foods.data,
          }),
        )
        .digest('hex'),
      workout_plan_id: workout?.id ?? null,
      diet_plan_id: diet?.id ?? null,
      workout_start: workout?.start_date ?? null,
      workout_end: workout?.end_date ?? null,
      diet_variants: diet?.uses_day_variants ?? false,
      diet_rotation_size: diet?.menu_rotation_enabled ? diet.menu_rotation_size : 1,
      week,
      days:
        workout?.workout_days.map((d) => ({ id: d.id, weekday: d.weekday, title: d.title })) ??
        [],
      workout_exercises:
        workout?.workout_days.flatMap((d) =>
          d.workout_day_exercises.flatMap((e) =>
            e.exercises
              ? [
                  {
                    id: e.id,
                    workout_day_id: d.id,
                    canonical: e.exercises.name,
                    display_name: e.exercises.name,
                    equipment: e.exercises.equipment ?? null,
                    muscle_group: e.exercises.muscle_group ?? null,
                    sets: e.sets ?? null,
                    rest_seconds: e.rest_seconds ?? null,
                    min_reps: e.min_reps ?? null,
                    max_reps: e.max_reps ?? null,
                    instructions: e.exercises.instructions?.slice(0, 500) ?? null,
                  },
                ]
              : [],
          ),
        ) ?? [],
      exercises: (exercises.data ?? []).map(named),
      meal_items:
        diet?.meals.flatMap((m) =>
          m.meal_items.flatMap((i) => {
            if (!i.foods) return [];
            const approved = parseSubstitutions(i.substitutions);
            return [{
              id: i.id,
              canonical: i.foods.name,
              meal_name: m.name,
              meal_position: m.position,
              day_type: m.day_type,
              rotation_index: m.rotation_index,
              amount: (i.amount?.trim() || (i.quantity != null && i.unit ? `${i.quantity} ${i.unit}` : '')).slice(0, 120) || null,
              approved_replacement_ids: approved.map((item) => item.food_id),
              approved_replacement_portions: approved.map((item) => ({
                food_id: item.food_id,
                amount: `${item.amount} ${item.unit}`.slice(0, 120),
              })),
            }];
          }),
        ) ?? [],
      foods: (foods.data ?? []).map(named),
    };
  }
}

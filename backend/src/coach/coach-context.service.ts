import {
  BadRequestException,
  Injectable,
  ServiceUnavailableException,
} from '@nestjs/common';
import { createHash } from 'node:crypto';
import { PlannerService } from '../planner/planner.service.js';
import { NutritionPlannerService } from '../planner/nutrition-planner.service.js';
import { SupabaseService } from '../supabase/supabase.service.js';
import type { CreateCoachSessionDto } from './dto/coach.dto.js';
@Injectable()
export class CoachContextService {
  constructor(
    private readonly workouts: PlannerService,
    private readonly nutrition: NutritionPlannerService,
    private readonly supabase: SupabaseService,
  ) {}
  async build(userId: string, token: string, selected: CreateCoachSessionDto) {
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
            diet,
            exercises: exercises.data,
            foods: foods.data,
          }),
        )
        .digest('hex'),
      workout_plan_id: workout?.id ?? null,
      diet_plan_id: diet?.id ?? null,
      days:
        workout?.workout_days.map((d) => ({ id: d.id, weekday: d.weekday })) ??
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
                  },
                ]
              : [],
          ),
        ) ?? [],
      exercises: (exercises.data ?? []).map(named),
      meal_items:
        diet?.meals.flatMap((m) =>
          m.meal_items.flatMap((i) =>
            i.foods ? [{ id: i.id, canonical: i.foods.name }] : [],
          ),
        ) ?? [],
      foods: (foods.data ?? []).map(named),
    };
  }
}

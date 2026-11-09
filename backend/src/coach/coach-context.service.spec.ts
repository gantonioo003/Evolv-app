import { randomUUID } from 'node:crypto';
import type { PlannerService } from '../planner/planner.service.js';
import type { NutritionPlannerService } from '../planner/nutrition-planner.service.js';
import type { SupabaseService } from '../supabase/supabase.service.js';
import { CoachContextService } from './coach-context.service.js';

describe('CoachContextService', () => {
  function setup() {
    const user = randomUUID(),
      plan = randomUUID(),
      day = randomUUID();
    const workout = {
      id: plan,
      status: 'active',
      workout_days: [
        {
          id: day,
          weekday: 'tuesday',
          workout_day_exercises: [
            { id: randomUUID(), exercises: { name: 'Supino reto' }, sets: 3 },
          ],
        },
      ],
    };
    const workouts = {
      listPlans: vi.fn().mockResolvedValue([{ id: plan }]),
      getPlan: vi.fn().mockResolvedValue(workout),
    };
    const nutrition = {
      listPlans: vi.fn().mockResolvedValue([]),
      getPlan: vi.fn(),
    };
    const result = {
      data: [{ id: randomUUID(), name: 'Flexao de bracos' }],
      error: null as unknown,
    };
    const chain = {
      select: vi.fn().mockReturnThis(),
      order: vi.fn().mockReturnThis(),
      limit: vi.fn().mockResolvedValue(result),
    };
    const client = { from: vi.fn().mockReturnValue(chain) };
    const supabase = { forUser: vi.fn().mockReturnValue(client) };
    return {
      user,
      plan,
      workout,
      workouts,
      nutrition,
      result,
      supabase,
      service: new CoachContextService(
        workouts as unknown as PlannerService,
        nutrition as unknown as NutritionPlannerService,
        supabase as unknown as SupabaseService,
      ),
    };
  }
  it('busca propriedade via servicos e usa apenas token do usuario', async () => {
    const t = setup();
    const snapshot = await t.service.build(t.user, 'user-jwt', {});
    expect(t.workouts.getPlan).toHaveBeenCalledWith(t.user, 'user-jwt', t.plan);
    expect(t.supabase.forUser).toHaveBeenCalledWith('user-jwt');
    expect(snapshot.actor_id).toBe(t.user);
    expect(snapshot.workout_exercises[0]?.canonical).toBe('Supino reto');
    expect(snapshot).not.toHaveProperty('token');
  });
  it('mudanca no conteudo do plano muda a revisao', async () => {
    const t = setup();
    const a = await t.service.build(t.user, 'jwt', {});
    t.workout.workout_days[0]!.workout_day_exercises[0]!.sets = 5;
    const b = await t.service.build(t.user, 'jwt', {});
    expect(a.revision).not.toBe(b.revision);
  });
  it('recusa varios ativos em vez de escolher arbitrariamente', async () => {
    const t = setup();
    t.workouts.listPlans.mockResolvedValue([
      { id: t.plan },
      { id: randomUUID() },
    ]);
    await expect(t.service.build(t.user, 'jwt', {})).rejects.toMatchObject({
      status: 400,
    });
  });
  it('recusa plano inativo e erro de catalogo', async () => {
    const t = setup();
    t.workout.status = 'archived';
    await expect(t.service.build(t.user, 'jwt', {})).rejects.toMatchObject({
      status: 400,
    });
    t.workout.status = 'active';
    t.result.error = { message: 'private' };
    await expect(t.service.build(t.user, 'jwt', {})).rejects.toMatchObject({
      status: 503,
    });
  });
});

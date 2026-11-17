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
      eq: vi.fn().mockReturnThis(),
      in: vi.fn().mockResolvedValue({ data: [], error: null }),
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
      chain,
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
  it('envia o nome da refeicao junto do alimento para identificar a troca', async () => {
    const t = setup();
    const diet = randomUUID();
    const option = randomUUID();
    t.nutrition.listPlans.mockResolvedValue([{ id: diet }]);
    t.nutrition.getPlan.mockResolvedValue({
      id: diet,
      status: 'active',
      meals: [
        {
          name: 'Cafe da manha',
          meal_items: [{
            id: randomUUID(), foods: { name: 'Ovo' }, quantity: 90, unit: 'g',
            substitutions: [{ food_id: option, name: 'Tofu', amount: 100, unit: 'g', nutrition: {} }],
          }],
        },
      ],
    });
    const snapshot = await t.service.build(t.user, 'jwt', {});
    expect(snapshot.meal_items[0]).toMatchObject({
      canonical: 'Ovo',
      meal_name: 'Cafe da manha',
      amount: '90 g',
      approved_replacement_ids: [option],
      approved_replacement_portions: [{ food_id: option, amount: '100 g' }],
    });
  });
  it('mudanca no conteudo do plano muda a revisao', async () => {
    const t = setup();
    const a = await t.service.build(t.user, 'jwt', {});
    t.workout.workout_days[0]!.workout_day_exercises[0]!.sets = 5;
    const b = await t.service.build(t.user, 'jwt', {});
    expect(a.revision).not.toBe(b.revision);
  });
  it('inclui a atividade de amanhã na virada da semana com a remarcação do calendário', async () => {
    const t = setup();
    const workout = { ...t.workout, start_date: '2026-11-01' };
    t.workouts.getPlan.mockResolvedValue(workout);
    t.chain.in.mockResolvedValue({
      data: [{
        activity_date: '2026-11-16',
        activity_type: 'resistance',
        workout_day_id: workout.workout_days[0]!.id,
      }],
      error: null,
    });
    const snapshot = await t.service.build(t.user, 'jwt', {}, '2026-11-15');
    expect(snapshot.week).toHaveLength(8);
    expect(t.chain.in).toHaveBeenCalledWith('activity_date', snapshot.week.map(day => day.date));
    expect(snapshot.week[7]).toMatchObject({
      date: '2026-11-16',
      workout_day_id: workout.workout_days[0]!.id,
    });
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

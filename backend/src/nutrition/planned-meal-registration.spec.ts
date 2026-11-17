import { randomUUID } from 'node:crypto';
import { coachDatabase } from '../../test/fixtures/coach-postgres.js';
import { calculateNutritionSummary } from './nutrition-summary.js';

it('stores the planned portions once and removes only the matching daily record', async () => {
  const { db, user } = await coachDatabase({ product: true });
  try {
    const owner = randomUUID();
    const otherUser = randomUUID();
    await user(owner);
    await user(otherUser);
    const plan = randomUUID();
    const meal = randomUUID();
    const secondMeal = randomUUID();
    const legacyMeal = randomUUID();
    const legacyLog = randomUUID();
    const loggedAt = '2026-11-11T01:00:00Z';
    const localDate = '2026-11-10';

    await db.query(
      "insert into diet_plans(id, user_id, name, status) values ($1, $2, 'Plano', 'active')",
      [plan, owner],
    );
    await db.query(
      "insert into meals(id, diet_plan_id, name, position) values ($1, $4, 'Principal', 0), ($2, $4, 'Principal', 1), ($3, $4, 'Antiga', 2)",
      [meal, secondMeal, legacyMeal, plan],
    );
    await db.query(
      `insert into meal_items(meal_id, name, quantity, unit, calories_kcal, protein_g, carbohydrate_g, fat_g, fiber_g)
       values ($1, 'Arroz', 150, 'g', 195, 4.05, 42.3, 0.45, 0.6),
              ($1, 'Ovo', 1, 'unidade', 75, 6, 0.5, 5, 0),
              ($2, 'Batata', 100, 'g', 80, 2, 18, 0, 2),
              ($3, 'Alimento sem porção', null, null, null, null, null, null, null)`,
      [meal, secondMeal, legacyMeal],
    );
    await db.query(
      "insert into food_logs(id, user_id, meal_name, description, logged_at) values ($1, $2, 'Principal', 'Registro antigo', $3)",
      [legacyLog, owner, loggedAt],
    );

    const register = (who: string, mealId: string, registered: boolean, date = localDate) =>
      db.transaction(async (tx) => {
        await tx.query("select set_config('request.jwt.claim.sub', $1, true)", [who]);
        await tx.exec('set local role authenticated');
        const result = await tx.query<{ registered: boolean }>(
          'select public.set_planned_meal_registration($1, $2, $3, $4) as registered',
          [mealId, date, loggedAt, registered],
        );
        return result.rows[0].registered;
      });
    const items = async () =>
      (await db.query<Parameters<typeof calculateNutritionSummary>[0][number]>(
        'select calories_kcal, protein_g, carbohydrate_g, fat_g, fiber_g from food_log_items where user_id = $1',
        [owner],
      )).rows;

    await expect(register(otherUser, meal, true)).rejects.toThrow('PLANNED_MEAL_NOT_FOUND');
    await expect(register(owner, legacyMeal, true)).rejects.toThrow('MEAL_PORTIONS_UNAVAILABLE');
    expect((await db.query('select id from food_logs')).rows).toEqual([{ id: legacyLog }]);

    await expect(Promise.all([register(owner, meal, true), register(owner, meal, true)]))
      .resolves.toEqual([true, true]);
    expect(calculateNutritionSummary(await items())).toEqual({
      items: 2, calories_kcal: 270, protein_g: 10.05, carbohydrate_g: 42.8, fat_g: 5.45, fiber_g: 0.6,
    });
    await expect(register(owner, secondMeal, true)).resolves.toBe(true);
    await db.query('update meal_items set calories_kcal = 999 where meal_id = $1', [meal]);
    await expect(register(owner, meal, true)).resolves.toBe(true);
    await expect(register(otherUser, meal, false)).resolves.toBe(false);
    expect(calculateNutritionSummary(await items()).calories_kcal).toBe(350);

    await expect(register(owner, meal, false, '2026-11-11')).resolves.toBe(false);
    expect(calculateNutritionSummary(await items()).calories_kcal).toBe(350);
    await expect(register(owner, meal, false)).resolves.toBe(false);
    await expect(register(owner, meal, false)).resolves.toBe(false);
    expect(calculateNutritionSummary(await items()).calories_kcal).toBe(80);
    expect((await db.query('select id from food_logs where planned_meal_id is null')).rows)
      .toEqual([{ id: legacyLog }]);
  } finally {
    await db.close();
  }
}, 30_000);

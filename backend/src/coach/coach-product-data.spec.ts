import { randomUUID } from 'node:crypto';
import { writeFileSync } from 'node:fs';
import { coachDatabase } from '../../test/fixtures/coach-postgres.js';
import { CoachAccountService } from './coach-account.service.js';
import { CoachContextService } from './coach-context.service.js';
import { NutritionPlannerService } from '../planner/nutrition-planner.service.js';
import { PlannerDayContextService } from '../planner/planner-day-context.service.js';
import { PlannerService } from '../planner/planner.service.js';
import type { SupabaseService } from '../supabase/supabase.service.js';
import { WorkoutsService } from '../workouts/workouts.service.js';
import { CreateExerciseLogDto } from '../workouts/dto/exercise-log.dto.js';
import { validate } from 'class-validator';

const date = '2026-11-10';

it('persiste planos, contexto do dia e registros em PostgreSQL com isolamento por conta', async () => {
  const { db, supabase, user } = await coachDatabase({ product: true });
  try {
    const a = randomUUID(),
      b = randomUUID(),
      empty = randomUUID();
    await user(a);
    await user(b);
    await user(empty);
    await db.query(
      'insert into profiles(id, current_weight_kg, available_training_days) values ($1, $2, $3), ($4, $5, $6)',
      [a, 73, '{tuesday}', b, 99, '{tuesday}'],
    );
    const sql = async (statement: string, values: unknown[]) =>
      (await db.query<{ id: string }>(statement + ' returning id', values))
        .rows[0]!.id;
    const exercise = async (name: string, equipment: string) =>
      sql(
        'insert into exercises (name, muscle_group, equipment) values ($1, $2, $3)',
        [name, 'upper_back', equipment],
      );
    const row = await exercise('Remada cavalinho', 'landmine');
    const pushup = await exercise('Flexão declinada', 'bodyweight');
    const plank = await exercise('Prancha', 'bodyweight');
    const foreignExercise = await exercise('Exercício isolado B', 'dumbbell');
    const workout = async (owner: string, name: string, exerciseId: string) => {
      const plan = await sql(
        "insert into workout_plans(user_id, name, status, start_date, weekly_frequency) values ($1, $2, 'active', $3, 1)",
        [owner, name, date],
      );
      const day = await sql(
        "insert into workout_days(workout_plan_id, weekday, title, focus) values ($1, 'tuesday', $2, 'Costas')",
        [plan, name],
      );
      await db.query(
        'insert into workout_day_exercises(workout_day_id, exercise_id, sets, min_reps, max_reps) values ($1, $2, 3, 8, 12)',
        [day, exerciseId],
      );
      return { plan, day };
    };
    const aPlan = await workout(a, 'Treino A', row);
    const bPlan = await workout(b, 'Treino B', foreignExercise);
    const diet = await sql(
      "insert into diet_plans(user_id, name, status, uses_day_variants, menu_rotation_enabled, menu_rotation_size) values ($1, 'Cardápio A', 'active', true, true, 2)",
      [a],
    );
    const rotation = Math.floor(Date.parse(date) / 86_400_000) % 2;
    const meal = async (kind: string, menu: number, foodName: string) => {
      const food = await sql(
        'insert into foods (name, calories_kcal) values ($1, 100)',
        [foodName],
      );
      const m = await sql(
        'insert into meals (diet_plan_id, name, position, day_type, rotation_index) values ($1, $2, 0, $3, $4)',
        [diet, 'Café da manhã', kind, menu],
      );
      await db.query(
        'insert into meal_items (meal_id, name, amount, food_id) values ($1, $2, $3, $4)',
        [m, foodName, '1 porção', food],
      );
    };
    await meal('training_day', rotation, 'Aveia');
    await meal('rest_day', rotation, 'Iogurte');
    await meal('rest_day', 1 - rotation, 'Pão');
    const client = supabase as unknown as SupabaseService;
    const calendar = new PlannerDayContextService(client);
    const profiles = new CoachAccountService(client, calendar);
    const plans = new CoachContextService(
      new PlannerService(client),
      new NutritionPlannerService(client),
      client,
    );
    const workouts = new WorkoutsService(client);
    const snapshot = await plans.build(a, a, {});
    expect(snapshot).toMatchObject({
      actor_id: a,
      workout_plan_id: aPlan.plan,
      diet_plan_id: diet,
      diet_rotation_size: 2,
    });
    expect(snapshot.workout_exercises.map((item) => item.canonical)).toEqual([
      'Remada cavalinho',
    ]);
    expect(snapshot.meal_items).toHaveLength(3);
    await expect(
      plans.build(a, a, { workout_plan_id: bPlan.plan }),
    ).rejects.toMatchObject({ status: 404 });
    await expect(
      plans.build(b, b, { diet_plan_id: diet }),
    ).rejects.toMatchObject({ status: 404 });

    const performed_at = date + 'T12:00:00Z';
    const loaded = await workouts.createExerciseLog(a, a, row, {
      load_kg: 32.5,
      repetitions: 10,
      performed_at,
      notes: 'não enviar ao Coach',
    });
    const bodyweight = await workouts.createExerciseLog(a, a, pushup, {
      repetitions: 12,
      performed_at,
    });
    const timed = await workouts.createExerciseLog(a, a, plank, {
      duration_seconds: 45,
      load_kg: 2.5,
      performed_at,
    });
    const legacy = await workouts.createExerciseLog(a, a, row, {
      reps_summary: '8',
      load_kg: 27.5,
      performed_at: date + 'T10:00:00Z',
    });
    await workouts.createExerciseLog(b, b, row, {
      load_kg: 90,
      repetitions: 2,
      performed_at,
    });
    expect([
      loaded.reps_summary,
      bodyweight.reps_summary,
      timed.reps_summary,
      legacy.reps_summary,
    ]).toEqual(['10 reps', '12 reps', '45 s', '8']);
    expect(bodyweight.load_kg).toBeNull();
    expect(timed.load_kg).toBe(2.5);
    await expect(
      workouts.createExerciseLog(a, a, plank, {
        repetitions: 2,
        duration_seconds: 50,
      }),
    ).rejects.toMatchObject({ status: 400 });
    expect(
      await validate(
        Object.assign(new CreateExerciseLogDto(), { duration_seconds: 1.5 }),
      ),
    ).not.toHaveLength(0);
    expect(
      await validate(
        Object.assign(new CreateExerciseLogDto(), {
          repetitions: 12,
          load_kg: 32.5,
        }),
      ),
    ).toHaveLength(0);
    expect(
      (await workouts.getExerciseHistory(a, a, row, 10)).map(
        (log) => log.load_kg,
      ),
    ).toEqual([32.5, 27.5]);
    expect(await workouts.getExerciseHistory(a, b, row, 10)).toEqual([]);
    await expect(
      workouts.updateExerciseLog(b, b, loaded.id, { load_kg: 88 }),
    ).rejects.toMatchObject({ status: 404 });

    const initial = await profiles.context(a, a, date, true);
    expect(initial).toMatchObject({
      age: null,
      height_cm: null,
      weight_kg: 73,
      day: { activity_type: 'resistance', nutrition_day_type: 'training_day' },
    });
    expect(initial.exercise_logs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          load_kg: 32.5,
          repetitions: 10,
          duration_seconds: null,
        }),
        expect.objectContaining({
          load_kg: null,
          repetitions: 12,
          duration_seconds: null,
        }),
        expect.objectContaining({
          load_kg: 2.5,
          repetitions: null,
          duration_seconds: 45,
        }),
        expect.objectContaining({
          load_kg: 27.5,
          repetitions: 8,
          duration_seconds: null,
        }),
      ]),
    );
    expect(JSON.stringify(initial)).not.toContain('não enviar ao Coach');
    await workouts.updateExerciseLog(a, a, loaded.id, {
      load_kg: 35,
      repetitions: 11,
    });
    await db.query('update profiles set current_weight_kg = 74 where id = $1', [
      a,
    ]);
    await db.query(
      'update workout_day_exercises set min_reps=10, max_reps=15 where workout_day_id=$1',
      [aPlan.day],
    );
    await db.query(
      "insert into daily_activity_overrides (user_id, activity_date, activity_type, nutrition_day_type) values ($1, $2, 'rest', 'rest_day')",
      [a, date],
    );
    const revised = await plans.build(a, a, {});
    const updated = await profiles.context(a, a, date, true);
    expect(revised.revision).not.toBe(snapshot.revision);
    expect(updated).toMatchObject({
      weight_kg: 74,
      day: {
        source: 'override',
        activity_type: 'rest',
        nutrition_day_type: 'rest_day',
      },
    });
    expect(updated.exercise_logs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ load_kg: 35, repetitions: 11 }),
      ]),
    );
    const other = await profiles.context(b, b, date, true);
    expect(other.exercise_logs).toHaveLength(1);
    expect(other).toMatchObject({
      weight_kg: 99,
      day: { activity_type: 'resistance' },
      exercise_logs: [{ load_kg: 90 }],
    });
    const weeklyRest = await profiles.context(a, a, '2026-11-11');
    expect(weeklyRest).toMatchObject({
      day: {
        source: 'default',
        activity_type: 'rest',
        nutrition_day_type: 'rest_day',
      },
    });
    const noPlan = await plans.build(empty, empty, {});
    const noData = await profiles.context(empty, empty, date);
    expect(noPlan).toMatchObject({
      workout_plan_id: null,
      diet_plan_id: null,
      workout_exercises: [],
      meal_items: [],
    });
    expect(noData).toMatchObject({
      weight_kg: null,
      height_cm: null,
      exercise_logs: [],
    });

    const output = process.env.EVOLV_PRODUCT_TEST_FIXTURE;
    if (output)
      writeFileSync(
        output,
        JSON.stringify(
          {
            date,
            initial: { snapshot, account: initial },
            updated: { snapshot: revised, account: updated },
            weekly_rest: { snapshot: revised, account: weeklyRest },
            other: { snapshot: await plans.build(b, b, {}), account: other },
            empty: { snapshot: noPlan, account: noData },
          },
          null,
          2,
        ) + '\n',
      );
  } finally {
    await db.close();
  }
}, 30000);

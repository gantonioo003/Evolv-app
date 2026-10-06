import { generateWorkoutPlan } from './planner.generator.js';
import { buildPlannerPersistencePayload } from './planner.persistence.js';
import type { PlannerExerciseCandidate } from './planner.types.js';

const cardioCatalog: PlannerExerciseCandidate[] = [
  {
    id: '11111111-1111-4111-8111-111111111111',
    name: 'Corrida continua',
    muscleGroup: 'full_body',
    equipment: 'treadmill',
    movementPattern: 'locomotion',
    difficulty: 'beginner',
    isCompound: true,
    kind: 'cardio',
    modalities: ['running', 'cardio-equipment'],
  },
];

describe('buildPlannerPersistencePayload', () => {
  it('converte uma prescricao por duracao sem inventar series ou repeticoes', () => {
    const generated = generateWorkoutPlan({
      input: {
        goal: 'health',
        level: 'beginner',
        availableDays: ['monday'],
        sessionMinutes: 30,
        modalities: ['running'],
      },
      exercises: cardioCatalog,
    });
    const payload = buildPlannerPersistencePayload({
      generated,
      userId: '22222222-2222-4222-8222-222222222222',
      goalId: null,
      name: 'Plano de corrida',
      startDate: '2026-10-04',
      status: 'active',
    });

    expect(payload).toMatchObject({
      status: 'active',
      planner_version: 'planner-rules-v1',
      days: [
        {
          exercises: [
            {
              prescription_kind: 'duration',
              duration_minutes: 30,
              sets: null,
              min_reps: null,
              max_reps: null,
            },
          ],
        },
      ],
    });
  });

  it('preserva metadados suficientes para auditar a geracao', () => {
    const generated = generateWorkoutPlan({
      input: {
        availableDays: ['monday'],
        modalities: ['running'],
      },
      exercises: cardioCatalog,
    });
    const payload = buildPlannerPersistencePayload({
      generated,
      userId: '22222222-2222-4222-8222-222222222222',
      goalId: '33333333-3333-4333-8333-333333333333',
      name: 'Plano auditavel',
      startDate: '2026-10-04',
      status: 'draft',
    });

    expect(payload).toMatchObject({
      goal_id: '33333333-3333-4333-8333-333333333333',
      split_type: 'custom',
      planner_input: {
        goal: 'maintenance',
        level: 'beginner',
        assumptions: expect.any(Array),
      },
    });
  });
});

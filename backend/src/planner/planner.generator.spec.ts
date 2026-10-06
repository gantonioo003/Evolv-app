import {
  generateWorkoutPlan,
  PlannerGenerationError,
} from './planner.generator.js';
import type {
  PlannerExerciseCandidate,
  PlannerGenerationRequest,
} from './planner.types.js';

const exercise = (
  id: string,
  name: string,
  muscleGroup: string,
  movementPattern: string,
  options: Partial<PlannerExerciseCandidate> = {},
): PlannerExerciseCandidate => ({
  id,
  name,
  muscleGroup,
  movementPattern,
  equipment: 'dumbbell',
  equipmentCategory: 'free_weight',
  difficulty: 'beginner',
  isCompound: true,
  ...options,
});

const catalog: PlannerExerciseCandidate[] = [
  exercise('squat-1', 'Agachamento goblet', 'quadriceps', 'squat'),
  exercise('squat-2', 'Agachamento livre', 'quadriceps', 'squat', {
    equipment: 'barbell',
    difficulty: 'intermediate',
  }),
  exercise('hinge-1', 'Romeno com halteres', 'hamstrings', 'hip_hinge'),
  exercise('hinge-2', 'Hip thrust', 'glutes', 'hip_extension', {
    equipment: 'barbell',
    difficulty: 'intermediate',
  }),
  exercise('push-1', 'Supino com halteres', 'chest', 'horizontal_push'),
  exercise('push-2', 'Flexao de bracos', 'chest', 'horizontal_push', {
    equipment: 'bodyweight',
  }),
  exercise(
    'press-1',
    'Desenvolvimento com halteres',
    'front_deltoid',
    'vertical_push',
  ),
  exercise('pull-1', 'Remada unilateral', 'upper_back', 'horizontal_pull'),
  exercise('pull-2', 'Remada invertida', 'upper_back', 'horizontal_pull', {
    equipment: 'bodyweight',
    difficulty: 'intermediate',
  }),
  exercise('vertical-pull-1', 'Puxada neutra', 'latissimus', 'vertical_pull', {
    equipment: 'lat_pulldown_machine',
    equipmentCategory: 'machine',
  }),
  exercise('vertical-pull-2', 'Barra fixa', 'latissimus', 'vertical_pull', {
    equipment: 'pull_up_bar',
    equipmentCategory: 'accessory',
    difficulty: 'advanced',
  }),
  exercise('lunge-1', 'Afundo', 'quadriceps', 'lunge'),
  exercise('curl-1', 'Mesa flexora', 'hamstrings', 'knee_flexion', {
    equipment: 'lying_leg_curl_machine',
    equipmentCategory: 'machine',
    isCompound: false,
  }),
  exercise(
    'lateral-1',
    'Elevacao lateral',
    'lateral_deltoid',
    'shoulder_abduction',
    {
      isCompound: false,
    },
  ),
  exercise(
    'rear-1',
    'Crucifixo invertido',
    'rear_deltoid',
    'horizontal_abduction',
    {
      equipment: 'pec_deck',
      equipmentCategory: 'machine',
      isCompound: false,
    },
  ),
  exercise('biceps-1', 'Rosca martelo', 'biceps', 'elbow_flexion', {
    isCompound: false,
  }),
  exercise('triceps-1', 'Triceps frances', 'triceps', 'elbow_extension', {
    isCompound: false,
  }),
  exercise(
    'calf-1',
    'Panturrilha unilateral',
    'gastrocnemius',
    'plantar_flexion',
    {
      equipment: 'bodyweight',
      isCompound: false,
    },
  ),
  exercise('core-1', 'Dead bug', 'transverse_abdominis', 'anti_extension', {
    equipment: 'bodyweight',
    isCompound: false,
  }),
  exercise('core-2', 'Prancha lateral', 'obliques', 'anti_lateral_flexion', {
    equipment: 'bodyweight',
    isCompound: false,
  }),
  exercise('cardio-1', 'Corrida continua', 'full_body', 'locomotion', {
    equipment: null,
    kind: 'cardio',
    modalities: ['running'],
  }),
  exercise('cardio-2', 'Bicicleta ergometrica', 'full_body', 'locomotion', {
    equipment: 'stationary_bike',
    kind: 'cardio',
    modalities: ['cycling', 'cardio-equipment'],
  }),
  exercise('mobility-1', 'Mobilidade de quadril', 'glutes', 'mobility', {
    equipment: 'bodyweight',
    isCompound: false,
    kind: 'mobility',
    modalities: ['mobility'],
  }),
  exercise('mobility-2', 'Mobilidade toracica', 'upper_back', 'mobility', {
    equipment: 'bodyweight',
    isCompound: false,
    kind: 'mobility',
    modalities: ['mobility'],
  }),
  exercise(
    'mobility-3',
    'Alongamento de posteriores',
    'hamstrings',
    'stretching',
    {
      equipment: 'bodyweight',
      isCompound: false,
      kind: 'mobility',
      modalities: ['stretching', 'mobility'],
    },
  ),
  exercise('mobility-4', 'Mobilidade de ombros', 'front_deltoid', 'mobility', {
    equipment: 'bodyweight',
    isCompound: false,
    kind: 'mobility',
    modalities: ['mobility'],
  }),
];

const baseRequest: PlannerGenerationRequest = {
  input: {
    goal: 'hypertrophy',
    level: 'intermediate',
    availableDays: ['monday', 'tuesday', 'thursday', 'friday'],
    sessionMinutes: 60,
    modalities: ['full-gym'],
  },
  exercises: catalog,
};

describe('generateWorkoutPlan', () => {
  it('gera sessoes completas na ordem composta antes dos acessorios', () => {
    const result = generateWorkoutPlan(baseRequest);

    expect(result.splitType).toBe('upper_lower');
    expect(result.days).toHaveLength(4);
    expect(result.days.every((day) => day.exercises.length >= 4)).toBe(true);
    expect(result.days[0].exercises[0].role).toBe('primary');
    expect(result.days[0].exercises.at(-1)?.role).toBe('accessory');
  });

  it('usa prescricao de forca para o primeiro composto', () => {
    const result = generateWorkoutPlan({
      ...baseRequest,
      input: { ...baseRequest.input, goal: 'strength' },
    });
    const prescription = result.days[0].exercises[0].prescription;

    expect(prescription).toEqual({
      kind: 'repetitions',
      sets: 4,
      minReps: 3,
      maxReps: 6,
      restSeconds: 180,
    });
  });

  it('nao entrega exercicios avancados para iniciantes', () => {
    const result = generateWorkoutPlan({
      ...baseRequest,
      input: {
        ...baseRequest.input,
        level: 'beginner',
        availableDays: ['monday', 'wednesday', 'friday'],
        desiredWeeklyFrequency: 3,
      },
    });
    const ids = result.days.flatMap((day) =>
      day.exercises.map((item) => item.exerciseId),
    );

    expect(ids).not.toContain('vertical-pull-2');
    expect(result.generation.eligibleCatalogSize).toBeLessThan(catalog.length);
  });

  it('respeita equipamentos disponiveis e exercicios evitados', () => {
    const result = generateWorkoutPlan({
      input: {
        goal: 'health',
        level: 'beginner',
        availableDays: ['monday', 'thursday'],
        modalities: ['bodyweight'],
        sessionMinutes: 35,
      },
      exercises: catalog,
      constraints: {
        availableEquipment: [],
        avoidedExerciseIds: ['push-2'],
      },
    });
    const exercises = result.days.flatMap((day) => day.exercises);

    expect(exercises.every((item) => item.equipment === 'bodyweight')).toBe(
      true,
    );
    expect(exercises.map((item) => item.exerciseId)).not.toContain('push-2');
  });

  it('evita repetir o mesmo exercicio quando o catalogo oferece alternativas', () => {
    const result = generateWorkoutPlan({
      ...baseRequest,
      input: {
        goal: 'maintenance',
        level: 'intermediate',
        availableDays: ['monday', 'wednesday', 'friday'],
        sessionMinutes: 25,
        modalities: ['full-gym'],
      },
    });
    const ids = result.days.flatMap((day) =>
      day.exercises.map((item) => item.exerciseId),
    );

    expect(new Set(ids).size).toBe(ids.length);
  });

  it('mantem o volume semanal por musculo dentro do limite do nivel', () => {
    const result = generateWorkoutPlan(baseRequest);

    expect(
      Object.values(result.generation.weeklySetsByMuscle).every(
        (sets) => sets <= result.generation.weeklySetCapPerMuscle,
      ),
    ).toBe(true);
  });

  it('gera cardio por duracao para uma rotina sem musculacao', () => {
    const result = generateWorkoutPlan({
      input: {
        goal: 'health',
        level: 'beginner',
        availableDays: ['monday', 'wednesday', 'friday'],
        sessionMinutes: 30,
        modalities: ['running'],
      },
      exercises: catalog,
    });

    expect(result.splitType).toBe('custom');
    expect(result.days[0].exercises[0].name).toBe('Corrida continua');
    expect(result.days[0].exercises[0].prescription).toEqual({
      kind: 'duration',
      durationMinutes: 30,
      restSeconds: 60,
    });
  });

  it('combina musculacao e cardio sem substituir o treino principal', () => {
    const result = generateWorkoutPlan({
      ...baseRequest,
      input: {
        ...baseRequest.input,
        goal: 'fat_loss',
        modalities: ['free-weights', 'running'],
      },
    });
    const firstDay = result.days[0];

    expect(firstDay.exercises.some((item) => item.role === 'primary')).toBe(
      true,
    );
    expect(firstDay.exercises.at(-1)?.role).toBe('conditioning');
  });

  it('produz exatamente o mesmo plano para a mesma entrada', () => {
    expect(generateWorkoutPlan(baseRequest)).toEqual(
      generateWorkoutPlan(baseRequest),
    );
  });

  it('rejeita um catalogo vazio com erro de dominio', () => {
    expect(() =>
      generateWorkoutPlan({ ...baseRequest, exercises: [] }),
    ).toThrowError(
      expect.objectContaining<Partial<PlannerGenerationError>>({
        code: 'EMPTY_EXERCISE_CATALOG',
      }),
    );
  });
});

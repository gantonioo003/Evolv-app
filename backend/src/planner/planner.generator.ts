import { recommendPlannerStructure } from './planner.rules.js';
import type {
  PlannerComposition,
  PlannerDurationPrescription,
  PlannerExerciseCandidate,
  PlannerExerciseKind,
  PlannerExercisePrescription,
  PlannerExerciseRole,
  PlannerGeneratedDay,
  PlannerGeneratedExercise,
  PlannerGeneratedPlan,
  PlannerGenerationRequest,
  PlannerGoal,
  PlannerLevel,
  PlannerModality,
  PlannerRecommendation,
  PlannerRepetitionPrescription,
  PlannerSplitType,
} from './planner.types.js';

type ExerciseSlot = {
  role: PlannerExerciseRole;
  muscleGroups: string[];
  movementPatterns?: string[];
  preferCompound?: boolean;
};

type GenerationState = {
  usedExerciseIds: Set<string>;
  weeklySetsByMuscle: Record<string, number>;
  warnings: string[];
};

const difficultyRank: Record<PlannerLevel, number> = {
  beginner: 0,
  intermediate: 1,
  advanced: 2,
};

const weeklySetCaps: Record<PlannerLevel, number> = {
  beginner: 10,
  intermediate: 14,
  advanced: 18,
};

const freeWeightEquipment = new Set([
  'barbell',
  'dumbbell',
  'ez_bar',
  'kettlebell',
]);

const calisthenicsEquipment = new Set([
  'bodyweight',
  'pull_up_bar',
  'dip_station',
  'suspension_trainer',
]);

const modalityEquipmentCategories: Partial<Record<PlannerModality, string[]>> =
  {
    machines: ['machine'],
    'free-weights': ['free_weight'],
    cables: ['cable'],
    functional: ['functional'],
  };

const resistanceModalities = new Set<PlannerModality>([
  'full-gym',
  'machines',
  'free-weights',
  'cables',
  'calisthenics',
  'bands',
  'functional',
  'suspension',
  'bodyweight',
  'plyometrics',
  'sports',
]);

const cardioModalities = new Set<PlannerModality>([
  'cardio-equipment',
  'running',
  'walking',
  'cycling',
  'rowing',
  'stairs',
  'swimming',
  'hiit',
]);

const mobilityModalities = new Set<PlannerModality>([
  'yoga-pilates',
  'mobility',
  'stretching',
]);

export type PlannerGenerationErrorCode =
  'EMPTY_EXERCISE_CATALOG' | 'NO_ELIGIBLE_EXERCISES';

export class PlannerGenerationError extends Error {
  constructor(
    readonly code: PlannerGenerationErrorCode,
    message: string,
  ) {
    super(message);
    this.name = 'PlannerGenerationError';
  }
}

export function generateWorkoutPlan({
  input,
  exercises,
  constraints,
}: PlannerGenerationRequest): PlannerGeneratedPlan {
  if (!exercises.length) {
    throw new PlannerGenerationError(
      'EMPTY_EXERCISE_CATALOG',
      'O catalogo de exercicios esta vazio.',
    );
  }

  const recommendation = recommendPlannerStructure(input);
  const uniqueCatalog = deduplicateCatalog(exercises);
  const eligibleCatalog = applyHardConstraints(
    uniqueCatalog,
    recommendation.level,
    constraints,
  );

  if (!eligibleCatalog.length) {
    throw new PlannerGenerationError(
      'NO_ELIGIBLE_EXERCISES',
      'Nenhum exercicio atende ao nivel e aos equipamentos disponiveis.',
    );
  }

  const state: GenerationState = {
    usedExerciseIds: new Set(),
    weeklySetsByMuscle: {},
    warnings: [],
  };
  const weeklySetCap = weeklySetCaps[recommendation.level];
  const days = recommendation.days.map((day) =>
    generateDay(day, recommendation, eligibleCatalog, state, weeklySetCap),
  );
  const totalWeeklySets = Object.values(state.weeklySetsByMuscle).reduce(
    (total, sets) => total + sets,
    0,
  );

  return {
    ...recommendation,
    days,
    warnings: [...recommendation.warnings, ...state.warnings],
    generation: {
      ruleVersion: 'planner-rules-v1',
      catalogSize: uniqueCatalog.length,
      eligibleCatalogSize: eligibleCatalog.length,
      totalWeeklySets,
      weeklySetsByMuscle: { ...state.weeklySetsByMuscle },
      weeklySetCapPerMuscle: weeklySetCap,
    },
  };
}

function generateDay(
  day: PlannerRecommendation['days'][number],
  recommendation: PlannerRecommendation,
  catalog: PlannerExerciseCandidate[],
  state: GenerationState,
  weeklySetCap: number,
): PlannerGeneratedDay {
  if (recommendation.splitType === 'custom') {
    return generateCustomDay(day, recommendation, catalog, state);
  }

  const targetExerciseCount = getTargetExerciseCount(
    recommendation.sessionMinutes,
    recommendation.level,
  );
  const includeConditioning =
    recommendation.composition === 'mixed' &&
    recommendation.sessionMinutes >= 35 &&
    catalog.some((exercise) => getExerciseKind(exercise) === 'cardio');
  const resistanceTarget = includeConditioning
    ? Math.max(2, targetExerciseCount - 1)
    : targetExerciseCount;
  const slots = createSlots(
    recommendation.splitType,
    day.title,
    day.position,
  ).slice(0, resistanceTarget);
  const selected: PlannerGeneratedExercise[] = [];

  for (const slot of slots) {
    const exercise = selectExercise({
      catalog,
      dayExercises: selected,
      goal: recommendation.goal,
      level: recommendation.level,
      modalities: recommendation.modalities,
      slot,
      state,
      weeklySetCap,
    });

    if (!exercise) continue;

    const prescription = createResistancePrescription(
      recommendation.goal,
      recommendation.level,
      slot.role,
      exercise.isCompound,
    );
    selected.push(
      toGeneratedExercise(exercise, selected.length, slot.role, prescription),
    );
    state.usedExerciseIds.add(exercise.id);
    state.weeklySetsByMuscle[exercise.muscleGroup] =
      (state.weeklySetsByMuscle[exercise.muscleGroup] ?? 0) + prescription.sets;
  }

  if (includeConditioning) {
    const conditioning = selectTimedExercise(
      catalog,
      'cardio',
      recommendation.modalities,
      state,
    );
    if (conditioning) {
      const prescription: PlannerDurationPrescription = {
        kind: 'duration',
        durationMinutes: Math.min(
          20,
          Math.max(10, Math.round(recommendation.sessionMinutes * 0.25)),
        ),
        restSeconds: 60,
      };
      selected.push(
        toGeneratedExercise(
          conditioning,
          selected.length,
          'conditioning',
          prescription,
        ),
      );
      state.usedExerciseIds.add(conditioning.id);
    }
  }

  if (selected.length < Math.min(3, resistanceTarget)) {
    addWarningOnce(
      state,
      `O catalogo nao conseguiu preencher completamente ${day.title}; revise modalidades ou equipamentos.`,
    );
  }

  return {
    ...day,
    estimatedMinutes: estimateSessionMinutes(selected),
    exercises: selected,
    totalWorkSets: countWorkSets(selected),
  };
}

function generateCustomDay(
  day: PlannerRecommendation['days'][number],
  recommendation: PlannerRecommendation,
  catalog: PlannerExerciseCandidate[],
  state: GenerationState,
): PlannerGeneratedDay {
  const preferredKind = selectCustomKind(
    recommendation.composition,
    day.position,
  );
  const targetCount = preferredKind === 'mobility' ? 4 : 1;
  const selected: PlannerGeneratedExercise[] = [];

  for (let index = 0; index < targetCount; index += 1) {
    const exercise = selectTimedExercise(
      catalog,
      preferredKind,
      recommendation.modalities,
      state,
      selected,
    );
    if (!exercise) break;

    const durationMinutes =
      preferredKind === 'mobility'
        ? Math.max(3, Math.floor(recommendation.sessionMinutes / targetCount))
        : recommendation.sessionMinutes;
    selected.push(
      toGeneratedExercise(
        exercise,
        selected.length,
        preferredKind === 'mobility' ? 'mobility' : 'conditioning',
        {
          kind: 'duration',
          durationMinutes,
          restSeconds: preferredKind === 'mobility' ? 30 : 60,
        },
      ),
    );
    state.usedExerciseIds.add(exercise.id);
  }

  if (!selected.length) {
    addWarningOnce(
      state,
      `Nao ha exercicios de ${preferredKind} compativeis para ${day.title}.`,
    );
  }

  return {
    ...day,
    estimatedMinutes: selected.length
      ? estimateSessionMinutes(selected)
      : day.estimatedMinutes,
    exercises: selected,
    totalWorkSets: 0,
  };
}

function selectExercise({
  catalog,
  dayExercises,
  goal,
  level,
  modalities,
  slot,
  state,
  weeklySetCap,
}: {
  catalog: PlannerExerciseCandidate[];
  dayExercises: PlannerGeneratedExercise[];
  goal: PlannerGoal;
  level: PlannerLevel;
  modalities: PlannerModality[];
  slot: ExerciseSlot;
  state: GenerationState;
  weeklySetCap: number;
}) {
  const compatible = catalog.filter((exercise) => {
    if (getExerciseKind(exercise) !== 'resistance') return false;
    if (dayExercises.some((item) => item.exerciseId === exercise.id))
      return false;
    if (!matchesSlot(exercise, slot)) return false;
    if (!matchesResistanceModalities(exercise, modalities)) return false;
    if (hasBadDayCombination(exercise, dayExercises)) return false;

    const expectedSets = createResistancePrescription(
      goal,
      level,
      slot.role,
      exercise.isCompound,
    ).sets;
    return (
      (state.weeklySetsByMuscle[exercise.muscleGroup] ?? 0) + expectedSets <=
      weeklySetCap
    );
  });

  const unused = compatible.filter(
    (exercise) => !state.usedExerciseIds.has(exercise.id),
  );
  const candidates = unused.length ? unused : compatible;

  if (!unused.length && compatible.length) {
    addWarningOnce(
      state,
      'O catalogo exigiu repetir um exercicio na semana; amplie as opcoes para obter mais variedade.',
    );
  }

  return sortCandidates(candidates, slot, level, dayExercises)[0];
}

function selectTimedExercise(
  catalog: PlannerExerciseCandidate[],
  kind: Exclude<PlannerExerciseKind, 'resistance'>,
  modalities: PlannerModality[],
  state: GenerationState,
  dayExercises: PlannerGeneratedExercise[] = [],
) {
  const selectedIds = new Set(dayExercises.map((item) => item.exerciseId));
  const expectedModalities =
    kind === 'cardio' ? cardioModalities : mobilityModalities;
  const requested = modalities.filter((item) => expectedModalities.has(item));
  const candidates = catalog
    .filter((exercise) => getExerciseKind(exercise) === kind)
    .filter((exercise) => !selectedIds.has(exercise.id))
    .filter((exercise) => matchesExplicitModalities(exercise, requested));
  const unused = candidates.filter(
    (exercise) => !state.usedExerciseIds.has(exercise.id),
  );

  return [...(unused.length ? unused : candidates)].sort(compareExercise)[0];
}

function createResistancePrescription(
  goal: PlannerGoal,
  level: PlannerLevel,
  role: PlannerExerciseRole,
  isCompound: boolean,
): PlannerRepetitionPrescription {
  const isPrimary = role === 'primary' || role === 'secondary';
  let prescription: PlannerRepetitionPrescription;

  if (goal === 'strength' && isPrimary && isCompound) {
    prescription = {
      kind: 'repetitions',
      sets: role === 'primary' ? 4 : 3,
      minReps: 3,
      maxReps: role === 'primary' ? 6 : 8,
      restSeconds: role === 'primary' ? 180 : 150,
    };
  } else if (goal === 'strength') {
    prescription = {
      kind: 'repetitions',
      sets: 3,
      minReps: 8,
      maxReps: 12,
      restSeconds: 90,
    };
  } else if (goal === 'hypertrophy' || goal === 'recomposition') {
    prescription = isCompound
      ? {
          kind: 'repetitions',
          sets: 3,
          minReps: 6,
          maxReps: 10,
          restSeconds: 120,
        }
      : {
          kind: 'repetitions',
          sets: 3,
          minReps: 10,
          maxReps: 15,
          restSeconds: 75,
        };
  } else if (goal === 'fat_loss') {
    prescription = {
      kind: 'repetitions',
      sets: isCompound ? 3 : 2,
      minReps: isCompound ? 8 : 10,
      maxReps: 15,
      restSeconds: isCompound ? 90 : 60,
    };
  } else {
    prescription = {
      kind: 'repetitions',
      sets: isCompound ? 3 : 2,
      minReps: 8,
      maxReps: isCompound ? 12 : 15,
      restSeconds: isCompound ? 90 : 60,
    };
  }

  if (role === 'core') {
    prescription = {
      kind: 'repetitions',
      sets: level === 'advanced' ? 3 : 2,
      minReps: 10,
      maxReps: 15,
      restSeconds: 60,
    };
  }

  if (level === 'beginner' && prescription.sets > 2 && role !== 'primary') {
    return { ...prescription, sets: 2 };
  }

  return prescription;
}

function createSlots(
  splitType: PlannerSplitType,
  title: string,
  dayPosition: number,
): ExerciseSlot[] {
  if (splitType === 'full_body') return createFullBodySlots(dayPosition);
  if (splitType === 'upper_lower') {
    return title.startsWith('Superiores')
      ? createUpperSlots(dayPosition)
      : createLowerSlots(dayPosition);
  }
  if (splitType === 'push_pull_legs') {
    if (title.startsWith('Empurrar')) return createPushSlots();
    if (title.startsWith('Puxar')) return createPullSlots();
    return createLowerSlots(dayPosition);
  }
  if (splitType === 'body_part') return createBodyPartSlots(title);
  if (title.startsWith('Superiores')) return createUpperSlots(dayPosition);
  if (title.startsWith('Inferiores') || title === 'Pernas') {
    return createLowerSlots(dayPosition);
  }
  if (title.startsWith('Empurrar')) return createPushSlots();
  if (title.startsWith('Puxar')) return createPullSlots();
  return createFullBodySlots(dayPosition);
}

function createFullBodySlots(dayPosition: number): ExerciseSlot[] {
  const lowerPrimary = dayPosition % 2 === 0 ? squatSlot() : hingeSlot();
  const lowerSecondary = dayPosition % 2 === 0 ? hingeSlot() : squatSlot();
  const pushPrimary =
    dayPosition % 2 === 0 ? horizontalPushSlot() : verticalPushSlot();
  const pullPrimary =
    dayPosition % 2 === 0 ? horizontalPullSlot() : verticalPullSlot();

  return [
    { ...lowerPrimary, role: 'primary' },
    { ...pushPrimary, role: 'primary' },
    { ...pullPrimary, role: 'primary' },
    { ...lowerSecondary, role: 'secondary' },
    {
      role: 'accessory',
      muscleGroups: ['lateral_deltoid', 'rear_deltoid', 'biceps', 'triceps'],
    },
    coreSlot(),
    calfSlot(),
    {
      role: 'accessory',
      muscleGroups: ['chest', 'latissimus', 'upper_back', 'glutes'],
      preferCompound: false,
    },
  ];
}

function createUpperSlots(dayPosition: number): ExerciseSlot[] {
  const firstPush =
    dayPosition % 2 === 0 ? horizontalPushSlot() : verticalPushSlot();
  const secondPush =
    dayPosition % 2 === 0 ? verticalPushSlot() : horizontalPushSlot();
  const firstPull =
    dayPosition % 2 === 0 ? horizontalPullSlot() : verticalPullSlot();
  const secondPull =
    dayPosition % 2 === 0 ? verticalPullSlot() : horizontalPullSlot();

  return [
    { ...firstPush, role: 'primary' },
    { ...firstPull, role: 'primary' },
    { ...secondPush, role: 'secondary' },
    { ...secondPull, role: 'secondary' },
    {
      role: 'accessory',
      muscleGroups: ['lateral_deltoid', 'rear_deltoid'],
      preferCompound: false,
    },
    {
      role: 'accessory',
      muscleGroups: dayPosition % 2 === 0 ? ['triceps'] : ['biceps'],
      preferCompound: false,
    },
    {
      role: 'accessory',
      muscleGroups: dayPosition % 2 === 0 ? ['biceps'] : ['triceps'],
      preferCompound: false,
    },
    coreSlot(),
  ];
}

function createLowerSlots(dayPosition: number): ExerciseSlot[] {
  const first = dayPosition % 2 === 0 ? squatSlot() : hingeSlot();
  const second = dayPosition % 2 === 0 ? hingeSlot() : squatSlot();

  return [
    { ...first, role: 'primary' },
    { ...second, role: 'primary' },
    {
      role: 'secondary',
      muscleGroups: ['quadriceps', 'glutes'],
      movementPatterns: ['lunge', 'step'],
      preferCompound: true,
    },
    {
      role: 'accessory',
      muscleGroups: ['hamstrings'],
      movementPatterns: ['knee_flexion'],
      preferCompound: false,
    },
    {
      role: 'accessory',
      muscleGroups: ['glutes', 'abductors', 'adductors'],
      preferCompound: false,
    },
    calfSlot(),
    coreSlot(),
    {
      role: 'accessory',
      muscleGroups: ['quadriceps', 'hamstrings'],
      preferCompound: false,
    },
  ];
}

function createPushSlots(): ExerciseSlot[] {
  return [
    { ...horizontalPushSlot(), role: 'primary' },
    { ...verticalPushSlot(), role: 'primary' },
    {
      role: 'secondary',
      muscleGroups: ['chest'],
      movementPatterns: ['horizontal_push', 'horizontal_adduction'],
    },
    {
      role: 'accessory',
      muscleGroups: ['lateral_deltoid'],
      movementPatterns: ['shoulder_abduction'],
      preferCompound: false,
    },
    {
      role: 'accessory',
      muscleGroups: ['triceps'],
      movementPatterns: ['elbow_extension'],
      preferCompound: false,
    },
    {
      role: 'accessory',
      muscleGroups: ['triceps', 'chest'],
      preferCompound: false,
    },
    coreSlot(),
  ];
}

function createPullSlots(): ExerciseSlot[] {
  return [
    { ...verticalPullSlot(), role: 'primary' },
    { ...horizontalPullSlot(), role: 'primary' },
    {
      role: 'secondary',
      muscleGroups: ['upper_back', 'latissimus'],
      movementPatterns: ['horizontal_pull', 'vertical_pull'],
    },
    {
      role: 'accessory',
      muscleGroups: ['rear_deltoid', 'trapezius'],
      preferCompound: false,
    },
    {
      role: 'accessory',
      muscleGroups: ['biceps'],
      movementPatterns: ['elbow_flexion'],
      preferCompound: false,
    },
    {
      role: 'accessory',
      muscleGroups: ['biceps', 'forearms'],
      preferCompound: false,
    },
    coreSlot(),
  ];
}

function createBodyPartSlots(title: string): ExerciseSlot[] {
  if (title.startsWith('Peito')) return createPushSlots();
  if (title.startsWith('Costas')) return createPullSlots();
  if (title === 'Pernas') return createLowerSlots(0);
  if (title === 'Ombros') {
    return [
      { ...verticalPushSlot(), role: 'primary' },
      {
        role: 'secondary',
        muscleGroups: ['lateral_deltoid'],
        movementPatterns: ['shoulder_abduction'],
      },
      {
        role: 'secondary',
        muscleGroups: ['rear_deltoid'],
        movementPatterns: ['horizontal_abduction', 'horizontal_pull'],
      },
      {
        role: 'accessory',
        muscleGroups: ['front_deltoid'],
        preferCompound: false,
      },
      {
        role: 'accessory',
        muscleGroups: ['trapezius'],
        preferCompound: false,
      },
      coreSlot(),
    ];
  }

  return [
    {
      role: 'primary',
      muscleGroups: ['biceps'],
      movementPatterns: ['elbow_flexion'],
    },
    {
      role: 'primary',
      muscleGroups: ['triceps'],
      movementPatterns: ['elbow_extension'],
    },
    {
      role: 'accessory',
      muscleGroups: ['biceps'],
      preferCompound: false,
    },
    {
      role: 'accessory',
      muscleGroups: ['triceps'],
      preferCompound: false,
    },
    {
      role: 'accessory',
      muscleGroups: ['forearms'],
      preferCompound: false,
    },
    {
      role: 'accessory',
      muscleGroups: ['lateral_deltoid', 'rear_deltoid'],
      preferCompound: false,
    },
  ];
}

function squatSlot(): ExerciseSlot {
  return {
    role: 'primary',
    muscleGroups: ['quadriceps', 'glutes', 'full_body'],
    movementPatterns: ['squat', 'lunge', 'step'],
    preferCompound: true,
  };
}

function hingeSlot(): ExerciseSlot {
  return {
    role: 'primary',
    muscleGroups: ['hamstrings', 'glutes', 'spinal_erectors', 'full_body'],
    movementPatterns: ['hip_hinge', 'hip_extension'],
    preferCompound: true,
  };
}

function horizontalPushSlot(): ExerciseSlot {
  return {
    role: 'primary',
    muscleGroups: ['chest', 'triceps'],
    movementPatterns: ['horizontal_push'],
    preferCompound: true,
  };
}

function verticalPushSlot(): ExerciseSlot {
  return {
    role: 'secondary',
    muscleGroups: ['front_deltoid', 'triceps', 'full_body'],
    movementPatterns: ['vertical_push'],
    preferCompound: true,
  };
}

function horizontalPullSlot(): ExerciseSlot {
  return {
    role: 'primary',
    muscleGroups: ['upper_back', 'rear_deltoid', 'biceps'],
    movementPatterns: ['horizontal_pull'],
    preferCompound: true,
  };
}

function verticalPullSlot(): ExerciseSlot {
  return {
    role: 'primary',
    muscleGroups: ['latissimus', 'biceps'],
    movementPatterns: ['vertical_pull'],
    preferCompound: true,
  };
}

function coreSlot(): ExerciseSlot {
  return {
    role: 'core',
    muscleGroups: [
      'rectus_abdominis',
      'obliques',
      'transverse_abdominis',
      'spinal_erectors',
    ],
    preferCompound: false,
  };
}

function calfSlot(): ExerciseSlot {
  return {
    role: 'accessory',
    muscleGroups: ['gastrocnemius', 'soleus'],
    movementPatterns: ['plantar_flexion'],
    preferCompound: false,
  };
}

function sortCandidates(
  candidates: PlannerExerciseCandidate[],
  slot: ExerciseSlot,
  level: PlannerLevel,
  dayExercises: PlannerGeneratedExercise[],
) {
  return [...candidates].sort((left, right) => {
    const scoreDifference =
      scoreCandidate(right, slot, level, dayExercises) -
      scoreCandidate(left, slot, level, dayExercises);
    return scoreDifference || compareExercise(left, right);
  });
}

function scoreCandidate(
  exercise: PlannerExerciseCandidate,
  slot: ExerciseSlot,
  level: PlannerLevel,
  dayExercises: PlannerGeneratedExercise[],
) {
  let score = 0;
  if (slot.muscleGroups.includes(exercise.muscleGroup)) score += 100;
  if (
    exercise.movementPattern &&
    slot.movementPatterns?.includes(exercise.movementPattern)
  ) {
    score += 80;
  }
  if (slot.preferCompound === exercise.isCompound) score += 30;
  if (exercise.difficulty === level) score += 10;
  if (exercise.muscleGroup === 'full_body') score += 5;
  if (
    exercise.movementPattern &&
    !dayExercises.some(
      (item) => item.movementPattern === exercise.movementPattern,
    )
  ) {
    score += 15;
  }
  return score;
}

function matchesSlot(exercise: PlannerExerciseCandidate, slot: ExerciseSlot) {
  return (
    slot.muscleGroups.includes(exercise.muscleGroup) ||
    (exercise.movementPattern !== null &&
      exercise.movementPattern !== undefined &&
      slot.movementPatterns?.includes(exercise.movementPattern))
  );
}

function hasBadDayCombination(
  exercise: PlannerExerciseCandidate,
  selected: PlannerGeneratedExercise[],
) {
  const sameMuscleCount = selected.filter(
    (item) => item.muscleGroup === exercise.muscleGroup,
  ).length;
  if (sameMuscleCount >= 2) return true;

  if (!exercise.movementPattern) return false;
  return (
    selected.filter((item) => item.movementPattern === exercise.movementPattern)
      .length >= 2
  );
}

function matchesResistanceModalities(
  exercise: PlannerExerciseCandidate,
  modalities: PlannerModality[],
) {
  const selected = modalities.filter((item) => resistanceModalities.has(item));
  if (!selected.length || selected.includes('full-gym')) return true;
  if (matchesExplicitModalities(exercise, selected)) return true;

  return selected.some((modality) => {
    if (modality === 'machines')
      return (
        exercise.equipmentCategory === 'machine' ||
        exercise.equipment?.endsWith('_machine') ||
        ['leg_press_45', 'pec_deck', 'smith_machine'].includes(
          exercise.equipment ?? '',
        )
      );
    if (modality === 'free-weights')
      return freeWeightEquipment.has(exercise.equipment ?? '');
    if (modality === 'cables')
      return (
        exercise.equipmentCategory === 'cable' ||
        exercise.equipment === 'cable_station'
      );
    if (modality === 'calisthenics')
      return calisthenicsEquipment.has(exercise.equipment ?? '');
    if (modality === 'bands') return exercise.equipment === 'resistance_band';
    if (modality === 'functional')
      return exercise.equipmentCategory === 'functional';
    if (modality === 'suspension')
      return exercise.equipment === 'suspension_trainer';
    if (modality === 'bodyweight') return exercise.equipment === 'bodyweight';
    if (modality === 'plyometrics')
      return ['jump', 'throw'].includes(exercise.movementPattern ?? '');
    if (modality === 'sports') return true;
    return (modalityEquipmentCategories[modality] ?? []).includes(
      exercise.equipmentCategory ?? '',
    );
  });
}

function matchesExplicitModalities(
  exercise: PlannerExerciseCandidate,
  selected: PlannerModality[],
) {
  if (!selected.length) return true;
  return Boolean(
    exercise.modalities?.some((modality) => selected.includes(modality)),
  );
}

function applyHardConstraints(
  catalog: PlannerExerciseCandidate[],
  level: PlannerLevel,
  constraints?: PlannerGenerationRequest['constraints'],
) {
  const avoided = new Set(constraints?.avoidedExerciseIds ?? []);
  const availableEquipment = constraints?.availableEquipment
    ? new Set([...constraints.availableEquipment, 'bodyweight'])
    : null;

  return catalog.filter((exercise) => {
    if (avoided.has(exercise.id)) return false;
    if (
      exercise.difficulty &&
      difficultyRank[exercise.difficulty] > difficultyRank[level]
    ) {
      return false;
    }
    if (
      availableEquipment &&
      exercise.equipment &&
      !availableEquipment.has(exercise.equipment)
    ) {
      return false;
    }
    return true;
  });
}

function deduplicateCatalog(catalog: PlannerExerciseCandidate[]) {
  const byId = new Map<string, PlannerExerciseCandidate>();
  for (const exercise of catalog) {
    if (!byId.has(exercise.id)) byId.set(exercise.id, exercise);
  }
  return [...byId.values()];
}

function getExerciseKind(
  exercise: PlannerExerciseCandidate,
): PlannerExerciseKind {
  return exercise.kind ?? 'resistance';
}

function selectCustomKind(
  composition: PlannerComposition,
  dayPosition: number,
): Exclude<PlannerExerciseKind, 'resistance'> {
  if (composition === 'mobility') return 'mobility';
  if (composition === 'mixed')
    return dayPosition % 2 === 0 ? 'cardio' : 'mobility';
  return 'cardio';
}

function getTargetExerciseCount(minutes: number, level: PlannerLevel) {
  const byDuration =
    minutes <= 25
      ? 3
      : minutes <= 35
        ? 4
        : minutes <= 50
          ? 5
          : minutes <= 65
            ? 6
            : minutes <= 90
              ? 7
              : 8;
  return level === 'beginner' ? Math.min(byDuration, 6) : byDuration;
}

function toGeneratedExercise(
  exercise: PlannerExerciseCandidate,
  position: number,
  role: PlannerExerciseRole,
  prescription: PlannerExercisePrescription,
): PlannerGeneratedExercise {
  return {
    exerciseId: exercise.id,
    name: exercise.name,
    position,
    muscleGroup: exercise.muscleGroup,
    movementPattern: exercise.movementPattern ?? null,
    equipment: exercise.equipment ?? null,
    isCompound: exercise.isCompound,
    role,
    prescription,
  };
}

function countWorkSets(exercises: PlannerGeneratedExercise[]) {
  return exercises.reduce(
    (total, exercise) =>
      total +
      (exercise.prescription.kind === 'repetitions'
        ? exercise.prescription.sets
        : 0),
    0,
  );
}

function estimateSessionMinutes(exercises: PlannerGeneratedExercise[]) {
  const seconds = exercises.reduce((total, exercise) => {
    if (exercise.prescription.kind === 'duration') {
      return total + exercise.prescription.durationMinutes * 60;
    }
    const { sets, restSeconds } = exercise.prescription;
    return total + sets * 40 + Math.max(0, sets - 1) * restSeconds + 45;
  }, 5 * 60);
  return Math.max(5, Math.round(seconds / 60));
}

function compareExercise(
  left: PlannerExerciseCandidate,
  right: PlannerExerciseCandidate,
) {
  return `${left.name}:${left.id}`.localeCompare(`${right.name}:${right.id}`);
}

function addWarningOnce(state: GenerationState, warning: string) {
  if (!state.warnings.includes(warning)) state.warnings.push(warning);
}

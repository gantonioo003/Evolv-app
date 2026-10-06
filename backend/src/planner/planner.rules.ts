import {
  plannerGoals,
  plannerLevels,
  plannerModalities,
  plannerStabilityPolicy,
  type PlannerComposition,
  type PlannerDayTemplate,
  type PlannerGoal,
  type PlannerInput,
  type PlannerLevel,
  type PlannerModality,
  type PlannerRecommendation,
  type PlannerSessionProfile,
  type PlannerSplitType,
  type PlannerWeekday,
} from './planner.types.js';

const weekdays: PlannerWeekday[] = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
];

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

const automaticFrequencyCaps: Record<PlannerLevel, number> = {
  beginner: 4,
  intermediate: 5,
  advanced: 6,
};

export type PlannerInputErrorCode =
  | 'NO_AVAILABLE_DAYS'
  | 'DUPLICATE_AVAILABLE_DAYS'
  | 'INVALID_WEEKDAY'
  | 'INVALID_GOAL'
  | 'INVALID_LEVEL'
  | 'INVALID_MODALITY'
  | 'INVALID_SESSION_DURATION'
  | 'INVALID_FREQUENCY'
  | 'FREQUENCY_EXCEEDS_AVAILABILITY';

export class PlannerInputError extends Error {
  constructor(
    readonly code: PlannerInputErrorCode,
    message: string,
  ) {
    super(message);
    this.name = 'PlannerInputError';
  }
}

export function recommendPlannerStructure(
  input: PlannerInput,
): PlannerRecommendation {
  validateInput(input);

  const assumptions: string[] = [];
  const warnings: string[] = [];
  const goal = input.goal ?? 'maintenance';
  const level = input.level ?? 'beginner';
  const sessionMinutes = input.sessionMinutes ?? 45;
  const modalities = [...(input.modalities ?? [])];

  if (!input.goal)
    assumptions.push('Objetivo nao informado: manutencao usada como base.');
  if (!input.level)
    assumptions.push(
      'Nivel nao informado: iniciante usado como base conservadora.',
    );
  if (!input.sessionMinutes)
    assumptions.push(
      'Duracao nao informada: sessoes de 45 minutos usadas como base.',
    );
  if (!modalities.length)
    assumptions.push(
      'Modalidades nao informadas: estrutura neutra, sem restringir o catalogo.',
    );

  const composition = classifyComposition(modalities);
  const weeklyFrequency = selectFrequency(input, level, warnings);
  const scheduledDays = spreadTrainingDays(
    input.availableDays,
    weeklyFrequency,
  );
  const splitType = selectSplit({
    composition,
    frequency: weeklyFrequency,
    goal,
    level,
    hasResistance: modalities.some((item) => resistanceModalities.has(item)),
  });
  const splitLabel = createSplitLabel(splitType, weeklyFrequency, composition);
  const agendaLabel = createAgendaLabel(weeklyFrequency);
  const sessionProfile = classifySessionDuration(sessionMinutes);
  const days = createDayTemplates({
    composition,
    estimatedMinutes: sessionMinutes,
    scheduledDays,
    splitType,
  });

  const rationale = [
    `${splitLabel} escolhido para ${weeklyFrequency} sessoes semanais.`,
    `Agenda distribuida nos dias disponiveis para favorecer recuperacao.`,
    `Duracao classificada como ${sessionProfile}.`,
  ];

  if (composition === 'mixed') {
    rationale.push(
      'Modalidades combinadas serao preservadas na geracao das sessoes.',
    );
  } else if (composition === 'cardio' || composition === 'mobility') {
    rationale.push(
      'Estrutura personalizada usada porque nao ha treino resistido selecionado.',
    );
  }

  return {
    goal,
    level,
    weeklyFrequency,
    splitType,
    splitLabel,
    agendaLabel,
    sessionMinutes,
    sessionProfile,
    composition,
    modalities,
    days,
    assumptions,
    rationale,
    warnings,
    stabilityPolicy: plannerStabilityPolicy,
  };
}

function validateInput(input: PlannerInput) {
  if (!input.availableDays.length) {
    throw new PlannerInputError(
      'NO_AVAILABLE_DAYS',
      'Informe pelo menos um dia disponivel.',
    );
  }

  if (new Set(input.availableDays).size !== input.availableDays.length) {
    throw new PlannerInputError(
      'DUPLICATE_AVAILABLE_DAYS',
      'Os dias disponiveis nao podem se repetir.',
    );
  }

  for (const day of input.availableDays) {
    if (!weekdays.includes(day)) {
      throw new PlannerInputError('INVALID_WEEKDAY', `Dia invalido: ${day}.`);
    }
  }

  if (input.goal && !plannerGoals.includes(input.goal)) {
    throw new PlannerInputError('INVALID_GOAL', 'Objetivo invalido.');
  }

  if (input.level && !plannerLevels.includes(input.level)) {
    throw new PlannerInputError('INVALID_LEVEL', 'Nivel invalido.');
  }

  for (const modality of input.modalities ?? []) {
    if (!plannerModalities.includes(modality)) {
      throw new PlannerInputError(
        'INVALID_MODALITY',
        `Modalidade invalida: ${modality}.`,
      );
    }
  }

  if (
    input.sessionMinutes !== undefined &&
    (!Number.isInteger(input.sessionMinutes) ||
      input.sessionMinutes < 20 ||
      input.sessionMinutes > 180)
  ) {
    throw new PlannerInputError(
      'INVALID_SESSION_DURATION',
      'A duracao deve ser um numero inteiro entre 20 e 180 minutos.',
    );
  }

  if (
    input.desiredWeeklyFrequency !== undefined &&
    (!Number.isInteger(input.desiredWeeklyFrequency) ||
      input.desiredWeeklyFrequency < 1 ||
      input.desiredWeeklyFrequency > 6)
  ) {
    throw new PlannerInputError(
      'INVALID_FREQUENCY',
      'A frequencia desejada deve estar entre 1 e 6 dias.',
    );
  }

  if (
    input.desiredWeeklyFrequency !== undefined &&
    input.desiredWeeklyFrequency > input.availableDays.length
  ) {
    throw new PlannerInputError(
      'FREQUENCY_EXCEEDS_AVAILABILITY',
      'A frequencia desejada excede os dias disponiveis.',
    );
  }
}

function selectFrequency(
  input: PlannerInput,
  level: PlannerLevel,
  warnings: string[],
) {
  if (input.desiredWeeklyFrequency !== undefined) {
    return input.desiredWeeklyFrequency;
  }

  const frequency = Math.min(
    input.availableDays.length,
    automaticFrequencyCaps[level],
  );

  if (frequency < input.availableDays.length) {
    warnings.push(
      `A recomendacao automatica reservou ${input.availableDays.length - frequency} dia(s) disponivel(is) para recuperacao.`,
    );
  }

  return frequency;
}

function classifyComposition(
  modalities: PlannerModality[],
): PlannerComposition {
  if (!modalities.length) return 'unspecified';

  const groups = new Set<
    Exclude<PlannerComposition, 'mixed' | 'unspecified'>
  >();
  for (const modality of modalities) {
    if (resistanceModalities.has(modality)) groups.add('resistance');
    if (cardioModalities.has(modality)) groups.add('cardio');
    if (mobilityModalities.has(modality)) groups.add('mobility');
  }

  if (groups.size > 1) return 'mixed';
  return groups.values().next().value ?? 'unspecified';
}

function selectSplit({
  composition,
  frequency,
  goal,
  level,
  hasResistance,
}: {
  composition: PlannerComposition;
  frequency: number;
  goal: PlannerGoal;
  level: PlannerLevel;
  hasResistance: boolean;
}): PlannerSplitType {
  if (
    composition === 'cardio' ||
    composition === 'mobility' ||
    (composition === 'mixed' && !hasResistance)
  ) {
    return 'custom';
  }

  if (frequency <= 2) return 'full_body';

  if (frequency === 3) {
    if (
      level === 'beginner' ||
      goal === 'strength' ||
      goal === 'health' ||
      goal === 'fat_loss' ||
      goal === 'recomposition' ||
      goal === 'maintenance'
    ) {
      return 'full_body';
    }
    return 'push_pull_legs';
  }

  if (frequency === 4) return 'upper_lower';

  if (frequency === 5) {
    return level === 'advanced' && goal === 'hypertrophy'
      ? 'body_part'
      : 'hybrid';
  }

  if (
    level !== 'beginner' &&
    (goal === 'hypertrophy' || goal === 'strength' || goal === 'recomposition')
  ) {
    return 'push_pull_legs';
  }

  return 'hybrid';
}

function createSplitLabel(
  splitType: PlannerSplitType,
  frequency: number,
  composition: PlannerComposition,
) {
  if (splitType === 'full_body') {
    if (frequency === 1) return 'Full body';
    return `Full body ${createLetterSequence(frequency)}`;
  }
  if (splitType === 'upper_lower') return 'Upper/Lower A/B';
  if (splitType === 'push_pull_legs') {
    return frequency >= 6 ? 'Push/Pull/Legs x2' : 'Push/Pull/Legs';
  }
  if (splitType === 'body_part') return 'Divisao por grupos musculares';
  if (splitType === 'hybrid') return 'Divisao hibrida';
  if (composition === 'cardio') return 'Condicionamento semanal';
  if (composition === 'mobility') return 'Mobilidade semanal';
  return 'Condicionamento e mobilidade';
}

function createAgendaLabel(frequency: number) {
  if (frequency === 1) return 'A';
  return createLetterSequence(frequency);
}

function createLetterSequence(length: number) {
  return Array.from({ length }, (_, index) =>
    String.fromCharCode('A'.charCodeAt(0) + index),
  ).join('');
}

function classifySessionDuration(minutes: number): PlannerSessionProfile {
  if (minutes <= 35) return 'compact';
  if (minutes <= 65) return 'standard';
  return 'extended';
}

function spreadTrainingDays(
  availableDays: PlannerWeekday[],
  frequency: number,
) {
  const positions = availableDays
    .map((day) => weekdays.indexOf(day))
    .sort((a, b) => a - b);
  if (positions.length === frequency) {
    return positions.map((position) => weekdays[position]);
  }

  const combinations = createCombinations(positions, frequency);
  let best = combinations[0];
  let bestScore = scoreSchedule(best);

  for (const combination of combinations.slice(1)) {
    const score = scoreSchedule(combination);
    if (score > bestScore) {
      best = combination;
      bestScore = score;
    }
  }

  return best.map((position) => weekdays[position]);
}

function createCombinations(values: number[], size: number) {
  const result: number[][] = [];

  function visit(start: number, current: number[]) {
    if (current.length === size) {
      result.push([...current]);
      return;
    }

    for (
      let index = start;
      index <= values.length - (size - current.length);
      index += 1
    ) {
      current.push(values[index]);
      visit(index + 1, current);
      current.pop();
    }
  }

  visit(0, []);
  return result;
}

function scoreSchedule(positions: number[]) {
  if (positions.length === 1) return 0;

  const gaps = positions.map((position, index) => {
    const next = positions[(index + 1) % positions.length];
    return index === positions.length - 1
      ? next + 7 - position
      : next - position;
  });
  const minimumGap = Math.min(...gaps);
  const maximumGap = Math.max(...gaps);
  const squaredGaps = gaps.reduce((total, gap) => total + gap * gap, 0);
  return minimumGap * 1000 - maximumGap * 100 - squaredGaps;
}

function createDayTemplates({
  composition,
  estimatedMinutes,
  scheduledDays,
  splitType,
}: {
  composition: PlannerComposition;
  estimatedMinutes: number;
  scheduledDays: PlannerWeekday[];
  splitType: PlannerSplitType;
}): PlannerDayTemplate[] {
  const focuses = createFocusSequence(
    splitType,
    scheduledDays.length,
    composition,
  );

  return scheduledDays.map((weekday, position) => ({
    weekday,
    position,
    title: focuses[position].title,
    focus: focuses[position].focus,
    estimatedMinutes,
  }));
}

function createFocusSequence(
  splitType: PlannerSplitType,
  frequency: number,
  composition: PlannerComposition,
) {
  const letters = createLetterSequence(frequency).split('');

  if (splitType === 'full_body') {
    return letters.map((letter) => ({
      title: frequency === 1 ? 'Full body' : `Full body ${letter}`,
      focus: 'Corpo inteiro',
    }));
  }

  if (splitType === 'upper_lower') {
    const sequence = [
      ['Superiores A', 'Membros superiores'],
      ['Inferiores A', 'Membros inferiores'],
      ['Superiores B', 'Membros superiores'],
      ['Inferiores B', 'Membros inferiores'],
    ];
    return sequence
      .slice(0, frequency)
      .map(([title, focus]) => ({ title, focus }));
  }

  if (splitType === 'push_pull_legs') {
    const sequence = Array.from({ length: frequency }, (_, index) => {
      const cycle = frequency <= 3 ? '' : index < 3 ? ' A' : ' B';
      const position = index % 3;
      if (position === 0)
        return [`Empurrar${cycle}`, 'Peito, ombros e triceps'];
      if (position === 1) return [`Puxar${cycle}`, 'Costas e biceps'];
      return [`Pernas${cycle}`, 'Membros inferiores'];
    });
    return sequence.map(([title, focus]) => ({ title, focus }));
  }

  if (splitType === 'body_part') {
    const sequence = [
      ['Peito e triceps', 'Peito e triceps'],
      ['Costas e biceps', 'Costas e biceps'],
      ['Pernas', 'Membros inferiores'],
      ['Ombros', 'Ombros'],
      ['Bracos e complementares', 'Bracos e pontos complementares'],
    ];
    return sequence
      .slice(0, frequency)
      .map(([title, focus]) => ({ title, focus }));
  }

  if (splitType === 'hybrid') {
    const sequence = [
      ['Superiores', 'Membros superiores'],
      ['Inferiores', 'Membros inferiores'],
      ['Empurrar', 'Peito, ombros e triceps'],
      ['Puxar', 'Costas e biceps'],
      ['Pernas', 'Membros inferiores'],
      ['Corpo inteiro', 'Corpo inteiro'],
    ];
    return sequence
      .slice(0, frequency)
      .map(([title, focus]) => ({ title, focus }));
  }

  const customTitle =
    composition === 'cardio'
      ? 'Condicionamento'
      : composition === 'mobility'
        ? 'Mobilidade'
        : 'Condicionamento e mobilidade';
  return letters.map((letter) => ({
    title: frequency === 1 ? customTitle : `${customTitle} ${letter}`,
    focus: customTitle,
  }));
}

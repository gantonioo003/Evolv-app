import {
  PlannerInputError,
  recommendPlannerStructure,
} from './planner.rules.js';
import type { PlannerInput } from './planner.types.js';

const everyDay: PlannerInput['availableDays'] = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
];

describe('recommendPlannerStructure', () => {
  it('monta full body ABC para iniciante com tres dias', () => {
    const result = recommendPlannerStructure({
      goal: 'hypertrophy',
      level: 'beginner',
      availableDays: everyDay,
      desiredWeeklyFrequency: 3,
      sessionMinutes: 50,
      modalities: ['machines', 'free-weights'],
    });

    expect(result.splitType).toBe('full_body');
    expect(result.splitLabel).toBe('Full body ABC');
    expect(result.agendaLabel).toBe('ABC');
    expect(result.days.map((day) => day.weekday)).toEqual([
      'monday',
      'wednesday',
      'friday',
    ]);
  });

  it('escolhe upper lower para quatro sessoes', () => {
    const result = recommendPlannerStructure({
      goal: 'strength',
      level: 'intermediate',
      availableDays: ['monday', 'tuesday', 'thursday', 'friday'],
      sessionMinutes: 60,
      modalities: ['full-gym'],
    });

    expect(result.splitType).toBe('upper_lower');
    expect(result.splitLabel).toBe('Upper/Lower A/B');
    expect(result.days.map((day) => day.title)).toEqual([
      'Superiores A',
      'Inferiores A',
      'Superiores B',
      'Inferiores B',
    ]);
  });

  it('usa ABCDE por grupos musculares para hipertrofia avancada', () => {
    const result = recommendPlannerStructure({
      goal: 'hypertrophy',
      level: 'advanced',
      availableDays: everyDay,
      desiredWeeklyFrequency: 5,
      sessionMinutes: 70,
      modalities: ['full-gym'],
    });

    expect(result.splitType).toBe('body_part');
    expect(result.agendaLabel).toBe('ABCDE');
    expect(result.days).toHaveLength(5);
  });

  it('usa push pull legs duas vezes em seis sessoes', () => {
    const result = recommendPlannerStructure({
      goal: 'recomposition',
      level: 'intermediate',
      availableDays: everyDay,
      desiredWeeklyFrequency: 6,
      modalities: ['machines', 'cables'],
    });

    expect(result.splitType).toBe('push_pull_legs');
    expect(result.splitLabel).toBe('Push/Pull/Legs x2');
    expect(result.days.at(-1)?.title).toBe('Pernas B');
  });

  it('aceita cardio sem treino resistido', () => {
    const result = recommendPlannerStructure({
      goal: 'health',
      level: 'beginner',
      availableDays: ['monday', 'wednesday', 'friday', 'sunday'],
      sessionMinutes: 35,
      modalities: ['running', 'cycling'],
    });

    expect(result.composition).toBe('cardio');
    expect(result.splitType).toBe('custom');
    expect(result.splitLabel).toBe('Condicionamento semanal');
  });

  it('preserva combinacao entre musculacao e cardio', () => {
    const result = recommendPlannerStructure({
      goal: 'fat_loss',
      level: 'intermediate',
      availableDays: ['monday', 'tuesday', 'thursday', 'saturday'],
      modalities: ['free-weights', 'running'],
    });

    expect(result.composition).toBe('mixed');
    expect(result.splitType).toBe('upper_lower');
    expect(result.rationale).toContain(
      'Modalidades combinadas serao preservadas na geracao das sessoes.',
    );
  });

  it('usa padroes conservadores quando dados opcionais foram pulados', () => {
    const result = recommendPlannerStructure({
      availableDays: ['monday', 'wednesday', 'friday'],
    });

    expect(result.goal).toBe('maintenance');
    expect(result.level).toBe('beginner');
    expect(result.sessionMinutes).toBe(45);
    expect(result.composition).toBe('unspecified');
    expect(result.assumptions).toHaveLength(4);
  });

  it('limita automaticamente a frequencia e reserva recuperacao', () => {
    const result = recommendPlannerStructure({
      level: 'beginner',
      availableDays: everyDay,
      modalities: ['calisthenics'],
    });

    expect(result.weeklyFrequency).toBe(4);
    expect(result.warnings[0]).toContain('3 dia(s)');
    expect(result.stabilityPolicy.automaticMutations).toBe(false);
  });

  it('rejeita frequencia maior que a disponibilidade', () => {
    expect(() =>
      recommendPlannerStructure({
        availableDays: ['monday', 'wednesday'],
        desiredWeeklyFrequency: 3,
      }),
    ).toThrowError(
      expect.objectContaining<Partial<PlannerInputError>>({
        code: 'FREQUENCY_EXCEEDS_AVAILABILITY',
      }),
    );
  });

  it('rejeita uma agenda sem dias disponiveis', () => {
    expect(() => recommendPlannerStructure({ availableDays: [] })).toThrowError(
      expect.objectContaining<Partial<PlannerInputError>>({
        code: 'NO_AVAILABLE_DAYS',
      }),
    );
  });

  it('produz sempre o mesmo resultado para a mesma entrada', () => {
    const input: PlannerInput = {
      goal: 'hypertrophy',
      level: 'advanced',
      availableDays: everyDay,
      desiredWeeklyFrequency: 5,
      modalities: ['full-gym', 'cardio-equipment'],
    };

    expect(recommendPlannerStructure(input)).toEqual(
      recommendPlannerStructure(input),
    );
  });
});

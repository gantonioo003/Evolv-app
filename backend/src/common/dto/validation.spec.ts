import { validate } from 'class-validator';
import { CreateFoodLogItemDto } from '../../nutrition/dto/create-food-log-item.dto.js';
import { CreateProgressEntryDto } from '../../progress/dto/progress-entry.dto.js';
import { CreateExerciseLogDto } from '../../workouts/dto/exercise-log.dto.js';

describe('DTO validation', () => {
  it('rejeita carga negativa', async () => {
    const dto = Object.assign(new CreateExerciseLogDto(), { load_kg: -1 });
    expect(await validate(dto)).not.toHaveLength(0);
  });

  it('rejeita alimento sem quantidade positiva', async () => {
    const dto = Object.assign(new CreateFoodLogItemDto(), {
      food_name: 'Arroz',
      quantity: 0,
      unit: 'g',
    });
    expect(await validate(dto)).not.toHaveLength(0);
  });

  it('aceita uma medicao de progresso valida', async () => {
    const dto = Object.assign(new CreateProgressEntryDto(), {
      measured_at: '2026-09-30',
      weight_kg: 82.5,
      waist_cm: 84,
    });
    expect(await validate(dto)).toHaveLength(0);
  });
});

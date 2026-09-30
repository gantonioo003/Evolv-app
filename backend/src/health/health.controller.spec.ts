import { HealthController } from './health.controller.js';
import type { HealthService } from './health.service.js';

describe('HealthController', () => {
  const readiness = vi.fn().mockResolvedValue({
    dependencies: { supabase: 'up' },
    service: 'evolv-backend',
    status: 'ready',
  });
  const controller = new HealthController({
    readiness,
  } as unknown as HealthService);

  it('informa que a API esta disponivel', () => {
    const result = controller.check();

    expect(result.service).toBe('evolv-backend');
    expect(result.status).toBe('ok');
    expect(result.timestamp).toBeTruthy();
  });

  it('consulta a disponibilidade das dependencias', async () => {
    await expect(controller.readiness()).resolves.toMatchObject({
      dependencies: { supabase: 'up' },
      status: 'ready',
    });
    expect(readiness).toHaveBeenCalledOnce();
  });
});

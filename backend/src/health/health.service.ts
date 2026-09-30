import { Injectable } from '@nestjs/common';
import { SupabaseService } from '../supabase/supabase.service.js';

@Injectable()
export class HealthService {
  constructor(private readonly supabase: SupabaseService) {}

  async readiness() {
    const startedAt = performance.now();
    await this.supabase.assertAvailable();

    return {
      dependencies: { supabase: 'up' },
      latencyMs: Math.round(performance.now() - startedAt),
      service: 'evolv-backend',
      status: 'ready',
      timestamp: new Date().toISOString(),
    };
  }
}

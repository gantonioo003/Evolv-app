import {
  Injectable,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  createClient,
  type SupabaseClient,
  type User,
} from '@supabase/supabase-js';
import type { Database } from '../database/database.types.js';

@Injectable()
export class SupabaseService {
  private readonly url: string;
  private readonly anonKey: string;
  private readonly authClient: SupabaseClient<Database>;

  constructor(config: ConfigService) {
    this.url = config.getOrThrow<string>('SUPABASE_URL');
    this.anonKey = config.getOrThrow<string>('SUPABASE_ANON_KEY');
    this.authClient = this.createClient();
  }

  async getUser(accessToken: string): Promise<User> {
    const { data, error } = await this.authClient.auth.getUser(accessToken);

    if (
      error &&
      (Number(error.status ?? 0) >= 500 ||
        error.name === 'AuthRetryableFetchError')
    ) {
      throw new ServiceUnavailableException({
        code: 'AUTH_SERVICE_UNAVAILABLE',
        message: 'O servico de autenticacao esta indisponivel no momento.',
      });
    }

    if (error || !data.user) {
      throw new UnauthorizedException({
        code: 'INVALID_ACCESS_TOKEN',
        message: 'Sessao invalida ou expirada.',
      });
    }

    return data.user;
  }

  async assertAvailable(): Promise<void> {
    try {
      const response = await fetch(`${this.url}/auth/v1/health`, {
        headers: { apikey: this.anonKey },
        signal: AbortSignal.timeout(3000),
      });

      if (response.ok) return;
    } catch {
      // The public error below intentionally hides network and provider details.
    }

    throw new ServiceUnavailableException({
      code: 'SUPABASE_UNAVAILABLE',
      message: 'O Supabase esta indisponivel no momento.',
    });
  }

  forUser(accessToken: string): SupabaseClient<Database> {
    return this.createClient(accessToken);
  }

  private createClient(accessToken?: string): SupabaseClient<Database> {
    return createClient<Database>(this.url, this.anonKey, {
      auth: {
        autoRefreshToken: false,
        detectSessionInUrl: false,
        persistSession: false,
      },
      global: accessToken
        ? { headers: { Authorization: `Bearer ${accessToken}` } }
        : undefined,
    });
  }
}

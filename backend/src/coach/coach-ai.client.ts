import {
  HttpException,
  Injectable,
  ServiceUnavailableException,
  GatewayTimeoutException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
@Injectable()
export class CoachAiClient {
  constructor(private readonly config: ConfigService) {}
  async request(
    userId: string,
    path: string,
    method: 'POST' | 'PUT' | 'DELETE' = 'POST',
    body?: unknown,
  ): Promise<unknown> {
    if (!this.config.get<boolean>('COACH_AI_ENABLED', false))
      throw new ServiceUnavailableException('COACH_AI_DISABLED');
    const key = this.config.get<string>('COACH_AI_SERVICE_KEY');
    if (!key || key.length < 32)
      throw new ServiceUnavailableException('COACH_AI_NOT_CONFIGURED');
    let response: Response;
    try {
      response = await fetch(
        new URL(
          path,
          this.config.get<string>('COACH_AI_URL', 'http://127.0.0.1:8010'),
        ),
        {
          method,
          redirect: 'error',
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer ' + key,
            'X-Evolv-User-ID': userId,
          },
          body: body === undefined ? undefined : JSON.stringify(body),
          signal: AbortSignal.timeout(
            this.config.get<number>('COACH_AI_TIMEOUT_MS', 180000),
          ),
        },
      );
    } catch (error) {
      if (
        error instanceof Error &&
        ['TimeoutError', 'AbortError'].includes(error.name)
      )
        throw new GatewayTimeoutException('COACH_AI_TIMEOUT');
      throw new ServiceUnavailableException('COACH_AI_UNAVAILABLE');
    }
    if (!response.ok) {
      const status = [404, 409, 422, 429].includes(response.status)
        ? response.status
        : 503;
      throw new HttpException('COACH_AI_REQUEST_FAILED', status);
    }
    if (response.status === 204) return null;
    try {
      return await response.json();
    } catch {
      throw new ServiceUnavailableException('COACH_AI_INVALID_RESPONSE');
    }
  }
}

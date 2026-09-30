import type { CallHandler, ExecutionContext } from '@nestjs/common';
import { RequestTimeoutException } from '@nestjs/common';
import type { ConfigService } from '@nestjs/config';
import { firstValueFrom, NEVER, of } from 'rxjs';
import { RequestTimeoutInterceptor } from './request-timeout.interceptor.js';

describe('RequestTimeoutInterceptor', () => {
  const config = {
    get: vi.fn().mockReturnValue(10),
  } as unknown as ConfigService;
  const interceptor = new RequestTimeoutInterceptor(config);
  const context = {} as ExecutionContext;

  it('mantem respostas concluidas dentro do limite', async () => {
    const next = { handle: () => of({ ok: true }) } as CallHandler;

    await expect(
      firstValueFrom(interceptor.intercept(context, next)),
    ).resolves.toEqual({ ok: true });
  });

  it('interrompe respostas que excedem o limite', async () => {
    const next = { handle: () => NEVER } as CallHandler;

    await expect(
      firstValueFrom(interceptor.intercept(context, next)),
    ).rejects.toBeInstanceOf(RequestTimeoutException);
  });
});

import type { CallHandler, ExecutionContext } from '@nestjs/common';
import { RequestTimeoutException } from '@nestjs/common';
import type { ConfigService } from '@nestjs/config';
import { firstValueFrom, NEVER, of, timer } from 'rxjs';
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
  it('usa limite separado no Coach sem alterar os demais endpoints', async () => {
    class Controller {}
    Reflect.defineMetadata('coachRequest', true, Controller);
    const configured = {
      get: (name: string, fallback: number) =>
        name === 'REQUEST_TIMEOUT_MS' ? 10 : fallback,
    } as ConfigService;
    const coachInterceptor = new RequestTimeoutInterceptor(configured);
    const coachContext = {
      getHandler: () => () => undefined,
      getClass: () => Controller,
    } as unknown as ExecutionContext;
    const next = { handle: () => timer(30) } as CallHandler;
    await expect(
      firstValueFrom(coachInterceptor.intercept(coachContext, next)),
    ).resolves.toBe(0);
  });
});

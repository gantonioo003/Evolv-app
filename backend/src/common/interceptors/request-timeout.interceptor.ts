import {
  CallHandler,
  ExecutionContext,
  Injectable,
  NestInterceptor,
  RequestTimeoutException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Reflector } from '@nestjs/core';
import {
  catchError,
  Observable,
  throwError,
  timeout,
  TimeoutError,
} from 'rxjs';

@Injectable()
export class RequestTimeoutInterceptor implements NestInterceptor {
  private readonly timeoutMs: number;
  private readonly coachTimeoutMs: number;

  constructor(
    config: ConfigService,
    private readonly reflector: Reflector = new Reflector(),
  ) {
    this.timeoutMs = config.get<number>('REQUEST_TIMEOUT_MS', 15000);
    this.coachTimeoutMs = Math.max(
      config.get<number>('COACH_REQUEST_TIMEOUT_MS', 210000),
      config.get<number>('COACH_AI_TIMEOUT_MS', 180000) + 10000,
    );
  }

  intercept(
    _context: ExecutionContext,
    next: CallHandler,
  ): Observable<unknown> {
    const isCoach =
      typeof _context.getHandler === 'function' &&
      this.reflector.getAllAndOverride<boolean>('coachRequest', [
        _context.getHandler(),
        _context.getClass(),
      ]);
    return next.handle().pipe(
      timeout(isCoach ? this.coachTimeoutMs : this.timeoutMs),
      catchError((error: unknown) => {
        if (error instanceof TimeoutError) {
          return throwError(
            () =>
              new RequestTimeoutException({
                code: 'REQUEST_TIMEOUT',
                message: 'A requisicao demorou mais que o esperado.',
              }),
          );
        }

        return throwError(() => error);
      }),
    );
  }
}

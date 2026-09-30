import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import type { Response } from 'express';
import type { RequestWithContext } from '../middleware/request-context.middleware.js';

type ErrorBody = {
  code?: string;
  message?: string | string[];
};

@Catch()
export class HttpExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(HttpExceptionFilter.name);

  catch(exception: unknown, host: ArgumentsHost): void {
    const context = host.switchToHttp();
    const response = context.getResponse<Response>();
    const request = context.getRequest<RequestWithContext>();
    const status =
      exception instanceof HttpException
        ? exception.getStatus()
        : HttpStatus.INTERNAL_SERVER_ERROR;
    const exceptionResponse =
      exception instanceof HttpException ? exception.getResponse() : null;
    const body =
      typeof exceptionResponse === 'object' && exceptionResponse !== null
        ? (exceptionResponse as ErrorBody)
        : null;
    const rawMessage =
      body?.message ??
      (typeof exceptionResponse === 'string' ? exceptionResponse : undefined);

    if (!(exception instanceof HttpException) || status >= 500) {
      this.logger.error(
        JSON.stringify({
          error:
            exception instanceof Error ? exception.message : 'Unknown error',
          path: request.url,
          requestId: request.requestId,
          statusCode: status,
        }),
        exception instanceof Error ? exception.stack : undefined,
      );
    }

    response.status(status).json({
      statusCode: status,
      code: body?.code ?? this.defaultCode(status),
      message:
        rawMessage ??
        (status === HttpStatus.INTERNAL_SERVER_ERROR
          ? 'Erro interno do servidor.'
          : 'A requisicao nao pode ser concluida.'),
      path: request.url,
      requestId: request.requestId,
      timestamp: new Date().toISOString(),
    });
  }

  private defaultCode(status: number): string {
    if (status === HttpStatus.UNAUTHORIZED) return 'UNAUTHORIZED';
    if (status === HttpStatus.FORBIDDEN) return 'FORBIDDEN';
    if (status === HttpStatus.NOT_FOUND) return 'NOT_FOUND';
    if (status === HttpStatus.BAD_REQUEST) return 'VALIDATION_ERROR';
    if (status === HttpStatus.CONFLICT) return 'CONFLICT';
    if (status === HttpStatus.UNPROCESSABLE_ENTITY) return 'VALIDATION_ERROR';
    if (status === HttpStatus.REQUEST_TIMEOUT) return 'REQUEST_TIMEOUT';
    if (status === HttpStatus.TOO_MANY_REQUESTS) return 'RATE_LIMITED';
    if (status === HttpStatus.SERVICE_UNAVAILABLE) return 'SERVICE_UNAVAILABLE';
    return 'INTERNAL_SERVER_ERROR';
  }
}

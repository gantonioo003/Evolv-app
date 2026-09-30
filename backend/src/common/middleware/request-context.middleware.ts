import { randomUUID } from 'node:crypto';
import { Logger } from '@nestjs/common';
import type { NextFunction, Request, Response } from 'express';

export type RequestWithContext = Request & { requestId?: string };

const requestIdPattern = /^[a-zA-Z0-9._:-]{1,100}$/;
const logger = new Logger('HTTP');

export function requestContextMiddleware(
  request: RequestWithContext,
  response: Response,
  next: NextFunction,
): void {
  const receivedRequestId = request.header('x-request-id');
  const requestId =
    receivedRequestId && requestIdPattern.test(receivedRequestId)
      ? receivedRequestId
      : randomUUID();
  const startedAt = performance.now();

  request.requestId = requestId;
  response.setHeader('X-Request-Id', requestId);
  response.once('finish', () => {
    logger.log(
      JSON.stringify({
        durationMs: Math.round(performance.now() - startedAt),
        method: request.method,
        path: request.originalUrl,
        requestId,
        statusCode: response.statusCode,
      }),
    );
  });

  next();
}

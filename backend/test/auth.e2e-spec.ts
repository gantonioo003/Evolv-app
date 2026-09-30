import {
  Controller,
  Get,
  INestApplication,
  UnauthorizedException,
  UseGuards,
} from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import type { User } from '@supabase/supabase-js';
import request from 'supertest';
import type { App } from 'supertest/types.js';
import { SupabaseAuthGuard } from '../src/auth/supabase-auth.guard.js';
import { CurrentUser } from '../src/common/decorators/current-user.decorator.js';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter.js';
import { requestContextMiddleware } from '../src/common/middleware/request-context.middleware.js';
import { SupabaseService } from '../src/supabase/supabase.service.js';

@Controller('private-test')
@UseGuards(SupabaseAuthGuard)
class PrivateTestController {
  @Get()
  read(@CurrentUser() user: User) {
    return { userId: user.id };
  }
}

describe('Supabase authentication (e2e)', () => {
  let app: INestApplication<App>;
  const getUser = vi.fn();

  beforeEach(async () => {
    getUser.mockReset();
    const moduleFixture: TestingModule = await Test.createTestingModule({
      controllers: [PrivateTestController],
      providers: [
        SupabaseAuthGuard,
        { provide: SupabaseService, useValue: { getUser } },
      ],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.use(requestContextMiddleware);
    app.useGlobalFilters(new HttpExceptionFilter());
    await app.init();
  });

  it('recusa requisicao sem token Bearer', async () => {
    const response = await request(app.getHttpServer())
      .get('/private-test')
      .expect(401);

    expect(response.body.code).toBe('MISSING_ACCESS_TOKEN');
    expect(response.body.requestId).toBeTruthy();
    expect(response.headers['x-request-id']).toBe(response.body.requestId);
    expect(getUser).not.toHaveBeenCalled();
  });

  it('recusa token invalido ou expirado', async () => {
    getUser.mockRejectedValueOnce(
      new UnauthorizedException({
        code: 'INVALID_ACCESS_TOKEN',
        message: 'Sessao invalida ou expirada.',
      }),
    );

    const response = await request(app.getHttpServer())
      .get('/private-test')
      .set('Authorization', 'Bearer expired-token')
      .expect(401);

    expect(response.body.code).toBe('INVALID_ACCESS_TOKEN');
    expect(response.body.message).toBe('Sessao invalida ou expirada.');
  });

  it('entrega a identidade para uma rota protegida', async () => {
    getUser.mockResolvedValueOnce({ id: 'user-123' } as User);

    await request(app.getHttpServer())
      .get('/private-test')
      .set('Authorization', 'Bearer valid-token')
      .set('X-Request-Id', 'e2e-auth-request')
      .expect(200)
      .expect({ userId: 'user-123' })
      .expect('X-Request-Id', 'e2e-auth-request');

    expect(getUser).toHaveBeenCalledWith('valid-token');
  });

  afterEach(async () => {
    await app.close();
  });
});

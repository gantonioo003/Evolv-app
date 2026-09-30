import { Logger, ValidationPipe } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory } from '@nestjs/core';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import helmet from 'helmet';
import { AppModule } from './app.module.js';
import { HttpExceptionFilter } from './common/filters/http-exception.filter.js';
import { requestContextMiddleware } from './common/middleware/request-context.middleware.js';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  const config = app.get(ConfigService);
  const port = config.get<number>('PORT', 3000);
  const apiPrefix = config.get<string>('API_PREFIX', 'api');
  const isProduction = config.get<string>('NODE_ENV') === 'production';
  const swaggerEnabled =
    config.get<boolean | undefined>('SWAGGER_ENABLED') ?? !isProduction;
  const corsOrigins = config
    .get<string>('CORS_ORIGINS', 'http://localhost:8081')
    .split(',')
    .map((origin) => origin.trim());

  app.setGlobalPrefix(apiPrefix);
  app.use(
    helmet({
      contentSecurityPolicy: swaggerEnabled ? false : undefined,
    }),
  );
  app.use(requestContextMiddleware);
  app.enableCors({ origin: corsOrigins });
  app.useGlobalPipes(
    new ValidationPipe({
      forbidNonWhitelisted: true,
      transform: true,
      whitelist: true,
    }),
  );
  app.useGlobalFilters(new HttpExceptionFilter());
  app.enableShutdownHooks();

  if (swaggerEnabled) {
    const swaggerConfig = new DocumentBuilder()
      .setTitle('Evolv API')
      .setDescription(
        'API autenticada para perfis, objetivos, treinos, cargas, dieta e progresso.',
      )
      .setVersion('0.1.0')
      .addBearerAuth(
        {
          bearerFormat: 'Supabase JWT',
          description:
            'Token de acesso temporario fornecido pelo Supabase Auth.',
          scheme: 'bearer',
          type: 'http',
        },
        'supabase',
      )
      .build();
    const documentFactory = () =>
      SwaggerModule.createDocument(app, swaggerConfig);

    SwaggerModule.setup(`${apiPrefix}/docs`, app, documentFactory, {
      jsonDocumentUrl: `${apiPrefix}/docs-json`,
      swaggerOptions: { persistAuthorization: true },
    });
  }

  await app.listen(port);
  Logger.log(
    `API disponivel em http://localhost:${port}/${apiPrefix}`,
    'Bootstrap',
  );
  if (swaggerEnabled) {
    Logger.log(
      `Documentacao em http://localhost:${port}/${apiPrefix}/docs`,
      'Bootstrap',
    );
  }
}
await bootstrap();

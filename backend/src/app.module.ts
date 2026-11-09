import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { APP_GUARD, APP_INTERCEPTOR } from '@nestjs/core';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { AuthModule } from './auth/auth.module.js';
import { CoachModule } from './coach/coach.module.js';
import { RequestTimeoutInterceptor } from './common/interceptors/request-timeout.interceptor.js';
import { envValidationSchema } from './config/env.validation.js';
import { HealthModule } from './health/health.module.js';
import { GoalsModule } from './goals/goals.module.js';
import { NutritionModule } from './nutrition/nutrition.module.js';
import { PlannerModule } from './planner/planner.module.js';
import { ProgressModule } from './progress/progress.module.js';
import { ProfilesModule } from './profiles/profiles.module.js';
import { SupabaseModule } from './supabase/supabase.module.js';
import { WorkoutsModule } from './workouts/workouts.module.js';

@Module({
  imports: [
    ConfigModule.forRoot({
      cache: true,
      isGlobal: true,
      validationSchema: envValidationSchema,
    }),
    ThrottlerModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService) => [
        {
          limit: config.get<number>('THROTTLE_LIMIT', 120),
          ttl: config.get<number>('THROTTLE_TTL_MS', 60000),
        },
      ],
    }),
    SupabaseModule,
    AuthModule,
    CoachModule,
    HealthModule,
    ProfilesModule,
    GoalsModule,
    WorkoutsModule,
    NutritionModule,
    ProgressModule,
    PlannerModule,
  ],
  providers: [
    { provide: APP_GUARD, useClass: ThrottlerGuard },
    { provide: APP_INTERCEPTOR, useClass: RequestTimeoutInterceptor },
  ],
})
export class AppModule {}

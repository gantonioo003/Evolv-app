import { Module } from '@nestjs/common';
import { AuthModule } from '../auth/auth.module.js';
import { PlannerModule } from '../planner/planner.module.js';
import { CoachController } from './coach.controller.js';
import { CoachService } from './coach.service.js';
import { CoachAiClient } from './coach-ai.client.js';
import { CoachContextService } from './coach-context.service.js';
import { CoachHistoryService } from './coach-history.service.js';
@Module({
  imports: [AuthModule, PlannerModule],
  controllers: [CoachController],
  providers: [
    CoachService,
    CoachAiClient,
    CoachContextService,
    CoachHistoryService,
  ],
})
export class CoachModule {}

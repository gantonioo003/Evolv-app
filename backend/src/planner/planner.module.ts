import { Module } from '@nestjs/common';
import { AuthModule } from '../auth/auth.module.js';
import { PlannerController } from './planner.controller.js';
import { PlannerDayContextService } from './planner-day-context.service.js';
import { NutritionPlannerService } from './nutrition-planner.service.js';
import { PlannerAdjustmentsService } from './planner-adjustments.service.js';
import { PlannerService } from './planner.service.js';

@Module({
  imports: [AuthModule],
  controllers: [PlannerController],
  providers: [
    PlannerService,
    NutritionPlannerService,
    PlannerAdjustmentsService,
    PlannerDayContextService,
  ],
  exports: [
    PlannerService,
    NutritionPlannerService,
    PlannerAdjustmentsService,
    PlannerDayContextService,
  ],
})
export class PlannerModule {}

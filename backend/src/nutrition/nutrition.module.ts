import { Module } from '@nestjs/common';
import { AuthModule } from '../auth/auth.module.js';
import { NutritionController } from './nutrition.controller.js';
import { NutritionService } from './nutrition.service.js';

@Module({
  imports: [AuthModule],
  controllers: [NutritionController],
  providers: [NutritionService],
  exports: [NutritionService],
})
export class NutritionModule {}

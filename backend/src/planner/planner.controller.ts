import {
  Body,
  Controller,
  Get,
  Param,
  ParseUUIDPipe,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import {
  ApiBearerAuth,
  ApiOperation,
  ApiTags,
  ApiUnauthorizedResponse,
} from '@nestjs/swagger';
import type { User } from '@supabase/supabase-js';
import { SupabaseAuthGuard } from '../auth/supabase-auth.guard.js';
import { AccessToken } from '../common/decorators/access-token.decorator.js';
import { CurrentUser } from '../common/decorators/current-user.decorator.js';
import { PaginationQueryDto } from '../common/dto/pagination-query.dto.js';
import { CreatePlannerAdjustmentDto } from './dto/create-planner-adjustment.dto.js';
import { GeneratePlannerPlanDto } from './dto/generate-planner-plan.dto.js';
import { GenerateNutritionPlanDto } from './dto/generate-nutrition-plan.dto.js';
import { ListPlannerPlansQueryDto } from './dto/list-planner-plans-query.dto.js';
import { GetDayContextQueryDto } from './dto/get-day-context-query.dto.js';
import { NutritionPlannerService } from './nutrition-planner.service.js';
import { PlannerAdjustmentsService } from './planner-adjustments.service.js';
import { PlannerDayContextService } from './planner-day-context.service.js';
import { PlannerService } from './planner.service.js';

@ApiTags('Planner')
@ApiBearerAuth('supabase')
@ApiUnauthorizedResponse({
  description: 'Sessao ausente, invalida ou expirada.',
})
@Controller('planner')
@UseGuards(SupabaseAuthGuard)
export class PlannerController {
  constructor(
    private readonly planner: PlannerService,
    private readonly nutritionPlanner: NutritionPlannerService,
    private readonly adjustments: PlannerAdjustmentsService,
    private readonly dayContext: PlannerDayContextService,
  ) {}

  @Get('day-context')
  @ApiOperation({ summary: 'Resolve treino e dieta aplicaveis a uma data' })
  getDayContext(
    @AccessToken() token: string,
    @Query() query: GetDayContextQueryDto,
  ) {
    return this.dayContext.get(token, query.date);
  }

  @Post('plans/generate')
  @ApiOperation({ summary: 'Gera e salva um plano de treino' })
  generate(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Body() dto: GeneratePlannerPlanDto,
  ) {
    return this.planner.generateAndSave(user.id, token, dto);
  }

  @Get('plans')
  @ApiOperation({ summary: 'Lista os planos do usuario' })
  list(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Query() query: ListPlannerPlansQueryDto,
  ) {
    return this.planner.listPlans(user.id, token, query);
  }

  @Get('plans/:planId')
  @ApiOperation({ summary: 'Busca um plano completo' })
  getOne(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('planId', ParseUUIDPipe) planId: string,
  ) {
    return this.planner.getPlan(user.id, token, planId);
  }

  @Post('plans/:planId/activate')
  @ApiOperation({ summary: 'Ativa um plano e arquiva o ativo anterior' })
  activate(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('planId', ParseUUIDPipe) planId: string,
  ) {
    return this.planner.setPlanStatus(user.id, token, planId, 'active');
  }

  @Post('plans/:planId/archive')
  @ApiOperation({ summary: 'Arquiva um plano' })
  archive(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('planId', ParseUUIDPipe) planId: string,
  ) {
    return this.planner.setPlanStatus(user.id, token, planId, 'archived');
  }

  @Post('nutrition-plans/generate')
  @ApiOperation({ summary: 'Gera e salva um plano alimentar' })
  generateNutritionPlan(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Body() dto: GenerateNutritionPlanDto,
  ) {
    return this.nutritionPlanner.generateAndSave(user.id, token, dto);
  }

  @Get('nutrition-plans')
  @ApiOperation({ summary: 'Lista os planos alimentares do usuario' })
  listNutritionPlans(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Query() query: ListPlannerPlansQueryDto,
  ) {
    return this.nutritionPlanner.listPlans(user.id, token, query);
  }

  @Get('nutrition-plans/:planId')
  @ApiOperation({ summary: 'Busca um plano alimentar completo' })
  getNutritionPlan(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('planId', ParseUUIDPipe) planId: string,
  ) {
    return this.nutritionPlanner.getPlan(user.id, token, planId);
  }

  @Post('nutrition-plans/:planId/activate')
  @ApiOperation({ summary: 'Ativa um plano alimentar' })
  activateNutritionPlan(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('planId', ParseUUIDPipe) planId: string,
  ) {
    return this.nutritionPlanner.setPlanStatus(
      user.id,
      token,
      planId,
      'active',
    );
  }

  @Post('nutrition-plans/:planId/archive')
  @ApiOperation({ summary: 'Arquiva um plano alimentar' })
  archiveNutritionPlan(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('planId', ParseUUIDPipe) planId: string,
  ) {
    return this.nutritionPlanner.setPlanStatus(
      user.id,
      token,
      planId,
      'archived',
    );
  }

  @Post('adjustments/preview')
  @ApiOperation({ summary: 'Cria uma previa sem alterar o plano' })
  previewAdjustment(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Body() dto: CreatePlannerAdjustmentDto,
  ) {
    return this.adjustments.preview(user.id, token, dto);
  }

  @Get('adjustments')
  @ApiOperation({ summary: 'Lista o historico de ajustes do Planner' })
  listAdjustments(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Query() query: PaginationQueryDto,
  ) {
    return this.adjustments.list(user.id, token, query.limit);
  }

  @Get('adjustments/:adjustmentId')
  @ApiOperation({ summary: 'Busca uma previa ou ajuste aplicado' })
  getAdjustment(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('adjustmentId', ParseUUIDPipe) adjustmentId: string,
  ) {
    return this.adjustments.get(user.id, token, adjustmentId);
  }

  @Post('adjustments/:adjustmentId/apply')
  @ApiOperation({ summary: 'Confirma e aplica um ajuste pendente' })
  applyAdjustment(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('adjustmentId', ParseUUIDPipe) adjustmentId: string,
  ) {
    return this.adjustments.apply(user.id, token, adjustmentId);
  }

  @Post('adjustments/:adjustmentId/reject')
  @ApiOperation({ summary: 'Descarta um ajuste pendente' })
  rejectAdjustment(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('adjustmentId', ParseUUIDPipe) adjustmentId: string,
  ) {
    return this.adjustments.reject(user.id, token, adjustmentId);
  }

  @Post('adjustments/:adjustmentId/revert')
  @ApiOperation({ summary: 'Desfaz um ajuste aplicado e ainda compativel' })
  revertAdjustment(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('adjustmentId', ParseUUIDPipe) adjustmentId: string,
  ) {
    return this.adjustments.revert(user.id, token, adjustmentId);
  }
}

import {
  Body,
  Controller,
  Delete,
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
import { CreateFoodLogDto } from './dto/create-food-log.dto.js';
import { CreateFoodLogItemDto } from './dto/create-food-log-item.dto.js';
import { NutritionLogsQueryDto } from './dto/nutrition-logs-query.dto.js';
import { NutritionService } from './nutrition.service.js';

@ApiTags('Nutrition')
@ApiBearerAuth('supabase')
@ApiUnauthorizedResponse({
  description: 'Sessao ausente, invalida ou expirada.',
})
@Controller('nutrition')
@UseGuards(SupabaseAuthGuard)
export class NutritionController {
  constructor(private readonly nutrition: NutritionService) {}

  @Get('active-plan')
  @ApiOperation({ summary: 'Busca o plano alimentar ativo' })
  getActivePlan(@CurrentUser() user: User, @AccessToken() token: string) {
    return this.nutrition.getActivePlan(user.id, token);
  }

  @Get('logs')
  @ApiOperation({ summary: 'Lista os registros alimentares' })
  listLogs(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Query() query: NutritionLogsQueryDto,
  ) {
    return this.nutrition.listLogs(user.id, token, query);
  }

  @Get('summary')
  @ApiOperation({ summary: 'Calcula os totais nutricionais de um periodo' })
  getSummary(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Query() query: NutritionLogsQueryDto,
  ) {
    return this.nutrition.getSummary(user.id, token, query);
  }

  @Post('logs')
  @ApiOperation({ summary: 'Cria um registro alimentar' })
  createLog(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Body() dto: CreateFoodLogDto,
  ) {
    return this.nutrition.createLog(user.id, token, dto);
  }

  @Post('logs/:foodLogId/items')
  @ApiOperation({ summary: 'Adiciona um alimento a um registro' })
  addItem(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('foodLogId', ParseUUIDPipe) foodLogId: string,
    @Body() dto: CreateFoodLogItemDto,
  ) {
    return this.nutrition.addItem(user.id, token, foodLogId, dto);
  }

  @Delete('logs/:foodLogId')
  @ApiOperation({ summary: 'Remove um registro alimentar' })
  removeLog(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('foodLogId', ParseUUIDPipe) foodLogId: string,
  ) {
    return this.nutrition.removeLog(user.id, token, foodLogId);
  }

  @Delete('log-items/:itemId')
  @ApiOperation({ summary: 'Remove um alimento registrado' })
  removeItem(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('itemId', ParseUUIDPipe) itemId: string,
  ) {
    return this.nutrition.removeItem(user.id, token, itemId);
  }
}

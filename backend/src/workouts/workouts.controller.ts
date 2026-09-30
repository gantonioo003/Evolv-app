import {
  Body,
  Controller,
  Get,
  Param,
  ParseUUIDPipe,
  Patch,
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
import { CreateWorkoutLogDto } from './dto/create-workout-log.dto.js';
import {
  CreateExerciseLogDto,
  UpdateExerciseLogDto,
} from './dto/exercise-log.dto.js';
import { ExerciseCatalogQueryDto } from './dto/exercise-catalog-query.dto.js';
import {
  ProgressionQueryDto,
  UpdateProgressionSuggestionDto,
} from './dto/progression-query.dto.js';
import { WorkoutsService } from './workouts.service.js';

@ApiTags('Workouts')
@ApiBearerAuth('supabase')
@ApiUnauthorizedResponse({
  description: 'Sessao ausente, invalida ou expirada.',
})
@Controller('workouts')
@UseGuards(SupabaseAuthGuard)
export class WorkoutsController {
  constructor(private readonly workouts: WorkoutsService) {}

  @Get('active-plan')
  @ApiOperation({ summary: 'Busca o plano de treino ativo' })
  getActivePlan(@CurrentUser() user: User, @AccessToken() token: string) {
    return this.workouts.getActivePlan(user.id, token);
  }

  @Get('exercises')
  @ApiOperation({ summary: 'Pesquisa o catalogo de exercicios' })
  listExercises(
    @AccessToken() token: string,
    @Query() query: ExerciseCatalogQueryDto,
  ) {
    return this.workouts.listExercises(token, query);
  }

  @Get('logs')
  @ApiOperation({ summary: 'Lista os treinos registrados' })
  listWorkoutLogs(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Query() query: PaginationQueryDto,
  ) {
    return this.workouts.listWorkoutLogs(user.id, token, query.limit);
  }

  @Post('logs')
  @ApiOperation({ summary: 'Registra um treino realizado' })
  createWorkoutLog(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Body() dto: CreateWorkoutLogDto,
  ) {
    return this.workouts.createWorkoutLog(user.id, token, dto);
  }

  @Get('exercises/:exerciseId/history')
  @ApiOperation({ summary: 'Busca o historico de carga de um exercicio' })
  getExerciseHistory(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('exerciseId', ParseUUIDPipe) exerciseId: string,
    @Query() query: PaginationQueryDto,
  ) {
    return this.workouts.getExerciseHistory(
      user.id,
      token,
      exerciseId,
      query.limit,
    );
  }

  @Post('exercises/:exerciseId/logs')
  @ApiOperation({ summary: 'Registra carga sem exigir um treino completo' })
  createExerciseLog(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('exerciseId', ParseUUIDPipe) exerciseId: string,
    @Body() dto: CreateExerciseLogDto,
  ) {
    return this.workouts.createExerciseLog(user.id, token, exerciseId, dto);
  }

  @Patch('exercise-logs/:logId')
  @ApiOperation({ summary: 'Atualiza um registro de carga' })
  updateExerciseLog(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('logId', ParseUUIDPipe) logId: string,
    @Body() dto: UpdateExerciseLogDto,
  ) {
    return this.workouts.updateExerciseLog(user.id, token, logId, dto);
  }

  @Get('progression-suggestions')
  @ApiOperation({ summary: 'Lista sugestoes opcionais de progressao' })
  listProgressionSuggestions(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Query() query: ProgressionQueryDto,
  ) {
    return this.workouts.listProgressionSuggestions(user.id, token, query);
  }

  @Patch('progression-suggestions/:suggestionId')
  @ApiOperation({ summary: 'Aceita ou descarta uma sugestao de progressao' })
  updateProgressionSuggestion(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('suggestionId', ParseUUIDPipe) suggestionId: string,
    @Body() dto: UpdateProgressionSuggestionDto,
  ) {
    return this.workouts.updateProgressionSuggestion(
      user.id,
      token,
      suggestionId,
      dto,
    );
  }
}

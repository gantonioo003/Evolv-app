import {
  Body,
  Controller,
  Get,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
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
import { CreateGoalDto } from './dto/create-goal.dto.js';
import { UpdateGoalDto } from './dto/update-goal.dto.js';
import { GoalsService } from './goals.service.js';

@ApiTags('Goals')
@ApiBearerAuth('supabase')
@ApiUnauthorizedResponse({
  description: 'Sessao ausente, invalida ou expirada.',
})
@Controller('goals')
@UseGuards(SupabaseAuthGuard)
export class GoalsController {
  constructor(private readonly goals: GoalsService) {}

  @Get()
  @ApiOperation({ summary: 'Lista os objetivos do usuario' })
  list(@CurrentUser() user: User, @AccessToken() token: string) {
    return this.goals.list(user.id, token);
  }

  @Get('active')
  @ApiOperation({ summary: 'Busca o objetivo ativo' })
  getActive(@CurrentUser() user: User, @AccessToken() token: string) {
    return this.goals.getActive(user.id, token);
  }

  @Post()
  @ApiOperation({ summary: 'Cria um objetivo' })
  create(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Body() dto: CreateGoalDto,
  ) {
    return this.goals.create(user.id, token, dto);
  }

  @Patch(':goalId')
  @ApiOperation({ summary: 'Atualiza um objetivo' })
  update(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('goalId', ParseUUIDPipe) goalId: string,
    @Body() dto: UpdateGoalDto,
  ) {
    return this.goals.update(user.id, token, goalId, dto);
  }
}

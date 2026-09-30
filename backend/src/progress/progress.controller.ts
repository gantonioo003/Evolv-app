import {
  Body,
  Controller,
  Delete,
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
import {
  CreateProgressEntryDto,
  UpdateProgressEntryDto,
} from './dto/progress-entry.dto.js';
import { ProgressService } from './progress.service.js';

@ApiTags('Progress')
@ApiBearerAuth('supabase')
@ApiUnauthorizedResponse({
  description: 'Sessao ausente, invalida ou expirada.',
})
@Controller('progress')
@UseGuards(SupabaseAuthGuard)
export class ProgressController {
  constructor(private readonly progress: ProgressService) {}

  @Get()
  @ApiOperation({ summary: 'Lista o historico de progresso' })
  list(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Query() query: PaginationQueryDto,
  ) {
    return this.progress.list(user.id, token, query.limit);
  }

  @Post()
  @ApiOperation({ summary: 'Registra peso, medidas ou observacoes' })
  create(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Body() dto: CreateProgressEntryDto,
  ) {
    return this.progress.create(user.id, token, dto);
  }

  @Patch(':entryId')
  @ApiOperation({ summary: 'Atualiza um registro de progresso' })
  update(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('entryId', ParseUUIDPipe) entryId: string,
    @Body() dto: UpdateProgressEntryDto,
  ) {
    return this.progress.update(user.id, token, entryId, dto);
  }

  @Delete(':entryId')
  @ApiOperation({ summary: 'Remove um registro de progresso' })
  remove(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('entryId', ParseUUIDPipe) entryId: string,
  ) {
    return this.progress.remove(user.id, token, entryId);
  }
}

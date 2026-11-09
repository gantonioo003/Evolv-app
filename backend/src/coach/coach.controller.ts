import {
  Body,
  BadRequestException,
  Controller,
  Delete,
  Param,
  ParseUUIDPipe,
  Post,
  Get,
  Patch,
  Query,
  SetMetadata,
  UseGuards,
} from '@nestjs/common';
import { ApiBearerAuth, ApiTags } from '@nestjs/swagger';
import type { User } from '@supabase/supabase-js';
import { SupabaseAuthGuard } from '../auth/supabase-auth.guard.js';
import { AccessToken } from '../common/decorators/access-token.decorator.js';
import { CurrentUser } from '../common/decorators/current-user.decorator.js';
import { CoachService } from './coach.service.js';
import { CoachHistoryService } from './coach-history.service.js';
import {
  CoachMessageDto,
  ConfirmCoachAdjustmentDto,
  CreateCoachSessionDto,
  CoachHistoryQueryDto,
  RenameCoachConversationDto,
} from './dto/coach.dto.js';

@ApiTags('Coach')
@ApiBearerAuth('supabase')
@Controller('coach')
@UseGuards(SupabaseAuthGuard)
@SetMetadata('coachRequest', true)
export class CoachController {
  constructor(
    private readonly coach: CoachService,
    private readonly history: CoachHistoryService,
  ) {}
  @Get('sessions')
  list(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Query() q: CoachHistoryQueryDto,
  ) {
    return this.history.list(user.id, token, q.limit, q.offset);
  }
  @Get('sessions/:sessionId/messages')
  messages(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('sessionId', ParseUUIDPipe) sid: string,
    @Query() q: CoachHistoryQueryDto,
  ) {
    return this.history.messages(user.id, token, sid, q.limit, q.offset);
  }
  @Patch('sessions/:sessionId')
  rename(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('sessionId', ParseUUIDPipe) sid: string,
    @Body() dto: RenameCoachConversationDto,
  ) {
    return this.history.rename(user.id, token, sid, dto.title);
  }
  @Post('sessions')
  create(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Body() dto: CreateCoachSessionDto,
  ) {
    return this.coach.create(user.id, token, dto);
  }
  @Delete('sessions/:sessionId')
  remove(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('sessionId', ParseUUIDPipe) sid: string,
  ) {
    return this.coach.remove(user.id, token, sid);
  }
  @Post('sessions/:sessionId/messages')
  message(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('sessionId', ParseUUIDPipe) sid: string,
    @Body() dto: CoachMessageDto,
  ) {
    return this.coach.message(user.id, token, sid, dto);
  }
  @Post('sessions/:sessionId/adjustments/:adjustmentId/apply')
  apply(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('sessionId', ParseUUIDPipe) sid: string,
    @Param('adjustmentId', ParseUUIDPipe) id: string,
    @Body() dto: ConfirmCoachAdjustmentDto,
  ) {
    if (dto.confirmed !== true)
      throw new BadRequestException('COACH_EXPLICIT_CONFIRMATION_REQUIRED');
    return this.coach.decide(user.id, token, sid, id, 'apply');
  }
  @Post('sessions/:sessionId/adjustments/:adjustmentId/reject')
  reject(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('sessionId', ParseUUIDPipe) sid: string,
    @Param('adjustmentId', ParseUUIDPipe) id: string,
    @Body() dto: ConfirmCoachAdjustmentDto,
  ) {
    if (dto.confirmed !== true)
      throw new BadRequestException('COACH_EXPLICIT_CONFIRMATION_REQUIRED');
    return this.coach.decide(user.id, token, sid, id, 'reject');
  }
  @Post('sessions/:sessionId/adjustments/:adjustmentId/revert')
  revert(
    @CurrentUser() user: User,
    @AccessToken() token: string,
    @Param('sessionId', ParseUUIDPipe) sid: string,
    @Param('adjustmentId', ParseUUIDPipe) id: string,
    @Body() dto: ConfirmCoachAdjustmentDto,
  ) {
    if (dto.confirmed !== true)
      throw new BadRequestException('COACH_EXPLICIT_CONFIRMATION_REQUIRED');
    return this.coach.decide(user.id, token, sid, id, 'revert');
  }
}

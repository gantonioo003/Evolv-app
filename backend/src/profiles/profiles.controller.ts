import { Body, Controller, Get, Patch, UseGuards } from '@nestjs/common';
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
import { UpdateProfileDto } from './dto/update-profile.dto.js';
import { ProfilesService } from './profiles.service.js';

@ApiTags('Profiles')
@ApiBearerAuth('supabase')
@ApiUnauthorizedResponse({
  description: 'Sessao ausente, invalida ou expirada.',
})
@Controller('profiles')
@UseGuards(SupabaseAuthGuard)
export class ProfilesController {
  constructor(private readonly profiles: ProfilesService) {}

  @Get('me')
  @ApiOperation({ summary: 'Busca o perfil do usuario autenticado' })
  getMine(@CurrentUser() user: User, @AccessToken() accessToken: string) {
    return this.profiles.getMine(user.id, accessToken);
  }

  @Patch('me')
  @ApiOperation({ summary: 'Atualiza o perfil do usuario autenticado' })
  updateMine(
    @CurrentUser() user: User,
    @AccessToken() accessToken: string,
    @Body() dto: UpdateProfileDto,
  ) {
    return this.profiles.updateMine(user.id, accessToken, dto);
  }
}

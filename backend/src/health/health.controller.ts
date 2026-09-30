import { Controller, Get } from '@nestjs/common';
import {
  ApiOkResponse,
  ApiOperation,
  ApiServiceUnavailableResponse,
  ApiTags,
} from '@nestjs/swagger';
import { SkipThrottle } from '@nestjs/throttler';
import { HealthService } from './health.service.js';

@ApiTags('Health')
@SkipThrottle()
@Controller('health')
export class HealthController {
  constructor(private readonly health: HealthService) {}

  @Get()
  @ApiOperation({ summary: 'Confirma que o processo da API esta ativo' })
  @ApiOkResponse({ description: 'API ativa.' })
  check() {
    return {
      service: 'evolv-backend',
      status: 'ok',
      timestamp: new Date().toISOString(),
    };
  }

  @Get('ready')
  @ApiOperation({ summary: 'Confirma que a API consegue acessar o Supabase' })
  @ApiOkResponse({ description: 'API e Supabase disponiveis.' })
  @ApiServiceUnavailableResponse({ description: 'Supabase indisponivel.' })
  readiness() {
    return this.health.readiness();
  }
}

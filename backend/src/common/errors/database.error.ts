import { InternalServerErrorException, Logger } from '@nestjs/common';
import type { PostgrestError } from '@supabase/supabase-js';

export function throwDatabaseError(
  context: string,
  error: PostgrestError,
  publicMessage: string,
): never {
  Logger.error(`${error.code}: ${error.message}`, error.details, context);
  throw new InternalServerErrorException({
    code: 'DATABASE_ERROR',
    message: publicMessage,
  });
}

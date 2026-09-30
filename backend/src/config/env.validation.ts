import Joi from 'joi';

export const envValidationSchema = Joi.object({
  NODE_ENV: Joi.string()
    .valid('development', 'test', 'production')
    .default('development'),
  PORT: Joi.number().port().default(3000),
  API_PREFIX: Joi.string().default('api'),
  CORS_ORIGINS: Joi.string().default('http://localhost:8081'),
  REQUEST_TIMEOUT_MS: Joi.number()
    .integer()
    .min(1000)
    .max(60000)
    .default(15000),
  SWAGGER_ENABLED: Joi.boolean().optional(),
  THROTTLE_LIMIT: Joi.number().integer().min(10).max(10000).default(120),
  THROTTLE_TTL_MS: Joi.number().integer().min(1000).max(3600000).default(60000),
  SUPABASE_URL: Joi.string().uri().required(),
  SUPABASE_ANON_KEY: Joi.string().min(20).required(),
});

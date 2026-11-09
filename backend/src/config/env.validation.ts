import Joi from 'joi';

export const envValidationSchema = Joi.object({
  NODE_ENV: Joi.string()
    .valid('development', 'test', 'production')
    .default('development'),
  PORT: Joi.number().port().default(3000),
  API_PREFIX: Joi.string().default('api'),
  COACH_AI_ENABLED: Joi.boolean().default(false),
  COACH_AI_URL: Joi.string()
    .uri({ scheme: ['http', 'https'] })
    .default('http://127.0.0.1:8010'),
  COACH_AI_SERVICE_KEY: Joi.when('COACH_AI_ENABLED', {
    is: true,
    // oxlint-disable-next-line unicorn/no-thenable -- Joi schema branch, not a Promise.
    then: Joi.string().min(32).required(),
    otherwise: Joi.string().allow('').optional(),
  }),
  COACH_AI_TIMEOUT_MS: Joi.number()
    .integer()
    .min(1000)
    .max(600000)
    .default(180000),
  COACH_REQUEST_TIMEOUT_MS: Joi.number()
    .integer()
    .min(1000)
    .max(610000)
    .default(210000),
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

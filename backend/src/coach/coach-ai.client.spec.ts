import { ConfigService } from '@nestjs/config';
import { CoachAiClient } from './coach-ai.client.js';

describe('CoachAiClient', () => {
  afterEach(() => vi.unstubAllGlobals());
  function client(enabled = true) {
    const values: Record<string, unknown> = {
      COACH_AI_ENABLED: enabled,
      COACH_AI_SERVICE_KEY: 'x'.repeat(40),
    };
    return new CoachAiClient({
      get: (k: string, d: unknown) => values[k] ?? d,
    } as ConfigService);
  }
  it('envia identidade de servico sem encaminhar JWT ao modelo', async () => {
    const request = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ session_id: 'test' })));
    vi.stubGlobal('fetch', request);
    await client().request('authenticated-user', '/v1/sessions', 'POST', {});
    expect(request.mock.calls[0][1].headers['X-Evolv-User-ID']).toBe(
      'authenticated-user',
    );
    expect(request.mock.calls[0][1].headers.Authorization).toBe(
      'Bearer ' + 'x'.repeat(40),
    );
    expect(request.mock.calls[0][1].redirect).toBe('error');
  });
  it('desativado nao faz chamada', async () => {
    const request = vi.fn();
    vi.stubGlobal('fetch', request);
    await expect(
      client(false).request('u', '/v1/sessions'),
    ).rejects.toMatchObject({ status: 503 });
    expect(request).not.toHaveBeenCalled();
  });
  it('oculta detalhes do upstream', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(new Response('private secret', { status: 500 })),
    );
    await expect(client().request('u', '/v1/sessions')).rejects.toMatchObject({
      message: 'COACH_AI_REQUEST_FAILED',
      status: 503,
    });
  });
  it('preserva ocupacao e reconhece timeout', async () => {
    const request = vi
      .fn()
      .mockResolvedValueOnce(new Response('', { status: 429 }))
      .mockRejectedValueOnce(new DOMException('private', 'TimeoutError'));
    vi.stubGlobal('fetch', request);
    await expect(client().request('u', '/v1/sessions')).rejects.toMatchObject({
      status: 429,
    });
    await expect(client().request('u', '/v1/sessions')).rejects.toMatchObject({
      status: 504,
    });
  });
  it('recusa JSON invalido', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('not-json')));
    await expect(client().request('u', '/v1/sessions')).rejects.toMatchObject({
      message: 'COACH_AI_INVALID_RESPONSE',
    });
  });
});

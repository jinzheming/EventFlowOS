import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './client';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('api client', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends CSRF tokens on state-changing requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: 'item-1', version: 1 }));
    vi.stubGlobal('fetch', fetchMock);

    await api.createItem('csrf-token', { title: 'Write docs', scope: 'work' });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/items',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ title: 'Write docs', scope: 'work' }),
        headers: expect.objectContaining({
          'content-type': 'application/json',
          'x-csrf-token': 'csrf-token',
        }),
      }),
    );
  });

  it('preserves If-Match headers when patching an item', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: 'item-1', version: 2 }));
    vi.stubGlobal('fetch', fetchMock);

    await api.patchItem('csrf-token', { id: 'item-1', version: 1 } as Parameters<typeof api.patchItem>[1], {
      status: 'done',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/items/item-1',
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({
          'content-type': 'application/json',
          'if-match': 'v1',
          'x-csrf-token': 'csrf-token',
        }),
      }),
    );
  });

  it('surfaces problem detail messages from failed requests', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'CSRF required' }, 403)));

    await expect(
      api.putReminder('bad-csrf', 'item-1', {
        timing: 'at_start',
        offset_minutes: 0,
        timezone: 'Asia/Shanghai',
        external_enabled: false,
      }),
    ).rejects.toThrow('CSRF required');
  });
});

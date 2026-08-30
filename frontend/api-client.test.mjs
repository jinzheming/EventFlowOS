import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { api, ApiError } from './src/api/client.ts';

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

test('CSRF_REQUIRED refreshes the session and retries the write once', async () => {
  const requests = [];
  globalThis.fetch = async (url, init = {}) => {
    requests.push({ url, init });
    if (requests.length === 1) {
      return new Response(
        JSON.stringify({
          status: 403,
          code: 'CSRF_REQUIRED',
          detail: 'Valid CSRF token is required.',
        }),
        { status: 403, headers: { 'content-type': 'application/problem+json' } },
      );
    }
    if (requests.length === 2) {
      return new Response(JSON.stringify({ csrf_token: 'fresh-token' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    }
    return new Response(null, { status: 204 });
  };

  await api.deleteItem('stale-token', 'item-1');

  assert.equal(requests.length, 3);
  assert.equal(requests[0].url, '/api/v1/items/item-1');
  assert.equal(new Headers(requests[0].init.headers).get('x-csrf-token'), 'stale-token');
  assert.equal(requests[1].url, '/api/v1/auth/session');
  assert.equal(requests[2].url, '/api/v1/items/item-1');
  assert.equal(new Headers(requests[2].init.headers).get('x-csrf-token'), 'fresh-token');
});

test('non-CSRF API errors preserve status and code without retrying', async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response(
      JSON.stringify({ status: 412, code: 'VERSION_CONFLICT', detail: 'Version conflict.' }),
      { status: 412, headers: { 'content-type': 'application/problem+json' } },
    );
  };

  await assert.rejects(
    api.patchItem('token', { id: 'item-1', version: 3 }, { title: 'updated' }),
    (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 412);
      assert.equal(error.code, 'VERSION_CONFLICT');
      return true;
    },
  );
  assert.equal(calls, 1);
});

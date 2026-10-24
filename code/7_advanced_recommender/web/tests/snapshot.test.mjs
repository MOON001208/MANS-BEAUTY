import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchCatalog } from '../scripts/snapshot-catalog.mjs';

const env = { NEXT_PUBLIC_SUPABASE_URL: 'https://test.supabase.co', NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test' };

test('snapshot reads every page even when server cap is below 500', async () => {
  const calls = [];
  const pages = [[{ id: 'a' }], [{ id: 'b' }], []];
  const rows = await fetchCatalog(env, async url => {
    calls.push(url);
    return { ok: true, json: async () => pages.shift() };
  });
  assert.deepEqual(rows.map(p => p.id), ['a', 'b']);
  assert.equal(new URL(calls[1]).searchParams.get('id'), 'gt.a');
});

test('snapshot rejects a privileged key before making requests', async () => {
  let called = false;
  await assert.rejects(fetchCatalog({ ...env, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'sb_secret_forbidden' }, async () => { called = true; }));
  assert.equal(called, false);
});

test('snapshot fails rather than silently truncating a repeated cursor', async () => {
  await assert.rejects(fetchCatalog(env, async () => ({ ok: true, json: async () => [{ id: 'same' }] })), /커서/);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { loadCatalog } from '../src/lib/catalog.ts';

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://test.supabase.co';
process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_test';

const product = { id: 'A1', name: '상품', profile_metadata: { version: 'rules-ko-v3', analyzed_count: 10 } };
const snapshot = { captured_at: '2026-11-03T00:00:00Z', count: 1, products: [product] };
const jsonResponse = body => ({ ok: true, json: async () => body });

test('live catalogue pages are used when available', async () => {
  const requests = [];
  const fetcher = async url => {
    requests.push(url);
    assert.ok(!url.includes('catalog-fallback'));
    return jsonResponse(requests.length === 1 ? [product] : []);
  };
  const result = await loadCatalog(new AbortController().signal, fetcher, 'https://site/catalog-fallback.json');
  assert.equal(result.source, 'live');
  assert.equal(result.products.length, 1);
  assert.equal(new URL(requests[1]).searchParams.get('id'), 'gt.A1');
});

test('API failure uses a dated public snapshot instead of returning zero recommendations', async () => {
  const requests = [];
  const result = await loadCatalog(new AbortController().signal, async url => {
    requests.push(url);
    return url.includes('catalog-fallback') ? jsonResponse(snapshot) : { ok: false, status: 503 };
  }, 'https://site/catalog-fallback.json');
  assert.equal(result.source, 'snapshot');
  assert.equal(result.capturedAt, snapshot.captured_at);
  assert.deepEqual(result.products, [product]);
  assert.equal(requests.length, 2);
});

test('unexpectedly empty API data also uses the snapshot', async () => {
  const result = await loadCatalog(new AbortController().signal,
    async url => jsonResponse(url.includes('catalog-fallback') ? snapshot : []),
    'https://site/catalog-fallback.json');
  assert.equal(result.source, 'snapshot');
});

test('both sources failing stays an error, not a valid empty catalogue', async () => {
  await assert.rejects(loadCatalog(new AbortController().signal,
    async () => ({ ok: false, status: 503 }), 'https://site/catalog-fallback.json'), /상품을 불러오지 못했습니다/);
});

test('a cancelled page does not fetch the fallback', async () => {
  const controller = new AbortController();
  let calls = 0;
  await assert.rejects(loadCatalog(controller.signal, async () => {
    calls += 1;
    controller.abort();
    throw new Error('cancelled');
  }, 'https://site/catalog-fallback.json'));
  assert.equal(calls, 1);
});

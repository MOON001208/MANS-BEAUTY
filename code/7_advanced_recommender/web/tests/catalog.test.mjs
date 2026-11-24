import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadCatalog } from '../src/lib/catalog.ts';
import { isFullFaceBase, isShadeCompatible, bestExplicitShadeOption } from '../src/lib/recommendation.ts';

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://test.supabase.co';
process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_test';

const product = { id: 'A1', name: '상품', profile_metadata: { version: 'rules-ko-v3', analyzed_count: 10 } };
const snapshot = { captured_at: '2026-11-03T00:00:00Z', count: 1, products: [product] };
const jsonResponse = body => ({ ok: true, json: async () => body });

test('shipped catalog preserves real formulation, gift, shade-range and sold-out regressions', () => {
  const { products } = JSON.parse(readFileSync(new URL('../public/catalog-fallback.json', import.meta.url)));
  const find = id => products.find(p => p.id === id);
  assert.equal(find('A000000258285').product_type, 'stick');
  assert.equal(find('A000000178092').product_type, 'liquid');
  for (const id of ['249713', '249714', '249774', '249778', '182290', '204828']) {
    assert.equal(isFullFaceBase(find('A000000' + id)), false, id);
  }
  const sand = find('A000000142173');
  assert.equal(isShadeCompatible(sand, '21'), false);
  assert.equal(isShadeCompatible(sand, '23'), true);
  assert.equal(bestExplicitShadeOption(sand, '23').sold_out, true);
  const range = find('A000000268424');
  assert.match(bestExplicitShadeOption(range, '23').name, /22~24호/);
  assert.equal(bestExplicitShadeOption(range, '25').sold_out, true);
  assert.equal(bestExplicitShadeOption(range, '21').sold_out, false);
});

test('a base form alone cannot qualify an excluded gift set or a listing with unrelated reviews', () => {
  for (const exclusion_reason of ['mixed_set', 'lip_contaminated_reviews']) {
    const profile_metadata = { ...product.profile_metadata, recommendation_eligibility: { eligible: false, exclusion_reason } };
    assert.equal(isFullFaceBase({ ...product, product_type: 'tone_lotion', profile_metadata }), false);
  }
  assert.equal(isFullFaceBase({ ...product, product_type: 'foundation_unknown' }), true);
});

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

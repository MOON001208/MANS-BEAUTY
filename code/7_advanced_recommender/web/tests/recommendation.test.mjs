import test from 'node:test';
import assert from 'node:assert/strict';
import { calcRecommendScore, searchProducts } from '../src/lib/recommendation.ts';
import { isPublicKey, validatePublicEnv } from '../scripts/check-public-env.mjs';

const product = { id: '1', name: '테스트', brand: '브랜드', compat_oily: 0.6, coverage_score: 4, longevity_score: 4, lightweight_score: 4, suitable_concerns: [], suitable_shades: ['23'], profile_metadata: { version: 'rules-ko-v1', analyzed_count: 30 } };
const score = (p, longevity) => calcRecommendScore(p, 'oily', [], 3, longevity, 3, '23');

test('unimportant longevity never rewards poor longevity', () => {
  assert.equal(score({ ...product, longevity_score: 1 }, 1), score({ ...product, longevity_score: 5 }, 1));
});
test('important longevity rewards better evidence', () => {
  assert.ok(score({ ...product, longevity_score: 5 }, 5) > score({ ...product, longevity_score: 1 }, 5));
});
test('source review total does not inflate confidence', () => {
  assert.equal(score({ ...product, review_count: 999999 }, 3), score({ ...product, review_count: 10 }, 3));
});
test('unversioned legacy profile is not ranked as current evidence', () => {
  assert.equal(score({ ...product, profile_metadata: null }, 3), -1);
});
test('search punctuation is literal, never a PostgREST filter', () => {
  assert.equal(searchProducts([product], '%,name.ilike.%').length, 0);
});
test('service role and secret keys are rejected', () => {
  const jwt = role => `eyJhbGciOiJIUzI1NiJ9.${Buffer.from(JSON.stringify({ role })).toString('base64url')}.signature`;
  assert.equal(isPublicKey(jwt('service_role')), false);
  assert.equal(isPublicKey('sb_secret_forbidden'), false);
  assert.equal(isPublicKey(jwt('anon')), true);
  assert.throws(() => validatePublicEnv({ NEXT_PUBLIC_SUPABASE_URL: 'https://test.supabase.co', NEXT_PUBLIC_SUPABASE_ANON_KEY: jwt('service_role') }));
  assert.throws(() => validatePublicEnv({ NEXT_PUBLIC_SUPABASE_URL: 'https://test.supabase.co', NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test', NEXT_PUBLIC_OTHER: jwt('service_role') }));
});

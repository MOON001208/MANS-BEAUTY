import test from 'node:test';
import assert from 'node:assert/strict';
import { calcRecommendScore, searchProducts, selectRecommendations, bestShadeOption, MIN_ANALYZED_REVIEWS } from '../src/lib/recommendation.ts';
import { isPublicKey, validatePublicEnv } from '../scripts/check-public-env.mjs';

const product = { id: '1', name: '테스트', brand: '브랜드', product_type: 'cushion', compat_oily: 0.6, coverage_score: 4, longevity_score: 4, lightweight_score: 4, suitable_concerns: [], suitable_shades: ['23'], profile_metadata: { version: 'rules-ko-v1', analyzed_count: 30 } };
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

const quiz = { skinType: 'oily', concerns: [], coveragePref: 3, longevityPref: 3, lightweightPref: 3, shade: 'any', applicationMethod: 'any' };
const withType = (id, product_type, extra = {}) => ({ ...product, id, product_type, ...extra });

test('thinly analyzed profiles are excluded, not merely ranked lower', () => {
  const thin = { ...product, id: 'thin', profile_metadata: { version: 'rules-ko-v1', analyzed_count: MIN_ANALYZED_REVIEWS - 1 } };
  const ids = selectRecommendations([product, thin], quiz).map(p => p.id);
  assert.deepEqual(ids, ['1']);
});
test('legacy profiles never reach the ranked list', () => {
  assert.deepEqual(selectRecommendations([{ ...product, profile_metadata: null }], quiz), []);
});
test('application method excludes the wrong product type', () => {
  const catalog = [withType('lotion', 'tone_lotion'), withType('cushion', 'cushion')];
  assert.deepEqual(selectRecommendations(catalog, { ...quiz, applicationMethod: 'hand' }).map(p => p.id), ['lotion']);
  assert.deepEqual(selectRecommendations(catalog, { ...quiz, applicationMethod: 'tool' }).map(p => p.id), ['cushion']);
});
test('equal scores break ties by id, so the order never wobbles between runs', () => {
  const catalog = [withType('b', 'cushion'), withType('a', 'cushion')];
  assert.deepEqual(selectRecommendations(catalog, quiz).map(p => p.id), ['a', 'b']);
});

const lined = options => ({ ...product, suitable_shades: [], profile_metadata: { version: 'rules-ko-v1', analyzed_count: 30, shade_lineup: { basis: 'number', options } } });
const two = lined([{ name: '01 라이트베이지', label: '01 라이트베이지', position: 0 }, { name: '02 내추럴베이지', label: '02 내추럴베이지', position: 1 }]);
const three = lined([{ name: '1호', label: '1호', position: 0 }, { name: '2호', label: '2호', position: 0.5 }, { name: '3호', label: '3호', position: 1 }]);
const shadeScore = (p, choice) => calcRecommendScore(p, 'oily', [], 3, 3, 3, choice);

test('a brand line suggests its lightest option for a light tone', () => {
  assert.equal(bestShadeOption(two, '21').label, '01 라이트베이지');
  assert.equal(bestShadeOption(two, '25').label, '02 내추럴베이지');
  assert.equal(bestShadeOption(three, '23').label, '2호');
});
test('brand numbering is never reported as a 21/23/25 shade', () => {
  assert.deepEqual(two.suitable_shades, []);
  assert.equal(bestShadeOption(two, 'any'), null);
});
test('a three shade line serves a standard tone better than a two shade line', () => {
  assert.ok(shadeScore(three, '23') > shadeScore(two, '23'));
  // At the extremes both lines have an exact option, so neither is favoured.
  assert.equal(shadeScore(three, '21'), shadeScore(two, '21'));
});
test('stated 21/23/25 shades still win over the relative fallback', () => {
  const stated = { ...product, suitable_shades: ['21'] };
  assert.ok(shadeScore(stated, '21') > shadeScore(two, '21'));
  // A product whose stated shades exclude the request is still penalised.
  assert.ok(shadeScore({ ...product, suitable_shades: ['25'] }, '21') < shadeScore(two, '21'));
});
test('a legacy profile exposes no lineup', () => {
  assert.equal(bestShadeOption({ ...two, profile_metadata: { ...two.profile_metadata, version: 'old' } }, '21'), null);
});

test('a concealer is not an answer to the full-face quiz', () => {
  const concealer = withType('con', 'concealer');
  const cushion = withType('cus', 'cushion');
  assert.deepEqual(selectRecommendations([concealer, cushion], quiz).map(p => p.id), ['cus']);
  // Nor when the tool answer would otherwise sweep in everything but tone lotion.
  assert.deepEqual(selectRecommendations([concealer, cushion], { ...quiz, applicationMethod: 'tool' }).map(p => p.id), ['cus']);
});

test('a buyable option is preferred over a nearer sold-out one', () => {
  const line = lined([
    { name: '1호', label: '1호', position: 0, sold_out: true },
    { name: '2호', label: '2호', position: 1, sold_out: false },
  ]);
  assert.equal(bestShadeOption(line, '21').label, '2호');
});
test('when every option is sold out the nearest is still named', () => {
  const line = lined([
    { name: '1호', label: '1호', position: 0, sold_out: true },
    { name: '2호', label: '2호', position: 1, sold_out: true },
  ]);
  assert.equal(bestShadeOption(line, '21').label, '1호');
});

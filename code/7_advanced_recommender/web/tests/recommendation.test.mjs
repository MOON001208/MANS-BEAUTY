import test from 'node:test';
import assert from 'node:assert/strict';
import {
  calcRecommendScore,
  searchProducts,
  selectRecommendations,
  splitRecommendations,
  bestShadeOption,
  shadeLineup,
  isShadeCompatible,
  classifyShadeMatch,
  parseExplicitShadeSpec,
  MIN_ANALYZED_REVIEWS,
  featureAssessment,
  evidenceSupport,
} from '../src/lib/recommendation.ts';
import { isPublicKey, validatePublicEnv } from '../scripts/check-public-env.mjs';

const product = { id: '1', name: '테스트', brand: '브랜드', product_type: 'cushion', compat_oily: 0.6, coverage_score: 4, longevity_score: 4, lightweight_score: 4, suitable_concerns: [], suitable_shades: ['23'], profile_metadata: { version: 'rules-ko-v3', analyzed_count: 30, evidence_counts: { coverage: 30, longevity: 30, lightweight: 30 } } };
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

test('known conflicting absolute shades cannot rank despite other strong scores', () => {
  const wrong = { ...product, id: 'wrong', suitable_shades: ['25'], compat_oily: 1, coverage_score: 5 };
  const unknown = { ...product, id: 'unknown', suitable_shades: [] };
  assert.deepEqual(selectRecommendations([wrong, unknown], { ...quiz, shade: '21' }).map(p => p.id), ['unknown']);
});

test('explicit 23-only products are excluded from both top and alternative recommendations when 21 is chosen', () => {
  const strongBase = { ...product, compat_oily: 1, coverage_score: 5, longevity_score: 5, lightweight_score: 5 };
  const explicit23OnlyCases = [
    { ...strongBase, id: 'stated-23', suitable_shades: ['23'] },
    { ...strongBase, id: 'option-map-23', suitable_shades: [], shade_options: { '23': '퍼펙트 커버(23호)' } },
    {
      ...strongBase,
      id: 'title-23-sand',
      name: '[피부착붙컬러] 그라펜 매치업 파운데이션 40ml 23 샌드 기획 (+엣지컷 퍼프)',
      suitable_shades: [],
      source_options: [{ id: '006', name: '매치업 샌드 기획 (+엣지컷 퍼프)', sold_out: true }],
    },
    { ...strongBase, id: 'title-23-ho', name: '매트 커버 파운데이션 23호 단품', suitable_shades: [] },
    {
      ...strongBase,
      id: 'soldout-23-only',
      suitable_shades: [],
      source_options: [{ id: '001', name: '23호 내추럴베이지', sold_out: true }],
    },
    {
      ...strongBase,
      id: 'lineup-23-to-29',
      name: '라끌랑 올데이 픽싱 커버 파운데이션 30ml (1호/2호) 2종 택1',
      suitable_shades: [],
      profile_metadata: {
        ...product.profile_metadata,
        shade_lineup: {
          basis: 'number',
          options: [
            { name: '1호 밝은피부용(23-25호)', label: '1호 밝은피부용', position: 0, sold_out: false },
            { name: '2호 보통피부용(27-29호)', label: '2호 보통피부용', position: 1, sold_out: false },
          ],
        },
      },
    },
    {
      ...strongBase,
      id: 'lineup-soldout-23-25',
      suitable_shades: [],
      profile_metadata: {
        ...product.profile_metadata,
        shade_lineup: {
          basis: 'number',
          options: [
            { name: '23호 샌드', label: '23호 샌드', position: 0, sold_out: true },
            { name: '25호 앰버', label: '25호 앰버', position: 1, sold_out: true },
          ],
        },
      },
    },
  ];
  const exact21 = { ...product, id: 'exact-21', suitable_shades: ['21'], shade_options: { '21': '21호 라이트' } };
  const relativeBrand = {
    ...product,
    id: 'relative-brand',
    name: '비레디 트루톤 커버로션 24H 40ml',
    suitable_shades: [],
    profile_metadata: {
      ...product.profile_metadata,
      shade_lineup: {
        basis: 'number',
        options: [
          { name: '[기획/10ml증정] 1호(밝은피부)', label: '1호', position: 0, sold_out: false },
          { name: '[기획/10ml증정] 2호(어두운피부)', label: '2호', position: 1, sold_out: false },
        ],
      },
    },
  };
  const unknownShade = {
    ...product,
    id: 'unknown-shade',
    name: '오브제 보송커버 2종 기획 (파운데이션 2호 + 오일 컨트롤 피니셔)',
    suitable_shades: [],
  };

  for (const item of explicit23OnlyCases) {
    assert.equal(isShadeCompatible(item, '21'), false, `${item.id} must conflict with 21`);
    assert.equal(classifyShadeMatch(item, '21'), 'conflict', `${item.id} must classify as conflict for 21`);
    assert.equal(bestShadeOption(item, '21'), null, `${item.id} must not suggest a 23+ option for 21`);
    assert.equal(isShadeCompatible(item, '23'), true, `${item.id} must remain eligible when 23 is chosen`);
  }

  const catalog = [...explicit23OnlyCases, exact21, relativeBrand, unknownShade];
  const ranked21 = selectRecommendations(catalog, { ...quiz, shade: '21' });
  assert.deepEqual(ranked21.map(p => p.id), ['exact-21', 'relative-brand', 'unknown-shade']);

  const groups21 = splitRecommendations(catalog, { ...quiz, shade: '21' });
  assert.deepEqual(groups21.primary.map(p => p.id), ['exact-21']);
  assert.deepEqual(groups21.alternatives.map(p => p.id), ['relative-brand', 'unknown-shade']);
});

test('non-shade numbers and brand shade numbers are never misread as explicit 21/23/25 shades', () => {
  for (const text of ['비레디 트루톤 커버로션 24H 40ml', '듀이셀 파운데이션 기획(+토너패드 20매)', '[누적판매 26만개] 스틱 파운데이션', '02호 뉴트럴베이지', '파운데이션 2호', '21ml', '221호']) {
    assert.equal(parseExplicitShadeSpec(text).hasExplicit, false, text);
  }
  assert.deepEqual([...parseExplicitShadeSpec('40ml 23 샌드 기획').shades], ['23']);
  assert.deepEqual([...parseExplicitShadeSpec('1호 밝은피부용(23-25호)').shades], ['23', '25']);
  assert.equal(parseExplicitShadeSpec('2호 보통피부용(27-29호)').hasExplicit, true);
  assert.deepEqual([...parseExplicitShadeSpec('2호 보통피부용(27-29호)').shades], []);
});

test('thinly analyzed profiles are excluded, not merely ranked lower', () => {
  const thin = { ...product, id: 'thin', profile_metadata: { version: 'rules-ko-v3', analyzed_count: MIN_ANALYZED_REVIEWS - 1 } };
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

const lined = options => ({ ...product, suitable_shades: [], profile_metadata: { version: 'rules-ko-v3', analyzed_count: 30, evidence_counts: { coverage: 30, longevity: 30, lightweight: 30 }, shade_lineup: { basis: 'number', options } } });
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
  assert.equal(classifyShadeMatch(two, '21'), 'relative');
});
test('a three shade line serves a standard tone better than a two shade line', () => {
  assert.ok(shadeScore(three, '23') > shadeScore(two, '23'));
  // At the extremes both lines have an exact option, so neither is favoured.
  assert.equal(shadeScore(three, '21'), shadeScore(two, '21'));
});
test('stated 21/23/25 shades still win over the relative fallback', () => {
  const stated = { ...product, suitable_shades: ['21'] };
  assert.ok(shadeScore(stated, '21') > shadeScore(two, '21'));
  // A product whose stated shades exclude the request is still penalised, including title-only 23호.
  assert.ok(shadeScore({ ...product, suitable_shades: ['25'] }, '21') < shadeScore(two, '21'));
  assert.ok(shadeScore({ ...product, suitable_shades: [], name: '커버 파운데이션 23호' }, '21') < shadeScore(two, '21'));
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

test('a buyable option is preferred over a nearer sold-out one for relative brand shades', () => {
  const line = lined([
    { name: '1호', label: '1호', position: 0, sold_out: true },
    { name: '2호', label: '2호', position: 1, sold_out: false },
  ]);
  assert.equal(bestShadeOption(line, '21').label, '2호');
});
test('all sold-out options still provide a labelled suggestion and shade bonus when compatible', () => {
  const line = lined([
    { name: '1호', label: '1호', position: 0, sold_out: true },
    { name: '2호', label: '2호', position: 1, sold_out: true },
  ]);
  assert.equal(bestShadeOption(line, '21').label, '1호');
  assert.equal(bestShadeOption(line, '21').sold_out, true);
  assert.equal(shadeLineup(line).options.length, 2);
  assert.equal(shadeScore(line, '21'), shadeScore(two, '21'));

  const soldOutExplicit = lined([
    { name: ' 21호 (라이트베이지)', label: '21호', position: 0, sold_out: true },
    { name: '23호 (샌드)', label: '23호', position: 1, sold_out: true },
  ]);
  assert.equal(bestShadeOption(soldOutExplicit, '21').label, '21호');
  assert.equal(bestShadeOption(soldOutExplicit, '21').sold_out, true);
  assert.equal(isShadeCompatible(soldOutExplicit, '25'), false);
  assert.equal(bestShadeOption(soldOutExplicit, '25'), null);
});

test('bestShadeOption never substitutes an in-stock conflicting explicit shade for a sold-out matching one', () => {
  const mixedStockExplicit = lined([
    { name: '21호 라이트', label: '21호 라이트', position: 0, sold_out: true },
    { name: '23호 샌드', label: '23호 샌드', position: 1, sold_out: false },
  ]);
  assert.equal(bestShadeOption(mixedStockExplicit, '21').label, '21호 라이트');
  assert.equal(bestShadeOption(mixedStockExplicit, '21').sold_out, true);
});

test('non-cover source categories cannot rank even with an old liquid type', () => {
  const categories = ['프라이머/베이스', '파우더/팩트', '쉐이딩', '컨실러'];
  const others = categories.map(category => withType(category, 'liquid', {
    profile_metadata: { ...product.profile_metadata, source_category: category },
  }));
  const foundation = withType('foundation', 'liquid', {
    profile_metadata: { ...product.profile_metadata, source_category: '파운데이션' },
  });
  for (const applicationMethod of ['any', 'tool']) {
    assert.deepEqual(selectRecommendations([...others, foundation], { ...quiz, applicationMethod }).map(p => p.id), ['foundation']);
  }
  assert.deepEqual(searchProducts(others, '').map(p => p.id), categories);
});

test('non-cover types stay excluded even without category metadata', () => {
  const others = ['primer', 'powder', 'shading'].map(type => withType(type, type));
  assert.deepEqual(selectRecommendations(others, quiz), []);
});

const allUnimportant = { coveragePref: 1, longevityPref: 1, lightweightPref: 1, naturalnessPref: 1, transferPref: 1, smoothnessPref: 1 };
const wearProduct = (id, value, count) => ({ ...product, id, profile_metadata: { ...product.profile_metadata,
  wear_attributes: { naturalness: { score: value, evidence_count: count } } } });

test('missing evidence stays null and receives a neutral ranking value, not a poor score', () => {
  const unknown = wearProduct('unknown', null, 0);
  const assessment = featureAssessment(unknown, { ...allUnimportant, naturalnessPref: 5 });
  assert.equal(assessment.points, 15);
  assert.equal(assessment.supportBonus, 0);
  assert.equal(assessment.known, 0);
  assert.equal(unknown.profile_metadata.wear_attributes.naturalness.score, null);
  assert.ok(featureAssessment(wearProduct('bad', 2, 100), { ...allUnimportant, naturalnessPref: 5 }).points < assessment.points);
});

test('confidence follows evidence for the requested attribute, not overall review volume', () => {
  const few = wearProduct('few', 4, 3), many = wearProduct('many', 4, 300);
  const prefs = { ...allUnimportant, naturalnessPref: 5 };
  assert.ok(featureAssessment(many, prefs).points > featureAssessment(few, prefs).points);
  assert.ok(featureAssessment(many, prefs).supportBonus > featureAssessment(few, prefs).supportBonus);
  assert.deepEqual(featureAssessment({ ...few, profile_metadata: { ...few.profile_metadata, analyzed_count: 90000 } }, prefs), featureAssessment(few, prefs));
  assert.equal(evidenceSupport(0), 0);
  assert.ok(evidenceSupport(300) < 1);
});

test('new user priorities affect the real ranking and 1 disables their effect', () => {
  const good = wearProduct('z-good', 4, 30), bad = wearProduct('a-bad', 2, 30);
  assert.deepEqual(selectRecommendations([bad, good], { ...quiz, ...allUnimportant, naturalnessPref: 5 }).map(p => p.id), ['z-good', 'a-bad']);
  assert.deepEqual(selectRecommendations([bad, good], { ...quiz, ...allUnimportant }).map(p => p.id), ['a-bad', 'z-good']);
});

test('fabricated non-null score with fewer than three references cannot influence ranking', () => {
  const prefs = { ...allUnimportant, naturalnessPref: 5 };
  assert.deepEqual(featureAssessment(wearProduct('thin', 5, 2), prefs), featureAssessment(wearProduct('unknown', null, 0), prefs));
});

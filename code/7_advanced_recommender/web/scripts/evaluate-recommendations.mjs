// Constraint-satisfaction evaluation for the recommendation ranking.
//
// This measures whether results respect the conditions the user set, and whether
// every claim shown is traceable to stored reviews. It is NOT a relevance metric:
// there are no human relevance labels or click logs yet, so NDCG/Recall would be
// unfounded here. Ranks the same list the site ranks, via selectRecommendations.
import { readFileSync, writeFileSync } from 'node:fs';
import { selectRecommendations, hasCurrentProfile, bestShadeOption, MIN_ANALYZED_REVIEWS } from '../src/lib/recommendation.ts';

const read = name => JSON.parse(readFileSync(new URL(`../tests/fixtures/${name}`, import.meta.url), 'utf-8'));
const snapshot = read('catalog-snapshot.json');
const { personas } = read('personas.json');
const share = (n, total) => (total ? n / total : null);
const pct = value => (value === null ? 'n/a' : `${(value * 100).toFixed(1)}%`);

const ATTRIBUTES = ['coverage', 'longevity', 'lightweight'];

function evaluate(persona) {
  const results = selectRecommendations(snapshot.products, persona);
  const meta = p => p.profile_metadata ?? {};
  const wantsShade = persona.shade && persona.shade !== 'any';

  // Hard invariants: the site must never show a stale or thinly-analyzed profile,
  // and the application-method filter is an exclusion, not a preference.
  const violations = [];
  for (const p of results) {
    if (!hasCurrentProfile(p)) violations.push(`${p.id}: 구버전 프로필`);
    if ((meta(p).analyzed_count ?? 0) < MIN_ANALYZED_REVIEWS) violations.push(`${p.id}: 분석 리뷰 ${MIN_ANALYZED_REVIEWS}개 미만`);
    if (persona.applicationMethod === 'hand' && p.product_type !== 'tone_lotion') violations.push(`${p.id}: 손 사용 조건 위반`);
    if (persona.applicationMethod === 'tool' && p.product_type === 'tone_lotion') violations.push(`${p.id}: 도구 사용 조건 위반`);
  }

  const shadeKnown = results.filter(p => p.suitable_shades?.length);
  // A product serves the tone if it states a matching shade or its own options
  // run light to dark, so the buyer can pick the right one.
  const viaLineup = wantsShade ? results.filter(p => !p.suitable_shades?.length && bestShadeOption(p, persona.shade)) : [];
  const adverse = results.filter(p => persona.concerns.some(c =>
    (meta(p).negative_concern_counts?.[c] ?? 0) >= 3 &&
    (meta(p).negative_concern_counts?.[c] ?? 0) > (meta(p).positive_concern_counts?.[c] ?? 0)));

  // Every claim the product card and modal display should name its source reviews.
  // Products showing no claim at all are excluded: counting them as "traceable"
  // would report a vacuous 100% that hides products with untraceable claims.
  const claiming = results.filter(p =>
    ATTRIBUTES.some(a => p[`${a}_score`] != null) || (p.suitable_concerns ?? []).length);
  const traceable = claiming.filter(p => {
    const shownAttributes = ATTRIBUTES.filter(a => p[`${a}_score`] != null);
    const attributesBacked = shownAttributes.every(a => (meta(p).evidence_review_ids?.[a] ?? []).length > 0);
    const concernsBacked = (p.suitable_concerns ?? []).every(c => (meta(p).concern_evidence_ids?.[c] ?? []).length > 0);
    return attributesBacked && concernsBacked;
  });

  return {
    id: persona.id,
    label: persona.label,
    returned: results.length,
    violations,
    // Requested shade is unavailable on some products; only a product that lists
    // shades and omits the requested one is a real conflict.
    shade_conflict_rate: wantsShade ? share(shadeKnown.filter(p => !p.suitable_shades.includes(persona.shade)).length, shadeKnown.length) : null,
    shade_lineup_rate: wantsShade ? share(viaLineup.length, results.length) : null,
    shade_unknown_rate: wantsShade ? share(results.length - shadeKnown.length - viaLineup.length, results.length) : null,
    concern_hit_rate: persona.concerns.length ? share(results.filter(p => persona.concerns.some(c => p.suitable_concerns?.includes(c))).length, results.length) : null,
    adverse_rate: persona.concerns.length ? share(adverse.length, results.length) : null,
    traceable_rate: share(traceable.length, claiming.length),
    no_claim_rate: share(results.length - claiming.length, results.length),
    top3: results.slice(0, 3).map(p => `${p.brand} ${p.name}`.slice(0, 44)),
  };
}

const rows = personas.map(evaluate);
const mean = key => {
  const values = rows.map(r => r[key]).filter(v => v !== null);
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
};
const report = {
  evaluated_at: new Date().toISOString(),
  catalog_captured_at: snapshot.captured_at,
  catalog_size: snapshot.count,
  personas: rows.length,
  summary: {
    total_violations: rows.reduce((n, r) => n + r.violations.length, 0),
    empty_results: rows.filter(r => !r.returned).length,
    mean_shade_conflict_rate: mean('shade_conflict_rate'),
    mean_concern_hit_rate: mean('concern_hit_rate'),
    mean_adverse_rate: mean('adverse_rate'),
    mean_traceable_rate: mean('traceable_rate'),
    mean_no_claim_rate: mean('no_claim_rate'),
    mean_shade_unknown_rate: mean('shade_unknown_rate'),
    mean_shade_lineup_rate: mean('shade_lineup_rate'),
  },
  rows,
};

console.log(`카탈로그 ${report.catalog_size}개 · 페르소나 ${report.personas}명 (스냅샷 ${snapshot.captured_at.slice(0, 10)})\n`);
console.log('페르소나                                   결과  호수충돌  자체호수  호수없음  고민적중  부작용  근거추적  주장없음');
for (const r of rows) {
  console.log(
    `${r.label.padEnd(42)} ${String(r.returned).padStart(2)}건  ${pct(r.shade_conflict_rate).padStart(7)}  ` +
    `${pct(r.shade_lineup_rate).padStart(7)}  ${pct(r.shade_unknown_rate).padStart(7)}  ${pct(r.concern_hit_rate).padStart(7)}  ${pct(r.adverse_rate).padStart(6)}  ` +
    `${pct(r.traceable_rate).padStart(7)}  ${pct(r.no_claim_rate).padStart(7)}`);
  for (const v of r.violations) console.log(`    위반: ${v}`);
}
const s = report.summary;
console.log(`
평균: 호수충돌 ${pct(s.mean_shade_conflict_rate)} · 자체호수 ${pct(s.mean_shade_lineup_rate)} · 호수없음 ${pct(s.mean_shade_unknown_rate)} · 고민적중 ${pct(s.mean_concern_hit_rate)}`);
console.log(`      부작용 ${pct(s.mean_adverse_rate)} · 근거추적 ${pct(s.mean_traceable_rate)} · 주장없음 ${pct(s.mean_no_claim_rate)}`);
console.log(`하드 조건 위반 ${s.total_violations}건 · 결과 0건인 페르소나 ${s.empty_results}명`);

writeFileSync(new URL('../tests/fixtures/evaluation-report.json', import.meta.url), JSON.stringify(report, null, 2));

// Only structural invariants fail the run. Rates are reported for comparison across
// changes; asserting a threshold on them would invent a quality bar we cannot justify.
if (s.total_violations || s.empty_results) {
  console.error('\n하드 조건 위반으로 실패했습니다.');
  process.exit(1);
}

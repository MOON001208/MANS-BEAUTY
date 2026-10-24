// Human responses are never manufactured. An empty report means awaiting review.
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { selectRecommendations, FEATURE_CONFIG, PROFILE_VERSION, attributeEvidence } from '../src/lib/recommendation.ts';

const digest = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');

export function createStudy(catalog, baseline, audit) {
  if (JSON.stringify(catalog.products.map(p => p.id).sort()) !== JSON.stringify([...baseline.catalog_ids].sort()) ||
      catalog.products.reduce((n, p) => n + (p.profile_metadata?.analyzed_count ?? 0), 0) !== baseline.analyzed_reviews) {
    throw new Error('비교 기준과 현재 카탈로그의 상품·리뷰 범위가 다릅니다. 같은 자료로 비교해야 합니다.');
  }
  if (audit.errors.length || audit.version !== PROFILE_VERSION) throw new Error('현재 규칙의 근거 감사를 먼저 통과해야 합니다.');
  const samples = audit.claim_samples;
  const card = id => {
    const product = catalog.products.find(p => p.id === id);
    if (!product) throw new Error('비교 상품이 카탈로그에 없습니다.');
    return { id, name: product.name, brand: product.brand, type: product.product_type,
      suitable_shades: product.suitable_shades ?? [], lineup: product.profile_metadata?.shade_lineup?.options ?? [],
      features: FEATURE_CONFIG.map(f => ({ label: f.label, ...attributeEvidence(product, f.key) })),
      evidence: samples.filter(s => s.product_id === id && s.polarity && s.polarity !== 'mixed').map(s => ({
        label: FEATURE_CONFIG.find(f => f.key === s.claim)?.label, polarity: s.polarity,
        review_id: s.review_id, text: s.extracted[s.polarity]?.[0] ?? '',
      })) };
  };
  const cases = baseline.cases.map(old => {
    const current = selectRecommendations(catalog.products, old.answers).slice(0, 3).map(p => p.id);
    const flip = parseInt(digest(old.id).slice(0, 2), 16) % 2 === 1;
    return { id: old.id, label: old.label, answers: old.answers,
      same_order: JSON.stringify(old.product_ids) === JSON.stringify(current),
      left: (flip ? current : old.product_ids).map(card), right: (flip ? old.product_ids : current).map(card),
      mapping: { left: flip ? 'current' : 'baseline', right: flip ? 'baseline' : 'current' } };
  });
  cases.sort((a, b) => Number(a.same_order) - Number(b.same_order));
  const body = { policy: PROFILE_VERSION, baseline_policy: baseline.policy, catalog_captured_at: catalog.captured_at,
    products: catalog.count, reviews: baseline.analyzed_reviews, cases };
  return { study_id: digest(body).slice(0, 20), ...body };
}

export function summarizeResponses(study, responses) {
  const choices = new Set(['left', 'right', 'tie', 'neither', 'unsure']);
  const validCases = new Map(study.cases.map(c => [c.id, c]));
  const unique = new Map();
  for (const response of [...responses].sort((a, b) => String(a.completed_at).localeCompare(String(b.completed_at)))) {
    if (response.study_id !== study.study_id || response.human_confirmed !== true || !response.response_id || !Array.isArray(response.answers)) {
      throw new Error('사람 평가 확인·평가 세트 ID·응답 형식을 확인하세요.');
    }
    const seen = new Set();
    for (const answer of response.answers) {
      if (!validCases.has(answer.case_id) || !choices.has(answer.choice) || seen.has(answer.case_id)) throw new Error('알 수 없거나 중복된 평가 사례·선택입니다.');
      seen.add(answer.case_id);
      unique.set(`${response.response_id}:${answer.case_id}`, { response_id: response.response_id, ...answer });
    }
  }
  const totals = { current: 0, baseline: 0, tie: 0, neither: 0, unsure: 0, identical_order: 0 };
  for (const answer of unique.values()) {
    const item = validCases.get(answer.case_id);
    // Identical lists cannot establish a preference between ranking policies.
    if (item.same_order) { totals.identical_order += 1; continue; }
    totals[item.mapping[answer.choice] ?? answer.choice] += 1;
  }
  return { study_id: study.study_id, status: unique.size ? 'human_responses_available' : 'awaiting_human_review',
    submitted_case_responses: unique.size, distinct_response_ids: new Set([...unique.values()].map(a => a.response_id)).size,
    totals, note: '조건과 리뷰 근거를 보고 사람이 고른 목록 선호 집계. 제품 실사용 효과·추천 정확도·학습된 최적 가중치를 뜻하지 않음.' };
}

if (process.argv[1]?.endsWith('human-review.mjs')) {
  const read = path => JSON.parse(readFileSync(path, 'utf8'));
  const [mode, ...files] = process.argv.slice(2);
  if (mode === 'prepare') {
    const auditPath = files[0] ?? '../.pipeline-cache/recommendation-audit.json';
    const study = createStudy(read('tests/fixtures/catalog-snapshot.json'), read('tests/fixtures/recommendation-v2-baseline.json'), read(auditPath));
    const encoded = JSON.stringify(study).replaceAll('<', '\\u003c');
    mkdirSync('public', { recursive: true });
    writeFileSync('public/recommendation-review.html', readFileSync('scripts/human-review-template.html', 'utf8').replace('__STUDY_JSON__', encoded));
    writeFileSync('tests/fixtures/human-review-study.json', JSON.stringify(study, null, 2) + '\n');
    console.log(`사람 평가 준비: ${study.cases.length}개 사례 · 순서 변경 ${study.cases.filter(c => !c.same_order).length}개 · 응답 0건`);
  } else if (mode === 'report') {
    const study = read('tests/fixtures/human-review-study.json');
    const report = summarizeResponses(study, files.map(read));
    writeFileSync('tests/fixtures/human-review-report.json', JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify(report, null, 2));
  } else throw new Error('사용법: node --experimental-strip-types scripts/human-review.mjs prepare [감사JSON] | report [사람이 저장한 응답JSON ...]');
}

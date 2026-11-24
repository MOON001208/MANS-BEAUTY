import test from 'node:test';
import assert from 'node:assert/strict';
import { summarizeResponses, createStudy, captureBaseline } from '../scripts/human-review.mjs';
import { PROFILE_VERSION } from '../src/lib/recommendation.ts';

// Synthetic unit fixtures only. Never exported as actual human labels.
const study = { study_id: 'unit-test-only', cases: [
  { id: 'a', same_order: false, mapping: { left: 'baseline', right: 'current' } },
  { id: 'b', same_order: true, mapping: { left: 'current', right: 'baseline' } },
] };
const response = answers => ({ study_id: study.study_id, response_id: 'test-only', human_confirmed: true, completed_at: '2026-10-24', answers });

test('no responses means awaiting real human review, not a successful quality score', () => {
  const result = summarizeResponses(study, []);
  assert.equal(result.status, 'awaiting_human_review');
  assert.equal(result.submitted_case_responses, 0);
  assert.equal(result.totals.current, 0);
});

test('blind left/right assignments are decoded and identical lists cannot establish a winner', () => {
  const result = summarizeResponses(study, [response([{ case_id: 'a', choice: 'right' }, { case_id: 'b', choice: 'left' }])]);
  assert.equal(result.totals.current, 1);
  assert.equal(result.totals.identical_order, 1);
});

test('re-exporting the same response cannot inflate human labels', () => {
  const r = response([{ case_id: 'a', choice: 'left' }]);
  const result = summarizeResponses(study, [r, { ...r, completed_at: '2026-10-25', answers: [{ case_id: 'a', choice: 'tie' }] }]);
  assert.equal(result.submitted_case_responses, 1);
  assert.equal(result.totals.tie, 1);
});

test('wrong study, non-human, unknown case and duplicate case are rejected', () => {
  for (const r of [ { ...response([]), study_id: 'other' }, { ...response([]), human_confirmed: false },
    response([{ case_id: 'x', choice: 'left' }]), response([{ case_id: 'a', choice: 'fake' }]),
    response([{ case_id: 'a', choice: 'left' }, { case_id: 'a', choice: 'right' }]) ]) {
    assert.throws(() => summarizeResponses(study, [r]));
  }
});

test('baseline and new data must describe the same catalog before a comparison is prepared', () => {
  assert.throws(() => createStudy({ products: [{ id: 'new' }] }, { catalog_ids: ['old'] }, { errors: [] }), /같은 자료/);
});

test('equal row counts do not permit different source products or review inputs', () => {
  const catalog = { count: 1, review_source_digest: 'original-reviews', products: [{
    id: 'p', name: '기존 상품', source_options: [{ name: '21호' }],
    profile_metadata: { version: PROFILE_VERSION, analyzed_count: 10 },
  }] };
  const baseline = captureBaseline(catalog, []);
  const audit = { errors: [], version: PROFILE_VERSION, claim_samples: [], products: 1, reviews: 10 };
  assert.doesNotThrow(() => createStudy(catalog, baseline, audit));
  assert.throws(() => createStudy({ ...catalog, review_source_digest: 'different-reviews' }, baseline, audit), /원본/);
  assert.throws(() => createStudy({ ...catalog, products: [{ ...catalog.products[0], name: '다른 상품' }] }, baseline, audit), /원본/);
  for (const field of ['catalog_source_digest', 'review_source_digest']) {
    const missing = { ...baseline };
    delete missing[field];
    assert.throws(() => createStudy(catalog, missing, audit), /원본/);
  }
  assert.throws(() => createStudy({ ...catalog, products: [{
    ...catalog.products[0], profile_metadata: { version: 'rules-ko-v3', analyzed_count: 10 },
  }] }, baseline, audit), /최신/);
  assert.throws(() => createStudy(catalog, baseline, { ...audit, reviews: 11 }), /최신/);
});

test('human response import rejects invalid dates and unexpected free-text payloads', () => {
  assert.throws(() => summarizeResponses(study, [{ ...response([]), completed_at: 'not-a-date' }]));
  assert.throws(() => summarizeResponses(study, [response([{ case_id: 'a', choice: 'left', reason: { text: 'bad type' } }])]));
  assert.throws(() => summarizeResponses(study, [response([null])]));
});

test('comparison cards retain full original reviews for both core and wear attributes', () => {
  const p = { id: 'p', name: '테스트 상품', product_type: 'liquid',
    profile_metadata: { version: PROFILE_VERSION, analyzed_count: 10 } };
  const answers = { id: 'one', skinType: 'dry', concerns: [], shade: 'any', applicationMethod: 'any',
    coveragePref: 1, longevityPref: 1, lightweightPref: 1 };
  const catalog = { count: 1, products: [p], review_source_digest: 'unit-test-reviews' };
  const baseline = captureBaseline(catalog, [answers]);
  const audit = { errors: [], version: PROFILE_VERSION, products: 1, reviews: 10, claim_samples: [
    { product_id: 'p', claim: 'coverage', review_id: 'r1', content: '처음 써봤고 커버력이 좋아요.',
      extracted: { positive: ['커버력이 좋아요'], negative: [] } },
    { product_id: 'p', claim: 'naturalness', polarity: 'positive', review_id: 'r2',
      content: '직접 써보니 자연스러워요.', extracted: { positive: ['자연스러워요'] } },
  ] };
  const result = createStudy(catalog, baseline, audit);
  assert.deepEqual(result.cases[0].left[0].evidence.map(e => e.text),
    ['처음 써봤고 커버력이 좋아요.', '직접 써보니 자연스러워요.']);
});

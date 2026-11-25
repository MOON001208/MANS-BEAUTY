import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { resolveReviewSummary } from '../src/lib/review-summary.ts';
import { PROFILE_VERSION } from '../src/lib/recommendation.ts';

function fixture({ key = 'coverage', count = 50, score = 4, scope = '' } = {}) {
  const rows = [
    { id: 'r1', product_id: 'p1', content: '커버력이 좋아요. 자연스러워요.', option_name: scope },
    { id: 'r2', product_id: 'p1', content: '커버력이 아쉬워요. 화장 티가 많이 나요.', option_name: scope },
    { id: 'r3', product_id: 'p1', content: '모공이 잘 가려져요. 자연스러워요. 그런데 화장 티가 많이 나요.', option_name: scope },
  ];
  const wear = key === 'naturalness';
  const sources = rows.map((row, i) => ({ id: row.id,
    sha256: createHash('sha256').update(row.content).digest('hex'),
    polarity: i === 1 ? 'negative' : wear && i === 2 ? 'mixed' : 'positive', semantic_verified: true,
    excerpts: wear ? i === 2 ? ['자연스러워요', '화장 티가 많이 나요']
      : [i === 0 ? '자연스러워요' : '화장 티가 많이 나요'] : [row.content.split('.')[0]],
  }));
  const entry = { totalEvidenceCount: count + (wear ? 1 : 0), sources };
  const wearEvidence = { evidence_count: count, mixed_count: 1, score,
    positive_review_ids: ['r1'], negative_review_ids: ['r2'], mixed_review_ids: ['r3'] };
  const product = { id: 'p1', name: '효능을 만들어내면 안 되는 상품명', coverage_score: score,
    profile_metadata: { version: PROFILE_VERSION, input_hash: 'input-hash',
      evidence_counts: { coverage: count }, evidence_review_ids: { coverage: rows.map(row => row.id) },
      wear_attributes: { naturalness: wearEvidence },
      option_wear: scope ? { [scope]: { attributes: { naturalness: wearEvidence } } } : {},
    } };
  const catalog = { schema_version: 1, method: 'rules-extractive-v1', profile_version: PROFILE_VERSION,
    generated_at: '2026-11-25T00:00:00Z', products: { p1: { input_hash: 'input-hash',
      attributes: { [key]: entry }, options: scope ? { [scope]: { [key]: entry } } : {},
    } } };
  return { product, key, scope, catalog, reviews: new Map(rows.map(row => [row.id, row])) };
}

test('sample summary retains negative and uses the same exact reviews as disclosure', async () => {
  const input = fixture();
  const result = await resolveReviewSummary(input);
  assert.equal(result.status, 'ready');
  assert.equal(result.totalEvidenceCount, 50);
  assert.equal(result.reviews.length, 3);
  assert.deepEqual(result.sampleReviewIds, result.reviews.map(review => review.id));
  assert.match(result.sentences[0], /표본 3건/);
  assert.match(result.sentences[0], /부정 표현 1건/);
  assert.match(result.sentences[1], /커버력이 아쉬워요/);
  assert.doesNotMatch(result.sentences.join(''), /AI|효능을 만들어내면/);
  assert.equal(result.sourceKind, 'rule_based');
});

test('mixed is distinct from positive and negative, including option scope', async () => {
  const result = await resolveReviewSummary(fixture({ key: 'naturalness', scope: '원문 옵션 A' }));
  assert.equal(result.status, 'ready');
  assert.deepEqual(result.polarityCounts, { positive: 1, negative: 1, mixed: 1 });
  assert.equal(result.totalEvidenceCount, 51);
  assert.match(result.sentences[0], /한 리뷰 안 평가 엇갈림 1건/);
  assert.match(result.sentences[1], /자연스러워요/);
  assert.match(result.sentences[1], /화장 티가 많이 나요/);
});

test('fewer than three clear reviews or a null score explicitly remains insufficient', async () => {
  for (const input of [fixture({ count: 2, score: null }), fixture({ count: 20, score: null })]) {
    const result = await resolveReviewSummary(input);
    assert.equal(result.status, 'insufficient');
    assert.deepEqual(result.sentences, []);
    assert.equal(result.insufficient, true);
    assert.match(result.message, /정보 부족/);
    assert.equal(result.reviews.length, 3);
  }
});

test('missing, foreign, empty or wrongly keyed original cannot support a summary', async () => {
  for (const mutate of [
    input => input.reviews.delete('r2'),
    input => input.reviews.set('r2', { ...input.reviews.get('r2'), product_id: 'p2' }),
    input => input.reviews.set('r2', { ...input.reviews.get('r2'), content: '' }),
    input => input.reviews.set('r2', { ...input.reviews.get('r2'), id: 'r1' }),
  ]) {
    const input = fixture(); mutate(input);
    const result = await resolveReviewSummary(input);
    assert.equal(result.status, 'unavailable');
    assert.deepEqual(result.sentences, []);
    assert.ok(result.reviews.every(row => row.product_id === 'p1'));
    assert.equal(result.reviews.length, 2);
  }
});

test('old profile, changed input hash, old IDs and edited raw text fail closed', async () => {
  for (const mutate of [
    input => { input.product.profile_metadata.version = 'rules-ko-v4'; },
    input => { input.product.profile_metadata.input_hash = 'new-input'; },
    input => { input.catalog.products.p1.attributes.coverage.sources[0].id = 'old-id'; },
    input => { input.reviews.get('r2').content += ' 원문 변경'; },
    input => { input.catalog.products.p1.attributes.coverage.sources[0].excerpts = ['만든 효능']; },
  ]) {
    const input = fixture(); mutate(input);
    const result = await resolveReviewSummary(input);
    assert.notEqual(result.status, 'ready');
    assert.deepEqual(result.sentences, []);
  }
});

test('missing catalog and wrong option keep safe original reviews with an explicit message', async () => {
  const input = fixture(); input.catalog = null;
  const result = await resolveReviewSummary(input);
  assert.equal(result.status, 'stale');
  assert.equal(result.reviews.length, 3);
  assert.ok(result.message);
  const scoped = fixture({ key: 'naturalness', scope: 'A' });
  scoped.reviews.get('r2').option_name = 'B';
  const wrongOption = await resolveReviewSummary(scoped);
  assert.deepEqual(wrongOption.sentences, []);
  assert.equal(wrongOption.reviews.length, 2);
});

test('uncertain hearsay in original evidence remains available only as raw text', async () => {
  const input = fixture();
  input.catalog.products.p1.attributes.coverage.sources[0].semantic_verified = false;
  const result = await resolveReviewSummary(input);
  assert.equal(result.status, 'unavailable');
  assert.deepEqual(result.sentences, []);
  assert.match(result.message, /전언/);
  assert.equal(result.reviews.length, 3);
});

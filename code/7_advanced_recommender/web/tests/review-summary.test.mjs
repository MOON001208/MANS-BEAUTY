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
  assert.match(result.message, /전체 근거 50건 중 펼침 표본 3건/);
  assert.deepEqual(result.polarityCounts, { positive: 2, negative: 1, mixed: 0 });
  assert.match(result.sentences[1], /커버력이 아쉬워요/);
  assert.doesNotMatch(result.sentences.join(''), /AI|효능을 만들어내면/);
  assert.equal(result.sourceKind, 'rule_based');
});

test('mixed is distinct from positive and negative, including option scope', async () => {
  const result = await resolveReviewSummary(fixture({ key: 'naturalness', scope: '원문 옵션 A' }));
  assert.equal(result.status, 'ready');
  assert.deepEqual(result.polarityCounts, { positive: 1, negative: 1, mixed: 1 });
  assert.equal(result.totalEvidenceCount, 51);
  assert.equal(result.clearEvidenceCount, 50);
  assert.equal(result.mixedEvidenceCount, 1);
  assert.match(result.sentences[0], /좋았다는 표현과 아쉬웠다는 표현/);
  assert.match(result.sentences[1], /자연스러워요/);
  assert.match(result.sentences[1], /화장 티가 많이 나요/);
});

test('raw CRLF is never normalized and edited line endings invalidate summary', async () => {
  const input = fixture();
  const row = input.reviews.get('r1');
  row.content += '\r\n원래 개행';
  input.catalog.products.p1.attributes.coverage.sources[0].sha256 = createHash('sha256').update(row.content).digest('hex');
  const result = await resolveReviewSummary(input);
  assert.equal(result.status, 'ready');
  assert.ok(result.reviews[0].content.includes('\r\n'));
  row.content = row.content.replace('\r\n', '\n');
  assert.equal((await resolveReviewSummary(input)).status, 'stale');
});

test('core attributes reject an option scope instead of using overall summary', async () => {
  const input = fixture(); input.scope = 'A';
  const result = await resolveReviewSummary(input);
  assert.equal(result.status, 'unavailable');
  assert.deepEqual(result.sentences, []);
  assert.match(result.message, /옵션별 요약/);
});

test('identical raw text contributes only once and does not inflate three-source threshold', async () => {
  const input = fixture();
  const row = input.reviews.get('r3'); row.content = input.reviews.get('r1').content;
  const source = input.catalog.products.p1.attributes.coverage.sources[2];
  source.sha256 = createHash('sha256').update(row.content).digest('hex'); source.excerpts = ['커버력이 좋아요'];
  const result = await resolveReviewSummary(input);
  assert.equal(result.status, 'insufficient');
  assert.equal(result.uniqueSampleCount, 2);
  assert.equal(result.reviews.length, 3);
  assert.deepEqual(result.polarityCounts, { positive: 1, negative: 1, mixed: 0 });
});

test('nonsecure context without Web Crypto gets an explicit unavailable state', async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: undefined });
  try {
    const result = await resolveReviewSummary(fixture());
    assert.equal(result.status, 'unavailable');
    assert.match(result.message, /접속 환경/);
    assert.deepEqual(result.sentences, []);
  } finally { Object.defineProperty(globalThis, 'crypto', descriptor); }
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
    assert.deepEqual(result.sampleReviewIds, ['r1', 'r2', 'r3']);
    assert.equal(result.insufficient, false);
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

test('mixed opinions cannot leave a ready summary when the safe opposite quotation is missing', async () => {
  const input = fixture();
  input.catalog.products.p1.attributes.coverage.sources[1].excerpts = [];
  const result = await resolveReviewSummary(input);
  assert.equal(result.status, 'unavailable');
  assert.deepEqual(result.sentences, []);
  assert.equal(result.reviews.length, 3);
  assert.match(result.message, /양쪽 맥락/);
});

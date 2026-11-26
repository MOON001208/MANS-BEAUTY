import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import { createHash } from 'node:crypto';
import { resolveReviewSummary } from '../src/lib/review-summary.ts';
import { PROFILE_VERSION } from '../src/lib/recommendation.ts';
import { resolveSampleReviews, buildPolarityMap } from '../src/components/reviewSummaryContract.ts';

const componentPath = fileURLToPath(new URL('../src/components/ReviewSummarySection.tsx', import.meta.url));
const source = ts.transpileModule(readFileSync(componentPath, 'utf8'), { compilerOptions: {
  module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
} }).outputText.replace(/from\s+['"]\.\/reviewSummaryContract['"]/g,
  `from ${JSON.stringify(pathToFileURL(path.resolve(path.dirname(componentPath), 'reviewSummaryContract.ts')).href)}`)
  .replace(/from\s+['"]react\/jsx-runtime['"]/g, `from ${JSON.stringify(import.meta.resolve('react/jsx-runtime'))}`);
const { ReviewSummarySection } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const rows = Array.from({ length: 13 }, (_, i) => ({ id: `r${i}`, product_id: 'p',
  content: `원문 ${i}\r\n원래 개행과   공백`, rating: 4, skin_type: '복합성', option_name: '옵션 A', author: 'PRIVATE_AUTHOR' }));
const byId = new Map(rows.map(row => [row.id, row]));
const summary = { sentences: ['확인한 표본에는 좋았다는 표현과 아쉬웠다는 표현이 함께 있습니다.'],
  totalEvidenceCount: 300, sampleReviewIds: rows.map(row => row.id), reviews: rows,
  clearEvidenceCount: 297, mixedEvidenceCount: 3,
  polarityCounts: { positive: 5, negative: 5, mixed: 3 }, sourceKind: 'rule_based',
  insufficient: false, status: 'ready', message: '표본의 의견 분포는 전체 리뷰와 다를 수 있습니다.' };
const render = (view = summary, open = false, reviews = byId) => renderToStaticMarkup(React.createElement(ReviewSummarySection,
  { toggleKey: 'wear:naturalness', productId: 'p', itemLabel: '화장 티', summary: view,
    evidenceById: reviews, open, onToggle() {},
    polarityByReviewId: buildPolarityMap({ positive_review_ids: rows.slice(0, 5).map(row => row.id),
      negative_review_ids: rows.slice(5, 10).map(row => row.id), mixed_review_ids: rows.slice(10).map(row => row.id) }) }));

test('closed then open disclosure preserves all thirteen reviews, mixed last IDs and raw whitespace', () => {
  const closed = render();
  assert.match(closed, /근거 리뷰 13건 보기/);
  assert.ok(closed.indexOf(summary.sentences[0]) < closed.indexOf('근거 리뷰 13건 보기'));
  assert.doesNotMatch(closed, /원문 12/);
  const opened = render(summary, true);
  assert.match(opened, /전체 근거 300건/);
  assert.match(opened, /점수 기준 297 · 엇갈림 3/);
  assert.match(opened, /표본 13건/);
  assert.match(opened, /확인 표본 · 긍정 5건/);
  assert.match(opened, /평가 엇갈림/);
  assert.ok(opened.includes(rows[12].content));
  assert.doesNotMatch(opened, /PRIVATE_AUTHOR/);
});

test('missing, foreign, incorrectly keyed and empty originals are filtered and cannot leave prose claims', () => {
  const map = new Map(byId);
  map.set('r0', { ...rows[0], product_id: 'other' });
  map.set('r1', { ...rows[1], id: 'r9' });
  map.set('r2', { ...rows[2], content: '' });
  map.delete('r3');
  const resolved = resolveSampleReviews('p', rows.map(row => row.id), map);
  assert.equal(resolved.missingCount, 4);
  assert.equal(resolved.matchedReviews.length, 9);
  const html = render({ ...summary, reviews: undefined }, true, map);
  assert.doesNotMatch(html, /확인한 표본에는 좋았다는/);
  assert.match(html, /13건 중 4건은/);
  assert.doesNotMatch(html, /원문 0\r/);
});

test('unavailable and insufficient show exact resolver reason, preserve raw access and hide zero counts', () => {
  for (const state of ['unavailable', 'insufficient']) {
    const html = render({ ...summary, sentences: [], status: state, insufficient: state === 'insufficient',
      message: '원문 해석이 불확실하여 요약을 보류했습니다.', polarityCounts: { positive: 0, negative: 0, mixed: 0 } });
    assert.match(html, /원문 해석이 불확실하여 요약을 보류했습니다/);
    assert.match(html, /근거 리뷰 13건 보기/);
    assert.doesNotMatch(html, /긍정 0건/);
  }
  assert.match(render({ ...summary, sentences: [], loading: true, reviews: undefined }, false, new Map()), /불러오는 중/);
  for (const status of ['unavailable', 'stale', 'insufficient']) {
    const html = render({ ...summary, status, insufficient: status === 'insufficient' }, true);
    assert.doesNotMatch(html, /확인 표본 ·|긍정 5건|부정 5건|리뷰 안 평가 엇갈림 3건|긍정 근거|부정 근거/);
  }
});

test('committed fallback catalog and summary artifact refer to the same profile inputs', () => {
  const fallback = JSON.parse(readFileSync(new URL('../public/catalog-fallback.json', import.meta.url), 'utf8'));
  const artifact = JSON.parse(readFileSync(new URL('../public/review-summaries.json', import.meta.url), 'utf8'));
  assert.equal(Object.keys(artifact.products).length, fallback.products.length);
  for (const product of fallback.products) assert.equal(artifact.products[product.id].input_hash,
    product.profile_metadata.input_hash, product.id);
  assert.deepEqual(artifact.snapshot, fallback.snapshot);
  assert.match(artifact.snapshot.id, /^[a-f0-9]{64}$/);
});

test('independently diagnosed semantic and quotation failures hold whole frozen entries and preserve every original', async () => {
  const cases = ['review_summary_held_samples.json', 'review_summary_context_samples.json', 'review_summary_control_samples.json'].flatMap(name =>
    JSON.parse(readFileSync(new URL(`../../tests/fixtures/${name}`, import.meta.url), 'utf8')).cases);
  for (const item of cases) {
    const product = item.product;
    const stored = { input_hash: product.profile_metadata.input_hash, attributes: {}, options: {} };
    if (item.scope) stored.options[item.scope] = { [item.key]: item.entry };
    else stored.attributes[item.key] = item.entry;
    const catalog = { schema_version: 1, method: 'rules-extractive-v1', profile_version: PROFILE_VERSION,
      generated_at: '2026-11-26T00:00:00Z', products: { [product.id]: stored } };
    const reviews = new Map(item.reviews.map(row => [row.id, row]));
    const view = await resolveReviewSummary({ product, key: item.key, scope: item.scope, catalog, reviews });
    assert.equal(view.status, item.expected_status ?? 'unavailable');
    assert.equal(view.reviews.length, item.expected_count);
    assert.equal(view.sampleReviewIds.length, item.expected_count);
    if (view.status === 'ready') assert.equal(view.sentences.length, 2);
    else assert.deepEqual(view.sentences, []);
    const html = renderToStaticMarkup(React.createElement(ReviewSummarySection, {
      toggleKey: item.key, productId: product.id, itemLabel: item.key, summary: view,
      evidenceById: reviews, open: true, onToggle() {},
      polarityByReviewId: new Map(item.entry.sources.map(source => [source.id, source.polarity])),
    }));
    if (view.status !== 'ready') assert.doesNotMatch(html, /정보 부족 ·|확인 표본 ·|긍정 근거|부정 근거/);
    for (const row of item.reviews) assert.ok(html.includes(row.content.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#x27;')));
  }
});

test('resolver to section preserves requested IDs and distinguishes retrieval failure from insufficient data', async () => {
  const originals = rows.slice(0, 5).map(row => ({ ...row, content: '커버력이 좋아요. ' + row.id }));
  const ids = originals.map(row => row.id);
  const product = { id: 'p', coverage_score: 4, profile_metadata: {
    version: PROFILE_VERSION, input_hash: 'input', evidence_counts: { coverage: 50 },
    evidence_review_ids: { coverage: ids },
  } };
  const entry = { totalEvidenceCount: 50, sources: originals.map(row => ({ id: row.id,
    sha256: createHash('sha256').update(row.content).digest('hex'), polarity: 'positive',
    excerpts: ['커버력이 좋아요'], semantic_verified: true })) };
  const catalog = { schema_version: 1, method: 'rules-extractive-v1', profile_version: PROFILE_VERSION,
    generated_at: '2026-11-26T00:00:00Z', products: { p: {
      input_hash: 'input', attributes: { coverage: entry }, options: {},
    } } };
  for (const count of [2, 0]) {
    const map = new Map(originals.slice(0, count).map(row => [row.id, row]));
    const view = await resolveReviewSummary({ product, key: 'coverage', catalog, reviews: map });
    assert.equal(view.status, 'unavailable');
    assert.equal(view.insufficient, false);
    assert.deepEqual(view.sampleReviewIds, ids);
    assert.equal(view.reviews.length, count);
    for (const error of [undefined, '근거 리뷰를 불러오지 못했습니다.']) {
      const html = render({ ...view, error }, true, map);
      assert.doesNotMatch(html, /정보 부족 ·|확인 표본 ·|긍정 근거|부정 근거/);
      assert.match(html, /전체 근거 50건/);
      if (error) assert.match(html, /role="alert"[^>]*>근거 리뷰를 불러오지 못했습니다/);
      else assert.match(html, /일부 근거 원문을 확인하지 못해/);
      if (count) {
        assert.match(html, /표본 2\/5건/);
        assert.match(html, /표본 5건 중 3건은/);
        assert.match(html, /근거 리뷰 닫기/);
        assert.ok(html.includes(originals[1].content));
      } else {
        assert.match(html, /표본 0\/5건/);
        assert.match(html, /연결된 표본 근거 5건을 현재 상품 원문에서 확인하지 못했습니다/);
        assert.doesNotMatch(html, /review-summary-evidence-item/);
      }
    }
  }
  const map = new Map(originals.map(row => [row.id, row]));
  const ready = await resolveReviewSummary({ product, key: 'coverage', catalog, reviews: map });
  assert.equal(ready.status, 'ready');
  const errorHtml = render({ ...ready, error: '원문 조회 오류' }, true, map);
  assert.match(errorHtml, /role="alert"[^>]*>원문 조회 오류/);
  assert.doesNotMatch(errorHtml, /확인한 커버력 표본|확인 표본 ·|긍정 근거/);
  for (const status of ['unavailable', 'stale']) {
    const html = render({ ...ready, status, insufficient: true, sentences: [], message: '원문 일치 확인 실패' }, true, map);
    assert.match(html, /원문 일치 확인 실패/);
    assert.doesNotMatch(html, /정보 부족 ·|긍정 근거/);
  }
});

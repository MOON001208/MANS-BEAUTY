import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
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
});

test('committed fallback catalog and summary artifact refer to the same profile inputs', () => {
  const fallback = JSON.parse(readFileSync(new URL('../public/catalog-fallback.json', import.meta.url), 'utf8'));
  const artifact = JSON.parse(readFileSync(new URL('../public/review-summaries.json', import.meta.url), 'utf8'));
  assert.equal(Object.keys(artifact.products).length, fallback.products.length);
  for (const product of fallback.products) assert.equal(artifact.products[product.id].input_hash,
    product.profile_metadata.input_hash, product.id);
});

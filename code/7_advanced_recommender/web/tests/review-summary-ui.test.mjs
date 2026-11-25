import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import {
  MAX_SAMPLE_REVIEW_IDS,
  MAX_SUMMARY_SENTENCES,
  buildPolarityMap,
  buildReviewSummaryView,
  collectMetadataSummaryReviewIds,
  extractMetadataSummary,
  resolveSampleReviews,
  resolveSourceLabel,
  selectBalancedSampleIds,
} from '../src/components/reviewSummaryContract.ts';

async function loadReviewSummarySection() {
  const componentPath = fileURLToPath(
    new URL('../src/components/ReviewSummarySection.tsx', import.meta.url),
  );
  const contractUrl = pathToFileURL(
    path.resolve(path.dirname(componentPath), 'reviewSummaryContract.ts'),
  ).href;
  const source = readFileSync(componentPath, 'utf8');
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  const jsxRuntimeUrl = import.meta.resolve('react/jsx-runtime');
  const rewritten = transpiled
    .replace(/from\s+['"]\.\/reviewSummaryContract['"]/g, `from ${JSON.stringify(contractUrl)}`)
    .replace(/from\s+['"]react\/jsx-runtime['"]/g, `from ${JSON.stringify(jsxRuntimeUrl)}`);
  const mod = await import(`data:text/javascript;base64,${Buffer.from(rewritten).toString('base64')}`);
  return mod.ReviewSummarySection;
}

const catalog = JSON.parse(
  readFileSync(new URL('../public/catalog-fallback.json', import.meta.url), 'utf8'),
);
const sampleProduct = catalog.products.find(p => p.id === 'A000000129149');

const makeReview = (id, product_id, content, extra = {}) => ({
  id,
  product_id,
  rating: 4,
  content,
  skin_type: '복합성',
  skin_tone: '23호',
  skin_trouble: '',
  option_name: '핸섬커버쿠션 1호',
  created_at: '2026-11-20T00:00:00Z',
  is_best: false,
  ...extra,
});

test('balanced sample selector caps at 5 and preserves minority polarity reviews', () => {
  const selected = selectBalancedSampleIds(
    {
      positive: ['p1', 'p2', 'p3', 'p4', 'p5'],
      negative: ['n1', 'n2', 'n3', 'n4'],
      mixed: ['m1'],
    },
    { positive: 9, negative: 4, mixed: 1 },
  );
  assert.equal(selected.length, MAX_SAMPLE_REVIEW_IDS);
  assert.ok(selected.includes('p1'));
  assert.ok(selected.includes('n1'));
  assert.ok(selected.includes('m1'));

  const negDominant = selectBalancedSampleIds(
    {
      positive: ['p1', 'p2', 'p3'],
      negative: ['n1', 'n2', 'n3', 'n4', 'n5'],
      mixed: [],
    },
    { positive: 3, negative: 11, mixed: 0 },
  );
  assert.deepEqual(negDominant, ['n1', 'p1', 'n2', 'p2', 'n3']);
});

test('resolveSampleReviews enforces strict product.id attribution and exposes missing counts', () => {
  const evidenceById = new Map([
    ['r1', makeReview('r1', 'P1', '커버력이 자연스럽습니다.')],
    ['r2', makeReview('r2', 'P2', '다른 상품 리뷰는 노출되면 안 됩니다.')],
    ['r3', makeReview('r3', 'P1', '지속력이 무난합니다.')],
  ]);
  const resolved = resolveSampleReviews('P1', ['r1', 'r2', 'r3', 'r4'], evidenceById);
  assert.deepEqual(resolved.matchedReviews.map(r => r.id), ['r1', 'r3']);
  assert.deepEqual(resolved.unattributedIds, ['r2']);
  assert.deepEqual(resolved.missingIds, ['r4']);
  assert.equal(resolved.missingCount, 2);
});

test('fallback builder never fabricates prose and preserves insufficient status for real catalog items', () => {
  assert.ok(sampleProduct, 'fixture product A000000129149 must exist in catalog fallback');

  const coverage = buildReviewSummaryView({
    product: sampleProduct,
    hasCurrentProfile: true,
    itemKey: 'coverage',
    score: sampleProduct.coverage_score,
    evidenceById: new Map(),
  });
  assert.equal(coverage.insufficient, false);
  assert.deepEqual(coverage.sentences, []);
  assert.equal(coverage.sourceLabel, '리뷰 요약');
  assert.equal(coverage.totalEvidenceCount, 56);
  assert.equal(coverage.sampleReviewIds.length, 5);

  const lightweight = buildReviewSummaryView({
    product: sampleProduct,
    hasCurrentProfile: true,
    itemKey: 'lightweight',
    score: sampleProduct.lightweight_score,
    evidenceById: new Map(),
    externalSummary: {
      sentences: ['이 문장은 정보 부족 상태에서 숨겨져야 합니다.'],
    },
  });
  assert.equal(lightweight.insufficient, true);
  assert.deepEqual(lightweight.sentences, []);
  assert.equal(lightweight.totalEvidenceCount, 2);
  assert.equal(lightweight.sampleReviewIds.length, 2);
});

test('option_wear scope isolates option evidence and never leaks overall product summary', () => {
  const productWithSummaries = {
    ...sampleProduct,
    profile_metadata: {
      ...sampleProduct.profile_metadata,
      review_summaries: {
        naturalness: {
          sentences: ['상품 전체 기준 자연스럽다는 사용 후 평가가 많습니다.'],
          source_kind: 'rule_based',
          source_label: 'AI 위장 금지',
        },
      },
    },
  };

  const overall = buildReviewSummaryView({
    product: productWithSummaries,
    hasCurrentProfile: true,
    itemKey: 'naturalness',
    wearScope: '',
    evidenceById: new Map(),
  });
  assert.deepEqual(overall.sentences, ['상품 전체 기준 자연스럽다는 사용 후 평가가 많습니다.']);
  assert.equal(overall.sourceLabel, '리뷰 요약');
  assert.equal(overall.totalEvidenceCount, 38);

  const optionScoped = buildReviewSummaryView({
    product: productWithSummaries,
    hasCurrentProfile: true,
    itemKey: 'naturalness',
    wearScope: '핸섬커버쿠션 1호',
    evidenceById: new Map(),
  });
  assert.deepEqual(optionScoped.sentences, []);
  assert.equal(optionScoped.totalEvidenceCount, 21);
  assert.deepEqual(optionScoped.polarityCounts, { positive: 20, negative: 1, mixed: 0 });
  assert.equal(optionScoped.sampleReviewIds.length, 5);
  assert.ok(optionScoped.sampleReviewIds.includes('13184706'), 'negative review sample is preserved');
});

test('source label allows AI badge only for genuinely ai_generated summaries and caps sentences to 2', () => {
  assert.equal(resolveSourceLabel({ sourceKind: 'rule_based', sourceLabel: 'AI 요약' }), '리뷰 요약');
  assert.equal(resolveSourceLabel({ sourceKind: 'ai_generated' }), 'AI 리뷰 요약');
  assert.equal(resolveSourceLabel({ sourceKind: 'ai_generated', sourceLabel: 'AI 사용 후 요약' }), 'AI 사용 후 요약');

  const view = buildReviewSummaryView({
    product: sampleProduct,
    hasCurrentProfile: true,
    itemKey: 'coverage',
    score: 3.89,
    evidenceById: new Map(),
    resolver: () => ({
      sentences: ['첫 번째 사용 후 평가입니다.', '두 번째 사용 후 평가입니다.', '세 번째 문장은 잘려야 합니다.'],
      sourceKind: 'rule_based',
      totalEvidenceCount: 56,
      sampleReviewIds: ['1', '2', '3', '4', '5', '6'],
    }),
  });
  assert.equal(view.sentences.length, MAX_SUMMARY_SENTENCES);
  assert.equal(view.sampleReviewIds.length, MAX_SAMPLE_REVIEW_IDS);
  assert.equal(view.sourceLabel, '리뷰 요약');
});

test('metadata extractor reads option-scoped summaries and collects sample IDs cleanly', () => {
  const enriched = {
    ...sampleProduct,
    profile_metadata: {
      ...sampleProduct.profile_metadata,
      review_summaries: {
        coverage: {
          sentences: ['잡티를 무난하게 가려준다는 사용 후기가 많습니다.'],
          sample_review_ids: ['10627059', '12486632'],
        },
        'concern:spots': {
          sentences: ['잡티 커버에 도움이 됐다는 사용 후 평가가 확인됩니다.'],
          sample_review_ids: ['11609593'],
        },
      },
      option_wear: {
        ...sampleProduct.profile_metadata.option_wear,
        '핸섬커버쿠션 1호': {
          ...sampleProduct.profile_metadata.option_wear['핸섬커버쿠션 1호'],
          review_summaries: {
            naturalness: {
              sentences: ['1호 옵션은 뜨지 않고 자연스럽게 표현된다는 후기가 많습니다.'],
              sample_review_ids: ['11158455'],
            },
          },
        },
      },
    },
  };
  assert.equal(
    extractMetadataSummary(enriched, 'naturalness', '핸섬커버쿠션 1호')?.sentences?.[0],
    '1호 옵션은 뜨지 않고 자연스럽게 표현된다는 후기가 많습니다.',
  );
  const collected = collectMetadataSummaryReviewIds(enriched, '핸섬커버쿠션 1호');
  assert.ok(collected.includes('10627059'));
  assert.ok(collected.includes('11609593'));
  assert.ok(collected.includes('11158455'));
});

test('ReviewSummarySection renders summary above toggle, distinguishes total vs sample counts, and blocks author/cross-product leaks', async () => {
  const ReviewSummarySection = await loadReviewSummarySection();
  const evidenceById = new Map([
    ['r1', makeReview('r1', 'P1', '바른 뒤 자연스럽게 밀착됩니다.', { author: 'SECRET_AUTHOR_NAME' })],
    ['r2', makeReview('r2', 'P1', '시간이 지나면 약간 묻어남이 있습니다.')],
    ['r_other', makeReview('r_other', 'P_OTHER', '타사 상품 원문 유출 금지')],
  ]);
  const polarityMap = buildPolarityMap({
    positive_review_ids: ['r1'],
    negative_review_ids: ['r2'],
    mixed_review_ids: [],
  });

  const html = renderToStaticMarkup(
    React.createElement(ReviewSummarySection, {
      toggleKey: 'wear:naturalness',
      productId: 'P1',
      itemLabel: '화장 티가 덜 나는 표현',
      summary: {
        sentences: [
          '자연스럽게 피부 톤을 정돈해 준다는 사용 후 평가가 다수입니다.',
          '다만 피부 상태에 따라 일부 묻어남을 언급한 후기도 함께 있습니다.',
        ],
        sourceKind: 'rule_based',
        sourceLabel: '리뷰 요약',
        totalEvidenceCount: 42,
        sampleReviewIds: ['r1', 'r2', 'r_other', 'r_missing'],
        polarityCounts: { positive: 35, negative: 5, mixed: 2 },
        insufficient: false,
      },
      evidenceById,
      open: true,
      onToggle: () => {},
      polarityByReviewId: polarityMap,
    }),
  );

  const summaryPos = html.indexOf('자연스럽게 피부 톤을 정돈해 준다는 사용 후 평가가 다수입니다.');
  const togglePos = html.indexOf('근거 리뷰 닫기 ▲');
  assert.ok(summaryPos > -1, 'summary text must render');
  assert.ok(togglePos > -1, 'evidence toggle must render');
  assert.ok(summaryPos < togglePos, 'summary must be placed directly above the evidence toggle');

  assert.match(html, /전체 근거 42건/);
  assert.match(html, /표본 2\/4건/);
  assert.match(html, /표본 4건 중 2건은 현재 상품 원문에서 확인되지 않아 2건만 표시합니다/);
  assert.match(html, /긍정 35건 · 부정 5건 · 리뷰 안 평가 엇갈림 2건/);
  assert.match(html, /긍정 근거/);
  assert.match(html, /부정 근거/);
  assert.match(html, /바른 뒤 자연스럽게 밀착됩니다/);
  assert.doesNotMatch(html, /타사 상품 원문 유출 금지/, 'cross-product review must never render');
  assert.doesNotMatch(html, /SECRET_AUTHOR_NAME/, 'author must never be rendered');
});

test('ReviewSummarySection explicitly renders loading, error, missing, and insufficient states without hiding failures', async () => {
  const ReviewSummarySection = await loadReviewSummarySection();

  const loadingHtml = renderToStaticMarkup(
    React.createElement(ReviewSummarySection, {
      toggleKey: 'coverage',
      productId: 'P1',
      itemLabel: '커버력',
      summary: {
        sentences: [],
        totalEvidenceCount: 15,
        sampleReviewIds: ['r1', 'r2'],
        loading: true,
      },
      evidenceById: new Map(),
      open: false,
      onToggle: () => {},
    }),
  );
  assert.match(loadingHtml, /근거 리뷰 2건을 불러오는 중입니다/);
  assert.match(loadingHtml, /전체 근거 15건 · 표본 2건 확인 중/);

  const errorHtml = renderToStaticMarkup(
    React.createElement(ReviewSummarySection, {
      toggleKey: 'coverage',
      productId: 'P1',
      itemLabel: '커버력',
      summary: {
        sentences: [],
        totalEvidenceCount: 15,
        sampleReviewIds: ['r1'],
        error: '근거 리뷰를 불러오지 못했습니다.',
      },
      evidenceById: new Map(),
      open: false,
      onToggle: () => {},
    }),
  );
  assert.match(errorHtml, /role="alert"/);
  assert.match(errorHtml, /근거 리뷰를 불러오지 못했습니다/);

  const missingHtml = renderToStaticMarkup(
    React.createElement(ReviewSummarySection, {
      toggleKey: 'longevity',
      productId: 'P1',
      itemLabel: '지속력',
      summary: {
        sentences: [],
        totalEvidenceCount: 9,
        sampleReviewIds: ['r1', 'r2', 'r3'],
      },
      evidenceById: new Map(),
      open: false,
      onToggle: () => {},
    }),
  );
  assert.match(missingHtml, /연결된 표본 근거 3건을 현재 상품 원문에서 확인하지 못했습니다/);

  const insufficientHtml = renderToStaticMarkup(
    React.createElement(ReviewSummarySection, {
      toggleKey: 'lightweight',
      productId: 'P1',
      itemLabel: '착용감',
      summary: {
        sentences: ['절대 표시되면 안 되는 문장'],
        totalEvidenceCount: 2,
        sampleReviewIds: ['r1'],
        insufficient: true,
      },
      evidenceById: new Map([['r1', makeReview('r1', 'P1', '가볍게 발립니다.')]]),
      open: false,
      onToggle: () => {},
    }),
  );
  assert.match(insufficientHtml, /정보 부족/);
  assert.doesNotMatch(insufficientHtml, /절대 표시되면 안 되는 문장/);
  assert.match(insufficientHtml, /근거 리뷰 1건 보기 ▼/);
});

test('page.tsx preserves formulation toggle, option_wear dropdown, original review list, and never queries author', () => {
  const pageSource = readFileSync(new URL('../src/app/page.tsx', import.meta.url), 'utf8');
  assert.match(pageSource, /renderEvidence\('formulation', meta\?\.formulation\?\.evidence_review_ids\)/);
  assert.match(pageSource, /setWearScope\(event\.target\.value\)/);
  assert.match(pageSource, /💬 실제 구매 리뷰/);
  assert.match(pageSource, /<ReviewSummarySection/);
  assert.doesNotMatch(pageSource, /\bauthor\b/, 'page.tsx must never query or render review author');
});

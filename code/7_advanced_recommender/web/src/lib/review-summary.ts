import type { Product, Review, WearAttributeKey } from './supabase';
import { hasCurrentProfile, PROFILE_VERSION } from './recommendation.ts';

export type ReviewSummaryItemKey = 'coverage' | 'longevity' | 'lightweight' | WearAttributeKey;
type Polarity = 'positive' | 'negative' | 'mixed';
interface SummarySource { id: string; sha256: string; polarity: Polarity; excerpts: string[]; semantic_verified: boolean }
interface SummaryEntry { totalEvidenceCount: number; sources: SummarySource[] }
export interface ReviewSummaryCatalog {
  schema_version: 1;
  method: 'rules-extractive-v1';
  profile_version: string;
  generated_at: string;
  products: Record<string, {
    input_hash: string;
    attributes: Partial<Record<ReviewSummaryItemKey, SummaryEntry>>;
    options: Record<string, Partial<Record<WearAttributeKey, SummaryEntry>>>;
  }>;
}
export interface ReviewSummaryView {
  sentences: string[];
  sourceLabel: string;
  sourceKind: 'rule_based';
  totalEvidenceCount: number;
  sampleReviewIds: string[];
  reviews: Review[];
  polarityCounts: Record<Polarity, number>;
  insufficient: boolean;
  status: 'ready' | 'insufficient' | 'unavailable' | 'stale';
  message: string;
}

const LABELS: Record<ReviewSummaryItemKey, string> = {
  coverage: '커버력', longevity: '지속력', lightweight: '착용감·가벼움',
  naturalness: '화장 티', transfer_resistance: '묻어남', smoothness: '들뜸·뭉침·끼임',
};
const isWear = (key: ReviewSummaryItemKey): key is WearAttributeKey =>
  key === 'naturalness' || key === 'transfer_resistance' || key === 'smoothness';

export function reviewSummaryEvidence(product: Product, key: ReviewSummaryItemKey, scope = '') {
  const meta = hasCurrentProfile(product) ? product.profile_metadata : null;
  const wear = isWear(key) ? (scope ? meta?.option_wear?.[scope]?.attributes : meta?.wear_attributes)?.[key] : undefined;
  const ids = isWear(key) ? [...(wear?.positive_review_ids ?? []), ...(wear?.negative_review_ids ?? []), ...(wear?.mixed_review_ids ?? [])]
    : meta?.evidence_review_ids?.[key] ?? [];
  const clearCount = isWear(key) ? wear?.evidence_count ?? 0 : meta?.evidence_counts?.[key] ?? 0;
  // Mixed reviews belong to the evidence total but not to the score denominator.
  const total = clearCount + (isWear(key) ? wear?.mixed_count ?? 0 : 0);
  const score = isWear(key) ? wear?.score : key === 'coverage' ? product.coverage_score
    : key === 'longevity' ? product.longevity_score : product.lightweight_score;
  return { ids: [...new Set(ids)], total, clearCount, score: meta ? score : null };
}

let catalogPromise: Promise<ReviewSummaryCatalog> | undefined;
export function loadReviewSummaryCatalog(): Promise<ReviewSummaryCatalog> {
  if (!catalogPromise) {
    const url = new URL('./review-summaries.json', globalThis.location?.href ?? 'http://localhost/').href;
    catalogPromise = fetch(url, { signal: AbortSignal.timeout(10_000) }).then(async response => {
      if (!response.ok) throw new Error('리뷰 요약 자료를 불러오지 못했습니다.');
      const catalog: ReviewSummaryCatalog = await response.json();
      if (!validCatalog(catalog)) throw new Error('리뷰 요약 자료의 형식을 확인하지 못했습니다.');
      return catalog;
    }).catch(error => { catalogPromise = undefined; throw error; });
  }
  return catalogPromise;
}

function validCatalog(catalog: ReviewSummaryCatalog | null | undefined): catalog is ReviewSummaryCatalog {
  return !!catalog && catalog.schema_version === 1 && catalog.method === 'rules-extractive-v1'
    && catalog.profile_version === PROFILE_VERSION && !!catalog.products
    && Number.isFinite(Date.parse(catalog.generated_at));
}

async function rawHash(content: string) {
  const bytes = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(content));
  return [...new Uint8Array(bytes)].map(value => value.toString(16).padStart(2, '0')).join('');
}

/** A summary and its disclosure share this exact review array. No score or
 * product-name based benefit generation; only preclassified, verified raw text.
 * Any changed, missing or foreign source invalidates the whole summary. */
export async function resolveReviewSummary({ product, key, scope = '', catalog, reviews }: {
  product: Product;
  key: ReviewSummaryItemKey;
  scope?: string;
  catalog: ReviewSummaryCatalog | null;
  reviews: ReadonlyMap<string, Review>;
}): Promise<ReviewSummaryView> {
  const { ids, total, clearCount, score } = reviewSummaryEvidence(product, key, scope);
  const found = ids.map(id => reviews.get(id)).filter((review, index): review is Review =>
    !!review && review.id === ids[index] && review.product_id === product.id && typeof review.content === 'string'
    && !!review.content.trim() && (!scope || !isWear(key) || review.option_name === scope));
  const result: ReviewSummaryView = {
    sentences: [], sourceLabel: '규칙 기반 리뷰 요약', sourceKind: 'rule_based',
    totalEvidenceCount: total, sampleReviewIds: found.map(review => review.id), reviews: found,
    polarityCounts: { positive: 0, negative: 0, mixed: 0 },
    insufficient: clearCount < 3 || score == null || found.length < 3,
    status: 'unavailable', message: '요약을 확인할 원문 근거가 없습니다.',
  };
  if (!ids.length) return { ...result, status: 'insufficient', insufficient: true,
    message: '이 항목을 요약할 원문 근거가 부족합니다.' };
  if (found.length !== ids.length) return { ...result, message: '일부 근거 원문을 확인하지 못해 요약을 표시하지 않습니다.' };
  const stored = validCatalog(catalog) ? catalog.products[product.id] : undefined;
  if (!stored || product.profile_metadata?.version !== catalog?.profile_version
      || !product.profile_metadata?.input_hash || stored.input_hash !== product.profile_metadata.input_hash) {
    return { ...result, status: 'stale', message: '현재 상품 분석과 일치하는 요약 자료가 없습니다. 아래 원문을 확인해 주세요.' };
  }
  const entry = isWear(key) && scope ? stored.options?.[scope]?.[key] : stored.attributes?.[key];
  if (!entry || !Array.isArray(entry.sources) || entry.totalEvidenceCount !== total
      || entry.sources.length !== ids.length || new Set(entry.sources.map(source => source.id)).size !== ids.length
      || entry.sources.some(source => !ids.includes(source.id))) {
    return { ...result, status: 'stale', message: '현재 근거 목록과 요약 자료가 달라 요약을 표시하지 않습니다.' };
  }
  try {
    const verified = await Promise.all(entry.sources.map(async source => {
      const review = reviews.get(source.id)!;
      return ['positive', 'negative', 'mixed'].includes(source.polarity)
        && typeof source.sha256 === 'string' && /^[a-f0-9]{64}$/.test(source.sha256)
        && Array.isArray(source.excerpts) && source.excerpts.every(text => typeof text === 'string'
          && !!text.trim() && text.length <= 200 && review.content.includes(text))
        && await rawHash(review.content) === source.sha256;
    }));
    if (verified.some(ok => !ok)) throw new Error('Changed source');
  } catch {
    return { ...result, status: 'stale', message: '근거 원문이 요약 자료와 일치하는지 확인하지 못해 요약을 표시하지 않습니다.' };
  }
  if (entry.sources.some(source => source.semantic_verified !== true)) {
    return { ...result, status: 'unavailable', message: '일부 원문에 전언 등 해석이 불확실한 표현이 있어 요약을 표시하지 않습니다. 아래 원문을 확인해 주세요.' };
  }
  const counts = { positive: 0, negative: 0, mixed: 0 };
  entry.sources.forEach(source => { counts[source.polarity]++; });
  result.polarityCounts = counts;
  if (result.insufficient) return { ...result, status: 'insufficient',
    message: '명확한 근거가 3건 미만이거나 점수가 정보 부족이어서 요약하지 않았습니다. 확인 가능한 원문은 아래에서 볼 수 있습니다.' };
  const parts = [counts.positive ? `긍정 표현 ${counts.positive}건` : '',
    counts.negative ? `부정 표현 ${counts.negative}건` : '',
    counts.mixed ? `한 리뷰 안 평가 엇갈림 ${counts.mixed}건` : ''].filter(Boolean);
  result.sentences = [`확인한 ${LABELS[key]} 근거 표본 ${found.length}건에는 ${parts.join(' · ')}이 있습니다.`];
  // Prefer a negative or mixed example whenever one exists. An excerpt is
  // quoted verbatim and always belongs to a review in the disclosure below.
  const examples: string[] = [];
  for (const polarity of ['mixed', 'negative', 'positive'] as const) {
    const source = entry.sources.find(item => item.polarity === polarity && item.excerpts.length);
    if (source) examples.push(...source.excerpts.slice(0, polarity === 'mixed' ? 2 : 1));
    if (examples.length >= 2) break;
  }
  if (examples.length) result.sentences.push(`원문 표현 예: ${examples.slice(0, 2).map(text => `“${text}”`).join(' / ')}.`);
  return { ...result, status: 'ready', message: '전체 리뷰의 의견 분포가 아니라 아래에서 확인할 수 있는 근거 표본의 요약입니다.' };
}

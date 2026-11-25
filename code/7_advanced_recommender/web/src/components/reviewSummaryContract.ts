import type { Review, WearEvidence } from '../lib/supabase';
import type { ReviewSummaryView as VerifiedSummaryView } from '../lib/review-summary';

export const MIN_SUMMARY_EVIDENCE_COUNT = 3;
export type CoreSummaryKey = 'coverage' | 'longevity' | 'lightweight';
export type WearSummaryKey = 'naturalness' | 'transfer_resistance' | 'smoothness';
export type ReviewSummaryPolarity = 'positive' | 'negative' | 'mixed';
export type ReviewSummaryView = Pick<VerifiedSummaryView, 'sentences' | 'totalEvidenceCount' | 'sampleReviewIds'>
  & Partial<Omit<VerifiedSummaryView, 'sentences' | 'totalEvidenceCount' | 'sampleReviewIds'>>
  & { loading?: boolean; error?: string };

/** Presentation helpers only. Claims come from the verified shared resolver. */
export function resolveSourceLabel(view: Pick<ReviewSummaryView, 'sourceLabel' | 'sourceKind'>) {
  return view.sourceLabel && !/AI/i.test(view.sourceLabel) ? view.sourceLabel : '규칙 기반 리뷰 요약';
}

export function resolveSampleReviews(productId: string, ids: readonly string[], byId: ReadonlyMap<string, Review>, limit = ids.length) {
  const requestedIds = [...new Set(ids)].slice(0, limit);
  const matchedReviews: Review[] = [], missingIds: string[] = [], unattributedIds: string[] = [];
  for (const id of requestedIds) {
    const review = byId.get(id);
    if (!review || review.id !== id || typeof review.content !== 'string' || !review.content.trim()) missingIds.push(id);
    else if (review.product_id !== productId) unattributedIds.push(id);
    else matchedReviews.push(review);
  }
  return { requestedIds, matchedReviews, missingIds, unattributedIds, missingCount: missingIds.length + unattributedIds.length };
}

export function buildPolarityMap(entry?: Pick<WearEvidence, 'positive_review_ids' | 'negative_review_ids' | 'mixed_review_ids'> | null) {
  const map = new Map<string, ReviewSummaryPolarity>();
  if (!entry) return map;
  for (const id of entry.positive_review_ids ?? []) map.set(id, 'positive');
  for (const id of entry.negative_review_ids ?? []) map.set(id, map.has(id) ? 'mixed' : 'negative');
  for (const id of entry.mixed_review_ids ?? []) map.set(id, 'mixed');
  return map;
}

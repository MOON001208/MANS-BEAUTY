'use client';

import type { Review } from '../lib/supabase';
import {
  MIN_SUMMARY_EVIDENCE_COUNT,
  resolveSampleReviews,
  resolveSourceLabel,
  type ReviewSummaryPolarity,
  type ReviewSummaryView,
} from './reviewSummaryContract';

export interface ReviewSummarySectionProps {
  /** Unique toggle key inside ProductModal (e.g. 'coverage', 'wear:naturalness', 'concern:pore'). */
  toggleKey: string;
  /** Current product ID used to enforce strict review attribution. */
  productId: string;
  /** Human-readable attribute or concern label for accessible announcements. */
  itemLabel: string;
  /** Structured summary view matching the UI-integration contract. */
  summary: ReviewSummaryView;
  /** Fetched original reviews keyed by review ID. */
  evidenceById: ReadonlyMap<string, Review>;
  /** Whether the sample original review drawer is expanded. */
  open: boolean;
  /** Toggle handler owned by ProductModal. */
  onToggle: (key: string) => void;
  /** Optional polarity label map for individual sample reviews (positive / negative / mixed). */
  polarityByReviewId?: ReadonlyMap<string, ReviewSummaryPolarity>;
  /** Optional scope pill (e.g., selected option name in wearScope). */
  scopeLabel?: string;
  /** Slightly tighter spacing for concern list rows. */
  compact?: boolean;
}

const POLARITY_LABEL: Record<ReviewSummaryPolarity, string> = {
  positive: '긍정 근거',
  negative: '부정 근거',
  mixed: '평가 엇갈림',
};

function InlineStars({ rating }: { rating: number }) {
  return (
    <div className="star-rating" aria-label={`별점 ${rating}점`}>
      {[1, 2, 3, 4, 5].map(step => (
        <svg
          key={step}
          width="13"
          height="13"
          viewBox="0 0 20 20"
          fill={step <= Math.round(rating) ? 'currentColor' : 'none'}
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path d="M10 1l2.39 4.84 5.34.78-3.87 3.77.91 5.33L10 13.28l-4.77 2.51.91-5.33-3.87-3.77 5.34-.78L10 1z" />
        </svg>
      ))}
    </div>
  );
}

export function ReviewSummarySection({
  toggleKey,
  productId,
  itemLabel,
  summary,
  evidenceById,
  open,
  onToggle,
  polarityByReviewId,
  scopeLabel,
  compact = false,
}: ReviewSummarySectionProps) {
  const sourceLabel = resolveSourceLabel(summary);
  const { requestedIds, matchedReviews: fetchedReviews, missingCount } = resolveSampleReviews(
    productId,
    summary.sampleReviewIds,
    evidenceById,
  );
  const matchedReviews = summary.reviews ?? fetchedReviews;
  const panelId = `evidence-panel-${toggleKey.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
  const isInsufficient = Boolean(summary.insufficient);
  const hasSentences = !isInsufficient && !summary.loading && !summary.error && missingCount === 0 && summary.sentences.length > 0;
  const sampleCountLabel = summary.loading && requestedIds.length > 0
    ? `표본 ${requestedIds.length}건 확인 중`
    : requestedIds.length > 0
      ? missingCount > 0
        ? `표본 ${matchedReviews.length}/${requestedIds.length}건`
        : `표본 ${matchedReviews.length}건`
      : null;

  return (
    <div
      className={`review-summary-block${compact ? ' review-summary-block-compact' : ''}`}
      data-summary-key={toggleKey}
      aria-label={`${itemLabel} 리뷰 요약 및 근거`}
    >
      {/* 1. 바로 위: 1~2문장 사용 후 평가 리뷰 요약 영역 */}
      <div className="review-summary-card">
        <div className="review-summary-header">
          <div className="review-summary-tags">
            <span
              className="review-summary-source"
            >
              {sourceLabel}
            </span>
            {scopeLabel && <span className="review-summary-scope">{scopeLabel}</span>}
          </div>
          <span className="review-summary-counts">
            전체 근거 {summary.totalEvidenceCount.toLocaleString()}건
            {sampleCountLabel ? ` · ${sampleCountLabel}` : ''}
            {summary.uniqueSampleCount != null && summary.uniqueSampleCount < matchedReviews.length
              ? ` · 서로 다른 내용 ${summary.uniqueSampleCount}건` : ''}
          </span>
        </div>

        {summary.loading ? (
          <p role="status" className="review-summary-empty">요약과 근거 원문의 일치 여부를 확인하고 있습니다.</p>
        ) : isInsufficient ? (
          <p className="review-summary-empty">
            정보 부족 · {summary.message || `사용 후 근거가 ${MIN_SUMMARY_EVIDENCE_COUNT}건 미만이라 요약하지 않습니다.`}
          </p>
        ) : hasSentences ? (
          <div className="review-summary-sentences">
            {summary.sentences.map((sentence, index) => (
              <p key={index} className="review-summary-sentence">
                {sentence}
              </p>
            ))}
          </div>
        ) : (
          <p className="review-summary-empty">
            {summary.message || '요약을 확인할 수 없습니다. 아래 근거 리뷰 원문을 직접 확인해 주세요.'}
          </p>
        )}

        {hasSentences && summary.message && <p className="review-summary-status">{summary.message}</p>}
        {summary.polarityCounts && !summary.loading && Object.values(summary.polarityCounts).some(count => count > 0) && (
          <p className="review-summary-polarity">
            확인 표본 · 긍정 {summary.polarityCounts.positive.toLocaleString()}건 · 부정{' '}
            {summary.polarityCounts.negative.toLocaleString()}건 · 리뷰 안 평가 엇갈림{' '}
            {summary.polarityCounts.mixed.toLocaleString()}건
          </p>
        )}
      </div>

      {/* 2. 바로 아래: 기존 근거 리뷰 N건 보기 토글 및 원문 확인 영역 */}
      <div className="review-summary-evidence">
        {summary.loading && requestedIds.length > 0 ? (
          <p role="status" className="review-summary-status">
            근거 리뷰 {requestedIds.length}건을 불러오는 중입니다...
          </p>
        ) : matchedReviews.length > 0 ? (
          <>
            <button
              type="button"
              className="review-summary-toggle"
              onClick={() => onToggle(toggleKey)}
              aria-expanded={open}
              aria-controls={panelId}
            >
              {open ? '근거 리뷰 닫기 ▲' : `근거 리뷰 ${matchedReviews.length}건 보기 ▼`}
            </button>

            {missingCount > 0 && (
              <p role="status" className="review-summary-status review-summary-status-warn">
                표본 {requestedIds.length}건 중 {missingCount}건은 현재 상품 원문에서 확인되지 않아{' '}
                {matchedReviews.length}건만 표시합니다.
              </p>
            )}

            {summary.error && (
              <p role="alert" className="review-summary-status review-summary-status-error">
                {summary.error}
              </p>
            )}

            {open && (
              <div id={panelId} className="review-summary-list">
                {summary.totalEvidenceCount > matchedReviews.length && (
                  <p className="review-summary-sample-note">
                    전체 근거 {summary.totalEvidenceCount.toLocaleString()}건 중 현재 상품에 귀속된 표본{' '}
                    {matchedReviews.length}건입니다.
                  </p>
                )}
                {matchedReviews.map(review => {
                  const polarity = polarityByReviewId?.get(review.id);
                  return (
                    <div key={review.id} className="review-summary-evidence-item">
                      <div className="review-summary-evidence-meta">
                        <InlineStars rating={review.rating} />
                        {review.skin_type && <span className="skin-tag">{review.skin_type}</span>}
                        {polarity && (
                          <span className={`review-polarity-tag review-polarity-${polarity}`}>
                            {POLARITY_LABEL[polarity]}
                          </span>
                        )}
                      </div>
                      <p className="review-summary-evidence-text">{review.content}</p>
                      {review.option_name && (
                        <p className="review-summary-evidence-option">옵션: {review.option_name}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : summary.error ? (
          <p role="alert" className="review-summary-status review-summary-status-error">
            {summary.error}
          </p>
        ) : requestedIds.length > 0 ? (
          <p role="status" className="review-summary-status review-summary-status-warn">
            연결된 표본 근거 {requestedIds.length}건을 현재 상품 원문에서 확인하지 못했습니다.
          </p>
        ) : summary.totalEvidenceCount > 0 ? (
          <p role="status" className="review-summary-status">
            전체 근거 {summary.totalEvidenceCount.toLocaleString()}건 중 연결된 표본 원문이 없습니다.
          </p>
        ) : null}
      </div>
    </div>
  );
}

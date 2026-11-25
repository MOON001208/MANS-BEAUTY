import type { Product, Review, SkinConcern, WearAttributeKey, WearEvidence } from '../lib/supabase';

export const MIN_SUMMARY_EVIDENCE_COUNT = 3;
export const MAX_SUMMARY_SENTENCES = 2;
export const MAX_SAMPLE_REVIEW_IDS = 5;

export type ReviewSummaryBasis = 'rule_based' | 'ai_generated';
export type CoreSummaryKey = 'coverage' | 'longevity' | 'lightweight';
export type WearSummaryKey = WearAttributeKey;
export type ConcernSummaryKey = `concern:${SkinConcern}`;
export type ReviewSummaryItemKey = CoreSummaryKey | WearSummaryKey | ConcernSummaryKey;
export type ReviewSummaryPolarity = 'positive' | 'negative' | 'mixed';

export interface ReviewSummaryPolarityCounts {
  positive: number;
  negative: number;
  mixed: number;
}

/**
 * Shared UI contract for each score/concern item in ProductModal.
 * The integration worker can supply this shape via `profile_metadata` or a resolver
 * without editing UI components.
 */
export interface ReviewSummaryView {
  /** 1~2 sentences summarizing post-use reviews (empty when insufficient or unavailable). */
  sentences: string[];
  /** Factual source label: '리뷰 요약' for rule-based; AI label only when genuinely AI-generated. */
  sourceLabel?: string;
  /** Optional explicit basis used to guard against accidental AI mislabeling. */
  sourceKind?: ReviewSummaryBasis;
  /** Total evidence count for the attribute/scope (distinct from expanded sample count). */
  totalEvidenceCount: number;
  /** Up to 5 sample original review IDs attributed to the current product.id. */
  sampleReviewIds: string[];
  /** Preserved positive / negative / mixed counts when available. */
  polarityCounts?: ReviewSummaryPolarityCounts;
  /** True when score is null or total evidence is below the 3-review threshold. */
  insufficient?: boolean;
  /** True while original evidence reviews are being fetched. */
  loading?: boolean;
  /** Error message when fetching original evidence reviews failed. */
  error?: string;
}

export interface ReviewSummaryProviderInput {
  product: Product;
  itemKey: ReviewSummaryItemKey;
  wearScope?: string;
  evidenceById: ReadonlyMap<string, Review>;
}

export type ReviewSummaryResolver = (
  input: ReviewSummaryProviderInput,
) => Partial<ReviewSummaryView> | null | undefined;

export interface MetadataReviewSummaryEntry {
  sentences?: readonly string[];
  summary?: string;
  source_label?: string;
  sourceLabel?: string;
  source_kind?: ReviewSummaryBasis;
  sourceKind?: ReviewSummaryBasis;
  total_evidence_count?: number;
  totalEvidenceCount?: number;
  sample_review_ids?: readonly string[];
  sampleReviewIds?: readonly string[];
  polarity_counts?: Partial<ReviewSummaryPolarityCounts>;
  polarityCounts?: Partial<ReviewSummaryPolarityCounts>;
  insufficient?: boolean;
}

export interface ResolvedSampleReviews {
  requestedIds: string[];
  matchedReviews: Review[];
  missingIds: string[];
  unattributedIds: string[];
  missingCount: number;
}

const WEAR_KEYS: ReadonlySet<string> = new Set<WearSummaryKey>([
  'naturalness',
  'transfer_resistance',
  'smoothness',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function toNonNegativeInt(value: unknown, fallback = 0): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback;
  return Math.max(0, Math.floor(value));
}

export function normalizeReviewIds(
  ids: readonly string[] | undefined | null,
  limit = MAX_SAMPLE_REVIEW_IDS,
): string[] {
  if (!ids?.length || limit <= 0) return [];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of ids) {
    const id = typeof raw === 'string' ? raw.trim() : '';
    if (!id || seen.has(id)) continue;
    seen.add(id);
    result.push(id);
    if (result.length >= limit) break;
  }
  return result;
}

export function normalizeSentences(sentences: readonly string[] | undefined | null): string[] {
  if (!sentences?.length) return [];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of sentences) {
    const text = typeof raw === 'string' ? raw.replace(/\s+/g, ' ').trim() : '';
    if (!text || seen.has(text)) continue;
    seen.add(text);
    result.push(text);
    if (result.length >= MAX_SUMMARY_SENTENCES) break;
  }
  return result;
}

export function resolveSourceLabel(
  view: Pick<ReviewSummaryView, 'sourceLabel' | 'sourceKind'>,
): string {
  const trimmed = view.sourceLabel?.trim();
  if (view.sourceKind === 'ai_generated') {
    return trimmed || 'AI 리뷰 요약';
  }
  if (view.sourceKind === 'rule_based') {
    if (trimmed && !/(?:^|[^A-Za-z])AI(?:[^A-Za-z]|$)/i.test(trimmed)) {
      return trimmed;
    }
    return '리뷰 요약';
  }
  return trimmed || '리뷰 요약';
}

/**
 * Selects up to `limit` (default 5) sample review IDs across positive/negative/mixed
 * groups without silencing minority polarities.
 */
export function selectBalancedSampleIds(
  groups: {
    positive?: readonly string[];
    negative?: readonly string[];
    mixed?: readonly string[];
  },
  counts?: Partial<ReviewSummaryPolarityCounts>,
  limit = MAX_SAMPLE_REVIEW_IDS,
): string[] {
  if (limit <= 0) return [];
  const rawBuckets: { key: ReviewSummaryPolarity; ids: string[]; weight: number; order: number }[] = [
    {
      key: 'positive',
      ids: normalizeReviewIds(groups.positive, limit),
      weight: toNonNegativeInt(counts?.positive, groups.positive?.length ?? 0),
      order: 0,
    },
    {
      key: 'negative',
      ids: normalizeReviewIds(groups.negative, limit),
      weight: toNonNegativeInt(counts?.negative, groups.negative?.length ?? 0),
      order: 1,
    },
    {
      key: 'mixed',
      ids: normalizeReviewIds(groups.mixed, limit),
      weight: toNonNegativeInt(counts?.mixed, groups.mixed?.length ?? 0),
      order: 2,
    },
  ];
  const buckets = rawBuckets
    .filter(bucket => bucket.ids.length > 0)
    .sort((a, b) => b.weight - a.weight || a.order - b.order);

  const seen = new Set<string>();
  const picked: string[] = [];
  let cursor = 0;
  while (picked.length < limit) {
    let progressed = false;
    for (const bucket of buckets) {
      if (cursor < bucket.ids.length) {
        progressed = true;
        const id = bucket.ids[cursor];
        if (!seen.has(id)) {
          seen.add(id);
          picked.push(id);
          if (picked.length >= limit) break;
        }
      }
    }
    if (!progressed) break;
    cursor += 1;
  }
  return picked;
}

export function buildPolarityMap(
  entry?: Pick<WearEvidence, 'positive_review_ids' | 'negative_review_ids' | 'mixed_review_ids'> | null,
): Map<string, ReviewSummaryPolarity> {
  const map = new Map<string, ReviewSummaryPolarity>();
  if (!entry) return map;
  for (const id of entry.positive_review_ids ?? []) {
    if (id) map.set(id, 'positive');
  }
  for (const id of entry.negative_review_ids ?? []) {
    if (id) map.set(id, map.has(id) ? 'mixed' : 'negative');
  }
  for (const id of entry.mixed_review_ids ?? []) {
    if (id) map.set(id, 'mixed');
  }
  return map;
}

/**
 * Resolves sample review IDs against `evidenceById` while enforcing strict
 * `review.product_id === productId` attribution. Missing and mismatched IDs are
 * reported explicitly so the UI never hides them silently.
 */
export function resolveSampleReviews(
  productId: string,
  sampleReviewIds: readonly string[],
  evidenceById: ReadonlyMap<string, Review>,
  limit = MAX_SAMPLE_REVIEW_IDS,
): ResolvedSampleReviews {
  const requestedIds = normalizeReviewIds(sampleReviewIds, limit);
  const matchedReviews: Review[] = [];
  const missingIds: string[] = [];
  const unattributedIds: string[] = [];

  for (const id of requestedIds) {
    const review = evidenceById.get(id);
    if (!review) {
      missingIds.push(id);
      continue;
    }
    if (review.product_id !== productId) {
      unattributedIds.push(id);
      continue;
    }
    matchedReviews.push(review);
  }

  return {
    requestedIds,
    matchedReviews,
    missingIds,
    unattributedIds,
    missingCount: missingIds.length + unattributedIds.length,
  };
}

function parseMetadataSummaryEntry(raw: unknown): Partial<ReviewSummaryView> | null {
  if (!isRecord(raw)) return null;
  const entry = raw as MetadataReviewSummaryEntry;
  const sentences = Array.isArray(entry.sentences)
    ? normalizeSentences(entry.sentences)
    : typeof entry.summary === 'string'
      ? normalizeSentences([entry.summary])
      : undefined;

  const sourceKind =
    entry.sourceKind === 'ai_generated' || entry.sourceKind === 'rule_based'
      ? entry.sourceKind
      : entry.source_kind === 'ai_generated' || entry.source_kind === 'rule_based'
        ? entry.source_kind
        : undefined;
  const sourceLabel =
    typeof entry.sourceLabel === 'string'
      ? entry.sourceLabel
      : typeof entry.source_label === 'string'
        ? entry.source_label
        : undefined;
  const totalEvidenceCount =
    typeof entry.totalEvidenceCount === 'number'
      ? toNonNegativeInt(entry.totalEvidenceCount)
      : typeof entry.total_evidence_count === 'number'
        ? toNonNegativeInt(entry.total_evidence_count)
        : undefined;
  const sampleIdsSource = Array.isArray(entry.sampleReviewIds)
    ? entry.sampleReviewIds
    : Array.isArray(entry.sample_review_ids)
      ? entry.sample_review_ids
      : undefined;
  const rawPolarity = entry.polarityCounts ?? entry.polarity_counts;
  const polarityCounts = isRecord(rawPolarity)
    ? {
        positive: toNonNegativeInt(rawPolarity.positive),
        negative: toNonNegativeInt(rawPolarity.negative),
        mixed: toNonNegativeInt(rawPolarity.mixed),
      }
    : undefined;

  const result: Partial<ReviewSummaryView> = {};
  if (sentences !== undefined) result.sentences = sentences;
  if (sourceLabel !== undefined) result.sourceLabel = sourceLabel;
  if (sourceKind !== undefined) result.sourceKind = sourceKind;
  if (totalEvidenceCount !== undefined) result.totalEvidenceCount = totalEvidenceCount;
  if (sampleIdsSource !== undefined) result.sampleReviewIds = normalizeReviewIds(sampleIdsSource);
  if (polarityCounts !== undefined) result.polarityCounts = polarityCounts;
  if (typeof entry.insufficient === 'boolean') result.insufficient = entry.insufficient;

  return Object.keys(result).length > 0 ? result : null;
}

/**
 * Safely reads optional summary payloads attached to `product.profile_metadata`
 * (e.g. `review_summaries` or `option_wear[scope].review_summaries`) without
 * modifying `web/src/lib/supabase.ts`.
 */
export function extractMetadataSummary(
  product: Product,
  itemKey: ReviewSummaryItemKey,
  wearScope = '',
): Partial<ReviewSummaryView> | null {
  const meta = product.profile_metadata as unknown;
  if (!isRecord(meta)) return null;

  if (wearScope && WEAR_KEYS.has(itemKey) && isRecord(meta.option_wear)) {
    const scopeGroup = meta.option_wear[wearScope];
    if (isRecord(scopeGroup)) {
      if (isRecord(scopeGroup.review_summaries) && itemKey in scopeGroup.review_summaries) {
        return parseMetadataSummaryEntry(scopeGroup.review_summaries[itemKey]);
      }
      if (isRecord(scopeGroup.summaries) && itemKey in scopeGroup.summaries) {
        return parseMetadataSummaryEntry(scopeGroup.summaries[itemKey]);
      }
    }
    if (isRecord(meta.review_summaries)) {
      const scopedKey = `option:${wearScope}:${itemKey}`;
      if (scopedKey in meta.review_summaries) {
        return parseMetadataSummaryEntry(meta.review_summaries[scopedKey]);
      }
    }
    // Never reuse overall product wear summary when a specific option scope is active.
    return null;
  }

  const containers = [meta.review_summaries, meta.summaries];
  for (const container of containers) {
    if (!isRecord(container)) continue;
    if (itemKey in container) {
      const parsed = parseMetadataSummaryEntry(container[itemKey]);
      if (parsed) return parsed;
    }
    if (itemKey.startsWith('concern:')) {
      const bareConcern = itemKey.slice('concern:'.length);
      if (isRecord(container.concerns) && bareConcern in container.concerns) {
        const parsed = parseMetadataSummaryEntry(container.concerns[bareConcern]);
        if (parsed) return parsed;
      }
    }
  }
  return null;
}

export function collectMetadataSummaryReviewIds(product: Product, wearScope = ''): string[] {
  const keys: ReviewSummaryItemKey[] = [
    'coverage',
    'longevity',
    'lightweight',
    'naturalness',
    'transfer_resistance',
    'smoothness',
    ...((product.suitable_concerns ?? []) as SkinConcern[]).map(
      concern => `concern:${concern}` as ConcernSummaryKey,
    ),
  ];
  const ids: string[] = [];
  for (const key of keys) {
    const parsed = extractMetadataSummary(product, key, WEAR_KEYS.has(key) ? wearScope : '');
    if (parsed?.sampleReviewIds?.length) {
      ids.push(...parsed.sampleReviewIds);
    }
  }
  return [...new Set(ids)];
}

export interface BuildReviewSummaryParams {
  product: Product;
  hasCurrentProfile: boolean;
  itemKey: ReviewSummaryItemKey;
  wearScope?: string;
  score?: number | null;
  evidenceById: ReadonlyMap<string, Review>;
  loading?: boolean;
  error?: string;
  externalSummary?: Partial<ReviewSummaryView> | null;
  resolver?: ReviewSummaryResolver;
}

/**
 * Builds a complete, fact-checked `ReviewSummaryView` from existing product metadata
 * plus an optional external summary payload or resolver.
 * Never fabricates summary sentences when evidence is insufficient or unconnected.
 */
export function buildReviewSummaryView({
  product,
  hasCurrentProfile,
  itemKey,
  wearScope = '',
  score,
  evidenceById,
  loading = false,
  error = '',
  externalSummary,
  resolver,
}: BuildReviewSummaryParams): ReviewSummaryView {
  const meta = hasCurrentProfile ? product.profile_metadata ?? null : null;

  let baseTotalCount = 0;
  let baseSampleIds: string[] = [];
  let basePolarity: ReviewSummaryPolarityCounts | undefined;
  let baseInsufficient = !hasCurrentProfile;

  if (WEAR_KEYS.has(itemKey)) {
    const wearKey = itemKey as WearSummaryKey;
    const entry = wearScope
      ? meta?.option_wear?.[wearScope]?.attributes?.[wearKey]
      : meta?.wear_attributes?.[wearKey];
    baseTotalCount = toNonNegativeInt(entry?.evidence_count);
    basePolarity = {
      positive: toNonNegativeInt(entry?.positive_count),
      negative: toNonNegativeInt(entry?.negative_count),
      mixed: toNonNegativeInt(entry?.mixed_count),
    };
    baseSampleIds = entry
      ? selectBalancedSampleIds(
          {
            positive: entry.positive_review_ids,
            negative: entry.negative_review_ids,
            mixed: entry.mixed_review_ids,
          },
          basePolarity,
        )
      : [];
    const effectiveScore = score !== undefined ? score : (entry?.score ?? null);
    baseInsufficient =
      !hasCurrentProfile ||
      !entry ||
      effectiveScore == null ||
      baseTotalCount < MIN_SUMMARY_EVIDENCE_COUNT;
  } else if (itemKey.startsWith('concern:')) {
    const concern = itemKey.slice('concern:'.length);
    const rawIds = meta?.concern_evidence_ids?.[concern] ?? [];
    const pos = toNonNegativeInt(meta?.positive_concern_counts?.[concern], rawIds.length);
    const neg = toNonNegativeInt(meta?.negative_concern_counts?.[concern], 0);
    baseSampleIds = normalizeReviewIds(rawIds);
    baseTotalCount = Math.max(pos, baseSampleIds.length);
    if (pos > 0 || neg > 0) {
      basePolarity = { positive: pos, negative: neg, mixed: 0 };
    }
    baseInsufficient = !hasCurrentProfile || baseTotalCount < MIN_SUMMARY_EVIDENCE_COUNT;
  } else {
    const coreKey = itemKey as CoreSummaryKey;
    baseTotalCount = toNonNegativeInt(meta?.evidence_counts?.[coreKey]);
    baseSampleIds = normalizeReviewIds(meta?.evidence_review_ids?.[coreKey]);
    const rawScore =
      score !== undefined
        ? score
        : coreKey === 'coverage'
          ? product.coverage_score
          : coreKey === 'longevity'
            ? product.longevity_score
            : product.lightweight_score;
    baseInsufficient =
      !hasCurrentProfile || rawScore == null || baseTotalCount < MIN_SUMMARY_EVIDENCE_COUNT;
  }

  const injected =
    externalSummary ??
    resolver?.({ product, itemKey, wearScope, evidenceById }) ??
    (hasCurrentProfile ? extractMetadataSummary(product, itemKey, wearScope) : null) ??
    null;

  const sampleReviewIds =
    injected?.sampleReviewIds !== undefined
      ? normalizeReviewIds(injected.sampleReviewIds)
      : baseSampleIds;

  const totalEvidenceCount = Math.max(
    injected?.totalEvidenceCount !== undefined
      ? toNonNegativeInt(injected.totalEvidenceCount)
      : baseTotalCount,
    sampleReviewIds.length,
  );

  const insufficient =
    baseInsufficient ||
    Boolean(injected?.insufficient) ||
    totalEvidenceCount < MIN_SUMMARY_EVIDENCE_COUNT;

  // Never show fabricated or speculative summary prose when evidence is insufficient.
  const sentences = insufficient ? [] : normalizeSentences(injected?.sentences);

  const sourceKind = injected?.sourceKind ?? (injected ? undefined : 'rule_based');
  const sourceLabel = resolveSourceLabel({
    sourceLabel: injected?.sourceLabel,
    sourceKind,
  });

  const polarityCounts = injected?.polarityCounts ?? basePolarity;
  const resolvedLoading = injected?.loading ?? loading;
  const resolvedError = injected?.error ?? (error || undefined);

  return {
    sentences,
    sourceLabel,
    sourceKind,
    totalEvidenceCount,
    sampleReviewIds,
    polarityCounts,
    insufficient,
    loading: resolvedLoading,
    error: resolvedError,
  };
}

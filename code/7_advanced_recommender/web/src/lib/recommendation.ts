import type { Product, SkinType, SkinConcern, ShadeChoice, ApplicationMethod, ShadeLineup, PriorityAttr, WearAttributeKey } from './supabase';

export const PROFILE_VERSION = 'rules-ko-v5';
// A policy prior, not a learned parameter or probability of correctness.
export const EVIDENCE_PRIOR = 5;
export const FEATURE_CONFIG = [
  { key: 'naturalness', pref: 'naturalnessPref', label: '화장 티가 덜 나는 표현', color: '#fbbf24' },
  { key: 'transfer_resistance', pref: 'transferPref', label: '묻어남이 적은 표현', color: '#fb923c' },
  { key: 'smoothness', pref: 'smoothnessPref', label: '들뜸·뭉침·끼임이 적은 표현', color: '#f472b6' },
  { key: 'coverage', pref: 'coveragePref', label: '커버력', color: '#a78bfa' },
  { key: 'longevity', pref: 'longevityPref', label: '지속력', color: '#60a5fa' },
  { key: 'lightweight', pref: 'lightweightPref', label: '착용감/가벼움', color: '#34d399' },
] as const;

export function evidenceSupport(count: number): number {
  const n = Number.isFinite(count) ? Math.max(0, count) : 0;
  return n / (n + EVIDENCE_PRIOR);
}

export function attributeEvidence(product: Product, key: PriorityAttr) {
  if (!hasCurrentProfile(product)) return { score: null, count: 0 };
  const wear = product.profile_metadata?.wear_attributes?.[key as WearAttributeKey];
  const count = wear?.evidence_count ?? product.profile_metadata?.evidence_counts?.[key] ?? 0;
  const raw = key === 'coverage' ? product.coverage_score : key === 'longevity' ? product.longevity_score : key === 'lightweight' ? product.lightweight_score : wear?.score;
  return { score: count >= 3 && raw != null && Number.isFinite(raw) ? raw : null, count };
}

export function featureAssessment(product: Product, prefs: Partial<QuizAnswers>) {
  let weightedValue = 0, weightedSupport = 0, totalWeight = 0, knownWeight = 0, known = 0;
  for (const feature of FEATURE_CONFIG) {
    const weight = Math.max(0, Math.min(5, prefs[feature.pref] ?? 1) - 1);
    if (!weight) continue;
    totalWeight += weight;
    const { score, count } = attributeEvidence(product, feature.key);
    const support = score == null ? 0 : evidenceSupport(count);
    // Neutral only for ranking arithmetic; the stored/displayed value stays null.
    const quality = score == null ? 0.5 : 0.5 + support * (Math.max(0, Math.min(1, (score - 1) / 4)) - 0.5);
    weightedValue += weight * quality;
    weightedSupport += weight * support;
    if (score != null) { knownWeight += weight; known += 1; }
  }
  return { points: totalWeight ? weightedValue / totalWeight * 30 : 0,
    supportBonus: totalWeight ? weightedSupport / totalWeight * 5 : 0,
    knownWeight, totalWeight, known };
}
export const SKIN_TYPE_COMPAT_COL = {
  oily: 'compat_oily', dry: 'compat_dry', sensitive: 'compat_sensitive', combination: 'compat_combination',
} as const;

/** Where each quiz tone sits on a product's own light-to-dark range. */
export const SHADE_TARGET: Record<'21' | '23' | '25', number> = { '21': 0, '23': 0.5, '25': 1 };

type ExplicitShade = '21' | '23' | '25';
export type ShadeMatchKind = 'any' | 'exact' | 'relative' | 'unknown' | 'conflict';

const QUIZ_SHADES: readonly ExplicitShade[] = ['21', '23', '25'];
const EXPLICIT_SHADE_RANGE = /(?<!\d)(19|2\d)\s*[~～–-]\s*(19|2\d)\s*호/g;
const EXPLICIT_SHADE_HO = /(?<!\d)(19|2\d)\s*호/g;
const EXPLICIT_SHADE_CODE = /(?<!\d)(21|23|25)[NnCcWw]\d?(?![A-Za-z0-9가-힣])/g;
const EXPLICIT_SHADE_HASH = /(?:^|[\s([/#])(?:no\.?\s*|#)(21|23|25)(?![A-Za-z0-9])/gi;
const EXPLICIT_SHADE_TONE_AFTER = /(?<!\d)(21|23|25)\s+(?:라이트|내추럴|네추럴|뉴트럴|미디엄|아이보리|베이지|샌드|앰버|탄|페어|딥|다크)/g;
const EXPLICIT_SHADE_TONE_BEFORE = /(?:라이트|내추럴|네추럴|뉴트럴|미디엄|아이보리|베이지|샌드|앰버|탄|페어|딥|다크)\s+(21|23|25)(?![\dA-Za-z]|ml|g|매|개|종)/gi;

function isExplicitShade(value: string): value is ExplicitShade {
  return value === '21' || value === '23' || value === '25';
}

/** Extracts cushion-scale shades (21/23/25) explicitly stated in an option or product title.
 *  Brand-relative numbers (1호, 02호, 001) and non-shade units (24H, 20ml, 20매) never match. */
export function parseExplicitShadeSpec(text: string | null | undefined): { hasExplicit: boolean; shades: Set<ExplicitShade> } {
  const shades = new Set<ExplicitShade>();
  if (!text) return { hasExplicit: false, shades };
  let hasExplicit = false;
  const remaining = text.replace(EXPLICIT_SHADE_RANGE, (_, left: string, right: string) => {
    hasExplicit = true;
    const low = Math.min(Number(left), Number(right));
    const high = Math.max(Number(left), Number(right));
    for (const candidate of QUIZ_SHADES) {
      const n = Number(candidate);
      if (n >= low && n <= high) shades.add(candidate);
    }
    return ' ';
  });
  for (const match of remaining.matchAll(EXPLICIT_SHADE_HO)) {
    hasExplicit = true;
    if (isExplicitShade(match[1])) {
      shades.add(match[1]);
    }
  }
  for (const pattern of [EXPLICIT_SHADE_CODE, EXPLICIT_SHADE_HASH, EXPLICIT_SHADE_TONE_AFTER, EXPLICIT_SHADE_TONE_BEFORE]) {
    for (const match of remaining.matchAll(pattern)) {
      if (isExplicitShade(match[1])) {
        hasExplicit = true;
        shades.add(match[1]);
      }
    }
  }
  return { hasExplicit, shades };
}

function optionShadeSpec(option: { name?: string | null; label?: string | null }) {
  const fromName = parseExplicitShadeSpec(option.name);
  const fromLabel = parseExplicitShadeSpec(option.label);
  return {
    hasExplicit: fromName.hasExplicit || fromLabel.hasExplicit,
    shades: new Set<ExplicitShade>([...fromName.shades, ...fromLabel.shades]),
  };
}

function isOptionShadeCompatible(option: { name?: string | null; label?: string | null }, shade: ExplicitShade): boolean {
  const spec = optionShadeSpec(option);
  return !spec.hasExplicit || spec.shades.has(shade);
}

export function shadeLineup(product: Product): ShadeLineup | null {
  return (hasCurrentProfile(product) ? product.profile_metadata?.shade_lineup : null) ?? null;
}

/** True unless the product explicitly states cushion-scale shade(s) that exclude `shade`.
 *  Brand-relative lineups (1호/2호, 아이보리/베이지/샌드) and unstated shades stay eligible. */
export function isShadeCompatible(product: Product, shade: ShadeChoice | null): boolean {
  if (!shade || shade === 'any') return true;
  // The current seller catalog includes sold-out shades that suitable_shades omits.
  const catalogOptions = (product.source_options ?? []).filter(o => o.name?.trim());
  if (catalogOptions.length) {
    const specs = catalogOptions.map(o => parseExplicitShadeSpec(o.name));
    if (specs.every(s => s.hasExplicit)) return specs.some(s => s.shades.has(shade));
  }
  if (product.suitable_shades?.length) {
    const stated = new Set<ExplicitShade>();
    for (const entry of product.suitable_shades) {
      if (isExplicitShade(entry)) stated.add(entry);
      else for (const s of parseExplicitShadeSpec(entry).shades) stated.add(s);
    }
    return stated.has(shade);
  }
  const shadeOptionEntries = Object.entries(product.shade_options ?? {});
  if (shadeOptionEntries.length) {
    return shadeOptionEntries.some(([key, label]) =>
      key === shade || parseExplicitShadeSpec(key).shades.has(shade) || parseExplicitShadeSpec(label).shades.has(shade));
  }
  const lineupOptions = shadeLineup(product)?.options ?? [];
  if (lineupOptions.length) {
    const specs = lineupOptions.map(optionShadeSpec);
    if (specs.every(spec => spec.hasExplicit)) {
      return specs.some(spec => spec.shades.has(shade));
    }
    return true;
  }
  const sourceOptions = (product.source_options ?? [])
    .filter(o => (o?.name ?? '').trim().length > 0);
  if (sourceOptions.length) {
    const specs = sourceOptions.map(o => parseExplicitShadeSpec(o.name));
    if (specs.every(spec => spec.hasExplicit)) {
      return specs.some(spec => spec.shades.has(shade));
    }
  }
  const titleSpec = parseExplicitShadeSpec(product.name);
  if (titleSpec.hasExplicit) {
    return titleSpec.shades.has(shade);
  }
  return true;
}

/** Exact seller option, including its stock state. Relative brand numbers never match. */
export function bestExplicitShadeOption(product: Product, shade: ShadeChoice | null) {
  if (!shade || shade === 'any' || !isShadeCompatible(product, shade)) return null;
  const sources = (product.source_options ?? []).filter(o => o.name?.trim());
  const candidates = sources.length ? sources.map(o => ({ name: o.name!, sold_out: o.sold_out }))
    : (shadeLineup(product)?.options ?? []);
  const matching = candidates.filter(o => parseExplicitShadeSpec(o.name).shades.has(shade));
  if (matching.length) return matching.find(o => !o.sold_out) ?? matching[0];
  const title = parseExplicitShadeSpec(product.name);
  if (!shadeLineup(product) && sources.length <= 1 && title.shades.has(shade)) {
    return { name: sources[0]?.name || product.name, sold_out: sources[0]?.sold_out };
  }
  if (product.suitable_shades?.includes(shade)) {
    return { name: product.shade_options?.[shade] || `${shade}호`, sold_out: undefined };
  }
  return null;
}

/** The option of this product closest to the requested tone, or null if it states none
 *  or every option explicitly conflicts with the requested cushion shade.
 *  Prefer in-stock options; if all compatible options are sold out, suggest the nearest
 *  one and let the card/modal display its sold-out status. */
export function bestShadeOption(product: Product, shade: ShadeChoice | null) {
  if (!shade || shade === 'any') return null;
  const options = shadeLineup(product)?.options;
  if (!options?.length) return null;
  const compatible = options.filter(o => isOptionShadeCompatible(o, shade));
  if (!compatible.length) return null;
  const target = SHADE_TARGET[shade];
  const nearest = (list: typeof compatible) =>
    list.reduce((best, o) => Math.abs(o.position - target) < Math.abs(best.position - target) ? o : best);
  const inStock = compatible.filter(o => !o.sold_out);
  return nearest(inStock.length ? inStock : compatible);
}

export function classifyShadeMatch(product: Product, shade: ShadeChoice | null): ShadeMatchKind {
  if (!shade || shade === 'any') return 'any';
  if (!isShadeCompatible(product, shade)) return 'conflict';
  if (bestExplicitShadeOption(product, shade)) return 'exact';
  if (bestShadeOption(product, shade)) return 'relative';
  return 'unknown';
}

export function hasCurrentProfile(product: Product): boolean {
  // These versions use the same public schema. This keeps live results available
  // while the new extractor's profiles are rolled out after the compatible web.
  return [PROFILE_VERSION, 'rules-ko-v4', 'rules-ko-v3'].includes(product.profile_metadata?.version ?? '');
}

export function getCompatScore(product: Product, skinType: SkinType): number | null {
  return hasCurrentProfile(product) ? product[SKIN_TYPE_COMPAT_COL[skinType]] : null;
}

export function calcRecommendScore(product: Product, skinType: SkinType, concerns: SkinConcern[], coveragePref: number, longevityPref: number, lightweightPref: number, shade: ShadeChoice | null, wearPrefs: Partial<QuizAnswers> = {}): number {
  if (!hasCurrentProfile(product)) return -1;
  const compat = getCompatScore(product, skinType);
  let score = (compat ?? 0.5) * 25;
  if (concerns.length) {
    score += concerns.filter(c => product.suitable_concerns?.includes(c)).length / concerns.length * 25;
    const adverse = product.profile_metadata?.negative_concern_counts ?? {};
    const positive = product.profile_metadata?.positive_concern_counts ?? {};
    score -= concerns.filter(c => (adverse[c] ?? 0) >= 3 && (adverse[c] ?? 0) > (positive[c] ?? 0)).length * 10;
  }
  // 1 = unimportant, so it contributes zero weight, not a preference for low quality.
  const features = featureAssessment(product, { ...wearPrefs, coveragePref, longevityPref, lightweightPref });
  score += features.points + features.supportBonus;
  if (shade && shade !== 'any') {
    if (!isShadeCompatible(product, shade)) {
      score -= 20;
    } else if (bestExplicitShadeOption(product, shade)) {
      score += 15;
    } else {
      // No 21/23/25 shade stated, but the product's own options may run light to
      // dark. Credit how closely its nearest option sits to the requested tone:
      // a three-shade line serves a standard tone better than a two-shade one.
      // Capped below the stated-shade bonus: "the lighter of two" is weaker
      // evidence than a shade named on the same scale the user answered on.
      const option = bestShadeOption(product, shade);
      if (option) score += 10 * (1 - Math.abs(option.position - SHADE_TARGET[shade]));
    }
  }
  // Confidence now uses evidence for requested attributes, not total review volume.
  return score;
}

export function searchProducts(products: Product[], search: string): Product[] {
  const term = search.trim().toLocaleLowerCase();
  return term ? products.filter(p => `${p.name} ${p.brand}`.toLocaleLowerCase().includes(term)) : products;
}

export interface QuizAnswers {
  skinType: SkinType;
  concerns: SkinConcern[];
  coveragePref: number;
  longevityPref: number;
  lightweightPref: number;
  naturalnessPref?: number;
  transferPref?: number;
  smoothnessPref?: number;
  shade: ShadeChoice | null;
  applicationMethod: ApplicationMethod | null;
}

// A product needs enough analyzed reviews before its profile is allowed to rank.
export const MIN_ANALYZED_REVIEWS = 5;
export const RESULT_LIMIT = 12;

// The quiz asks how to cover the whole face and which tone to match, so it
// ranks full-face base makeup. A concealer answers a different question -
// hiding one spot - and its review scores describe that job, not this one.
// Concealers stay in the catalog; they are just not an answer to this quiz.
const RECOMMENDABLE_TYPES = new Set(['cushion', 'liquid', 'stick', 'tone_lotion', 'foundation_unknown']);
const NON_COVER_CATEGORIES = new Set(['컨실러', '프라이머/베이스', '메이크업베이스/프라이머', '파우더/팩트', '파우더', '쉐이딩']);

export function isFullFaceBase(product: Product): boolean {
  if (product.profile_metadata?.recommendation_eligibility?.eligible === false) return false;
  const category = product.profile_metadata?.source_category?.replace(/\s+/g, '') ?? '';
  return RECOMMENDABLE_TYPES.has(product.product_type ?? '') && !NON_COVER_CATEGORIES.has(category);
}

/** The ranking the site shows. Kept here so the offline evaluation scores the same list. */
export function selectRecommendations(products: Product[], quiz: QuizAnswers): (Product & { _score: number })[] {
  return products
    .filter(p => hasCurrentProfile(p) && (p.profile_metadata?.analyzed_count ?? 0) >= MIN_ANALYZED_REVIEWS)
    .filter(isFullFaceBase)
    // An explicitly incompatible shade must not be rescued by unrelated scores or fallback slots.
    // Products with only relative brand shades or unstated shades remain eligible as uncertain.
    .filter(p => isShadeCompatible(p, quiz.shade))
    .filter(p => quiz.applicationMethod === 'hand' ? p.product_type === 'tone_lotion' : quiz.applicationMethod === 'tool' ? p.product_type !== 'tone_lotion' : true)
    .map(p => ({ ...p, _score: calcRecommendScore(p, quiz.skinType, quiz.concerns, quiz.coveragePref, quiz.longevityPref, quiz.lightweightPref, quiz.shade, quiz) }))
    .sort((a, b) => b._score - a._score || a.id.localeCompare(b.id))
    .slice(0, RESULT_LIMIT);
}

/** Splits ranked recommendations into top/exact matches and uncertain/relative alternatives.
 *  Explicitly conflicting shades are excluded from both primary and alternative lists. */
export function splitRecommendations(products: Product[], quiz: QuizAnswers) {
  const ranked = selectRecommendations(products, quiz);
  if (!quiz.shade || quiz.shade === 'any') {
    return { primary: ranked.slice(0, 3), alternatives: ranked.slice(3) };
  }
  return {
    primary: ranked.filter(p => classifyShadeMatch(p, quiz.shade) === 'exact'),
    alternatives: ranked.filter(p => classifyShadeMatch(p, quiz.shade) !== 'exact'),
  };
}

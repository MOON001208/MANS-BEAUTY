import type { Product, SkinType, SkinConcern, ShadeChoice, ApplicationMethod, ShadeLineup } from './supabase';

export const PROFILE_VERSION = 'rules-ko-v1';
export const SKIN_TYPE_COMPAT_COL = {
  oily: 'compat_oily', dry: 'compat_dry', sensitive: 'compat_sensitive', combination: 'compat_combination',
} as const;

/** Where each quiz tone sits on a product's own light-to-dark range. */
export const SHADE_TARGET: Record<'21' | '23' | '25', number> = { '21': 0, '23': 0.5, '25': 1 };

export function shadeLineup(product: Product): ShadeLineup | null {
  return (hasCurrentProfile(product) ? product.profile_metadata?.shade_lineup : null) ?? null;
}

/** The option of this product closest to the requested tone, or null if it states none.
 *  Prefer in-stock options; if all are sold out, suggest the nearest one and
 *  let the card/modal display its sold-out status. */
export function bestShadeOption(product: Product, shade: ShadeChoice | null) {
  if (!shade || shade === 'any') return null;
  const options = shadeLineup(product)?.options;
  if (!options?.length) return null;
  const target = SHADE_TARGET[shade];
  const nearest = (list: typeof options) =>
    list.reduce((best, o) => Math.abs(o.position - target) < Math.abs(best.position - target) ? o : best);
  const inStock = options.filter(o => !o.sold_out);
  return nearest(inStock.length ? inStock : options);
}

export function hasCurrentProfile(product: Product): boolean {
  return product.profile_metadata?.version === PROFILE_VERSION;
}

export function getCompatScore(product: Product, skinType: SkinType): number | null {
  return hasCurrentProfile(product) ? product[SKIN_TYPE_COMPAT_COL[skinType]] : null;
}

export function calcRecommendScore(product: Product, skinType: SkinType, concerns: SkinConcern[], coveragePref: number, longevityPref: number, lightweightPref: number, shade: ShadeChoice | null): number {
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
  const pairs = [[coveragePref, product.coverage_score], [longevityPref, product.longevity_score], [lightweightPref, product.lightweight_score]];
  const totalWeight = pairs.reduce((n, [importance]) => n + Math.max(0, (importance ?? 1) - 1), 0);
  if (totalWeight > 0) {
    score += pairs.reduce((n, [importance, value]) => n + Math.max(0, (importance ?? 1) - 1) * (value == null ? 0 : Math.max(0, Math.min(1, (value - 1) / 4))), 0) / totalWeight * 30;
  }
  if (shade && shade !== 'any') {
    if (product.suitable_shades?.length) {
      if (product.suitable_shades.includes(shade)) score += 15;
      else score -= 20;
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
  // Small confidence adjustment uses analyzed reviews, never source site's total count.
  score += Math.min(Math.log10((product.profile_metadata?.analyzed_count ?? 0) + 1), 3) / 3 * 5;
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
const RECOMMENDABLE_TYPES = new Set(['cushion', 'liquid', 'stick', 'tone_lotion']);
const NON_COVER_CATEGORIES = new Set(['컨실러', '프라이머/베이스', '메이크업베이스/프라이머', '파우더/팩트', '파우더', '쉐이딩']);

export function isFullFaceBase(product: Product): boolean {
  const category = product.profile_metadata?.source_category?.replace(/\s+/g, '') ?? '';
  return RECOMMENDABLE_TYPES.has(product.product_type ?? '') && !NON_COVER_CATEGORIES.has(category);
}

/** The ranking the site shows. Kept here so the offline evaluation scores the same list. */
export function selectRecommendations(products: Product[], quiz: QuizAnswers): (Product & { _score: number })[] {
  return products
    .filter(p => hasCurrentProfile(p) && (p.profile_metadata?.analyzed_count ?? 0) >= MIN_ANALYZED_REVIEWS)
    .filter(isFullFaceBase)
    .filter(p => quiz.applicationMethod === 'hand' ? p.product_type === 'tone_lotion' : quiz.applicationMethod === 'tool' ? p.product_type !== 'tone_lotion' : true)
    .map(p => ({ ...p, _score: calcRecommendScore(p, quiz.skinType, quiz.concerns, quiz.coveragePref, quiz.longevityPref, quiz.lightweightPref, quiz.shade) }))
    .sort((a, b) => b._score - a._score || a.id.localeCompare(b.id))
    .slice(0, RESULT_LIMIT);
}

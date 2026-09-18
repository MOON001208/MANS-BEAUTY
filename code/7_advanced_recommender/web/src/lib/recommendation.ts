import type { Product, SkinType, SkinConcern, ShadeChoice } from './supabase';

export const PROFILE_VERSION = 'rules-ko-v1';
export const SKIN_TYPE_COMPAT_COL = {
  oily: 'compat_oily', dry: 'compat_dry', sensitive: 'compat_sensitive', combination: 'compat_combination',
} as const;

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
    if (product.suitable_shades?.includes(shade)) score += 15;
    else if (product.suitable_shades?.length) score -= 20;
  }
  // Small confidence adjustment uses analyzed reviews, never source site's total count.
  score += Math.min(Math.log10((product.profile_metadata?.analyzed_count ?? 0) + 1), 3) / 3 * 5;
  return score;
}

export function searchProducts(products: Product[], search: string): Product[] {
  const term = search.trim().toLocaleLowerCase();
  return term ? products.filter(p => `${p.name} ${p.brand}`.toLocaleLowerCase().includes(term)) : products;
}

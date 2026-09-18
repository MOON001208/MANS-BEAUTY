// Saves the ranking-relevant catalog fields so the evaluation is reproducible and
// runnable in CI. Public key only: this reads exactly what a visitor can read.
import { writeFileSync } from 'node:fs';

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
if (!url || !key) {
  console.error('NEXT_PUBLIC_SUPABASE_URL 과 NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY 가 필요합니다.');
  process.exit(1);
}

const FIELDS = [
  'id', 'name', 'brand', 'category', 'product_type', 'star_rating', 'review_count',
  'coverage_score', 'longevity_score', 'lightweight_score',
  'suitable_shades', 'suitable_skin_types', 'suitable_concerns',
  'compat_oily', 'compat_dry', 'compat_sensitive', 'compat_combination',
  'ingredient_level', 'profile_metadata', 'last_updated_at',
];

const response = await fetch(`${url}/rest/v1/products?select=${FIELDS.join(',')}&order=id&limit=1000`, {
  headers: { apikey: key, Authorization: `Bearer ${key}` },
});
if (!response.ok) {
  console.error(`상품 조회 실패: HTTP ${response.status}`);
  process.exit(1);
}
const products = await response.json();
writeFileSync(
  new URL('../tests/fixtures/catalog-snapshot.json', import.meta.url),
  JSON.stringify({ captured_at: new Date().toISOString(), count: products.length, products }, null, 2),
);
console.log(`카탈로그 스냅샷 저장: 상품 ${products.length}개`);

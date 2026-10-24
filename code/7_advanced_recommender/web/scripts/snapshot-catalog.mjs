// Public data only; keyset pagination also works under a low API row cap.
import { existsSync, writeFileSync } from 'node:fs';
import { validatePublicEnv } from './check-public-env.mjs';

export const FIELDS = [
  'id', 'name', 'brand', 'category', 'product_type', 'star_rating', 'review_count',
  'coverage_score', 'longevity_score', 'lightweight_score',
  'suitable_shades', 'shade_options', 'source_options', 'suitable_skin_types', 'suitable_concerns',
  'compat_oily', 'compat_dry', 'compat_sensitive', 'compat_combination',
  'ingredients_raw', 'ingredient_level', 'profile_metadata', 'last_updated_at',
];

export async function fetchCatalog(env = process.env, fetcher = fetch) {
  validatePublicEnv(env);
  const key = env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const products = [];
  let last;
  while (true) {
    const params = new URLSearchParams({ select: FIELDS.join(','), order: 'id', limit: '500' });
    if (last) params.set('id', `gt.${last}`);
    const response = await fetcher(`${env.NEXT_PUBLIC_SUPABASE_URL}/rest/v1/products?${params}`, {
      headers: { apikey: key, Authorization: `Bearer ${key}` },
    });
    if (!response.ok) throw new Error(`상품 조회 실패: HTTP ${response.status}`);
    const page = await response.json();
    if (!Array.isArray(page)) throw new Error('상품 조회 응답 형식 오류');
    if (!page.length) return products;
    const next = page[page.length - 1]?.id;
    if (!next || next === last) throw new Error('상품 조회 커서가 진행하지 않습니다.');
    products.push(...page);
    last = next;
  }
}

if (process.argv[1]?.endsWith('snapshot-catalog.mjs')) {
  for (const file of ['.env.local', '.env']) if (existsSync(file)) process.loadEnvFile(file);
  try {
    const products = await fetchCatalog();
    writeFileSync(new URL('../tests/fixtures/catalog-snapshot.json', import.meta.url),
      JSON.stringify({ captured_at: new Date().toISOString(), count: products.length, products }, null, 2));
    console.log(`카탈로그 스냅샷 저장: 상품 ${products.length}개`);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}

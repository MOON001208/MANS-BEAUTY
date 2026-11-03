import type { Product } from './supabase';
import { PROFILE_VERSION } from './recommendation.ts';

export interface CatalogResult {
  products: Product[];
  source: 'live' | 'snapshot';
  capturedAt?: string;
}

interface CatalogSnapshot {
  captured_at: string;
  count: number;
  products: Product[];
}

export async function loadCatalog(
  signal: AbortSignal,
  fetcher: typeof fetch = fetch,
  fallbackUrl = new URL('./catalog-fallback.json', globalThis.location?.href ?? 'http://localhost/').href,
): Promise<CatalogResult> {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const products: Product[] = [];
  let lastId: string | undefined;

  try {
    if (!url || !key) throw new Error('공개 상품 API 설정 없음');
    while (!signal.aborted) {
      const params = new URLSearchParams({ select: '*', order: 'id', limit: '500' });
      if (lastId) params.set('id', `gt.${lastId}`);
      // A stalled API must not leave the quiz showing a loading state forever.
      const response = await fetcher(`${url}/rest/v1/products?${params}`, {
        headers: { apikey: key, Authorization: `Bearer ${key}` },
        signal: AbortSignal.any([signal, AbortSignal.timeout(10_000)]),
      });
      if (!response.ok) throw new Error(`상품 API HTTP ${response.status}`);
      const page: unknown = await response.json();
      if (!Array.isArray(page)) throw new Error('상품 API 응답 형식 오류');
      if (!page.length) {
        if (!products.length) throw new Error('상품 API가 빈 목록을 반환함');
        return { products, source: 'live' };
      }
      const nextId = page[page.length - 1]?.id;
      if (typeof nextId !== 'string' || nextId === lastId) throw new Error('상품 목록 페이지를 확인하지 못했습니다.');
      products.push(...page as Product[]);
      lastId = nextId;
    }
    throw new Error('상품 조회 취소');
  } catch (error) {
    if (signal.aborted) throw error;
    const response = await fetcher(fallbackUrl, { signal });
    if (!response.ok) throw new Error('상품을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.');
    const snapshot: CatalogSnapshot = await response.json();
    if (!Array.isArray(snapshot.products) || snapshot.products.length < 1 ||
        snapshot.count !== snapshot.products.length || !Number.isFinite(Date.parse(snapshot.captured_at)) ||
        snapshot.products.some(p => !p.id || p.profile_metadata?.version !== PROFILE_VERSION)) {
      throw new Error('저장된 상품 자료를 확인하지 못했습니다. 잠시 후 다시 시도해주세요.');
    }
    return { products: snapshot.products, source: 'snapshot', capturedAt: snapshot.captured_at };
  }
}

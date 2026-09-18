import { supabase, type Product } from './supabase';

export async function loadCatalog(signal: AbortSignal): Promise<Product[]> {
  const products: Product[] = [];
  let lastId: string | undefined;
  while (!signal.aborted) {
    let query = supabase.from('products').select('*').order('id').limit(500);
    if (lastId) query = query.gt('id', lastId);
    const { data, error } = await query.abortSignal(signal);
    if (error) throw new Error('상품을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.');
    if (!data?.length) return products;
    products.push(...data as Product[]);
    const nextId = data[data.length - 1].id as string;
    if (lastId === nextId) throw new Error('상품 목록 페이지를 확인하지 못했습니다.');
    lastId = nextId;
  }
  return products;
}

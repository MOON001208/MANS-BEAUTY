import type { Product } from '../lib/supabase';
import { hasCurrentProfile } from '../lib/recommendation';

export function IngredientDetails({ product }: { product: Product }) {
  const source = hasCurrentProfile(product) ? product.profile_metadata?.ingredient_source : null;
  const entries = source?.entries.length ? source.entries : (product.ingredients_raw ? [{ label: '이전에 수집한 전성분 · 현재 원문 확인 불가', text: product.ingredients_raw }] : []);
  return (
    <section aria-label="전성분 정보" style={{ marginBottom: 20, padding: 14, border: '1px solid var(--border-color)', borderRadius: 12 }}>
      <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: 8 }}>전성분</h3>
      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 8 }}>
        판매자가 기재한 옵션·구성품 구분을 그대로 표시합니다.
        {source?.checked_at && ` 확인일 ${new Date(source.checked_at).toLocaleDateString('ko-KR', { timeZone: 'Asia/Seoul' })}`}
      </p>
      {!entries.length && <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>텍스트 전성분을 확인하지 못했습니다.</p>}
      {entries.map((entry, index) => (
        <details key={`${entry.label}-${index}`} style={{ marginTop: 8 }}>
          <summary style={{ cursor: 'pointer', fontSize: '0.8rem' }}>{entry.label} 보기</summary>
          <p style={{ fontSize: '0.76rem', lineHeight: 1.8, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', marginTop: 8 }}>{entry.text}</p>
        </details>
      ))}
      {source?.references.map((entry, index) => (
        <p key={`${entry.label}-${index}`} style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: 8 }}>{entry.label}: {entry.text}</p>
      ))}
      {!!source?.images?.length && <p style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: 8 }}>판매자 상세페이지의 전성분 표입니다. 옵션별 적용 여부는 원문에서 확인해 주세요.</p>}
      {source?.images?.filter(entry => entry.url.startsWith('https://image.oliveyoung.co.kr/')).map((entry, index) => (
        <a key={index} href={entry.url} target="_blank" rel="noopener noreferrer" style={{ display: 'block', marginTop: 8, fontSize: '0.76rem', color: '#a5b4fc' }}>{entry.label} ↗</a>
      ))}
      {source?.source_url.startsWith('https://www.oliveyoung.co.kr/') && (
        <a href={source.source_url} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-block', marginTop: 10, fontSize: '0.76rem', color: '#a5b4fc' }}>판매자 원문 확인 ↗</a>
      )}
    </section>
  );
}

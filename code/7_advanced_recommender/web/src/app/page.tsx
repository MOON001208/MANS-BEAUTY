'use client';

import { useState, useEffect, useCallback } from 'react';
import { supabase, Product, Review, SkinType, SkinConcern, PriorityAttr, ShadeChoice } from '@/lib/supabase';

// ─── 상수 ──────────────────────────────────────────────────────────────────
const SKIN_TYPE_OPTIONS: { key: SkinType; label: string; icon: string; desc: string }[] = [
  { key: 'oily', label: '지성', icon: '💧', desc: '번들거림, 모공 신경 쓰임' },
  { key: 'dry', label: '건성', icon: '🌵', desc: '건조함, 당김이 자주 느껴짐' },
  { key: 'combination', label: '복합성', icon: '⚖️', desc: 'T존 지성, 볼 건성' },
  { key: 'sensitive', label: '민감성', icon: '🌸', desc: '쉽게 트러블, 자극에 예민' },
];

const CONCERN_OPTIONS: { key: SkinConcern; label: string; icon: string }[] = [
  { key: 'acne', label: '여드름/트러블', icon: '😣' },
  { key: 'pore', label: '모공', icon: '🕳️' },
  { key: 'redness', label: '홍조', icon: '🔴' },
  { key: 'spots', label: '잡티/다크서클', icon: '🌑' },
  { key: 'wrinkle', label: '주름', icon: '〰️' },
];

const PRIORITY_OPTIONS: { key: PriorityAttr; label: string; icon: string; desc: string }[] = [
  { key: 'coverage', label: '커버력', icon: '🎭', desc: '잡티·트러블을 확실히 가리고 싶음' },
  { key: 'longevity', label: '지속력', icon: '⏱️', desc: '하루종일 무너지지 않길 원함' },
  { key: 'lightweight', label: '가벼운 착용감', icon: '💨', desc: '바른 것 같지 않은 자연스러운 느낌' },
];

const SHADE_OPTIONS: { key: ShadeChoice; label: string; desc: string; color?: string }[] = [
  { key: '21', label: '21호 (밝은 톤)', desc: '"피부 하얗네?" 라는 말을 종종 듣는 편. 밝은 아이보리 계열', color: '#FADAC1' },
  { key: '23', label: '23호 (표준 톤)', desc: '피부가 하얗지도 까맣지도 않은 대한민국 평균 남성 피부', color: '#E8CBAE' },
  { key: '25', label: '25호 (어두운 톤)', desc: '가무잡잡하고 건강한 피부. 평소 야외 활동을 즐기는 편', color: '#D2AA85' },
  { key: 'any', label: '잘 몰라요', desc: '내 톤을 모르겠다 (무난한 제품 위주로 추천)', color: 'transparent' },
];

const SKIN_TYPE_COMPAT_COL: Record<SkinType, keyof Product> = {
  oily: 'compat_oily',
  dry: 'compat_dry',
  sensitive: 'compat_sensitive',
  combination: 'compat_combination',
};

const CONCERN_LABEL: Record<SkinConcern, string> = {
  acne: '여드름', pore: '모공', redness: '홍조', spots: '잡티', wrinkle: '주름',
};

// ─── 유틸 ───────────────────────────────────────────────────────────────────
function getCompatScore(product: Product, skinType: SkinType): number {
  const col = SKIN_TYPE_COMPAT_COL[skinType];
  return (product[col] as number | null) ?? 0.5;
}

function calcRecommendScore(product: Product, skinType: SkinType, concerns: SkinConcern[], priority: PriorityAttr | null, userShade: ShadeChoice | null): number {
  let score = 0;
  // 1. 피부 호환성 (50점 배정으로 대폭 강화)
  const compat = getCompatScore(product, skinType);
  score += compat * 50;

  // 🚨 페널티: 피부 성분 호환성이 현저하게 낮으면 최종 점수를 극단적 삭감 대기 (0.35 미만일 때)
  const penalty = compat < 0.35;

  // 2. 피부 고민 일치도 (40점 배정으로 상향)
  if (concerns.length > 0) {
    const matched = concerns.filter(c => (product.suitable_concerns ?? []).includes(c)).length;
    score += (matched / concerns.length) * 40;
  } else {
    score += 20; // 선택한 고민이 없으면 중간 점수
  }

  // 3. 최우선 고려 속성 (10점 부수적 요소로 강등)
  if (priority === 'coverage') score += ((product.coverage_score ?? 3) / 5) * 10;
  if (priority === 'longevity') score += ((product.longevity_score ?? 3) / 5) * 10;
  if (priority === 'lightweight') score += ((product.lightweight_score ?? 3) / 5) * 10;
  if (!priority) score += 5;

  // 4. 호수 일치도 (10점 강등)
  if (userShade && userShade !== 'any') {
    const pShades = product.suitable_shades || [];
    if (pShades.length === 0) {
      score += 5; // 정보 없으면 중간 점수
    } else if (pShades.includes(userShade)) {
      score += 10; // 정확히 일치하면 만점
    } else {
      const order = ['21', '23', '25'];
      const uIdx = order.indexOf(userShade);
      const isAdj = pShades.some(p => Math.abs(uIdx - order.indexOf(p)) === 1);
      if (isAdj) score += 5; // 인접 호수면 중간 점수
    }
  } else {
    score += 8; // 호수 상관없으면 무난
  }

  // 5. 인기/대중성 방지 (리뷰 편향 억제를 위해 최대 2점만 추가)
  score += Math.min(Math.log10((product.review_count || 0) + 1) / 4, 1) * 2;

  // 🚨 최종 점수에 페널티 반영 (피부성분 꽝이면 70% 감점해서 무조건 순위밖으로)
  if (penalty) score *= 0.3;

  return score;
}

// ─── 컴포넌트: 별점 ─────────────────────────────────────────────────────────
function StarRating({ rating }: { rating: number }) {
  return (
    <div className="star-rating">
      {[1, 2, 3, 4, 5].map(s => (
        <svg key={s} width="13" height="13" viewBox="0 0 20 20"
          fill={s <= Math.round(rating) ? 'currentColor' : 'none'}
          stroke="currentColor" strokeWidth="1.5">
          <path d="M10 1l2.39 4.84 5.34.78-3.87 3.77.91 5.33L10 13.28l-4.77 2.51.91-5.33-3.87-3.77 5.34-.78L10 1z" />
        </svg>
      ))}
    </div>
  );
}

// ─── 컴포넌트: 점수 바 ───────────────────────────────────────────────────────
function ScoreBar({ label, value, color }: { label: string; value: number | null; color: string }) {
  const pct = value ? ((value - 1) / 4) * 100 : 0;
  return (
    <div style={{ marginBottom: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{label}</span>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color }}>{value?.toFixed(1) ?? '—'}</span>
      </div>
      <div style={{ height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
        <div style={{ height: '100%', borderRadius: '3px', width: value ? `${pct}%` : '0%', background: color, transition: 'width 0.6s ease' }} />
      </div>
    </div>
  );
}

// ─── 컴포넌트: 성분 배지 ─────────────────────────────────────────────────────
function IngredientBadge({ level }: { level: string | null }) {
  if (!level) return null;
  const config: Record<string, { color: string; bg: string }> = {
    '자연유래': { color: '#4ade80', bg: 'rgba(74,222,128,0.12)' },
    '저자극': { color: '#60a5fa', bg: 'rgba(96,165,250,0.12)' },
    '일반': { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)' },
  };
  const c = config[level] ?? config['일반'];
  return (
    <span style={{ fontSize: '0.65rem', fontWeight: 600, padding: '2px 7px', borderRadius: '6px', color: c.color, background: c.bg, border: `1px solid ${c.color}33` }}>
      {level === '자연유래' ? '🌿 ' : level === '저자극' ? '💙 ' : ''}{level}
    </span>
  );
}

// ─── 컴포넌트: 상품 카드 ─────────────────────────────────────────────────────
function ProductCard({ product, skinType, priority, userShade, onClick, rank }: {
  product: Product; skinType: SkinType; priority: PriorityAttr | null; userShade: ShadeChoice | null;
  onClick: () => void; rank: number;
}) {
  const typeLabel: Record<string, string> = { cushion: '쿠션', liquid: '리퀴드', stick: '스틱', tone_lotion: '톤로션/BB' };
  const compatScore = getCompatScore(product, skinType);
  const rankColors = ['', 'linear-gradient(135deg,#ffd700,#ff8c00)', 'linear-gradient(135deg,#c0c0c0,#808080)', 'linear-gradient(135deg,#cd7f32,#8b4500)'];

  // 단일 호수 추천 계산 로직
  let recommendedShadeStr = '';
  if (product.suitable_shades && product.suitable_shades.length > 0) {
    if (userShade && userShade !== 'any' && product.suitable_shades.includes(userShade)) {
      recommendedShadeStr = userShade;
    } else if (userShade && userShade !== 'any') {
      // 가장 가까운 호수 찾기
      const order = ['21', '23', '25'];
      const uIdx = order.indexOf(userShade);
      // pIdx 정렬 후 uIdx 와 인접한 것 찾기
      const availableIdxs = product.suitable_shades.map(s => order.indexOf(s)).filter(i => i !== -1);
      if (availableIdxs.length > 0) {
        availableIdxs.sort((a, b) => Math.abs(a - uIdx) - Math.abs(b - uIdx));
        recommendedShadeStr = order[availableIdxs[0]];
      } else {
        recommendedShadeStr = product.suitable_shades[0];
      }
    } else {
      // 사용자가 '잘 몰라요' 선택했을 경우 제품의 가장 무난한 추천인 중간값이나 23호
      recommendedShadeStr = product.suitable_shades.includes('23') ? '23' : product.suitable_shades[0];
    }
  }

  return (
    <div className="product-card animate-fadeInUp" onClick={onClick} style={{ cursor: 'pointer', position: 'relative' }}>
      {rank <= 3 && (
        <div style={{
          position: 'absolute', top: '12px', right: '12px', zIndex: 2,
          width: '28px', height: '28px', borderRadius: '50%', background: rankColors[rank],
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '0.7rem', fontWeight: 900, color: '#fff', boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
        }}>{rank}</div>
      )}
      <div className="image-wrapper">
        {product.thumbnail_url
          ? <img src={product.thumbnail_url} alt={product.name} loading="lazy" />
          : <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '3rem', opacity: 0.15 }}>🧴</div>
        }
        <div style={{ position: 'absolute', top: '12px', left: '12px' }}>
          <span className="category-badge" style={{
            background: product.product_type === 'cushion' ? 'rgba(99,102,241,0.8)' :
              product.product_type === 'stick' ? 'rgba(168,85,247,0.8)' :
                product.product_type === 'tone_lotion' ? 'rgba(20,184,166,0.8)' : 'rgba(59,130,246,0.8)',
          }}>
            {typeLabel[product.product_type ?? ''] ?? product.category}
          </span>
        </div>
      </div>
      <div style={{ padding: '14px 16px 16px' }}>
        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px' }}>{product.brand}</p>
        <h3 style={{ fontSize: '0.88rem', fontWeight: 600, lineHeight: 1.4, marginBottom: '10px', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{product.name}</h3>
        {(product.coverage_score || product.longevity_score || product.lightweight_score) && (
          <div style={{ marginBottom: '10px' }}>
            {(priority === 'coverage' || !priority) && <ScoreBar label="커버력" value={product.coverage_score} color="#a78bfa" />}
            {(priority === 'longevity' || !priority) && <ScoreBar label="지속력" value={product.longevity_score} color="#60a5fa" />}
            {(priority === 'lightweight' || !priority) && <ScoreBar label="착용감" value={product.lightweight_score} color="#34d399" />}
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <StarRating rating={product.star_rating || 0} />
                <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-primary)' }}>{product.star_rating?.toFixed(1) || '0.0'}</span>
              </div>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>({(product.review_count || 0).toLocaleString()})</span>
            </div>
            <span style={{ fontSize: '1rem', fontWeight: 700, background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              {product.price?.toLocaleString()}원
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
            <IngredientBadge level={product.ingredient_level} />
            <div style={{ fontSize: '0.65rem', color: compatScore >= 0.7 ? '#4ade80' : compatScore >= 0.5 ? '#fbbf24' : '#f87171' }}>
              {skinType === 'oily' ? '지성' : skinType === 'dry' ? '건성' : skinType === 'sensitive' ? '민감성' : '복합성'} 호환 {Math.round(compatScore * 100)}%
            </div>
          </div>
        </div>
        {product.suitable_shades && product.suitable_shades.length > 0 && recommendedShadeStr && (
          <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px dashed rgba(255,255,255,0.1)' }}>
            <span style={{ fontSize: '0.7rem', color: '#a5b4fc', fontWeight: 600 }}>💡 구매 권장 옵션: </span>
            <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>
              {product.shade_options?.[recommendedShadeStr] || `${recommendedShadeStr}호`}
            </span>
            {userShade === 'any' && <span style={{ fontSize: '0.65rem', color: 'gray', marginLeft: '6px' }}>(가장 무난한 톤)</span>}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── 컴포넌트: 퀴즈 ─────────────────────────────────────────────────────────
interface QuizState {
  skinType: SkinType | null;
  concerns: SkinConcern[];
  priority: PriorityAttr | null;
  shade: ShadeChoice | null;
}

function SkinQuiz({ onComplete }: { onComplete: (state: QuizState) => void }) {
  const [step, setStep] = useState(0);
  const [state, setState] = useState<QuizState>({ skinType: null, concerns: [], priority: null, shade: null });

  const steps = [
    { title: '피부 타입이 어떻게 되세요?', subtitle: '가장 가까운 항목을 선택해주세요' },
    { title: '고민이 있는 피부 문제가 있나요?', subtitle: '복수 선택 가능 · 없으면 다음으로' },
    { title: '어떤 부분이 가장 중요하세요?', subtitle: '한 가지를 선택해주세요' },
    { title: '주로 사용하는 호수가 있나요?', subtitle: '잘 모르면 "잘 모르겠어요" 선택' },
  ];
  const canNext = [!!state.skinType, true, !!state.priority, !!state.shade];

  const btnBase = (selected: boolean): React.CSSProperties => ({
    borderRadius: '16px', cursor: 'pointer', textAlign: 'left', transition: 'all 0.2s',
    border: `2px solid ${selected ? 'rgba(99,102,241,0.8)' : 'var(--glass-border)'}`,
    background: selected ? 'rgba(99,102,241,0.15)' : 'var(--glass-bg)',
    backdropFilter: 'blur(20px)',
  });

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto', padding: '0 20px' }}>
      {/* 프로그레스 */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: '32px' }}>
        {steps.map((_, i) => (
          <div key={i} style={{ flex: 1, height: '4px', borderRadius: '2px', background: i <= step ? 'linear-gradient(90deg,#6366f1,#8b5cf6)' : 'rgba(255,255,255,0.1)', transition: 'background 0.3s' }} />
        ))}
      </div>
      <h2 style={{ fontSize: '1.4rem', fontWeight: 800, marginBottom: '8px' }}>{steps[step].title}</h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: '28px', fontSize: '0.9rem' }}>{steps[step].subtitle}</p>

      {/* Step 0 */}
      {step === 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          {SKIN_TYPE_OPTIONS.map(opt => (
            <button key={opt.key} onClick={() => setState(s => ({ ...s, skinType: opt.key }))}
              style={{ ...btnBase(state.skinType === opt.key), padding: '16px' }}>
              <div style={{ fontSize: '1.6rem', marginBottom: '8px' }}>{opt.icon}</div>
              <div style={{ fontWeight: 700, color: state.skinType === opt.key ? '#a5b4fc' : 'var(--text-primary)', marginBottom: '4px' }}>{opt.label}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{opt.desc}</div>
            </button>
          ))}
        </div>
      )}

      {/* Step 1 */}
      {step === 1 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
          {CONCERN_OPTIONS.map(opt => {
            const sel = state.concerns.includes(opt.key);
            return (
              <button key={opt.key}
                onClick={() => setState(s => ({ ...s, concerns: sel ? s.concerns.filter(c => c !== opt.key) : [...s.concerns, opt.key] }))}
                style={{ ...btnBase(sel), padding: '10px 18px', borderRadius: '24px', fontSize: '0.9rem', fontWeight: sel ? 600 : 400, color: sel ? '#a5b4fc' : 'var(--text-secondary)' }}>
                {opt.icon} {opt.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Step 2 */}
      {step === 2 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {PRIORITY_OPTIONS.map(opt => (
            <button key={opt.key} onClick={() => setState(s => ({ ...s, priority: opt.key }))}
              style={{ ...btnBase(state.priority === opt.key), padding: '16px 20px', display: 'flex', alignItems: 'center', gap: '14px' }}>
              <span style={{ fontSize: '1.8rem' }}>{opt.icon}</span>
              <div>
                <div style={{ fontWeight: 700, color: state.priority === opt.key ? '#a5b4fc' : 'var(--text-primary)', marginBottom: '3px' }}>{opt.label}</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{opt.desc}</div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Step 3 */}
      {step === 3 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '12px' }}>
          {SHADE_OPTIONS.map(opt => (
            <button key={opt.key} onClick={() => setState(s => ({ ...s, shade: opt.key }))}
              style={{ ...btnBase(state.shade === opt.key), padding: '16px 20px', display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '42px', height: '42px', borderRadius: '50%', flexShrink: 0,
                background: opt.color === 'transparent' ? 'rgba(255,255,255,0.05)' : opt.color,
                border: opt.color === 'transparent' ? '1px dashed rgba(255,255,255,0.2)' : '2px solid rgba(0,0,0,0.1)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem'
              }}>
                {opt.color === 'transparent' && '🤷‍♂️'}
              </div>
              <div>
                <div style={{ fontWeight: 800, fontSize: '1.05rem', color: state.shade === opt.key ? '#a5b4fc' : 'var(--text-primary)', marginBottom: '4px' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                  {opt.desc}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* 버튼 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '32px' }}>
        {step > 0
          ? <button onClick={() => setStep(s => s - 1)} className="filter-btn">← 이전</button>
          : <div />
        }
        <button
          onClick={() => { if (step === 3) onComplete(state); else setStep(s => s + 1); }}
          disabled={!canNext[step]}
          style={{
            padding: '12px 28px', borderRadius: '14px', fontWeight: 700, fontSize: '0.95rem',
            background: canNext[step] ? 'linear-gradient(135deg,#6366f1,#8b5cf6)' : 'rgba(255,255,255,0.08)',
            color: canNext[step] ? '#fff' : 'var(--text-muted)',
            border: 'none', cursor: canNext[step] ? 'pointer' : 'not-allowed', transition: 'all 0.2s',
          }}>
          {step === 3 ? '✨ 추천 받기' : '다음 →'}
        </button>
      </div>
    </div>
  );
}

// ─── 컴포넌트: 모달 ─────────────────────────────────────────────────────────
function ProductModal({ product, skinType, onClose }: { product: Product; skinType: SkinType; onClose: () => void }) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loadingReviews, setLoadingReviews] = useState(true);

  useEffect(() => {
    supabase.from('reviews').select('*').eq('product_id', product.id)
      .order('is_best', { ascending: false }).order('rating', { ascending: false }).limit(15)
      .then(({ data }) => { setReviews(data || []); setLoadingReviews(false); });
  }, [product.id]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div style={{ padding: '24px 28px', borderBottom: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <p style={{ fontSize: '0.72rem', color: '#a5b4fc', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{product.brand}</p>
                <IngredientBadge level={product.ingredient_level} />
              </div>
              <h2 style={{ fontSize: '1.15rem', fontWeight: 800, lineHeight: 1.3, marginBottom: '10px' }}>{product.name}</h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <StarRating rating={product.star_rating || 0} />
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>리뷰 {product.review_count?.toLocaleString()}개</span>
                <span style={{ fontSize: '1.05rem', fontWeight: 800, background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                  {product.price?.toLocaleString()}원
                </span>
              </div>
            </div>
            <button onClick={onClose} style={{ width: '34px', height: '34px', borderRadius: '10px', border: '1px solid var(--border-color)', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', flexShrink: 0, marginLeft: '16px', fontSize: '1rem' }}>✕</button>
          </div>
        </div>

        <div style={{ padding: '20px 28px 28px', overflowY: 'auto', maxHeight: 'calc(90vh - 140px)' }}>
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '12px' }}>🤖 AI 분析 점수</h3>
            <ScoreBar label="커버력" value={product.coverage_score} color="#a78bfa" />
            <ScoreBar label="지속력" value={product.longevity_score} color="#60a5fa" />
            <ScoreBar label="착용감" value={product.lightweight_score} color="#34d399" />
          </div>

          <div style={{ marginBottom: '20px', padding: '14px', borderRadius: '12px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '12px' }}>🧬 피부 호환성</h3>
            {([['oily', '지성'], ['dry', '건성'], ['sensitive', '민감성'], ['combination', '복합성']] as [SkinType, string][]).map(([type, label]) => (
              <ScoreBar key={type} label={label}
                value={((product[SKIN_TYPE_COMPAT_COL[type]] as number | null) ?? 0.5) * 5}
                color={type === skinType ? '#f59e0b' : '#6b7280'} />
            ))}
          </div>

          {product.suitable_concerns && product.suitable_concerns.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '10px' }}>💊 적합 피부고민</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {product.suitable_concerns.map(c => <span key={c} className="skin-tag">{CONCERN_LABEL[c as SkinConcern] ?? c}</span>)}
              </div>
            </div>
          )}

          {product.suitable_shades && product.suitable_shades.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '10px' }}>🎨 구매 가능 옵션 (AI 추천 호수)</h3>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {product.suitable_shades.map(s => (
                  <span key={s} style={{ padding: '6px 14px', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 600, background: 'rgba(99,102,241,0.15)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.3)' }}>
                    {product.shade_options?.[s] || `${s}호`}
                  </span>
                ))}
              </div>
            </div>
          )}

          {product.product_url && (
            <a href={product.product_url} target="_blank" rel="noopener noreferrer"
              style={{ display: 'block', textAlign: 'center', padding: '10px', borderRadius: '12px', marginBottom: '20px', background: 'rgba(99,102,241,0.12)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.3)', fontSize: '0.85rem', fontWeight: 600, textDecoration: 'none' }}>
              🛍️ 올리브영에서 보기 →
            </a>
          )}

          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '12px' }}>💬 실제 구매 리뷰</h3>
          {loadingReviews
            ? <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>로딩 중...</div>
            : reviews.length === 0
              ? <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>수집된 리뷰가 없습니다.</div>
              : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {reviews.map(r => (
                    <div key={r.id} className="review-card">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <StarRating rating={r.rating} />
                          {r.skin_type && <span className="skin-tag">{r.skin_type}</span>}
                          {r.is_best && <span style={{ fontSize: '0.65rem', color: '#fbbf24', fontWeight: 700 }}>👑 BEST</span>}
                        </div>
                        <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                          {r.created_at ? new Date(r.created_at).toLocaleDateString('ko-KR') : ''}
                        </span>
                      </div>
                      <p style={{ fontSize: '0.84rem', lineHeight: 1.6, color: 'var(--text-secondary)' }}>{r.content}</p>
                      {r.option_name && <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '6px' }}>옵션: {r.option_name}</p>}
                    </div>
                  ))}
                </div>
              )
          }
        </div>
      </div>
    </div>
  );
}

// ─── 스켈레톤 ────────────────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div className="product-card">
      <div className="skeleton" style={{ aspectRatio: '1', width: '100%' }} />
      <div style={{ padding: '14px 16px 16px' }}>
        <div className="skeleton" style={{ width: '40%', height: '11px', marginBottom: '8px' }} />
        <div className="skeleton" style={{ width: '90%', height: '15px', marginBottom: '5px' }} />
        <div className="skeleton" style={{ width: '70%', height: '15px', marginBottom: '12px' }} />
        <div className="skeleton" style={{ width: '100%', height: '6px', marginBottom: '5px' }} />
        <div className="skeleton" style={{ width: '100%', height: '6px', marginBottom: '12px' }} />
        <div className="skeleton" style={{ width: '50%', height: '14px' }} />
      </div>
    </div>
  );
}

// ─── 메인 ────────────────────────────────────────────────────────────────────
export default function HomePage() {
  const [mode, setMode] = useState<'quiz' | 'result' | 'browse'>('quiz');
  const [quizResult, setQuizResult] = useState<QuizState | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [browseCategory, setBrowseCategory] = useState('all');
  const [browseSort, setBrowseSort] = useState<'review_count' | 'star_rating' | 'price_asc'>('review_count');
  const [browseSearch, setBrowseSearch] = useState('');

  const fetchRecommendations = useCallback(async (quiz: QuizState) => {
    setLoading(true);
    // Python 로직처럼 DB에서 넉넉하게 긁어온 다음, 프론트에서 가중치 점수로 정렬 (strict 필터링 제거)
    const { data } = await supabase.from('products').select('*').limit(200);
    if (data) {
      const scored = (data as Product[])
        .map(p => ({ ...p, _score: calcRecommendScore(p, quiz.skinType!, quiz.concerns, quiz.priority, quiz.shade) }))
        .sort((a: any, b: any) => b._score - a._score)
        .slice(0, 12);
      setProducts(scored);
    }
    setLoading(false);
  }, []);

  const fetchBrowse = useCallback(async () => {
    setLoading(true);
    let query = supabase.from('products').select('*');
    if (browseCategory !== 'all') query = query.ilike('category', `%${browseCategory}%`);
    if (browseSearch.trim()) query = query.or(`name.ilike.%${browseSearch}%,brand.ilike.%${browseSearch}%`);
    switch (browseSort) {
      case 'review_count': query = query.order('review_count', { ascending: false }); break;
      case 'star_rating': query = query.order('star_rating', { ascending: false }); break;
      case 'price_asc': query = query.order('price', { ascending: true }); break;
    }
    const { data } = await query.limit(55);
    setProducts(data as Product[] || []);
    setLoading(false);
  }, [browseCategory, browseSort, browseSearch]);

  useEffect(() => { if (mode === 'browse') fetchBrowse(); }, [mode, fetchBrowse]);

  const handleQuizComplete = (state: QuizState) => {
    setQuizResult(state);
    setMode('result');
    fetchRecommendations(state);
  };

  const currentSkinType: SkinType = quizResult?.skinType ?? 'combination';

  return (
    <main>
      {/* Hero */}
      <section className="hero-gradient" style={{ padding: '52px 24px 36px', textAlign: 'center' }}>
        <div style={{ maxWidth: '760px', margin: '0 auto' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '5px 14px', borderRadius: '20px', marginBottom: '18px',
            background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)', fontSize: '0.78rem', color: '#a5b4fc',
          }}>
            ✨ AI 기반 맞춤 추천 · 올리브영 24,934개 실 리뷰 분석
          </div>
          <h1 style={{
            fontSize: 'clamp(1.8rem, 5vw, 3.2rem)', fontWeight: 900, lineHeight: 1.1, marginBottom: '14px',
            background: 'linear-gradient(135deg, #f0f0f5 0%, #a5b4fc 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            내 피부에 딱 맞는<br />남성 화장품 찾기
          </h1>
          <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '28px', lineHeight: 1.6 }}>
            피부타입과 고민을 입력하면 AI가 최적의 제품을 추천해드립니다.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }}>
            {[['quiz', '🎯 맞춤 추천'], ['browse', '📋 전체 보기']].map(([m, label]) => (
              <button key={m} onClick={() => setMode(m as 'quiz' | 'browse')}
                className={`filter-btn ${(mode === m || (mode === 'result' && m === 'quiz')) ? 'active' : ''}`}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* 퀴즈 */}
      {mode === 'quiz' && (
        <section style={{ padding: '40px 24px 80px' }}>
          <SkinQuiz onComplete={handleQuizComplete} />
        </section>
      )}

      {/* 추천 결과 */}
      {mode === 'result' && quizResult && (
        <section style={{ maxWidth: '1200px', margin: '0 auto', padding: '32px 24px 80px' }}>
          <div style={{ padding: '14px 20px', borderRadius: '14px', marginBottom: '24px', background: 'rgba(99,102,241,0.07)', border: '1px solid rgba(99,102,241,0.2)', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>추천 기준:</span>
            {quizResult.skinType && <span className="skin-tag">{SKIN_TYPE_OPTIONS.find(o => o.key === quizResult.skinType)?.label} 피부</span>}
            {quizResult.concerns.map(c => <span key={c} className="skin-tag">{CONCERN_OPTIONS.find(o => o.key === c)?.label}</span>)}
            {quizResult.priority && <span className="skin-tag">{PRIORITY_OPTIONS.find(o => o.key === quizResult.priority)?.label} 중시</span>}
            {quizResult.shade && quizResult.shade !== 'any' && <span className="skin-tag">{quizResult.shade}호</span>}
            <button onClick={() => setMode('quiz')} className="filter-btn" style={{ marginLeft: 'auto', fontSize: '0.78rem' }}>다시 선택</button>
          </div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 800, marginBottom: '4px' }}>🏅 맞춤 추천 결과</h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '22px' }}>
            {loading ? '분석 중...' : `총 ${products.length}개의 맞춤 추천 제품 (관련도 순)`}
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '20px' }}>
            {loading ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
              : products.map((p, i) => (
                <ProductCard key={p.id} product={p} skinType={currentSkinType}
                  priority={quizResult.priority} userShade={quizResult.shade} rank={i + 1} onClick={() => setSelectedProduct(p)} />
              ))}
          </div>
        </section>
      )}

      {/* 전체 보기 */}
      {mode === 'browse' && (
        <section style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px 24px 80px' }}>
          <div style={{ position: 'relative', marginBottom: '18px' }}>
            <input type="text" placeholder="브랜드 또는 제품명 검색..."
              value={browseSearch} onChange={e => setBrowseSearch(e.target.value)}
              style={{ width: '100%', padding: '12px 20px 12px 44px', borderRadius: '14px', border: '1px solid var(--glass-border)', background: 'var(--glass-bg)', backdropFilter: 'blur(20px)', color: 'var(--text-primary)', fontSize: '0.9rem', outline: 'none' }} />
            <span style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', opacity: 0.4 }}>🔍</span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: '10px', marginBottom: '22px' }}>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {[['all', '전체'], ['쿠션', '쿠션/파운데이션'], ['톤 로션', '톤 로션/BB']].map(([k, l]) => (
                <button key={k} className={`filter-btn ${browseCategory === k ? 'active' : ''}`} onClick={() => setBrowseCategory(k)}>{l}</button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {[['review_count', '리뷰 많은순'], ['star_rating', '평점 높은순'], ['price_asc', '가격 낮은순']].map(([k, l]) => (
                <button key={k} className={`filter-btn ${browseSort === k ? 'active' : ''}`} onClick={() => setBrowseSort(k as typeof browseSort)}>{l}</button>
              ))}
            </div>
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '18px' }}>
            {loading ? '로딩 중...' : `총 ${products.length}개 상품`}
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '20px' }}>
            {loading ? Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)
              : products.map((p, i) => (
                <ProductCard key={p.id} product={p} skinType="combination"
                  priority={null} userShade={null} rank={i + 1} onClick={() => setSelectedProduct(p)} />
              ))}
          </div>
        </section>
      )}

      <footer style={{ padding: '28px 24px', textAlign: 'center', borderTop: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
        <p>MEN&apos;S BEAUTY PICK — 올리브영 24,934개 리뷰 · Gemini AI 분석 기반 남성 화장품 추천 시스템</p>
        <p style={{ marginTop: '4px', opacity: 0.5 }}>교육 목적으로 제작 · 상업적 이용 불가</p>
      </footer>

      {selectedProduct && (
        <ProductModal product={selectedProduct} skinType={currentSkinType} onClose={() => setSelectedProduct(null)} />
      )}
    </main>
  );
}

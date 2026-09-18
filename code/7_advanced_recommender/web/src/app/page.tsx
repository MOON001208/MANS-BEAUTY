'use client';

import { useState, useEffect, useMemo } from 'react';
import { supabase, Product, Review, SkinType, SkinConcern, ShadeChoice, ApplicationMethod } from '@/lib/supabase';
import { bestShadeOption, getCompatScore, hasCurrentProfile, searchProducts, selectRecommendations, shadeLineup } from '@/lib/recommendation';
import { loadCatalog } from '@/lib/catalog';
import Image from 'next/image';

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

const SHADE_OPTIONS: { key: ShadeChoice; label: string; desc: string; color?: string }[] = [
  { key: '21', label: '21호 (밝은 톤)', desc: '"피부 하얗네?" 라는 말을 종종 듣는 편. 밝은 아이보리 계열', color: '#FADAC1' },
  { key: '23', label: '23호 (표준 톤)', desc: '평소 사용하는 제품의 23호와 비교해요', color: '#E8CBAE' },
  { key: '25', label: '25호 (어두운 톤)', desc: '가무잡잡하고 건강한 피부. 평소 야외 활동을 즐기는 편', color: '#D2AA85' },
  { key: 'any', label: '잘 몰라요', desc: '호수 가중치 없이 다른 조건으로 비교해요', color: 'transparent' },
];

const APPLICATION_OPTIONS: { key: ApplicationMethod; label: string; icon: string; desc: string }[] = [
  { key: 'hand', label: '손으로 간편하게', icon: '✋', desc: '도구 없이 손으로 빠르게 발라요 (톤로션/BB 추천)' },
  { key: 'tool', label: '도구로 꼼꼼하게', icon: '🖌️', desc: '퍼프나 브러시로 정교하게 발라요 (쿠션/파운데이션 추천)' },
  { key: 'any', label: '상관없어요', icon: '🤷‍♂️', desc: '발린다면 어떤 방법이든!' },
];

const CONCERN_LABEL: Record<SkinConcern, string> = {
  acne: '여드름', pore: '모공', redness: '홍조', spots: '잡티', wrinkle: '주름',
};

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
  const pct = value == null ? 0 : Math.max(0, Math.min(100, ((value - 1) / 4) * 100));
  return (
    <div style={{ marginBottom: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{label}</span>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color }}>{value?.toFixed(1) ?? '정보 부족'}</span>
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
    '성분 확인': { color: '#4ade80', bg: 'rgba(74,222,128,0.12)' },
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
function ProductCard({ product, skinType, userShade, onClick, rank }: {
  product: Product; skinType: SkinType; userShade: ShadeChoice | null;
  onClick: () => void; rank: number;
}) {
  const typeLabel: Record<string, string> = { cushion: '쿠션', liquid: '리퀴드', stick: '스틱', tone_lotion: '톤로션/BB', concealer: '컨실러' };
  const compatScore = getCompatScore(product, skinType);
  const rankColors = ['', 'linear-gradient(135deg,#ffd700,#ff8c00)', 'linear-gradient(135deg,#c0c0c0,#808080)', 'linear-gradient(135deg,#cd7f32,#8b4500)'];

  // Only display an exact known shade; never invent an adjacent or default shade.
  const recommendedShadeStr = userShade && userShade !== 'any' && product.suitable_shades?.includes(userShade) ? userShade : '';
  const lineup = shadeLineup(product);
  const lineupOption = product.suitable_shades?.length ? null : bestShadeOption(product, userShade);
  const lineupPlace = !lineupOption ? '' : lineupOption.position === 0 ? '가장 밝은 쪽' : lineupOption.position === 1 ? '가장 어두운 쪽' : '중간';

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
          ? <Image src={product.thumbnail_url} alt={product.name} width={400} height={400} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
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
            <ScoreBar label="커버력" value={hasCurrentProfile(product) ? product.coverage_score : null} color="#a78bfa" />
            <ScoreBar label="지속력" value={hasCurrentProfile(product) ? product.longevity_score : null} color="#60a5fa" />
            <ScoreBar label="착용감/가벼움" value={hasCurrentProfile(product) ? product.lightweight_score : null} color="#34d399" />
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <StarRating rating={product.star_rating || 0} />
                <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-primary)' }}>{product.star_rating?.toFixed(1) ?? '평점 정보 없음'}</span>
              </div>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>({(product.review_count || 0).toLocaleString()})</span>
            </div>
            <span style={{ fontSize: '1rem', fontWeight: 700, background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              {product.price == null ? '가격 정보 없음' : product.price.toLocaleString() + '원'}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
            <IngredientBadge level={hasCurrentProfile(product) ? product.ingredient_level : null} />
            <div style={{ fontSize: '0.65rem', color: compatScore !== null && compatScore >= 0.7 ? '#4ade80' : compatScore !== null && compatScore >= 0.5 ? '#fbbf24' : '#f87171' }}>
              {skinType === 'oily' ? '지성' : skinType === 'dry' ? '건성' : skinType === 'sensitive' ? '민감성' : '복합성'} 리뷰 {compatScore == null ? '정보 부족' : `${(1 + compatScore * 4).toFixed(1)}/5`}
            </div>
          </div>
        </div>
        {recommendedShadeStr && (
          <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px dashed rgba(255,255,255,0.1)' }}>
            <span style={{ fontSize: '0.7rem', color: '#a5b4fc', fontWeight: 600 }}>💡 선택 호수와 일치하는 옵션: </span>
            <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>
              {product.shade_options?.[recommendedShadeStr] || `${recommendedShadeStr}호`}
            </span>
          </div>
        )}
        {lineupOption && lineup && (
          <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px dashed rgba(255,255,255,0.1)' }}>
            <span style={{ fontSize: '0.7rem', color: '#a5b4fc', fontWeight: 600 }}>🎨 이 제품에서 고를 옵션: </span>
            <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>{lineupOption.label}</span>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginLeft: '6px' }}>
              ({lineup.options.length}종 중 {lineupPlace})
            </span>
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
  coveragePref: number;
  longevityPref: number;
  lightweightPref: number;
  shade: ShadeChoice | null;
  applicationMethod: ApplicationMethod | null;
}

function SkinQuiz({ onComplete }: { onComplete: (state: QuizState) => void }) {
  const [step, setStep] = useState(0);
  const [state, setState] = useState<QuizState>({ skinType: null, concerns: [], coveragePref: 3, longevityPref: 3, lightweightPref: 3, shade: null, applicationMethod: null });

  const steps = [
    { title: '피부 타입이 어떻게 되세요?', subtitle: '가장 가까운 항목을 선택해주세요' },
    { title: '고민이 있는 피부 문제가 있나요?', subtitle: '복수 선택 가능 · 없으면 다음으로' },
    { title: '각 기능이 얼마나 중요한가요?', subtitle: '각 1~5점 (1: 신경안씀, 5: 매우 중요)' },
    { title: '주로 사용하는 호수가 있나요?', subtitle: '잘 모르면 "잘 모르겠어요" 선택' },
    { title: '어떤 방식으로 바르고 싶으세요?', subtitle: '선호하는 사용 방식을 선택해주세요' },
  ];
  const canNext = [!!state.skinType, true, true, !!state.shade, !!state.applicationMethod];

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

      {/* Step 2 (Sliders) */}
      {step === 2 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', padding: '10px 0' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>커버력 중요도</span>
              <span style={{ color: '#a5b4fc', fontWeight: 700 }}>{state.coveragePref}점</span>
            </div>
            <input type="range" min="1" max="5" step="1"
              value={state.coveragePref} onChange={e => setState(s => ({ ...s, coveragePref: parseInt(e.target.value) }))}
              style={{ width: '100%', accentColor: '#a78bfa', cursor: 'pointer' }} />
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>지속력 중요도</span>
              <span style={{ color: '#60a5fa', fontWeight: 700 }}>{state.longevityPref}점</span>
            </div>
            <input type="range" min="1" max="5" step="1"
              value={state.longevityPref} onChange={e => setState(s => ({ ...s, longevityPref: parseInt(e.target.value) }))}
              style={{ width: '100%', accentColor: '#60a5fa', cursor: 'pointer' }} />
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>착용감/가벼움 중요도</span>
              <span style={{ color: '#34d399', fontWeight: 700 }}>{state.lightweightPref}점</span>
            </div>
            <input type="range" min="1" max="5" step="1"
              value={state.lightweightPref} onChange={e => setState(s => ({ ...s, lightweightPref: parseInt(e.target.value) }))}
              style={{ width: '100%', accentColor: '#34d399', cursor: 'pointer' }} />
          </div>
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

      {/* Step 4 */}
      {step === 4 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '12px' }}>
          {APPLICATION_OPTIONS.map(opt => (
            <button key={opt.key} onClick={() => setState(s => ({ ...s, applicationMethod: opt.key }))}
              style={{ ...btnBase(state.applicationMethod === opt.key), padding: '16px 20px', display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '42px', height: '42px', borderRadius: '50%', flexShrink: 0,
                background: state.applicationMethod === opt.key ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.4rem',
              }}>
                {opt.icon}
              </div>
              <div>
                <div style={{ fontWeight: 800, fontSize: '1.05rem', color: state.applicationMethod === opt.key ? '#a5b4fc' : 'var(--text-primary)', marginBottom: '4px' }}>
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
          onClick={() => { if (step === 4) onComplete(state); else setStep(s => s + 1); }}
          disabled={!canNext[step]}
          style={{
            padding: '12px 28px', borderRadius: '14px', fontWeight: 700, fontSize: '0.95rem',
            background: canNext[step] ? 'linear-gradient(135deg,#6366f1,#8b5cf6)' : 'rgba(255,255,255,0.08)',
            color: canNext[step] ? '#fff' : 'var(--text-muted)',
            border: 'none', cursor: canNext[step] ? 'pointer' : 'not-allowed', transition: 'all 0.2s',
          }}>
          {step === 4 ? '✨ 추천 받기' : '다음 →'}
        </button>
      </div>
    </div>
  );
}

// ─── 컴포넌트: 모달 ─────────────────────────────────────────────────────────
function ProductModal({ product, skinType, userShade, onClose }: { product: Product; skinType: SkinType; userShade: ShadeChoice | null; onClose: () => void }) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loadingReviews, setLoadingReviews] = useState(true);
  const [reviewError, setReviewError] = useState('');
  const [evidenceById, setEvidenceById] = useState<Map<string, Review>>(new Map());
  const [evidenceError, setEvidenceError] = useState('');
  const [openEvidence, setOpenEvidence] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    supabase.from('reviews').select('id,product_id,rating,content,skin_type,skin_tone,skin_trouble,option_name,created_at,is_best')
      .eq('product_id', product.id).order('created_at', { ascending: false }).limit(30).abortSignal(controller.signal)
      .then(({ data, error }) => {
        if (controller.signal.aborted) return;
        setReviews((data || []) as Review[]);
        setReviewError(error ? '리뷰를 불러오지 못했습니다.' : '');
        setLoadingReviews(false);
      });
    return () => controller.abort();
  }, [product.id]);

  // Reviews that produced each score and concern tag, so a claim can be traced to its source.
  const meta = hasCurrentProfile(product) ? product.profile_metadata : null;
  const evidenceIds = useMemo(() => [...new Set([
    ...Object.values(meta?.evidence_review_ids ?? {}).flat(),
    ...Object.values(meta?.concern_evidence_ids ?? {}).flat(),
  ])], [meta]);

  useEffect(() => {
    if (!evidenceIds.length) return;
    const controller = new AbortController();
    supabase.from('reviews').select('id,product_id,rating,content,skin_type,skin_tone,skin_trouble,option_name,created_at,is_best')
      .in('id', evidenceIds).abortSignal(controller.signal)
      .then(({ data, error }) => {
        if (controller.signal.aborted) return;
        setEvidenceById(new Map(((data || []) as Review[]).map(r => [r.id, r])));
        // Silence would be indistinguishable from a product that simply has no evidence.
        setEvidenceError(error ? '근거 리뷰를 불러오지 못했습니다.' : '');
      });
    return () => controller.abort();
  }, [evidenceIds]);

  const modalLineup = shadeLineup(product);
  const modalPick = bestShadeOption(product, userShade);

  const renderEvidence = (key: string, ids?: string[]) => {
    const found = (ids ?? []).map(id => evidenceById.get(id)).filter((r): r is Review => !!r);
    if (!found.length) return null;
    const open = openEvidence === key;
    return (
      <div style={{ marginBottom: '10px' }}>
        <button onClick={() => setOpenEvidence(open ? null : key)} aria-expanded={open}
          style={{ background: 'none', border: 'none', padding: '2px 0', color: '#a5b4fc', fontSize: '0.7rem', cursor: 'pointer' }}>
          {open ? '근거 리뷰 닫기 ▲' : `근거 리뷰 ${found.length}건 보기 ▼`}
        </button>
        {open && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
            {found.map(r => (
              <div key={r.id} style={{ padding: '8px 10px', borderRadius: '8px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <StarRating rating={r.rating} />
                  {r.skin_type && <span className="skin-tag">{r.skin_type}</span>}
                </div>
                <p style={{ fontSize: '0.78rem', lineHeight: 1.5, color: 'var(--text-secondary)' }}>{r.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div style={{ padding: '24px 28px', borderBottom: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <p style={{ fontSize: '0.72rem', color: '#a5b4fc', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{product.brand}</p>
                <IngredientBadge level={hasCurrentProfile(product) ? product.ingredient_level : null} />
              </div>
              <h2 style={{ fontSize: '1.15rem', fontWeight: 800, lineHeight: 1.3, marginBottom: '10px' }}>{product.name}</h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <StarRating rating={product.star_rating || 0} />
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>리뷰 {product.review_count?.toLocaleString()}개</span>
                <span style={{ fontSize: '1.05rem', fontWeight: 800, background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                  {product.price == null ? '가격 정보 없음' : product.price.toLocaleString() + '원'}
                </span>
              </div>
            </div>
            <button onClick={onClose} style={{ width: '34px', height: '34px', borderRadius: '10px', border: '1px solid var(--border-color)', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', flexShrink: 0, marginLeft: '16px', fontSize: '1rem' }}>✕</button>
          </div>
        </div>

        <div style={{ padding: '20px 28px 28px', overflowY: 'auto', maxHeight: 'calc(90vh - 140px)' }}>
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '12px' }}>📊 리뷰 표현 기반 점수</h3>
            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 12 }}>분석 리뷰 {product.profile_metadata?.analyzed_count?.toLocaleString() ?? 0}개 · 점수는 수집된 리뷰의 표현을 요약합니다. 근거가 부족한 항목은 정보 부족으로 표시합니다.</p>
            {evidenceError && <p role="alert" style={{ fontSize: '0.72rem', color: '#f87171', marginBottom: 8 }}>{evidenceError}</p>}
            {([['coverage', '커버력', '#a78bfa', product.coverage_score], ['longevity', '지속력', '#60a5fa', product.longevity_score], ['lightweight', '착용감', '#34d399', product.lightweight_score]] as [string, string, string, number | null][]).map(([key, label, color, value]) => (
              <div key={key}>
                <ScoreBar label={label} value={hasCurrentProfile(product) ? value : null} color={color} />
                {renderEvidence(key, meta?.evidence_review_ids?.[key])}
              </div>
            ))}
          </div>

          <div style={{ marginBottom: '20px', padding: '14px', borderRadius: '12px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '12px' }}>🧬 같은 피부타입 구매자의 평점 지표</h3>
            {([['oily', '지성'], ['dry', '건성'], ['sensitive', '민감성'], ['combination', '복합성']] as [SkinType, string][]).map(([type, label]) => (
              <ScoreBar key={type} label={label}
                value={getCompatScore(product, type) == null ? null : 1 + getCompatScore(product, type)! * 4}
                color={type === skinType ? '#f59e0b' : '#6b7280'} />
            ))}
          </div>

          {product.suitable_concerns && product.suitable_concerns.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '10px' }}>리뷰에서 긍정적으로 언급된 고민</h3>
              {product.suitable_concerns.map(c => (
                <div key={c} style={{ marginBottom: '6px' }}>
                  <div style={{ marginBottom: '4px' }}><span className="skin-tag">{CONCERN_LABEL[c as SkinConcern] ?? c}</span></div>
                  {renderEvidence('concern:' + c, meta?.concern_evidence_ids?.[c])}
                </div>
              ))}
            </div>
          )}

          {product.suitable_shades && product.suitable_shades.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '10px' }}>🎨 확인된 호수 (재고는 판매처에서 확인)</h3>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {product.suitable_shades.map(s => (
                  <span key={s} style={{ padding: '6px 14px', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 600, background: 'rgba(99,102,241,0.15)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.3)' }}>
                    {product.shade_options?.[s] || `${s}호`}
                  </span>
                ))}
              </div>
            </div>
          )}

          {!product.suitable_shades?.length && modalLineup && (
            <div style={{ marginBottom: '16px' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '6px' }}>🎨 이 제품의 호수 (밝은 순)</h3>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '10px' }}>
                브랜드가 표기한 순서입니다. 21/23/25 기준과 직접 대응하지는 않습니다. 재고는 판매처에서 확인하세요.
              </p>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {modalLineup.options.map(option => {
                  const picked = option.name === modalPick?.name;
                  return (
                    <span key={option.name} style={{
                      padding: '6px 14px', borderRadius: '8px', fontSize: '0.82rem', fontWeight: picked ? 700 : 500,
                      background: picked ? 'rgba(99,102,241,0.18)' : 'rgba(255,255,255,0.04)',
                      color: picked ? '#a5b4fc' : 'var(--text-secondary)',
                      border: `1px solid ${picked ? 'rgba(99,102,241,0.4)' : 'var(--border-color)'}`,
                    }}>
                      {option.label}{picked && ' ← 선택한 톤에 가장 가까움'}
                    </span>
                  );
                })}
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
          {reviewError && <p role="alert">{reviewError}</p>}
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
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [retry, setRetry] = useState(0);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [browseCategory, setBrowseCategory] = useState('all');
  const [browseSort, setBrowseSort] = useState<'review_count' | 'star_rating' | 'price_asc'>('review_count');
  const [browseSearch, setBrowseSearch] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    loadCatalog(controller.signal).then(data => {
      if (controller.signal.aborted) return;
      setProducts(data);
      setLoadError('');
      setLoading(false);
    }).catch(() => {
      if (controller.signal.aborted) return;
      setProducts([]);
      setLoadError('상품을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.');
      setLoading(false);
    });
    return () => controller.abort();
  }, [retry]);

  const displayProducts = useMemo(() => {
    if (mode === 'result' && quizResult?.skinType) {
      return selectRecommendations(products, { ...quizResult, skinType: quizResult.skinType });
    }
    const filtered = searchProducts(products, browseSearch).filter(p => browseCategory === 'all' || p.category?.includes(browseCategory));
    return filtered.sort((a, b) => browseSort === 'price_asc' ? (a.price ?? Infinity) - (b.price ?? Infinity) : browseSort === 'star_rating' ? (b.star_rating ?? 0) - (a.star_rating ?? 0) : (b.review_count ?? 0) - (a.review_count ?? 0));
  }, [products, mode, quizResult, browseSearch, browseCategory, browseSort]);

  const handleQuizComplete = (state: QuizState) => {
    setQuizResult(state);
    setMode('result');
  };
  const storedReviewCount = products.reduce((n, p) => n + (p.profile_metadata?.analyzed_count ?? 0), 0);
  const latestUpdate = products.map(p => p.last_updated_at).filter(Boolean).sort().at(-1);

  const currentSkinType: SkinType = quizResult?.skinType ?? 'combination';

  return (
    <main>
      {loadError && <div role="alert" style={{ padding: 24, textAlign: 'center' }}>
        {loadError} <button className="filter-btn" onClick={() => { setLoading(true); setRetry(n => n + 1); }}>다시 시도</button>
      </div>}
      {!loading && !loadError && mode !== 'quiz' && displayProducts.length === 0 && <p role="status" style={{ padding: 24, textAlign: 'center' }}>조건에 맞는 분석 자료가 아직 충분하지 않습니다. 전체 보기에서 상품을 확인해 주세요.</p>}
      {/* Hero */}
      <section className="hero-gradient" style={{ padding: '52px 24px 36px', textAlign: 'center' }}>
        <div style={{ maxWidth: '760px', margin: '0 auto' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '5px 14px', borderRadius: '20px', marginBottom: '18px',
            background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)', fontSize: '0.78rem', color: '#a5b4fc',
          }}>
            ✨ 리뷰 기반 맞춤 추천 · 분석 리뷰 {storedReviewCount.toLocaleString()}개
          </div>
          <h1 style={{
            fontSize: 'clamp(1.8rem, 5vw, 3.2rem)', fontWeight: 900, lineHeight: 1.1, marginBottom: '14px',
            background: 'linear-gradient(135deg, #f0f0f5 0%, #a5b4fc 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            내 피부에 딱 맞는<br />남성 화장품 찾기
          </h1>
          <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '28px', lineHeight: 1.6 }}>
            피부타입과 고민, 중요하게 생각하는 기능을 기준으로 제품을 비교해보세요.
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
            <span className="skin-tag">커버{quizResult.coveragePref} 유지{quizResult.longevityPref} 착용{quizResult.lightweightPref}</span>
            {quizResult.shade && quizResult.shade !== 'any' && <span className="skin-tag">{quizResult.shade}호</span>}
            {quizResult.applicationMethod && quizResult.applicationMethod !== 'any' && <span className="skin-tag">{APPLICATION_OPTIONS.find(o => o.key === quizResult.applicationMethod)?.label}</span>}
            <button onClick={() => setMode('quiz')} className="filter-btn" style={{ marginLeft: 'auto', fontSize: '0.78rem' }}>다시 선택</button>
          </div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 800, marginBottom: '4px' }}>🏅 맞춤 추천 결과</h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '22px' }}>
            {loading ? '분석 중...' : `총 ${displayProducts.length}개의 맞춤 추천 제품 (관련도 순)`}
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '20px' }}>
            {loading ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
              : displayProducts.map((p, i) => (
                <ProductCard key={p.id} product={p} skinType={currentSkinType}
                  userShade={quizResult.shade} rank={i + 1} onClick={() => setSelectedProduct(p)} />
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
            {loading ? '로딩 중...' : `총 ${displayProducts.length}개 상품`}
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '20px' }}>
            {loading ? Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)
              : displayProducts.map((p, i) => (
                <ProductCard key={p.id} product={p} skinType="combination"
                  userShade={null} rank={i + 1} onClick={() => setSelectedProduct(p)} />
              ))}
          </div>
        </section>
      )}

      <footer style={{ padding: '28px 24px', textAlign: 'center', borderTop: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
        <p>MEN&apos;S BEAUTY PICK — 분석 리뷰 {storedReviewCount.toLocaleString()}개 · 근거를 확인하는 남성 화장품 추천</p>
        <p>마지막 상품 갱신: {latestUpdate ? new Date(latestUpdate).toLocaleDateString('ko-KR') : '확인 중'}</p>
        <p style={{ marginTop: '4px', opacity: 0.5 }}>교육 목적으로 제작 · 상업적 이용 불가</p>
      </footer>

      {selectedProduct && (
        <ProductModal key={selectedProduct.id} product={selectedProduct} skinType={currentSkinType}
          userShade={quizResult?.shade ?? null} onClose={() => setSelectedProduct(null)} />
      )}
    </main>
  );
}

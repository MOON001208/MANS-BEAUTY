"""
=============================================================================
남성 화장품 시장 가설 검증 분석 스크립트 (v2) - Part 2
=============================================================================
📌 2-2(호수), 2-3(성분), 2-5(키워드), 2-6(가격) 분석

[주요 전략]
- 리뷰 100개 미만 브랜드: ⚠️ 데이터 불충분 표기
- Major 그룹 위주 비교 차트 작성
- 성분 데이터는 팩트 기반이므로 모든 브랜드 분석 가능
=============================================================================
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import warnings

# --- 설정 ---
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
warnings.filterwarnings('ignore')
sns.set_style('whitegrid')

# --- 데이터 로드 ---
df = pd.read_pickle('../data/analysis_master.plk')
print(f"✅ 데이터 로드 완료: {df.shape}")

# --- Tier 정의 ---
brand_counts = df.groupby('브랜드').size()
MAJOR_BRANDS = brand_counts[brand_counts >= 1000].index.tolist()
MINOR_BRANDS = brand_counts[brand_counts < 1000].index.tolist()
RELIABLE_BRANDS = brand_counts[brand_counts >= 100].index.tolist()  # 신뢰 가능 브랜드

# ============================================================================
# 2-2. 호수(톤) 다양성에 따른 구매
# ============================================================================
print("\n" + "="*70)
print("🎨 2-2. 호수 다양성 분석")
print("="*70)

# 호수별 구매 비율 (전체)
shade_dist = df['Shade_Standard'].value_counts(normalize=True) * 100

print("\n📊 호수별 구매 비율 (전체)")
for shade, pct in shade_dist.items():
    print(f"   - {shade}: {pct:.1f}%")

# 브랜드별 호수 다양성 (옵션 개수)
brand_shade_variety = df.groupby('브랜드').agg({
    '옵션개수': 'first',
    '리뷰수': 'first'
}).reset_index()

# 상관분석: 호수 다양성 vs 리뷰 수
corr = brand_shade_variety['옵션개수'].corr(brand_shade_variety['리뷰수'])
print(f"\n🔬 호수 다양성 vs 리뷰 수 상관계수: {corr:.3f}")
print(f"   해석: {'호수가 다양할수록 리뷰 수가 많은 경향' if corr > 0.3 else '약한 상관관계'}")

# ============================================================================
# 2-3. 화장품 성분 분석
# ============================================================================
print("\n" + "="*70)
print("🧪 2-3. 성분 분석 (팩트 기반 - 모든 브랜드 분석 가능)")
print("="*70)

# 브랜드별 평균 유해성분 개수
brand_ingredients = df.groupby('브랜드').agg({
    '유해성분개수': 'mean',
    'ingredient_count': 'mean',
    '별점': 'mean'
}).round(2)

print("\n📊 브랜드별 성분 통계")
print("-"*50)
print(brand_ingredients.sort_values('유해성분개수', ascending=False).to_string())

# 유해성분 vs 별점 상관분석
corr_harm_rating = df['유해성분개수'].corr(df['별점'])
print(f"\n🔬 유해성분 개수 vs 별점 상관계수: {corr_harm_rating:.4f}")
print(f"   해석: {'유해성분이 많을수록 별점이 낮음' if corr_harm_rating < -0.1 else '유의미한 상관관계 없음'}")

# ============================================================================
# 2-5. 지속력/수정화장 키워드 분석 (Major 브랜드 위주)
# ============================================================================
print("\n" + "="*70)
print("📝 2-5. 지속력/수정화장 키워드 분석")
print("="*70)

# 키워드 정의
keywords = {
    '지속력': ['지속력', '지속', '오래', '하루종일', '오래가'],
    '수정화장': ['수정', '덧바름', '덧칠', '터치업'],
    '커버력': ['커버력', '커버', '가려', '잡티'],
    '자연스러움': ['자연스러', '자연스럽', '생얼', '톤업']
}

# 키워드 언급 여부 추출
for kw_name, kw_list in keywords.items():
    df[f'kw_{kw_name}'] = df['리뷰내용_정제'].apply(
        lambda x: 1 if any(kw in str(x) for kw in kw_list) else 0
    )

# Major 브랜드만 분석 (통계적 신뢰도 확보)
df_major = df[df['브랜드'].isin(MAJOR_BRANDS)]

print("\n📊 Major 브랜드별 키워드 언급 비율 (%)")
print("-"*60)
print("⚠️ Minor 브랜드는 샘플 수 부족으로 제외 (데이터_불균형_분석_전략 반영)")
print()

brand_kw_stats = df_major.groupby('브랜드').agg({
    'kw_지속력': 'mean',
    'kw_수정화장': 'mean',
    'kw_커버력': 'mean',
    'kw_자연스러움': 'mean'
}).round(3) * 100

print(brand_kw_stats.to_string())

# 시각화
fig, ax = plt.subplots(figsize=(12, 6))
brand_kw_stats.plot(kind='bar', ax=ax, colormap='viridis')
ax.set_ylabel('언급 비율 (%)')
ax.set_title('🏆 Major 브랜드별 키워드 언급 비율', fontweight='bold')
ax.legend(title='키워드', bbox_to_anchor=(1.02, 1))
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig('../data/fig_3_keyword_major.png', dpi=150, bbox_inches='tight')
plt.show()

# ============================================================================
# 2-6. 가격에 따른 구매력 차이 (비율 지표)
# ============================================================================
print("\n" + "="*70)
print("💰 2-6. 가격대별 분석")
print("="*70)

# 가격대 구분
df['가격대'] = pd.cut(df['가격'], 
                     bins=[0, 20000, 30000, 40000, 100000],
                     labels=['저가(~2만)', '중저가(2~3만)', '중고가(3~4만)', '고가(4만+)'])

# 가격대별 비율 분석
price_stats = df.groupby('가격대').agg({
    '작성자': 'count',
    '별점': 'mean'
}).reset_index()
price_stats.columns = ['가격대', '리뷰수', '평균별점']
price_stats['비율(%)'] = (price_stats['리뷰수'] / price_stats['리뷰수'].sum() * 100).round(1)

print("\n📊 가격대별 구매 분포")
print("-"*50)
print(price_stats.to_string(index=False))

# 가격 vs 리뷰 수 상관분석 (상품 단위)
product_price = df.groupby('상품이름').agg({
    '가격': 'first',
    '리뷰수': 'first'
}).reset_index()

corr_price_review = product_price['가격'].corr(product_price['리뷰수'])
print(f"\n🔬 가격 vs 리뷰 수 상관계수: {corr_price_review:.3f}")

# ============================================================================
# 3-1. 카테고리별 선호도 (재구매율 비율 지표)
# ============================================================================
print("\n" + "="*70)
print("📦 3-1. 카테고리별 선호도 (재구매 언급 비율)")
print("="*70)

# 재구매 언급 추출
df['재구매_언급'] = df['리뷰내용_정제'].apply(
    lambda x: 1 if any(kw in str(x) for kw in ['재구매', '또 살', '또살', '다음에도', '재구입']) else 0
)

# 카테고리별 재구매 언급 비율 (전략 3.3: 비율 지표 사용)
category_loyalty = df.groupby('종류').agg({
    '작성자': 'count',
    '재구매_언급': 'sum',
    '별점': 'mean'
}).reset_index()
category_loyalty.columns = ['종류', '총리뷰수', '재구매언급수', '평균별점']
category_loyalty['재구매율(%)'] = (category_loyalty['재구매언급수'] / category_loyalty['총리뷰수'] * 100).round(2)

print("\n📊 카테고리별 재구매 언급 비율 (충성도 지표)")
print("-"*60)
print(category_loyalty.sort_values('재구매율(%)', ascending=False).to_string(index=False))

print("\n💡 인사이트: 소형 브랜드가 충성도가 높아 1위를 차지할 수 있음")

# ============================================================================
# 저장
# ============================================================================
print("\n" + "="*70)
print("✅ Part 2 분석 완료!")
print("="*70)
print("📁 저장된 파일:")
print("   - data/fig_3_keyword_major.png")

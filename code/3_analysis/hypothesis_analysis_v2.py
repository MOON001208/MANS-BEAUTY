"""
=============================================================================
남성 화장품 시장 가설 검증 분석 스크립트 (v2)
=============================================================================
📌 데이터_불균형_분석_전략.md 반영 버전

[주요 전략]
1. Tier 구분: Major(1000+) vs Minor(1000 미만) 그룹 분리 분석
2. 비율/효율 지표 사용: 총합 대신 평균, 비율 사용
3. Top 2 제외 시장 분석: 오브제/비레디 제외 시 트렌드 확인
4. 데이터 불충분 표기: 리뷰 100개 미만은 신뢰도 경고

실행방법: python hypothesis_analysis_v2.py 또는 Jupyter에서 셀 단위 실행
=============================================================================
"""

# ============================================================================
# 0. 환경 설정 및 데이터 로드
# ============================================================================
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import warnings

# --- 한글 폰트 설정 (Windows) ---
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지

# --- 경고 숨기기 ---
warnings.filterwarnings('ignore')

# --- 시각화 스타일 ---
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)

print("✅ 라이브러리 로드 완료")

# --- 데이터 로드 ---
# analysis_master.plk: product_master_final + review_processed_metadata 병합본
df = pd.read_pickle('../data/analysis_master.plk')

print(f"📊 데이터 Shape: {df.shape}")
print(f"📅 리뷰 기간: {df['날짜'].min()} ~ {df['날짜'].max()}")

# ============================================================================
# 0-1. 브랜드 Tier 정의 (데이터_불균형_분석_전략 2.2)
# ============================================================================
# 전략: 리뷰 1000개 이상 = Major, 미만 = Minor
# Major: 통계적 유의성 확보, 정량 분석 가능
# Minor: 정성적 분석 또는 '기타'로 묶어 다양성 지표로 활용

# 브랜드별 리뷰 수 계산
brand_review_counts = df.groupby('브랜드').size().reset_index(name='리뷰수')
brand_review_counts['Tier'] = brand_review_counts['리뷰수'].apply(
    lambda x: 'Major' if x >= 1000 else 'Minor'
)

print("\n" + "="*60)
print("📊 브랜드 Tier 분류 (임계값: 1,000개)")
print("="*60)
print("\n🏆 Major 브랜드 (1,000개 이상):")
major_brands = brand_review_counts[brand_review_counts['Tier'] == 'Major']
for _, row in major_brands.iterrows():
    print(f"   - {row['브랜드']}: {row['리뷰수']:,}개")

print("\n📦 Minor 브랜드 (1,000개 미만):")
minor_brands = brand_review_counts[brand_review_counts['Tier'] == 'Minor']
for _, row in minor_brands.iterrows():
    # 전략: 100개 미만은 "⚠️ 데이터 불충분" 표기
    warning = " ⚠️ 데이터 불충분" if row['리뷰수'] < 100 else ""
    print(f"   - {row['브랜드']}: {row['리뷰수']:,}개{warning}")

# Tier 정보를 원본 df에 매핑
tier_map = dict(zip(brand_review_counts['브랜드'], brand_review_counts['Tier']))
df['Tier'] = df['브랜드'].map(tier_map)

# Major/Minor 브랜드 리스트 저장
MAJOR_BRANDS = major_brands['브랜드'].tolist()
MINOR_BRANDS = minor_brands['브랜드'].tolist()

# ============================================================================
# 1. 남성 뷰티 추세 분석
# ============================================================================
print("\n" + "="*70)
print("📈 1. 남성 뷰티 추세 분석")
print("="*70)

# --- 1-1. 전체 시장 vs Top2 제외 시장 비교 (전략 3.1) ---
# 전략: 오브제+비레디가 시장을 왜곡할 수 있으므로 분리 분석
TOP2_BRANDS = ['오브제', '비레디']

# 연도별 리뷰 수 (전체)
yearly_all = df.groupby('Review_Year').size().reset_index(name='전체')

# 연도별 리뷰 수 (Top2 제외)
df_excl_top2 = df[~df['브랜드'].isin(TOP2_BRANDS)]
yearly_excl_top2 = df_excl_top2.groupby('Review_Year').size().reset_index(name='Top2제외')

# 병합
yearly_compare = yearly_all.merge(yearly_excl_top2, on='Review_Year')
yearly_compare['Top2비중(%)'] = (
    (yearly_compare['전체'] - yearly_compare['Top2제외']) / yearly_compare['전체'] * 100
).round(1)

print("\n📊 연도별 리뷰 추이 (전체 vs Top2 제외)")
print("-"*50)
print(yearly_compare.to_string(index=False))

# 시각화
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 좌측: 전체 vs Top2 제외 비교
ax1 = axes[0]
x = yearly_compare['Review_Year']
width = 0.35
ax1.bar(x - width/2, yearly_compare['전체'], width, label='전체 시장', color='steelblue')
ax1.bar(x + width/2, yearly_compare['Top2제외'], width, label='Top2 제외', color='coral')
ax1.set_xlabel('연도')
ax1.set_ylabel('리뷰 수')
ax1.set_title('📈 시장 트렌드: 전체 vs Top2(오브제/비레디) 제외', fontweight='bold')
ax1.legend()

# 우측: Top2 비중 추이
ax2 = axes[1]
ax2.plot(x, yearly_compare['Top2비중(%)'], marker='o', linewidth=2, color='purple')
ax2.set_xlabel('연도')
ax2.set_ylabel('Top2 비중 (%)')
ax2.set_title('📊 시장 집중도: Top2 브랜드가 차지하는 비중', fontweight='bold')
ax2.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='50% 기준선')
ax2.legend()

plt.tight_layout()
plt.savefig('../data/fig_1_market_trend.png', dpi=150, bbox_inches='tight')
plt.show()

print("\n💡 인사이트: Top2 브랜드를 제외해도 시장이 성장하는지 확인하세요.")

# ============================================================================
# 2-1. 브랜드별 구매력 차이 (비율 지표 사용)
# ============================================================================
print("\n" + "="*70)
print("🏷️ 2-1. 브랜드별 구매력 차이")
print("="*70)

# 전략 2.1: 절대 비교 대신 '효율' 지표 사용
# - 총 리뷰 수 대신 → 상품당 평균 리뷰 수
# - 총합 대신 → 평균 별점

brand_stats = df.groupby('브랜드').agg({
    '상품이름': 'nunique',       # 상품 종류 수
    '작성자': 'count',           # 총 리뷰 수
    '별점': 'mean',              # 평균 별점
    '가격': 'mean'               # 평균 가격
}).reset_index()
brand_stats.columns = ['브랜드', '상품수', '총리뷰수', '평균별점', '평균가격']

# 효율 지표: 상품당 평균 리뷰 수 (= 상품 하나가 얼마나 관심을 받는가)
brand_stats['상품당_리뷰수'] = (brand_stats['총리뷰수'] / brand_stats['상품수']).round(1)

# Tier 정보 추가
brand_stats['Tier'] = brand_stats['브랜드'].map(tier_map)

# 정렬 (효율 지표 기준)
brand_stats = brand_stats.sort_values('상품당_리뷰수', ascending=False)

print("\n📊 브랜드별 효율 지표 (상품당 리뷰 수 기준)")
print("-"*70)
print(brand_stats.to_string(index=False))

# 시각화: Major vs Minor 분리
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

for i, tier in enumerate(['Major', 'Minor']):
    ax = axes[i]
    tier_data = brand_stats[brand_stats['Tier'] == tier].sort_values('상품당_리뷰수', ascending=True)
    colors = 'steelblue' if tier == 'Major' else 'coral'
    
    ax.barh(tier_data['브랜드'], tier_data['상품당_리뷰수'], color=colors)
    ax.set_xlabel('상품당 리뷰 수 (효율 지표)')
    ax.set_title(f'{"🏆" if tier=="Major" else "📦"} {tier} 브랜드 효율성', fontweight='bold')
    
    # 수치 표시
    for j, (brand, val) in enumerate(zip(tier_data['브랜드'], tier_data['상품당_리뷰수'])):
        ax.text(val + 10, j, f'{val:.0f}', va='center', fontsize=9)

plt.tight_layout()
plt.savefig('../data/fig_2_brand_efficiency.png', dpi=150, bbox_inches='tight')
plt.show()

# ============================================================================
# 2-4. 유튜버 홍보 효과 (데이터 불균형을 증거로 활용)
# ============================================================================
print("\n" + "="*70)
print("🎬 2-4. 유튜버 홍보 효과 분석")
print("="*70)

# 전략 3.2-4: "데이터 불균형 자체가 홍보 효과의 가장 강력한 증거"
viral_stats = df.groupby('is_viral').agg({
    '브랜드': 'nunique',
    '작성자': 'count',
    '별점': 'mean'
}).reset_index()
viral_stats.columns = ['is_viral', '브랜드수', '총리뷰수', '평균별점']
viral_stats['is_viral'] = viral_stats['is_viral'].map({0: '일반', 1: '바이럴'})

# 브랜드당 평균 리뷰 수 계산 (효율 지표)
viral_stats['브랜드당_평균리뷰'] = (viral_stats['총리뷰수'] / viral_stats['브랜드수']).round(0)

print("\n📊 바이럴 vs 일반 비교")
print("-"*50)
print(viral_stats.to_string(index=False))

# t-검정: 별점 차이 유의성
viral_scores = df[df['is_viral'] == 1]['별점'].dropna()
normal_scores = df[df['is_viral'] == 0]['별점'].dropna()
t_stat, p_val = stats.ttest_ind(viral_scores, normal_scores)

print(f"\n🔬 통계 검정 (Independent t-test)")
print(f"   - 바이럴 평균 별점: {viral_scores.mean():.3f}")
print(f"   - 일반 평균 별점: {normal_scores.mean():.3f}")
print(f"   - t-statistic: {t_stat:.4f}")
print(f"   - p-value: {p_val:.6f}")
print(f"   - 결론: {'✅ 유의한 차이 있음 (p<0.05)' if p_val < 0.05 else '❌ 유의한 차이 없음'}")

# ============================================================================
# 3. 카테고리별 선호도 (비율 지표 사용)
# ============================================================================
print("\n" + "="*70)
print("📦 3. 카테고리별 선호도")
print("="*70)

category_stats = df.groupby('종류').agg({
    '상품이름': 'nunique',
    '작성자': 'count',
    '별점': 'mean',
    '가격': 'mean'
}).reset_index()
category_stats.columns = ['종류', '상품수', '총리뷰수', '평균별점', '평균가격']
category_stats['상품당_리뷰수'] = (category_stats['총리뷰수'] / category_stats['상품수']).round(1)
category_stats = category_stats.sort_values('총리뷰수', ascending=False)

print("\n📊 카테고리별 통계")
print("-"*60)
print(category_stats.to_string(index=False))

# ============================================================================
# 종합 결론
# ============================================================================
print("\n" + "="*70)
print("📋 종합 결론 (데이터 불균형 전략 반영)")
print("="*70)

print("""
💡 분석 시 유의사항 (솔직한 데이터 공개):
   - 브랜드별 데이터 모수 차이가 큽니다 (최대 11,000개 vs 최소 30개)
   - 이는 시장의 '쏠림 현상'을 반영합니다
   
🔹 주요 발견:
   1. Top2 브랜드(오브제/비레디)가 시장의 상당 비중을 차지
   2. Top2를 제외해도 나머지 시장도 성장 추세인지 확인 필요
   3. Major 그룹은 정량 분석, Minor 그룹은 정성적 특징 분석 권장
   
⚠️ 신뢰도 경고:
   - 리뷰 100개 미만 브랜드의 통계는 참고용으로만 활용하세요
""")

print("✅ 분석 완료! 그래프가 data/ 폴더에 저장되었습니다.")

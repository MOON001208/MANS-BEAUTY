"""
콘텐츠 기반 추천 엔진 (Content-Based Recommender)
사용자 프로필과 제품 프로필을 매칭하여 맞춤형 추천을 제공합니다.

매칭 알고리즘:
- 가중 점수 합계 방식
- 8가지 속성별 유사도 계산
- 최적 매칭 제품 TOP 5 추천
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import pickle

# ===== 속성별 가중치 =====
WEIGHTS = {
    "skin_brightness": 0.15,   # 피부 밝기 (호수)
    "skin_concerns": 0.35,     # 피부고민 (매우 높임: 35%)
    "skin_type": 0.35,         # 피부타입 (매우 높임: 35%)
    "coverage": 0.05,          # 커버력 등은 부수적
    "longevity": 0.05,         # 지속력
    "lightweight": 0.05,       # 착용감
}


@dataclass
class UserProfile:
    """사용자 입력 프로필"""
    skin_brightness: str = "23"  # "21", "23", "25"
    skin_concerns: List[str] = field(default_factory=lambda: [])  # ["acne", "pore", ...]
    skin_type: str = "combination"  # "oily", "dry", "sensitive", "combination"
    coverage_pref: int = 3  # 1-5
    longevity_pref: int = 3  # 1-5
    lightweight_pref: int = 3  # 1-5
    product_type_pref: str = "any"  # "cushion", "liquid", "any"


@dataclass
class RecommendationResult:
    """추천 결과"""
    product_name: str
    brand: str
    match_score: float  # 0-1
    match_details: Dict[str, float]
    product_info: Dict
    match_reasons: List[str]


def calculate_shade_similarity(user_shade: str, product_shades: List[str]) -> float:
    """
Shade_Standard
    호수 유사도 계산
    정확히 일치하면 1.0, 인접하면 0.5, 아니면 0.0
    """
    if not product_shades:
        return 0.5  # 정보 없으면 중간 점수
    
    # 정확히 일치
    if user_shade in product_shades:
        return 1.0
    
    # 인접 호수 매핑
    shade_order = ["21", "23", "25"]
    try:
        user_idx = shade_order.index(user_shade)
        for shade in product_shades:
            if shade in shade_order:
                prod_idx = shade_order.index(shade)
                if abs(user_idx - prod_idx) == 1:
                    return 0.5
    except ValueError:
        pass
    
    return 0.0


def calculate_concerns_similarity(user_concerns: List[str], product_concerns: List[str]) -> float:
    """
    피부고민 유사도 계산 (자카드 유사도)
    """
    if not user_concerns:
        return 1.0  # 사용자가 고민을 선택하지 않으면 모든 제품 OK
    if not product_concerns:
        return 0.5  # 제품 정보 없으면 중간 점수
    
    user_set = set(user_concerns)
    product_set = set(product_concerns)
    
    intersection = len(user_set & product_set)
    union = len(user_set | product_set)
    
    if union == 0:
        return 0.5
    
    return intersection / len(user_set)  # 사용자 고민 중 몇 개가 커버되는지


def calculate_skin_type_similarity(user_type: str, product_types: List[str], compat_scores: Dict[str, float]) -> float:
    """
    피부타입 유사도 계산
    """
    # 호환성 점수 사용 (성분 기반)
    compat_key = f"compat_{user_type}"
    if compat_key.replace("compat_", "") == "oily":
        base_compat = compat_scores.get('compat_oily', 0.5)
    elif compat_key.replace("compat_", "") == "dry":
        base_compat = compat_scores.get('compat_dry', 0.5)
    elif compat_key.replace("compat_", "") == "sensitive":
        base_compat = compat_scores.get('compat_sensitive', 0.5)
    else:
        base_compat = compat_scores.get('compat_combination', 0.5)
    
    # 리뷰에서 추출된 피부타입과도 매칭
    if user_type in product_types:
        return min(1.0, base_compat + 0.3)
    
    return base_compat


def calculate_numeric_similarity(user_pref: int, product_score: float) -> float:
    """
    수치형 속성 유사도 계산 (1-5 척도)
    차이가 적을수록 높은 점수
    """
    if pd.isna(product_score):
        return 0.5  # 정보 없으면 중간 점수
    
    diff = abs(user_pref - product_score)
    # 차이가 0이면 1.0, 차이가 4이면 0.0
    return max(0, 1 - diff / 4)


def calculate_category_match(user_pref: str, product_value: str) -> float:
    """
    범주형 속성 일치 여부
    """
    if user_pref == "any":
        return 1.0
    if user_pref.lower() == product_value.lower():
        return 1.0
    return 0.0





def generate_match_reasons(user: UserProfile, product: Dict, details: Dict[str, float]) -> List[str]:
    """
    매칭 이유 설명 생성
    """
    reasons = []
    
    # 높은 점수 속성 설명
    if details.get('skin_type', 0) >= 0.7:
        reasons.append(f"✓ {user.skin_type} 피부타입에 적합")
    
    if details.get('concerns', 0) >= 0.5 and user.skin_concerns:
        reasons.append(f"✓ {', '.join(user.skin_concerns)} 고민에 효과적")
    
    if details.get('coverage', 0) >= 0.7:
        level = "높은" if user.coverage_pref >= 4 else "자연스러운"
        reasons.append(f"✓ {level} 커버력 제공")
    
    if details.get('longevity', 0) >= 0.7:
        reasons.append("✓ 지속력 우수")
    
    if details.get('lightweight', 0) >= 0.7:
        reasons.append("✓ 가벼운 착용감")
    
    if product.get('ingredient_level') in ["저자극", "자연유래"]:
        reasons.append(f"✓ {product.get('ingredient_level')} 성분")
    
    if details.get('shade', 0) >= 0.8:
        reasons.append(f"✓ {user.skin_brightness}호 적합")
    
    return reasons if reasons else ["✓ 전반적으로 적합한 제품"]


def recommend(user: UserProfile, products_df: pd.DataFrame, top_n: int = 5) -> List[RecommendationResult]:
    """
    사용자 프로필에 맞는 제품 추천
    """
    results = []
    
    # 제품 유형 필터링: "any"가 아니면 해당 유형만 추천
    if user.product_type_pref != "any":
        filtered_df = products_df[products_df['product_type'].str.lower() == user.product_type_pref.lower()]
        # 필터링 결과가 없으면 원본 사용
        if len(filtered_df) == 0:
            filtered_df = products_df
    else:
        filtered_df = products_df
    
    for _, product in filtered_df.iterrows():
        # 각 속성별 유사도 계산
        shade_sim = calculate_shade_similarity(
            user.skin_brightness, 
            product.get('suitable_shades', []) or []
        )
        
        concerns_sim = calculate_concerns_similarity(
            user.skin_concerns,
            product.get('suitable_concerns', []) or []
        )
        
        skin_type_sim = calculate_skin_type_similarity(
            user.skin_type,
            product.get('suitable_skin_types', []) or [],
            {
                'compat_oily': product.get('compat_oily', 0.5),
                'compat_dry': product.get('compat_dry', 0.5),
                'compat_sensitive': product.get('compat_sensitive', 0.5),
                'compat_combination': product.get('compat_combination', 0.5),
            }
        )
        
        coverage_sim = calculate_numeric_similarity(
            user.coverage_pref, 
            product.get('coverage_score', 3.0)
        )
        
        longevity_sim = calculate_numeric_similarity(
            user.longevity_pref,
            product.get('longevity_score', 3.0)
        )
        
        lightweight_sim = calculate_numeric_similarity(
            user.lightweight_pref,
            product.get('lightweight_score', 3.0)
        )
        
        # 가중 합계 계산
        details = {
            'shade': shade_sim,
            'concerns': concerns_sim,
            'skin_type': skin_type_sim,
            'coverage': coverage_sim,
            'longevity': longevity_sim,
            'lightweight': lightweight_sim,
        }
        
        total_score = (
            WEIGHTS['skin_brightness'] * shade_sim +
            WEIGHTS['skin_concerns'] * concerns_sim +
            WEIGHTS['skin_type'] * skin_type_sim +
            WEIGHTS['coverage'] * coverage_sim +
            WEIGHTS['longevity'] * longevity_sim +
            WEIGHTS['lightweight'] * lightweight_sim
        )
        
        # 🚨 페널티: 피부 성분 호환성이 너무 낮으면 점수 극단적 삭감
        if skin_type_sim < 0.35:
            total_score *= 0.3 # 70% 감점
            
        # 리뷰 점수 반영 (인기도 편향을 억제하기 위해 극소량만 보너스 부여)
        review_bonus = min(product.get('review_count', 0) / 2000, 1) * 0.02
        rating_bonus = max(product.get('avg_rating', 0) - 4.0, 0) * 0.03
        total_score += review_bonus + rating_bonus
        
        # 매칭 이유 생성
        reasons = generate_match_reasons(user, product.to_dict(), details)
        
        result = RecommendationResult(
            product_name=product['product_name'],
            brand=product.get('brand', ''),
            match_score=round(total_score, 3),
            match_details=details,
            product_info={
                'product_type': product.get('product_type'),
                'coverage_score': product.get('coverage_score'),
                'longevity_score': product.get('longevity_score'),
                'lightweight_score': product.get('lightweight_score'),
                'ingredient_level': product.get('ingredient_level'),
                'review_count': product.get('review_count'),
                'avg_rating': product.get('avg_rating'),
                'price': product.get('price'),
                'shade_options': product.get('shade_options', {}),
                'product_link': product.get('product_link', ''),
            },
            match_reasons=reasons
        )
        
        results.append(result)
    
    # 점수 기준 정렬
    results.sort(key=lambda x: x.match_score, reverse=True)
    
    return results[:top_n]


def print_recommendations(results: List[RecommendationResult]):
    """추천 결과 출력"""
    print("\n" + "="*60)
    print("🎯 맞춤형 추천 결과")
    print("="*60)
    
    for i, rec in enumerate(results, 1):
        print(f"\n[{i}위] {rec.product_name} ({rec.brand})")
        print(f"    매칭률: {rec.match_score*100:.1f}%")
        print(f"    제품유형: {rec.product_info['product_type']} | 성분: {rec.product_info['ingredient_level']}")
        print(f"    커버력: {rec.product_info['coverage_score']}/5 | 지속력: {rec.product_info['longevity_score']}/5")
        print(f"    리뷰수: {rec.product_info['review_count']}개 | 평점: {rec.product_info['avg_rating']}")
        print(f"    추천 이유:")
        for reason in rec.match_reasons:
            print(f"      {reason}")


def main():
    """테스트 실행"""
    base_path = Path(__file__).parent.parent / "data"
    
    # 제품 프로필 로드
    print("Loading product profiles...")
    df_profiles = pd.read_pickle(base_path / "product_profiles.plk")
    print(f"Loaded {len(df_profiles)} products")
    
    # 테스트 사용자 프로필
    test_user = UserProfile(
        skin_brightness="23",
        skin_concerns=["pore", "acne"],
        skin_type="oily",
        coverage_pref=4,
        longevity_pref=4,
        lightweight_pref=4,
        product_type_pref="cushion"
    )
    
    print("\n=== 테스트 사용자 프로필 ===")
    print(f"피부 밝기: {test_user.skin_brightness}호")
    print(f"피부 고민: {test_user.skin_concerns}")
    print(f"피부 타입: {test_user.skin_type}")
    print(f"커버력 선호: {test_user.coverage_pref}/5")
    print(f"지속력 선호: {test_user.longevity_pref}/5")
    print(f"착용감 선호: {test_user.lightweight_pref}/5")
    print(f"제품 유형: {test_user.product_type_pref}")
    
    # 추천 실행
    recommendations = recommend(test_user, df_profiles, top_n=5)
    
    # 결과 출력
    print_recommendations(recommendations)
    
    # 결과 저장
    results_dict = [vars(r) for r in recommendations]
    output_path = base_path / "test_recommendations.plk"
    with open(output_path, 'wb') as f:
        pickle.dump(results_dict, f)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()

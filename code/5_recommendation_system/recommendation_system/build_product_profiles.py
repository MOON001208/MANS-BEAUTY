"""
제품 프로필 구축 모듈 (Product Profile Builder)
리뷰에서 추출한 속성과 성분 분석 결과를 결합하여 각 제품의 프로필을 생성합니다.

제품 프로필 구조:
- 8가지 핵심 속성 벡터
- 리뷰 기반 통계
- 성분 호환성 점수
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
import pickle
from collections import Counter


@dataclass
class ProductProfile:
    """제품 프로필 데이터 클래스"""
    product_id: str
    product_name: str
    brand: str
    
    # 적합한 호수 (피부 밝기)
    suitable_shades: List[str] = field(default_factory=list)
    
    # 호수별 옵션 정보 (예: {"21": "1호 라이트베이지", "23": "2호 베이지", "25": "3호 샌드"})
    shade_options: Dict[str, str] = field(default_factory=dict)
    
    # 적합한 피부고민
    suitable_concerns: List[str] = field(default_factory=list)
    
    # 적합한 피부타입
    suitable_skin_types: List[str] = field(default_factory=list)
    
    # 수치형 속성 (1-5점 평균)
    coverage_score: float = 3.0
    longevity_score: float = 3.0
    lightweight_score: float = 3.0
    
    # 제품 유형
    product_type: str = "unknown"
    
    # 성분정도
    ingredient_level: str = "일반"
    
    # 피부타입별 호환성 점수 (0-1)
    compat_oily: float = 0.5
    compat_dry: float = 0.5
    compat_sensitive: float = 0.5
    compat_combination: float = 0.5
    
    # 메타데이터
    review_count: int = 0
    avg_rating: float = 0.0
    price: Optional[int] = None
    product_link: str = ""


def get_top_items(items_list: List[List[str]], min_freq: float = 0.1) -> List[str]:
    """
    리스트들의 아이템 빈도를 계산하여 상위 항목 반환
    min_freq: 최소 빈도 비율 (전체의 10% 이상인 경우 포함)
    """
    if not items_list or len(items_list) == 0:
        return []
    
    # 모든 아이템 펼치기
    all_items = []
    for items in items_list:
        if isinstance(items, list):
            all_items.extend(items)
        elif items:
            all_items.append(items)
    
    if not all_items:
        return []
    
    # 빈도 계산
    counter = Counter(all_items)
    total = len(items_list)
    
    # 최소 빈도 이상인 항목만 선택
    result = [item for item, count in counter.most_common() 
              if count / total >= min_freq]
    
    return result[:5]  # 최대 5개


def extract_shade_options(options: pd.Series) -> Dict[str, str]:
    """
    옵션 컬럼에서 호수별 옵션 정보 추출
    예: "[옵션] 2호 베이지" -> {"23": "2호 베이지"}
    """
    shade_options = {}
    
    # 호수 매핑 패턴
    shade_patterns = {
        "21": ["1호", "21호", "라이트", "아이보리", "밝은"],
        "23": ["2호", "23호", "베이지", "뉴트럴", "중간"],
        "25": ["3호", "25호", "27호", "샌드", "탠", "다크", "어두운"]
    }
    
    for option in options.dropna().unique():
        if not option or not isinstance(option, str):
            continue
        
        # [옵션] 접두사 제거
        clean_option = option.replace("[옵션]", "").strip()
        
        for shade, patterns in shade_patterns.items():
            for pattern in patterns:
                if pattern in clean_option:
                    # 더 구체적인 옵션 저장 (기존보다 길면 업데이트)
                    if shade not in shade_options or len(clean_option) > len(shade_options[shade]):
                        shade_options[shade] = clean_option
                    break
    
    return shade_options


def aggregate_numeric_scores(scores: pd.Series) -> float:
    """수치형 점수 집계 (NaN 제외 평균)"""
    valid_scores = scores.dropna()
    if len(valid_scores) == 0:
        return 3.0  # 기본값
    return round(valid_scores.mean(), 2)


def analyze_shade_suitability(product_reviews: pd.DataFrame) -> List[str]:
    """
    구매 옵션, AI 추출 호수, 감성 분석을 결합하여 제품에 적합한 호수 결정
    """
    shade_scores = Counter()
    
    # 호수 패턴 (데이터 정규화용)
    shade_map = {
        "21": ["21", "21호", "1호", "라이트"],
        "23": ["23", "23호", "2호", "베이지", "뉴트럴"],
        "25": ["25", "25호", "27", "3호", "샌드", "탠"]
    }
    
    # 키워드 (감성 보정용)
    BRIGHT_KEYWORDS = ["밝다", "밝아", "하얘", "하얗", "부담", "티나", "백탁", "밝네"]
    DARK_KEYWORDS = ["어둡다", "어두워", "칙칙", "검어", "시커", "어둡네"]

    for _, row in product_reviews.iterrows():
        review_text = str(row.get('리뷰내용', '')) + " " + str(row.get('gemini_normalized', ''))
        sentiment = row.get('attr_sentiment', 'neutral')
        
        # 1. 구매 옵션에서 호수 감별
        purchased_shade = None
        option_text = str(row.get('옵션', ''))
        for s_code, patterns in shade_map.items():
            if any(p in option_text for p in patterns):
                purchased_shade = s_code
                break
        
        # 2. AI 추출 호수 (참고용)
        ai_shade = str(row.get('attr_shade', ''))
        
        # 분석 대상 호수 결정 (구매 옵션 우선)
        target_shade = purchased_shade if purchased_shade else (ai_shade if ai_shade in shade_map else None)
        
        if not target_shade:
            continue
            
        # 3. 감성 및 키워드 기반 점수 계산
        if sentiment == 'positive':
            shade_scores[target_shade] += 1.2
        elif sentiment == 'negative':
            # 부정적인데 너무 밝다는 의견이면 -> 호수 조정
            is_bright = any(k in review_text for k in BRIGHT_KEYWORDS)
            is_dark = any(k in review_text for k in DARK_KEYWORDS)
            
            if is_bright:
                # 23호 샀는데 너무 밝다 -> 실제로는 21호 사용자에게 더 맞을 수 있음
                if target_shade == "23": shade_scores["21"] += 0.5
                elif target_shade == "25": shade_scores["23"] += 0.5
            elif is_dark:
                # 23호 샀는데 너무 어둡다 -> 실제로는 25호 사용자에게 더 맞을 수 있음
                if target_shade == "21": shade_scores["23"] += 0.5
                elif target_shade == "23": shade_scores["25"] += 0.5
            else:
                # 호수 문제는 아닌 일반 부정 (점수 낮게 반영)
                shade_scores[target_shade] += 0.2
        else:
            shade_scores[target_shade] += 0.8

    # 일정 점수 이상인 호수만 필터링하여 반환
    total_reviews = len(product_reviews)
    min_score = max(2, total_reviews * 0.05) # 최소 2점 혹은 5% 이상
    
    final_shades = [s for s, score in shade_scores.most_common() if score >= min_score]
    return sorted(final_shades) if final_shades else (["23"] if "23" in shade_scores else [])


def build_product_profile(
    product_name: str,
    product_reviews: pd.DataFrame,
    ingredient_info: Optional[pd.Series] = None
) -> ProductProfile:
    """단일 제품의 프로필 생성"""
    
    if len(product_reviews) == 0:
        return None
    
    first_row = product_reviews.iloc[0]
    
    # 기본 정보
    profile = ProductProfile(
        product_id=str(hash(product_name)),
        product_name=product_name,
        brand=first_row.get('브랜드', ''),
        review_count=len(product_reviews),
        avg_rating=round(product_reviews['별점'].mean(), 2) if '별점' in product_reviews else 0.0,
        product_link=first_row.get('상품링크', ''),
    )
    
    # 가격 (첫 번째 리뷰의 가격 사용)
    price = first_row.get('가격', None)
    if price and not pd.isna(price):
        profile.price = int(price)
    
    # 수치형 속성 집계
    if 'attr_coverage' in product_reviews.columns:
        profile.coverage_score = aggregate_numeric_scores(product_reviews['attr_coverage'])
    if 'attr_longevity' in product_reviews.columns:
        profile.longevity_score = aggregate_numeric_scores(product_reviews['attr_longevity'])
    if 'attr_lightweight' in product_reviews.columns:
        profile.lightweight_score = aggregate_numeric_scores(product_reviews['attr_lightweight'])
    
    # 범주형 속성 집계
    if 'attr_skin_types' in product_reviews.columns:
        profile.suitable_skin_types = get_top_items(product_reviews['attr_skin_types'].tolist())
    if 'attr_skin_concerns' in product_reviews.columns:
        profile.suitable_concerns = get_top_items(product_reviews['attr_skin_concerns'].tolist())
    
    # 호수 추천 로직 개선 (구매옵션 + AI추출 + 감성분석 결합)
    profile.suitable_shades = analyze_shade_suitability(product_reviews)
    
    # 제품 유형 (한글 -> 영어 변환 포함)
    type_mapping = {
        '쿠션': 'cushion',
        '스틱파운데이션': 'stick',
        '리퀴드파운데이션': 'liquid',
        '파운데이션': 'liquid',  # 일반 파운데이션은 제품명으로 추가 분류
    }
    
    raw_type = None
    if '종류' in product_reviews.columns:
        type_counts = product_reviews['종류'].value_counts()
        if len(type_counts) > 0:
            raw_type = type_counts.index[0]
    elif 'attr_product_type' in product_reviews.columns:
        type_counts = product_reviews['attr_product_type'].value_counts()
        if len(type_counts) > 0:
            raw_type = type_counts.index[0]
    
    if raw_type:
        # 한글 -> 영어 변환
        profile.product_type = type_mapping.get(raw_type, raw_type)
        
        # '파운데이션' 타입의 경우 제품명으로 추가 분류
        if raw_type == '파운데이션':
            name_lower = product_name.lower()
            if '스틱' in product_name:
                profile.product_type = 'stick'
            elif '쿠션' in product_name:
                profile.product_type = 'cushion'
            # 그 외는 liquid 유지
    
    # 성분 정보 병합
    if ingredient_info is not None:
        profile.ingredient_level = ingredient_info.get('ingredient_level', '일반')
        profile.compat_oily = ingredient_info.get('compat_oily', 0.5)
        profile.compat_dry = ingredient_info.get('compat_dry', 0.5)
        profile.compat_sensitive = ingredient_info.get('compat_sensitive', 0.5)
        profile.compat_combination = ingredient_info.get('compat_combination', 0.5)
    
    # 호수별 옵션 정보 추출
    if '옵션' in product_reviews.columns:
        profile.shade_options = extract_shade_options(product_reviews['옵션'])
    
    return profile


def match_product_name(name1: str, name2: str) -> bool:
    """제품명 유사성 체크"""
    # 정규화
    n1 = name1.replace(" ", "").lower()
    n2 = name2.replace(" ", "").lower()
    
    # 완전 일치
    if n1 == n2:
        return True
    
    # 부분 포함
    if len(n1) > 10 and len(n2) > 10:
        if n1[:15] in n2 or n2[:15] in n1:
            return True
    
    return False


def build_all_profiles(df_reviews: pd.DataFrame, df_ingredients: pd.DataFrame) -> pd.DataFrame:
    """전체 제품 프로필 생성"""
    print("Building product profiles...")
    
    # 제품별 그룹화
    product_groups = df_reviews.groupby('상품이름')
    print(f"Total unique products: {len(product_groups)}")
    
    profiles = []
    for product_name, group in product_groups:
        # 성분 정보 찾기
        ingredient_info = None
        for idx, row in df_ingredients.iterrows():
            if match_product_name(product_name, row['product_name']):
                ingredient_info = row
                break
        
        profile = build_product_profile(product_name, group, ingredient_info)
        if profile:
            profiles.append(vars(profile))
    
    df_profiles = pd.DataFrame(profiles)
    print(f"Created {len(df_profiles)} product profiles")
    
    return df_profiles


def main():
    """메인 실행 함수"""
    # recommendation_system 폴더 기준: parent.parent.parent = 프로젝트 루트
    base_path = Path(__file__).parent.parent.parent / "data"
    
    # 데이터 로드
    print("Loading data...")
    # Gemini 버전 사용 (더 정확한 속성 추출)
    review_file = base_path / "review_attributes_gemini.plk"
    if not review_file.exists():
        # Gemini 버전이 없으면 키워드 버전 사용
        review_file = base_path / "review_attributes.plk"
        print("Using keyword-based attributes (Gemini version not found)")
    else:
        print("Using Gemini-extracted attributes")
    
    df_reviews = pd.read_pickle(review_file)
    df_ingredients = pd.read_pickle(base_path / "ingredient_risk_mapping.plk")
    
    print(f"Reviews: {len(df_reviews)}")
    print(f"Ingredient mappings: {len(df_ingredients)}")
    
    # 프로필 생성
    df_profiles = build_all_profiles(df_reviews, df_ingredients)
    
    # 결과 저장
    output_path = base_path / "product_profiles.plk"
    df_profiles.to_pickle(output_path)
    print(f"Saved to {output_path}")
    
    # CSV로도 저장
    csv_path = base_path / "product_profiles.csv"
    df_profiles.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"Saved to {csv_path}")
    
    # 통계 출력
    print("\n=== Profile Statistics ===")
    print(f"Total products: {len(df_profiles)}")
    print(f"\nProduct types:")
    print(df_profiles['product_type'].value_counts())
    print(f"\nAverage scores:")
    print(f"  Coverage: {df_profiles['coverage_score'].mean():.2f}")
    print(f"  Longevity: {df_profiles['longevity_score'].mean():.2f}")
    print(f"  Lightweight: {df_profiles['lightweight_score'].mean():.2f}")
    print(f"\nReview count stats:")
    print(f"  Mean: {df_profiles['review_count'].mean():.1f}")
    print(f"  Max: {df_profiles['review_count'].max()}")
    print(f"  Min: {df_profiles['review_count'].min()}")
    
    # 샘플 출력
    print("\n=== Sample Profiles ===")
    sample_cols = ['product_name', 'brand', 'product_type', 'coverage_score', 
                   'longevity_score', 'ingredient_level', 'review_count']
    print(df_profiles[sample_cols].head(10).to_string())


if __name__ == "__main__":
    main()

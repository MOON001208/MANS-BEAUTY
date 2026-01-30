"""
리뷰 속성 추출 모듈 (Content-Based Filtering용)
정규화된 한국어 리뷰에서 8가지 핵심 속성을 추출합니다.

8가지 속성:
1. 피부 밝기 (21호/23호/25호)
2. 피부고민 (여드름/모공/트러블/홍조/잡티)
3. 피부타입 (건성/지성/복합성/민감성)
4. 커버력 (1-5점)
5. 지속력 (1-5점)
6. 가벼운 착용감 (1-5점)
7. 쿠션 vs 리퀴드 (제품 유형)
8. 성분정도 (자연유래/저자극/일반)
"""

import pandas as pd
import numpy as np
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import pickle
from pathlib import Path

# ===== 키워드 맵 정의 =====

COVERAGE_KEYWORDS = {
    "high": [
        "풀커버", "커버력 좋", "커버가 잘", "완벽하게 가려", "커버력이 좋", 
        "잡티 커버", "커버 잘", "커버력 대박", "커버력이 대박", "확실히 커버"
    ],
    "medium": [
        "자연스러운", "데일리", "자연스럽게", "내추럴", "은은한 커버",
        "적당한 커버", "적당히 커버"
    ],
    "low": [
        "쌩얼 메이크업", "맨얼굴", "투명", "커버력 없", "커버 안", 
        "커버력이 없", "커버력 약", "쌩피"
    ]
}

LONGEVITY_KEYWORDS = {
    "high": [
        "하루종일", "저녁까지", "오래가", "안무너", "지속력 좋", "지속력이 좋",
        "밤까지", "퇴근까지", "안 무너", "무너짐 없", "지속력 대박", "하루 내내"
    ],
    "medium": [
        "반나절", "점심때까지", "오전까지", "4-5시간", "몇시간"
    ],
    "low": [
        "무너짐", "번들거림", "뜸", "금방 무너", "빨리 무너", "지속력 별로",
        "지속력이 별로", "무너져", "3시간", "몇시간 못가"
    ]
}

LIGHTWEIGHT_KEYWORDS = {
    "high": [
        "가볍", "촉촉", "밀착", "답답하지 않", "얇게", "가벼운 착용감",
        "무겁지 않", "산뜻", "맑은", "투명"
    ],
    "medium": [
        "적당", "보통"
    ],
    "low": [
        "답답", "무겁", "두꺼운", "뻑뻑", "꺼끌", "끈적", "무거운 착용감"
    ]
}

SKIN_TYPE_KEYWORDS = {
    "oily": ["지성", "유분", "피지", "번들", "기름", "번질", "지복합"],
    "dry": ["건성", "촉촉함", "건조", "당김", "건복합"],
    "combination": ["복합성", "T존", "U존", "복합"],
    "sensitive": ["민감", "자극", "순한", "저자극", "예민"]
}

SKIN_CONCERNS_KEYWORDS = {
    "acne": ["여드름", "트러블", "뾰루지", "좁쌀"],
    "pore": ["모공", "블랙헤드", "피지"],
    "redness": ["홍조", "붉은기", "빨간", "붉"],
    "spots": ["잡티", "점", "기미", "주근깨", "칙칙"],
    "wrinkle": ["주름", "팔자", "눈가"]
}

PRODUCT_TYPE_KEYWORDS = {
    "cushion": ["쿠션", "팩트"],
    "liquid": ["리퀴드", "파운데이션", "파데"],
    "stick": ["스틱"]
}

SHADE_KEYWORDS = {
    "21": ["21호", "21", "밝은톤", "가장 밝은", "라이트"],
    "23": ["23호", "23", "중간톤", "웜베이지", "베이지"],
    "25": ["25호", "27호", "27", "어두운", "다크", "탠"]
}


@dataclass
class ReviewAttributes:
    """리뷰에서 추출된 속성"""
    coverage: Optional[float] = None  # 1-5점
    longevity: Optional[float] = None  # 1-5점
    lightweight: Optional[float] = None  # 1-5점
    skin_type: List[str] = field(default_factory=list)
    skin_concerns: List[str] = field(default_factory=list)
    product_type: Optional[str] = None
    shade: Optional[str] = None
    ingredient_level: Optional[str] = None


def extract_score_from_keywords(text: str, keyword_map: Dict[str, List[str]]) -> Optional[float]:
    """
    키워드 기반으로 1-5점 점수 추출
    high: 4-5점, medium: 3점, low: 1-2점
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    high_count = sum(1 for kw in keyword_map.get("high", []) if kw in text_lower)
    medium_count = sum(1 for kw in keyword_map.get("medium", []) if kw in text_lower)
    low_count = sum(1 for kw in keyword_map.get("low", []) if kw in text_lower)
    
    if high_count > 0 and low_count == 0:
        return 4.5 if high_count > 1 else 4.0
    elif low_count > 0 and high_count == 0:
        return 1.5 if low_count > 1 else 2.0
    elif high_count > low_count:
        return 3.5
    elif low_count > high_count:
        return 2.5
    elif medium_count > 0:
        return 3.0
    
    return None


def extract_categories(text: str, keyword_map: Dict[str, List[str]]) -> List[str]:
    """
    키워드 기반으로 범주 추출 (복수 가능)
    """
    if not text:
        return []
    
    text_lower = text.lower()
    categories = []
    
    for category, keywords in keyword_map.items():
        if any(kw in text_lower for kw in keywords):
            categories.append(category)
    
    return categories


def extract_single_category(text: str, keyword_map: Dict[str, List[str]]) -> Optional[str]:
    """
    키워드 기반으로 단일 범주 추출 (가장 먼저 매칭된 것)
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    for category, keywords in keyword_map.items():
        if any(kw in text_lower for kw in keywords):
            return category
    
    return None


def parse_existing_skin_info(skin_type_str: str) -> Tuple[List[str], List[str], Optional[str]]:
    """
    기존 피부타입 컬럼 파싱 (예: "복합성,웜톤,잡티,미백")
    Returns: (피부타입 리스트, 피부고민 리스트, 톤)
    """
    if pd.isna(skin_type_str) or not skin_type_str:
        return [], [], None
    
    parts = [p.strip() for p in skin_type_str.split(",")]
    
    skin_types = []
    concerns = []
    tone = None
    
    type_map = {"건성": "dry", "지성": "oily", "복합성": "combination", "민감성": "sensitive"}
    concern_map = {"잡티": "spots", "트러블": "acne", "주름": "wrinkle", "미백": "whitening", 
                   "각질": "dryness", "모공": "pore"}
    
    for part in parts:
        # 피부타입 체크
        for kor, eng in type_map.items():
            if kor in part:
                skin_types.append(eng)
        
        # 피부고민 체크
        for kor, eng in concern_map.items():
            if kor in part:
                concerns.append(eng)
        
        # 톤 체크
        if "웜톤" in part or "웜" in part:
            tone = "warm"
        elif "쿨톤" in part or "쿨" in part:
            tone = "cool"
    
    return skin_types, concerns, tone


def extract_attributes_from_review(row: pd.Series) -> Dict:
    """
    단일 리뷰에서 모든 속성 추출
    """
    review_text = row.get('gemini_normalized', '') or row.get('리뷰내용_정제', '')
    product_name = row.get('상품이름', '')
    existing_skin = row.get('피부타입', '')
    existing_shade = row.get('호수', '')
    
    # 기존 데이터에서 피부정보 파싱
    parsed_types, parsed_concerns, tone = parse_existing_skin_info(existing_skin)
    
    # 리뷰 텍스트에서 추가 속성 추출
    review_text_combined = f"{review_text} {product_name}"
    
    # 수치형 속성 추출
    coverage = extract_score_from_keywords(review_text, COVERAGE_KEYWORDS)
    longevity = extract_score_from_keywords(review_text, LONGEVITY_KEYWORDS)
    lightweight = extract_score_from_keywords(review_text, LIGHTWEIGHT_KEYWORDS)
    
    # 범주형 속성 - 리뷰에서 추가 추출
    review_skin_types = extract_categories(review_text, SKIN_TYPE_KEYWORDS)
    review_concerns = extract_categories(review_text, SKIN_CONCERNS_KEYWORDS)
    
    # 기존 데이터와 리뷰에서 추출한 데이터 병합
    all_skin_types = list(set(parsed_types + review_skin_types))
    all_concerns = list(set(parsed_concerns + review_concerns))
    
    # 제품 유형 - 제품명에서 추출
    product_type = extract_single_category(product_name, PRODUCT_TYPE_KEYWORDS)
    if not product_type:
        product_type = extract_single_category(review_text, PRODUCT_TYPE_KEYWORDS)
    
    # 호수
    shade = None
    if not pd.isna(existing_shade) and existing_shade:
        shade = str(existing_shade)
    else:
        shade = extract_single_category(review_text_combined, SHADE_KEYWORDS)
    
    return {
        'coverage': coverage,
        'longevity': longevity,
        'lightweight': lightweight,
        'skin_types': all_skin_types,
        'skin_concerns': all_concerns,
        'product_type': product_type,
        'shade': shade,
        'tone': tone
    }


def process_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """
    전체 리뷰 DataFrame 처리
    """
    print(f"Processing {len(df)} reviews...")
    
    # 속성 추출
    attributes_list = []
    for idx, row in df.iterrows():
        if idx % 5000 == 0:
            print(f"  Processing row {idx}...")
        attrs = extract_attributes_from_review(row)
        attributes_list.append(attrs)
    
    # 새 컬럼 추가
    df['attr_coverage'] = [a['coverage'] for a in attributes_list]
    df['attr_longevity'] = [a['longevity'] for a in attributes_list]
    df['attr_lightweight'] = [a['lightweight'] for a in attributes_list]
    df['attr_skin_types'] = [a['skin_types'] for a in attributes_list]
    df['attr_skin_concerns'] = [a['skin_concerns'] for a in attributes_list]
    df['attr_product_type'] = [a['product_type'] for a in attributes_list]
    df['attr_shade'] = [a['shade'] for a in attributes_list]
    df['attr_tone'] = [a['tone'] for a in attributes_list]
    
    return df


def main():
    """메인 실행 함수"""
    base_path = Path(__file__).parent.parent / "data"
    
    # 정규화된 리뷰 로드
    input_path = base_path / "reviews_normalized.plk"
    print(f"Loading reviews from {input_path}...")
    df = pd.read_pickle(input_path)
    
    # 속성 추출
    df_with_attrs = process_reviews(df)
    
    # 결과 저장
    output_path = base_path / "review_attributes.plk"
    df_with_attrs.to_pickle(output_path)
    print(f"Saved to {output_path}")
    
    # 통계 출력
    print("\n=== Extraction Statistics ===")
    print(f"Total reviews: {len(df_with_attrs)}")
    print(f"Coverage extracted: {df_with_attrs['attr_coverage'].notna().sum()} ({df_with_attrs['attr_coverage'].notna().mean()*100:.1f}%)")
    print(f"Longevity extracted: {df_with_attrs['attr_longevity'].notna().sum()} ({df_with_attrs['attr_longevity'].notna().mean()*100:.1f}%)")
    print(f"Lightweight extracted: {df_with_attrs['attr_lightweight'].notna().sum()} ({df_with_attrs['attr_lightweight'].notna().mean()*100:.1f}%)")
    print(f"Product type extracted: {df_with_attrs['attr_product_type'].notna().sum()} ({df_with_attrs['attr_product_type'].notna().mean()*100:.1f}%)")
    
    # 샘플 출력
    print("\n=== Sample Results ===")
    sample = df_with_attrs[['gemini_normalized', 'attr_coverage', 'attr_longevity', 'attr_lightweight', 'attr_product_type']].head(5)
    for idx, row in sample.iterrows():
        print(f"\nReview: {row['gemini_normalized'][:100]}...")
        print(f"  Coverage: {row['attr_coverage']}, Longevity: {row['attr_longevity']}, Lightweight: {row['attr_lightweight']}, Type: {row['attr_product_type']}")


if __name__ == "__main__":
    main()

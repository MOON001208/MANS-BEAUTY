"""
성분 위험도 매핑 모듈 (Ingredient Risk Mapping)
화장품 성분을 분석하여 피부타입별 호환성 점수를 계산합니다.

기능:
1. 자극 성분 / 안전 성분 분류
2. 피부타입별 주의 성분 매핑
3. 성분정도 점수 계산 (자연유래/저자극/일반)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Set, Optional
from pathlib import Path
import pickle

# ===== 성분 분류 데이터베이스 =====

# 자극 가능성이 있는 성분
IRRITANT_INGREDIENTS = {
    # 알코올류
    "변성알코올", "에탄올", "알코올", "이소프로필알코올",
    "Alcohol Denat", "Denatured Alcohol", "Ethanol", "Isopropyl Alcohol",
    
    # 향료/색소
    "향료", "인공향료", "Fragrance", "Parfum",
    "색소", "타르색소",
    
    # 파라벤류
    "메칠파라벤", "에칠파라벤", "프로필파라벤", "부틸파라벤",
    "Methylparaben", "Ethylparaben", "Propylparaben", "Butylparaben",
    
    # 황산염
    "소듐라우릴설페이트", "소듐라우레스설페이트",
    "SLS", "SLES", "Sodium Lauryl Sulfate", "Sodium Laureth Sulfate",
    
    # 기타 주의 성분
    "트라이에탄올아민", "TEA", "Triethanolamine",
    "벤조페논", "Benzophenone",
    "포름알데히드", "Formaldehyde",
}

# 안전/유익한 성분
SAFE_INGREDIENTS = {
    # 보습 성분
    "히알루론산", "Hyaluronic Acid", "소듐히알루로네이트",
    "세라마이드", "Ceramide",
    "글리세린", "Glycerin",
    "판테놀", "Panthenol", "D-판테놀",
    "베타인", "Betaine",
    
    # 진정 성분
    "알로에베라", "Aloe Vera", "알로에베라잎추출물",
    "센텔라아시아티카", "Centella Asiatica", "병풀추출물",
    "녹차추출물", "Green Tea Extract", "카멜리아시넨시스잎추출물",
    "티트리", "Tea Tree", "티트리잎오일",
    "카모마일", "Chamomile", "카모마일꽃추출물",
    
    # 항산화 성분
    "나이아신아마이드", "Niacinamide", "비타민B3",
    "토코페롤", "Tocopherol", "비타민E",
    "아스코빅애씨드", "Ascorbic Acid", "비타민C",
}

# 피부타입별 주의 성분
SKIN_TYPE_WARNINGS = {
    "oily": {
        # 모공 막힘 유발 성분 (코메도제닉)
        "코코넛오일", "Coconut Oil", "코코스누시페라오일",
        "미네랄오일", "Mineral Oil",
        "라놀린", "Lanolin",
        "이소프로필미리스테이트", "Isopropyl Myristate",
        "카카오버터", "Cocoa Butter",
    },
    "dry": {
        # 건조 유발 성분
        "변성알코올", "에탄올", "알코올",
        "Alcohol Denat", "Ethanol",
        "소듐라우릴설페이트", "SLS",
    },
    "sensitive": {
        # 민감피부 자극 성분
        "향료", "Fragrance", "Parfum",
        "색소", "인공색소",
        "에센셜오일", "Essential Oil",
        "멘톨", "Menthol",
        "캠퍼", "Camphor",
    },
    "combination": {
        # 복합성 피부는 지성 구역에 주의
        "미네랄오일", "Mineral Oil",
    }
}

# 자연유래 성분 패턴 (추출물, 오일 등)
NATURAL_PATTERNS = [
    "추출물", "Extract",
    "오일", "Oil",
    "버터", "Butter",
    "워터", "Water",
    "에센스", "Essence",
    "잎", "Leaf",
    "꽃", "Flower",
    "뿌리", "Root",
    "열매", "Fruit",
    "씨앗", "Seed",
]


@dataclass
class IngredientAnalysis:
    """성분 분석 결과"""
    product_name: str
    total_ingredients: int
    irritant_count: int
    irritant_list: List[str]
    safe_count: int
    safe_list: List[str]
    natural_count: int
    oily_warning_count: int
    dry_warning_count: int
    sensitive_warning_count: int
    ingredient_level: str  # "자연유래" | "저자극" | "일반"
    compatibility_scores: Dict[str, float]  # 피부타입별 호환성 점수


def check_ingredient_match(ingredient: str, target_set: Set[str]) -> bool:
    """성분이 타겟 세트에 포함되는지 확인 (부분 매칭 포함)"""
    ingredient_lower = ingredient.lower()
    for target in target_set:
        if target.lower() in ingredient_lower or ingredient_lower in target.lower():
            return True
    return False


def count_natural_ingredients(ingredients: List[str]) -> int:
    """자연유래 성분 개수 카운트"""
    count = 0
    for ing in ingredients:
        for pattern in NATURAL_PATTERNS:
            if pattern.lower() in ing.lower():
                count += 1
                break
    return count


def calculate_ingredient_level(analysis: 'IngredientAnalysis') -> str:
    """성분정도 레벨 계산"""
    if analysis.total_ingredients == 0:
        return "일반"
    
    natural_ratio = analysis.natural_count / analysis.total_ingredients
    irritant_ratio = analysis.irritant_count / analysis.total_ingredients
    
    # 자연유래 성분 비율이 높고 자극 성분이 적으면 "자연유래"
    if natural_ratio >= 0.3 and irritant_ratio <= 0.05:
        return "자연유래"
    # 자극 성분이 적으면 "저자극"
    elif irritant_ratio <= 0.1:
        return "저자극"
    else:
        return "일반"


def calculate_compatibility_scores(analysis: 'IngredientAnalysis') -> Dict[str, float]:
    """피부타입별 호환성 점수 계산 (0-1, 높을수록 좋음)"""
    scores = {}
    
    # 기본 점수 (자극 성분 기반)
    if analysis.total_ingredients == 0:
        base_score = 0.5
    else:
        irritant_ratio = analysis.irritant_count / analysis.total_ingredients
        base_score = max(0, 1 - irritant_ratio * 5)  # 자극 성분 20%면 0점
    
    # 지성 피부 점수
    oily_penalty = min(analysis.oily_warning_count * 0.1, 0.3)
    scores["oily"] = max(0, base_score - oily_penalty)
    
    # 건성 피부 점수
    dry_penalty = min(analysis.dry_warning_count * 0.15, 0.4)
    scores["dry"] = max(0, base_score - dry_penalty)
    
    # 민감성 피부 점수
    sensitive_penalty = min(analysis.sensitive_warning_count * 0.15, 0.5)
    scores["sensitive"] = max(0, base_score - sensitive_penalty)
    
    # 복합성 피부 점수 (지성과 건성의 평균)
    scores["combination"] = (scores["oily"] + scores["dry"]) / 2
    
    return scores


def analyze_ingredients(product_name: str, ingredients: List[str]) -> IngredientAnalysis:
    """단일 제품의 성분 분석"""
    irritants = []
    safe = []
    
    oily_warnings = 0
    dry_warnings = 0
    sensitive_warnings = 0
    
    for ing in ingredients:
        # 자극 성분 체크
        if check_ingredient_match(ing, IRRITANT_INGREDIENTS):
            irritants.append(ing)
        
        # 안전 성분 체크
        if check_ingredient_match(ing, SAFE_INGREDIENTS):
            safe.append(ing)
        
        # 피부타입별 주의 성분 체크
        if check_ingredient_match(ing, SKIN_TYPE_WARNINGS.get("oily", set())):
            oily_warnings += 1
        if check_ingredient_match(ing, SKIN_TYPE_WARNINGS.get("dry", set())):
            dry_warnings += 1
        if check_ingredient_match(ing, SKIN_TYPE_WARNINGS.get("sensitive", set())):
            sensitive_warnings += 1
    
    natural_count = count_natural_ingredients(ingredients)
    
    analysis = IngredientAnalysis(
        product_name=product_name,
        total_ingredients=len(ingredients),
        irritant_count=len(irritants),
        irritant_list=irritants,
        safe_count=len(safe),
        safe_list=safe,
        natural_count=natural_count,
        oily_warning_count=oily_warnings,
        dry_warning_count=dry_warnings,
        sensitive_warning_count=sensitive_warnings,
        ingredient_level="",  # 아래에서 계산
        compatibility_scores={}  # 아래에서 계산
    )
    
    analysis.ingredient_level = calculate_ingredient_level(analysis)
    analysis.compatibility_scores = calculate_compatibility_scores(analysis)
    
    return analysis


def process_products(df: pd.DataFrame) -> pd.DataFrame:
    """전체 제품 DataFrame 성분 분석"""
    print(f"Processing {len(df)} products...")
    
    results = []
    for idx, row in df.iterrows():
        ingredients = row.get('ingredients_list', [])
        if ingredients is None or len(ingredients) == 0:
            continue
        
        product_name = row['product_name']
        analysis = analyze_ingredients(product_name, ingredients)
        
        results.append({
            'product_name': product_name,
            'total_ingredients': analysis.total_ingredients,
            'irritant_count': analysis.irritant_count,
            'irritant_list': analysis.irritant_list,
            'safe_count': analysis.safe_count,
            'safe_list': analysis.safe_list,
            'natural_count': analysis.natural_count,
            'ingredient_level': analysis.ingredient_level,
            'compat_oily': analysis.compatibility_scores.get('oily', 0.5),
            'compat_dry': analysis.compatibility_scores.get('dry', 0.5),
            'compat_sensitive': analysis.compatibility_scores.get('sensitive', 0.5),
            'compat_combination': analysis.compatibility_scores.get('combination', 0.5),
        })
    
    return pd.DataFrame(results)


def main():
    """메인 실행 함수"""
    base_path = Path(__file__).parent.parent / "data"
    
    # 성분 데이터 로드
    input_path = base_path / "product_ingredients_clean.plk"
    print(f"Loading ingredients from {input_path}...")
    df = pd.read_pickle(input_path)
    
    # 성분 분석
    df_analyzed = process_products(df)
    
    # 결과 저장
    output_path = base_path / "ingredient_risk_mapping.plk"
    df_analyzed.to_pickle(output_path)
    print(f"Saved to {output_path}")
    
    # CSV로도 저장 (가독성을 위해)
    csv_path = base_path / "ingredient_risk_mapping.csv"
    df_analyzed.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"Saved to {csv_path}")
    
    # 통계 출력
    print("\n=== Analysis Statistics ===")
    print(f"Total products analyzed: {len(df_analyzed)}")
    print(f"\nIngredient Level Distribution:")
    print(df_analyzed['ingredient_level'].value_counts())
    
    print(f"\nAverage Compatibility Scores:")
    for col in ['compat_oily', 'compat_dry', 'compat_sensitive', 'compat_combination']:
        print(f"  {col}: {df_analyzed[col].mean():.3f}")
    
    # 샘플 출력
    print("\n=== Sample Results ===")
    sample = df_analyzed[['product_name', 'ingredient_level', 'irritant_count', 'safe_count', 'compat_sensitive']].head(5)
    print(sample.to_string())


if __name__ == "__main__":
    main()

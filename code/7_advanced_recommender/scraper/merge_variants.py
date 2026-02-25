"""
상품 병합 스크립트 (merge_variants.py)
동일 상품의 변형(리필, 기획세트 등)을 본품으로 합칩니다.

예시:
- "비레디 블루 쿠션 4세대 15g" (본품)
- "비레디 블루 쿠션 4세대 리필 15g" → 본품으로 병합
- "오브제 내추럴 커버 파운데이션 기획세트(+클렌징폼 50ml)" → 본품으로 병합

병합 규칙:
1. 상품명에서 "리필", "기획", "세트" 등 접미사를 제거해 정규화
2. 같은 브랜드 + 정규화된 이름이 같은 상품끼리 그룹핑
3. 그룹 내에서 본품(리필/기획이 아닌) 선택 → 리뷰 수 합산, 리뷰 재맵핑
4. 변형 상품 삭제
"""
import os
import re
import logging
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== 상품명 정규화 ==========
def normalize_name(name: str) -> str:
    """상품명에서 변형 식별자를 제거하여 정규화 (병합용)"""
    normalized = name

    # 1. 프로모션 태그 제거: [2월올영픽/1등파데], [NEW/덱스PICK], [덱스 PICK] 등
    normalized = re.sub(r'\[.*?\]', '', normalized)

    # 2. 괄호와 그 안의 내용 제거 (SPF 정보나 기획 등의 부가정보가 많음)
    # 예: (SPF 34 PA++), (+클렌징폼 50ml), (리필포함) 등은 병합 비교에서 제외
    normalized = re.sub(r'\(.*?\)', '', normalized)

    # 3. 키워드 제거
    variant_keywords = [
        r'리필용?', r'기획세트?', r'기획', r'세트',
        r'단품', r'본품', r'증정', r'추가', r'리뉴얼',
    ]
    for kw in variant_keywords:
        normalized = re.sub(kw, ' ', normalized)

    # 4. 용량 및 기타 기술 정보 제거
    normalized = re.sub(r'\d+\s*(g|ml|매|호)', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'SPF\s*\d+\+?\s*,?\s*PA\+*', '', normalized, flags=re.IGNORECASE)

    # 5. N종 택1 제거
    normalized = re.sub(r'\d+종\s*택\s*\d+', '', normalized)

    # 6. 특수문자 제거 및 공백 정규화 (동일성 비교를 위해 극단적으로 정준화)
    normalized = re.sub(r'[^가-힣a-zA-Z0-9]', ' ', normalized)
    normalized = re.sub(r'\s+', '', normalized).strip()

    return normalized


def is_variant(name: str) -> bool:
    """제품이 변형(리필/기획/세트)인지 판별 (본품 선정을 위한 로직)"""
    variant_patterns = [
        r'리필',
        r'기획세트',
        r'기획\s*\(',
        r'\+',  # +클렌징폼
        r'추가\s*증정',
    ]
    for p in variant_patterns:
        if re.search(p, name):
            return True
    return False


# ========== 메인 병합 로직 ==========
def merge_products():
    """Supabase에서 상품을 가져와 변형을 본품으로 병합"""

    # 1. 모든 상품 조회
    result = supabase.table("products").select("*").execute()
    products = result.data
    logging.info(f"총 {len(products)}개 상품 조회")

    # 2. 브랜드 + 정규화된 이름으로 그룹핑
    groups = {}
    for p in products:
        key = (p["brand"], normalize_name(p["name"]))
        if key not in groups:
            groups[key] = []
        groups[key].append(p)

    # 3. 2개 이상인 그룹만 병합 대상
    merge_count = 0
    for (brand, norm_name), group in groups.items():
        if len(group) < 2:
            continue

        logging.info(f"\n{'='*50}")
        logging.info(f"병합 그룹: [{brand}] {norm_name}")
        for p in group:
            logging.info(f"  - {p['name']} (ID: {p['id']}, 리뷰: {p.get('review_count', 0)})")

        # 4. 본품 선택: 변형이 아닌 것 우선, 그 중 리뷰 수 가장 많은 것
        non_variants = [p for p in group if not is_variant(p["name"])]
        if non_variants:
            # 비변형 중 리뷰 수 최다
            main_product = max(non_variants, key=lambda x: x.get("review_count", 0) or 0)
        else:
            # 모두 변형이면 리뷰 수 최다
            main_product = max(group, key=lambda x: x.get("review_count", 0) or 0)

        variant_products = [p for p in group if p["id"] != main_product["id"]]

        logging.info(f"  ✅ 본품: {main_product['name']} (ID: {main_product['id']})")

        # 5. 변형의 리뷰를 본품으로 재맵핑
        total_merged_reviews = 0
        for variant in variant_products:
            variant_id = variant["id"]
            logging.info(f"  🔄 병합: {variant['name']} (ID: {variant_id})")

            # 리뷰의 product_id를 본품 ID로 변경
            try:
                update_result = supabase.table("reviews").update({
                    "product_id": main_product["id"]
                }).eq("product_id", variant_id).execute()
                merged = len(update_result.data) if update_result.data else 0
                total_merged_reviews += merged
                logging.info(f"    → 리뷰 {merged}개 재맵핑")
            except Exception as e:
                logging.error(f"    → 리뷰 재맵핑 오류: {e}")

            # 변형 상품 삭제
            try:
                supabase.table("products").delete().eq("id", variant_id).execute()
                logging.info(f"    → 상품 삭제 완료")
            except Exception as e:
                logging.error(f"    → 상품 삭제 오류: {e}")

        # 6. 본품의 리뷰 수 업데이트 (합산)
        total_reviews = sum(p.get("review_count", 0) or 0 for p in group)
        try:
            supabase.table("products").update({
                "review_count": total_reviews
            }).eq("id", main_product["id"]).execute()
            logging.info(f"  📊 총 리뷰 수 업데이트: {total_reviews}")
        except Exception as e:
            logging.error(f"  리뷰 수 업데이트 오류: {e}")

        merge_count += len(variant_products)

    logging.info(f"\n{'='*50}")
    logging.info(f"병합 완료: {merge_count}개 변형 상품 → 본품으로 통합")

    # 최종 상품 수 확인
    final = supabase.table("products").select("id", count="exact").execute()
    logging.info(f"최종 상품 수: {final.count}개")


if __name__ == "__main__":
    merge_products()

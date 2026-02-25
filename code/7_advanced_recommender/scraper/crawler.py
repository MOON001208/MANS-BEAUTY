"""
올리브영 맨즈케어 크롤러 v2
- 쿠션/파운데이션 + 톤로션/BB 전체 수집
- 상품 정보 + 리뷰 + 전성분 수집
- Supabase에 저장
"""
import os
import re
import time
import math
import json
import logging
from bs4 import BeautifulSoup
from curl_cffi import requests as cf_requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ========== Config ==========
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    logging.info("Supabase 연결 성공")
else:
    logging.warning("Supabase 자격증명 없음 - .env 파일 확인")

# 올리브영 맨즈케어 > 메이크업 하위 카테고리
CATEGORIES = {
    "1000001000700080011": "쿠션/파운데이션",
    "1000001000700080015": "톤 로션/BB",
}

REVIEWS_URL = "https://m.oliveyoung.co.kr/review/api/v2/reviews"

COMMON_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "origin": "https://www.oliveyoung.co.kr",
    "referer": "https://www.oliveyoung.co.kr/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}


# ========== 1. 상품 목록 수집 ==========
def get_all_products(disp_cat_no: str, category_name: str) -> list[dict]:
    """특정 카테고리의 모든 상품 수집 (페이지네이션)"""
    all_products = []
    page = 1

    while True:
        url = f"https://www.oliveyoung.co.kr/store/display/getMCategoryList.do?dispCatNo={disp_cat_no}&pageIdx={page}&rowsPerPage=48"
        logging.info(f"  [{category_name}] Page {page} 수집 중...")

        try:
            res = cf_requests.get(url, impersonate="chrome124")
            soup = BeautifulSoup(res.text, "html.parser")
            items = soup.select("div.prd_info")

            if not items:
                logging.info(f"  [{category_name}] Page {page} - 상품 없음, 종료")
                break

            for item in items:
                a_tag = item.select_one("a.prd_thumb")
                if not a_tag:
                    continue

                goods_no = a_tag.get("data-ref-goodsno", "")
                if not goods_no:
                    # href에서 추출 시도
                    href = a_tag.get("href", "")
                    m = re.search(r"goodsNo=([A-Z0-9]+)", href)
                    goods_no = m.group(1) if m else ""

                if not goods_no:
                    continue

                name_el = item.select_one("p.tx_name")
                brand_el = item.select_one("span.tx_brand")
                price_el = item.select_one("span.tx_cur span.tx_num")
                org_price_el = item.select_one("span.tx_org span.tx_num")
                img_el = item.select_one("img")

                name = name_el.text.strip() if name_el else ""
                brand = brand_el.text.strip() if brand_el else ""
                price_str = price_el.text.strip().replace(",", "") if price_el else "0"
                org_price_str = org_price_el.text.strip().replace(",", "") if org_price_el else price_str

                try:
                    price = int(price_str)
                except ValueError:
                    price = 0
                try:
                    original_price = int(org_price_str)
                except ValueError:
                    original_price = price

                img_url = img_el.get("src", "") if img_el else ""
                product_url = f"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo={goods_no}"

                # 제품 유형 추론
                product_type = "liquid"  # default
                name_lower = name.lower()
                if "쿠션" in name_lower or "cushion" in name_lower:
                    product_type = "cushion"
                elif "스틱" in name_lower or "stick" in name_lower:
                    product_type = "stick"
                elif "톤로션" in name_lower or "bb" in name_lower or "비비" in name_lower:
                    product_type = "tone_lotion"

                all_products.append({
                    "id": goods_no,
                    "name": name,
                    "brand": brand,
                    "category": category_name,
                    "price": price,
                    "original_price": original_price,
                    "thumbnail_url": img_url,
                    "product_url": product_url,
                    "product_type": product_type,
                })

            # 같은 페이지면 더 이상 없음
            if len(items) < 24:
                break

            page += 1
            time.sleep(1)

        except Exception as e:
            logging.error(f"  상품 목록 수집 오류 (page {page}): {e}")
            break

    # ID 기준 중복 제거
    seen = set()
    unique = []
    for p in all_products:
        if p["id"] not in seen:
            seen.add(p["id"])
            unique.append(p)

    logging.info(f"  [{category_name}] 총 {len(unique)}개 상품 수집 완료")
    return unique


# ========== 2. 상품 상세 (별점, 리뷰수) ==========
def fetch_product_stats(goods_no: str) -> dict:
    """리뷰 통계 API에서 별점과 리뷰 수 가져오기"""
    url = f"https://m.oliveyoung.co.kr/review/api/v2/reviews/{goods_no}/stats"
    try:
        res = cf_requests.get(url, headers=COMMON_HEADERS, impersonate="chrome124")
        res.raise_for_status()
        data = res.json().get("data", {})
        rating_dist = data.get("ratingDistribution", {})
        return {
            "review_count": data.get("reviewCount", 0),
            "star_rating": rating_dist.get("averageRating", 0),
        }
    except Exception as e:
        logging.warning(f"  Stats 조회 실패 ({goods_no}): {e}")
        return {"review_count": 0, "star_rating": 0}


# ========== 3. 전성분 수집 ==========
def fetch_ingredients(goods_no: str) -> str:
    """상품 상세 페이지에서 전성분 텍스트 추출"""
    url = f"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo={goods_no}"
    try:
        res = cf_requests.get(url, impersonate="chrome124")
        soup = BeautifulSoup(res.text, "html.parser")

        # 전성분 영역 찾기 (여러 셀렉터 시도)
        # 방법 1: "전성분" 텍스트 이후의 내용
        for tag in soup.find_all(["dt", "th", "strong", "span", "p"]):
            text = tag.get_text(strip=True)
            if "전성분" in text or "전 성분" in text:
                # 다음 형제 요소에서 성분 추출
                next_el = tag.find_next(["dd", "td", "div", "p"])
                if next_el:
                    ingredients = next_el.get_text(strip=True)
                    if len(ingredients) > 10:
                        return ingredients

        # 방법 2: 상품 상세 텍스트에서 성분 패턴 추출
        detail_area = soup.select_one("#artcInfo, .goods_detail_cont, .tabConts")
        if detail_area:
            full_text = detail_area.get_text()
            # "전성분" 이후 텍스트 추출
            match = re.search(r"전\s*성\s*분[:\s]*(.+?)(?=\n\n|\Z)", full_text, re.DOTALL)
            if match:
                return match.group(1).strip()[:2000]

    except Exception as e:
        logging.warning(f"  전성분 수집 실패 ({goods_no}): {e}")

    return ""


# ========== 피부 코드 디코딩 ==========
SKIN_TYPE_CODES = {
    "A01": "건성", "A02": "지성", "A03": "복합성", "A04": "중성", "A05": "민감성",
}
SKIN_TONE_CODES = {
    "B01": "쿨톤", "B02": "웜톤", "B03": "뉴트럴",
}
SKIN_TROUBLE_CODES = {
    "C01": "건조함", "C02": "여드름", "C03": "모공", "C04": "블랙헤드",
    "C05": "미백", "C06": "주름", "C07": "탄력", "C08": "다크서클",
    "C09": "홍조", "C10": "잡티", "C11": "각질",
}


# ========== 4. 리뷰 수집 ==========
def get_existing_review_ids(goods_no: str) -> set:
    """Supabase에서 이미 수집된 리뷰 ID 목록 조회"""
    if not supabase:
        return set()
    try:
        result = supabase.table("reviews").select("id").eq("product_id", goods_no).execute()
        return {r["id"] for r in result.data}
    except Exception as e:
        logging.warning(f"  기존 리뷰 ID 조회 실패: {e}")
        return set()


def fetch_reviews(goods_no: str, total_review_count: int, existing_ids: set = None) -> list[dict]:
    """리뷰 API에서 리뷰 전체 수집 (증분: 이미 수집된 리뷰 ID가 나오면 중단)"""
    page_size = 10
    total_pages = math.ceil(total_review_count / page_size)
    all_reviews = []
    hit_existing = False
    
    # 중간에 끊겨서 수집된 리뷰가 전체 목표치보다 50개 이상 부족하면, 중단(break)하지 않고 중복만 건너뜀
    is_interrupted = existing_ids and (total_review_count - len(existing_ids) > 50)

    review_headers = COMMON_HEADERS.copy()
    review_headers["content-type"] = "application/json"

    for page in range(1, total_pages + 1):
        payload = {
            "goodsNumber": goods_no,
            "page": page,
            "size": page_size,
            "sortType": "USEFUL_SCORE_DESC",
            "reviewType": "ALL",
        }

        try:
            res = cf_requests.post(REVIEWS_URL, headers=review_headers, json=payload, impersonate="chrome124")
            res.raise_for_status()
            data = res.json()

            reviews_list = data.get("data", [])
            if not reviews_list:
                break

            for review in reviews_list:
                # 실제 API 필드: reviewId, reviewScore, profileDto, goodsDto, createdDateTime
                review_id = str(review.get("reviewId", ""))
                if not review_id:
                    continue

                # 증분 수집: 이미 수집된 리뷰면 스킵
                if existing_ids and review_id in existing_ids:
                    if not is_interrupted:
                        hit_existing = True
                        break
                    else:
                        continue # 중간에 끊겼던 거면 스킵만 하고 다음 리뷰 계속 확인

                # 프로필에서 피부 정보 추출
                profile = review.get("profileDto", {}) or {}
                skin_type_code = profile.get("skinType", "")
                skin_tone_code = profile.get("skinTone", "")
                skin_trouble_codes = profile.get("skinTrouble", []) or []

                # 코드 → 한글 변환
                skin_type = SKIN_TYPE_CODES.get(skin_type_code, skin_type_code)
                skin_tone = SKIN_TONE_CODES.get(skin_tone_code, skin_tone_code)
                skin_troubles = [SKIN_TROUBLE_CODES.get(c, c) for c in skin_trouble_codes]
                skin_trouble = ",".join(skin_troubles) if skin_troubles else None

                # 옵션명
                goods_dto = review.get("goodsDto", {}) or {}
                option_name = goods_dto.get("optionName", "")

                all_reviews.append({
                    "id": review_id,
                    "product_id": goods_no,
                    "author": profile.get("memberNickname", "Anonymous"),
                    "rating": int(review.get("reviewScore", 0)),
                    "content": review.get("content", ""),
                    "skin_type": skin_type if skin_type else None,
                    "skin_tone": skin_tone if skin_tone else None,
                    "skin_trouble": skin_trouble,
                    "option_name": option_name,
                    "is_best": False,
                    "created_at": review.get("createdDateTime"),
                })

            time.sleep(0.3)

            # 이미 수집된 리뷰에 도달하면 종료
            if hit_existing:
                logging.info(f"  ✋ 이미 수집된 리뷰 도달 - 증분 수집 완료 (page {page})")
                break

        except Exception as e:
            logging.warning(f"  리뷰 수집 오류 ({goods_no}, page {page}): {e}")
            break

    return all_reviews


# ========== 5. Supabase 저장 ==========
def save_product_to_supabase(product: dict):
    """상품을 Supabase에 upsert"""
    if not supabase:
        return

    try:
        supabase.table("products").upsert({
            "id": product["id"],
            "name": product["name"],
            "brand": product["brand"],
            "category": product["category"],
            "price": product["price"],
            "original_price": product.get("original_price"),
            "star_rating": product.get("star_rating"),
            "review_count": product.get("review_count"),
            "thumbnail_url": product["thumbnail_url"],
            "product_url": product["product_url"],
            "product_type": product.get("product_type"),
            "ingredients_raw": product.get("ingredients_raw", ""),
        }).execute()
    except Exception as e:
        logging.error(f"  상품 저장 오류 ({product['id']}): {e}")


def save_reviews_to_supabase(reviews: list[dict]):
    """리뷰 배치를 Supabase에 upsert"""
    if not supabase or not reviews:
        return

    try:
        # 배치로 저장 (50개씩)
        batch_size = 50
        for i in range(0, len(reviews), batch_size):
            batch = reviews[i:i + batch_size]
            supabase.table("reviews").upsert(batch).execute()
    except Exception as e:
        logging.error(f"  리뷰 저장 오류: {e}")


# ========== Main ==========
def main():
    if not supabase:
        logging.error("Supabase 연결 불가. .env 파일을 확인하세요.")
        return

    total_products = 0
    total_reviews = 0

    for cat_id, cat_name in CATEGORIES.items():
        logging.info(f"{'='*60}")
        logging.info(f"카테고리: {cat_name} ({cat_id})")
        logging.info(f"{'='*60}")

        # 1. 상품 목록 수집
        products = get_all_products(cat_id, cat_name)

        for idx, product in enumerate(products, 1):
            goods_no = product["id"]
            logging.info(f"\n[{idx}/{len(products)}] {product['brand']} - {product['name']}")

            # 2. 리뷰 통계 (별점, 리뷰 수)
            stats = fetch_product_stats(goods_no)
            product["star_rating"] = stats["star_rating"]
            product["review_count"] = stats["review_count"]
            logging.info(f"  ⭐ {stats['star_rating']:.1f} | 리뷰 {stats['review_count']}개")

            # 3. 전성분 수집
            ingredients = fetch_ingredients(goods_no)
            product["ingredients_raw"] = ingredients
            if ingredients:
                logging.info(f"  🧪 전성분: {ingredients[:60]}...")
            else:
                logging.info(f"  🧪 전성분: 미수집")

            # 4. 상품 저장
            save_product_to_supabase(product)

            # 5. 리뷰 수집 (전체 / 증분)
            if stats["review_count"] > 0:
                existing_ids = get_existing_review_ids(goods_no)
                new_needed = stats["review_count"] - len(existing_ids)
                if new_needed > 0:
                    logging.info(f"  💬 기존 {len(existing_ids)}개 / 신규 약 {new_needed}개 수집 시작")
                    reviews = fetch_reviews(goods_no, stats["review_count"], existing_ids)
                    save_reviews_to_supabase(reviews)
                    total_reviews += len(reviews)
                    logging.info(f"  💬 신규 리뷰 {len(reviews)}개 저장 완료")
                else:
                    logging.info(f"  💬 이미 전체 수집됨 ({len(existing_ids)}개) - 스킵")
            else:
                logging.info(f"  💬 리뷰 없음")

            total_products += 1
            time.sleep(0.5)

    logging.info(f"\n{'='*60}")
    logging.info(f"크롤링 완료!")
    logging.info(f"  총 상품: {total_products}개")
    logging.info(f"  총 리뷰: {total_reviews}개")
    logging.info(f"{'='*60}")


if __name__ == "__main__":
    main()

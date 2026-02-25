"""
제품 프로필 구축 파이프라인 (build_profiles.py)
=========================================
Supabase에서 리뷰 데이터를 가져와 Gemini API로 분석한 뒤
각 제품의 추천 프로필 점수를 계산하여 DB에 업데이트합니다.

처리 순서:
  1. Supabase에서 products / reviews 로드
  2. (선택) 리뷰 텍스트를 Gemini 배치 API로 속성 추출
     - coverage(커버력), longevity(지속력), lightweight(착용감) → 1~5점
     - skin_types, skin_concerns, shade, sentiment
  3. 리뷰 구조 데이터(skin_type / skin_trouble / option_name) 직접 활용
  4. 성분(ingredients_raw) 분석 → 피부타입별 호환성 점수
  5. 제품별 집계 → products 테이블 UPDATE
"""

import os
import re
import json
import time
import logging
import pickle
from pathlib import Path
from typing import Optional
from collections import Counter

import numpy as np
from dotenv import load_dotenv
from supabase import create_client, Client

# Gemini
from google import genai

# ──────────────────────────────────────────────
# 환경 설정
# ──────────────────────────────────────────────
load_dotenv()

import sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)
# 실시간 출력을 위해 버퍼링 해제
for handler in logging.root.handlers:
    if hasattr(handler, 'stream'):
        handler.stream = sys.stdout

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# 체크포인트 경로 (중단 시 이어받기)
CHECKPOINT_PATH = Path(__file__).parent / "gemini_checkpoint.pkl"

# 상품별 최대 분석 리뷰 수 (비용/시간 제어)
MAX_REVIEWS_PER_PRODUCT = 300
GEMINI_BATCH_SIZE = 10       # 배치당 리뷰 수
GEMINI_DELAY = 0.8           # 배치 간 대기 (초) – rate limit 방지
GEMINI_MODEL = "gemini-2.0-flash-lite"

# ──────────────────────────────────────────────
# ① 성분 분석 (ingredient_risk_mapper 로직 내장)
# ──────────────────────────────────────────────

IRRITANT_INGREDIENTS = {
    "변성알코올", "에탄올", "알코올", "이소프로필알코올",
    "alcohol denat", "denatured alcohol", "ethanol", "isopropyl alcohol",
    "향료", "인공향료", "fragrance", "parfum",
    "메칠파라벤", "에칠파라벤", "프로필파라벤", "부틸파라벤",
    "methylparaben", "ethylparaben", "propylparaben", "butylparaben",
    "소듐라우릴설페이트", "소듐라우레스설페이트", "sls", "sles",
    "sodium lauryl sulfate", "sodium laureth sulfate",
    "트라이에탄올아민", "tea", "triethanolamine",
    "벤조페논", "benzophenone",
    "포름알데히드", "formaldehyde",
}

SKIN_TYPE_WARNINGS = {
    "oily": {"코코넛오일", "coconut oil", "미네랄오일", "mineral oil", "라놀린",
              "lanolin", "이소프로필미리스테이트", "isopropyl myristate", "카카오버터", "cocoa butter"},
    "dry":  {"변성알코올", "에탄올", "알코올", "alcohol denat", "ethanol",
              "소듐라우릴설페이트", "sls"},
    "sensitive": {"향료", "fragrance", "parfum", "에센셜오일", "essential oil",
                  "멘톨", "menthol", "캠퍼", "camphor"},
}

NATURAL_PATTERNS = ["추출물", "extract", "오일", "oil", "버터", "butter",
                    "워터", "water", "에센스", "essence", "잎", "꽃", "뿌리", "열매", "씨앗"]


def analyze_ingredients(ingredients_raw: str) -> dict:
    """
    전성분 텍스트를 쉼표로 분리하여 피부타입별 호환성 점수를 반환합니다.
    반환: {compat_oily, compat_dry, compat_sensitive, compat_combination, ingredient_level}
    """
    if not ingredients_raw or len(ingredients_raw.strip()) < 5:
        return dict(compat_oily=0.5, compat_dry=0.5, compat_sensitive=0.5,
                    compat_combination=0.5, ingredient_level="일반")

    # 쉼표/줄바꿈으로 분리, 소문자 변환
    ingredients = [i.strip().lower() for i in re.split(r"[,\n]+", ingredients_raw) if i.strip()]
    total = len(ingredients)
    if total == 0:
        return dict(compat_oily=0.5, compat_dry=0.5, compat_sensitive=0.5,
                    compat_combination=0.5, ingredient_level="일반")

    # 자극 성분 카운트
    irritant_count = sum(
        1 for ing in ingredients
        if any(irr in ing for irr in IRRITANT_INGREDIENTS)
    )

    # 자연유래 카운트
    natural_count = sum(
        1 for ing in ingredients
        if any(pat in ing for pat in NATURAL_PATTERNS)
    )

    # 피부타입별 주의 성분 카운트
    warn = {st: sum(1 for ing in ingredients if any(w in ing for w in warns))
            for st, warns in SKIN_TYPE_WARNINGS.items()}

    # 기본 점수
    irritant_ratio = irritant_count / total
    base_score = max(0.0, 1.0 - irritant_ratio * 5)

    scores = {
        "compat_oily":        round(max(0.0, base_score - min(warn["oily"] * 0.10, 0.30)), 3),
        "compat_dry":         round(max(0.0, base_score - min(warn["dry"]  * 0.15, 0.40)), 3),
        "compat_sensitive":   round(max(0.0, base_score - min(warn["sensitive"] * 0.15, 0.50)), 3),
    }
    scores["compat_combination"] = round((scores["compat_oily"] + scores["compat_dry"]) / 2, 3)

    # 성분 등급
    natural_ratio = natural_count / total
    if natural_ratio >= 0.3 and irritant_ratio <= 0.05:
        level = "자연유래"
    elif irritant_ratio <= 0.1:
        level = "저자극"
    else:
        level = "일반"

    scores["ingredient_level"] = level
    return scores


# ──────────────────────────────────────────────
# ② Gemini 배치 추출 (review text → 속성)
# ──────────────────────────────────────────────

BATCH_PROMPT = """당신은 화장품 리뷰 분석 전문가입니다. 다음 {count}개의 남성 화장품 리뷰를 분석하고, 각 리뷰에 대해 속성을 아래 형식으로 추출해주세요.

### 추출 속성:
1. coverage (커버력): 1~5점 (1=쌩얼/투명, 5=풀커버). 언급 없으면 null
2. longevity (지속력): 1~5점 (1=금방 무너짐, 5=하루종일). 언급 없으면 null
3. lightweight (착용감): 1~5점 (1=무겁고 답답, 5=가볍고 산뜻). 언급 없으면 null
4. skin_concerns: ["acne","pore","redness","spots","wrinkle"] 중 해당되는 것들 (배열)
5. shade: "21","23","25" 중 하나 또는 null (호수 언급 있을 때)
6. sentiment: "positive","neutral","negative" 중 하나

### 리뷰 목록:
{reviews_json}

### 응답 형식 (JSON 배열만, 설명 없이):
[
  {{"coverage":4,"longevity":3,"lightweight":4,"skin_concerns":["pore"],"shade":"23","sentiment":"positive"}},
  ...
]"""

DEFAULT_ATTR = {
    "coverage": None, "longevity": None, "lightweight": None,
    "skin_concerns": [], "shade": None, "sentiment": "neutral",
}


def _call_gemini_batch(reviews_data: list) -> list:
    """Gemini에 배치 리뷰를 보내고 속성 배열을 받습니다."""
    reviews_json = json.dumps(
        [{"id": i, "product": r["product_name"], "review": r["content"][:300]}
         for i, r in enumerate(reviews_data)],
        ensure_ascii=False,
    )
    prompt = BATCH_PROMPT.format(count=len(reviews_data), reviews_json=reviews_json)

    try:
        resp = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"temperature": 0.1, "max_output_tokens": 2000},
        )
        text = resp.text.strip()
        # ```json ... ``` 제거
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        results = json.loads(text)
        # 개수 맞추기
        if len(results) != len(reviews_data):
            results = (results + [DEFAULT_ATTR] * len(reviews_data))[:len(reviews_data)]
        return results
    except Exception as e:
        logging.warning(f"    Gemini 오류 (기본값 사용): {e}")
        return [DEFAULT_ATTR.copy() for _ in reviews_data]


def extract_attributes_for_product(product_id: str, product_name: str, reviews: list) -> list:
    """
    상품의 리뷰 목록을 Gemini로 배치 분석.
    체크포인트에서 이어받기 지원.
    반환: 리뷰별 속성 dict 목록 (reviews와 같은 순서)
    """
    total = len(reviews)
    all_results = []

    for batch_start in range(0, total, GEMINI_BATCH_SIZE):
        batch = reviews[batch_start:batch_start + GEMINI_BATCH_SIZE]
        batch_data = [{"product_name": product_name, "content": r.get("content", "")} for r in batch]

        for attempt in range(3):
            try:
                results = _call_gemini_batch(batch_data)
                all_results.extend(results)
                break
            except Exception:
                if attempt < 2:
                    time.sleep((attempt + 1) * 5)
                else:
                    all_results.extend([DEFAULT_ATTR.copy() for _ in batch])

        logging.info(f"    배치 {batch_start//GEMINI_BATCH_SIZE + 1}/{(total-1)//GEMINI_BATCH_SIZE + 1} 완료")
        time.sleep(GEMINI_DELAY)

    return all_results


# ──────────────────────────────────────────────
# ③ 구조 데이터 → 피부타입/호수 분석
#    reviews 테이블의 skin_type, skin_trouble, option_name 칼럼 활용
# ──────────────────────────────────────────────

# 올리브영 피부타입 코드 → 표준 매핑
SKIN_TYPE_MAP = {
    "건성": "dry", "지성": "oily", "복합성": "combination",
    "중성": "combination", "민감성": "sensitive",
}

SKIN_TROUBLE_MAP = {
    "여드름": "acne", "모공": "pore", "홍조": "redness",
    "잡티": "spots", "주름": "wrinkle", "트러블": "acne",
    "다크서클": "spots", "칙칙함": "spots"
}

# 옵션명 → 호수 매핑
SHADE_OPTION_PATTERNS = {
    "21": ["1호", "21호", "21", "라이트베이지", "라이트", "아이보리"],
    "23": ["2호", "23호", "23", "베이지", "뉴트럴베이지", "내추럴베이지"],
    "25": ["3호", "25호", "25", "샌드베이지", "샌드", "탠", "앰버베이지"],
}

BRIGHT_KEYWORDS = ["밝다", "밝아", "하얘", "밝네", "부담", "티나", "백탁"]
DARK_KEYWORDS = ["어둡다", "어두워", "칙칙", "검어", "어둡네"]


def get_shade_from_option(option_name: str) -> Optional[str]:
    """옵션명에서 호수 추출"""
    if not option_name:
        return None
    opt = option_name.lower()
    for shade, patterns in SHADE_OPTION_PATTERNS.items():
        if any(p.lower() in opt for p in patterns):
            return shade
    return None


def aggregate_product_profile(
    product: dict,
    reviews: list,
    gemini_attrs: list,
) -> dict:
    """
    리뷰 데이터 + Gemini 속성을 집계하여 products 테이블 업데이트용 딕셔너리 생성.
    """

    n = len(reviews)
    if n == 0:
        return {}

    # ── 수치형 점수 집계 (Gemini 추출) ──────────────
    def safe_mean(vals):
        non_null = [v for v in vals if v is not None]
        return round(float(np.mean(non_null)), 2) if non_null else 3.0

    coverage_vals    = [a.get("coverage")    for a in gemini_attrs]
    longevity_vals   = [a.get("longevity")   for a in gemini_attrs]
    lightweight_vals = [a.get("lightweight") for a in gemini_attrs]

    coverage_score    = safe_mean(coverage_vals)
    longevity_score   = safe_mean(longevity_vals)
    lightweight_score = safe_mean(lightweight_vals)

    # ── 피부타입 집계 (reviews.skin_type 우선, Gemini 보조 없음) ──
    skin_type_counter = Counter()
    skin_concern_counter = Counter()
    shade_scores: dict[str, float] = {s: 0.0 for s in ["21", "23", "25"]}

    for rev, attr in zip(reviews, gemini_attrs):
        sentiment = attr.get("sentiment", "neutral")
        content = rev.get("content", "")

        # 피부타입 (구조 데이터 우선)
        raw_skin = rev.get("skin_type") or ""
        for kor, eng in SKIN_TYPE_MAP.items():
            if kor in raw_skin:
                skin_type_counter[eng] += 1
                break

        # 피부고민 (구조 데이터 우선)
        raw_trouble = rev.get("skin_trouble") or ""
        for kor, eng in SKIN_TROUBLE_MAP.items():
            if kor in raw_trouble:
                skin_concern_counter[eng] += 1
        # Gemini 보조
        for concern in attr.get("skin_concerns", []):
            skin_concern_counter[concern] += 0.5

        # 호수 (옵션명 우선)
        shade = get_shade_from_option(rev.get("option_name") or "")
        if not shade:
            shade = attr.get("shade")  # Gemini fallback

        if shade and shade in shade_scores:
            weight = 1.2 if sentiment == "positive" else 0.8 if sentiment == "neutral" else 0.2
            # 색상 피드백 보정
            if sentiment == "negative":
                is_bright = any(k in content for k in BRIGHT_KEYWORDS)
                is_dark = any(k in content for k in DARK_KEYWORDS)
                if is_bright:
                    adj = {"23": "21", "25": "23"}.get(shade)
                    if adj: shade_scores[adj] += 0.5
                elif is_dark:
                    adj = {"21": "23", "23": "25"}.get(shade)
                    if adj: shade_scores[adj] += 0.5
            shade_scores[shade] = shade_scores.get(shade, 0.0) + weight

    # ── 적합 피부타입 (상위 빈도, 최소 5%) ─────────
    min_skin_freq = max(2, n * 0.05)
    suitable_skin_types = [
        st for st, cnt in skin_type_counter.most_common()
        if cnt >= min_skin_freq
    ][:4]

    # ── 적합 피부고민 (상위 빈도, 최소 5%) ─────────
    min_concern_freq = max(2, n * 0.05)
    suitable_concerns = [
        sc for sc, cnt in skin_concern_counter.most_common()
        if cnt >= min_concern_freq
    ][:5]

    # ── 적합 호수 (최소 점수 이상) ───────────────
    min_shade_score = max(2.0, n * 0.05)
    suitable_shades = sorted(
        [s for s, sc in shade_scores.items() if sc >= min_shade_score]
    )
    if not suitable_shades and max(shade_scores.values(), default=0) > 0:
        suitable_shades = [max(shade_scores, key=shade_scores.get)]

    # ── 실제 옵션 명 매핑 (shade_options) ─────────
    shade_options = {}
    for rev in reviews:
        opt = rev.get("option_name", "")
        if not opt: continue
        opt_lower = opt.lower()
        for shade, patterns in SHADE_OPTION_PATTERNS.items():
            if any(p.lower() in opt_lower for p in patterns):
                clean_opt = re.sub(r'[\(\[\{].*?[\)\]\}]', '', opt).strip()
                if not clean_opt:
                    clean_opt = opt.strip()
                if shade not in shade_options or len(clean_opt) > len(shade_options[shade]):
                    shade_options[shade] = clean_opt

    # ── 성분 분석 ──────────────────────────────
    compat = analyze_ingredients(product.get("ingredients_raw") or "")

    return {
        "coverage_score":    coverage_score,
        "longevity_score":   longevity_score,
        "lightweight_score": lightweight_score,
        "suitable_skin_types": suitable_skin_types,
        "suitable_concerns": suitable_concerns,
        "suitable_shades":   suitable_shades,
        "shade_options":     shade_options,
        "ingredient_level":  compat.get("ingredient_level", "일반"),
        "compat_oily":       compat.get("compat_oily", 0.5),
        "compat_dry":        compat.get("compat_dry", 0.5),
        "compat_sensitive":  compat.get("compat_sensitive", 0.5),
        "compat_combination":compat.get("compat_combination", 0.5),
    }


# ──────────────────────────────────────────────
# ④ 데이터 로드
# ──────────────────────────────────────────────

def load_all_products() -> list:
    resp = supabase.table("products").select("*").execute()
    return resp.data or []


def load_reviews_for_product(product_id: str) -> list:
    """
    해당 상품의 리뷰를 최대 MAX_REVIEWS_PER_PRODUCT개 로드.
    is_best=True 우선, 이후 최신순.
    """
    # best 리뷰 먼저
    best = (
        supabase.table("reviews")
        .select("id,content,rating,skin_type,skin_tone,skin_trouble,option_name,created_at")
        .eq("product_id", product_id)
        .eq("is_best", True)
        .limit(100)
        .execute()
    ).data or []

    # 나머지
    rest_limit = MAX_REVIEWS_PER_PRODUCT - len(best)
    if rest_limit > 0:
        best_ids = {r["id"] for r in best}
        rest = (
            supabase.table("reviews")
            .select("id,content,rating,skin_type,skin_tone,skin_trouble,option_name,created_at")
            .eq("product_id", product_id)
            .eq("is_best", False)
            .order("created_at", desc=True)
            .limit(rest_limit)
            .execute()
        ).data or []
        rest = [r for r in rest if r["id"] not in best_ids]
    else:
        rest = []

    return best + rest


# ──────────────────────────────────────────────
# ⑤ 체크포인트
# ──────────────────────────────────────────────

def load_checkpoint() -> set:
    """이미 처리된 product_id 집합 반환"""
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "rb") as f:
            return pickle.load(f)
    return set()


def save_checkpoint(done_ids: set):
    with open(CHECKPOINT_PATH, "wb") as f:
        pickle.dump(done_ids, f)


# ──────────────────────────────────────────────
# ⑥ 메인
# ──────────────────────────────────────────────

def main():
    logging.info("=" * 60)
    logging.info("제품 프로필 구축 시작")
    logging.info("=" * 60)

    products = load_all_products()
    logging.info(f"총 {len(products)}개 제품 로드")

    done_ids = load_checkpoint()
    if done_ids:
        logging.info(f"체크포인트: {len(done_ids)}개 이미 처리됨 → 이어서 진행")

    success, skipped, fail = 0, 0, 0

    for idx, product in enumerate(products, 1):
        pid = product["id"]
        pname = product.get("name", "")[:40]

        if pid in done_ids:
            logging.info(f"[{idx}/{len(products)}] ⏭  스킵 (이미 처리됨): {pname}")
            skipped += 1
            continue

        logging.info(f"\n[{idx}/{len(products)}] {product.get('brand','')} - {pname}")

        try:
            # 리뷰 로드
            reviews = load_reviews_for_product(pid)
            logging.info(f"  리뷰 {len(reviews)}개 로드")

            if len(reviews) == 0:
                logging.warning("  리뷰 없음 → 건너뜀")
                done_ids.add(pid)
                save_checkpoint(done_ids)
                skipped += 1
                continue

            # Gemini 배치 분석
            logging.info(f"  Gemini 분석 중...")
            gemini_attrs = extract_attributes_for_product(pid, product.get("name", ""), reviews)

            # 프로필 집계
            profile = aggregate_product_profile(product, reviews, gemini_attrs)
            logging.info(
                f"  커버력:{profile['coverage_score']} "
                f"지속력:{profile['longevity_score']} "
                f"착용감:{profile['lightweight_score']}"
            )
            logging.info(f"  피부타입:{profile['suitable_skin_types']}  호수:{profile['suitable_shades']}")
            logging.info(f"  성분등급:{profile['ingredient_level']}  민감성호환:{profile['compat_sensitive']}")

            # Supabase 업데이트
            supabase.table("products").update(profile).eq("id", pid).execute()
            logging.info(f"  ✅ DB 업데이트 완료")

            done_ids.add(pid)
            save_checkpoint(done_ids)
            success += 1

        except Exception as e:
            logging.error(f"  ❌ 처리 실패: {e}")
            fail += 1

    # 완료 후 체크포인트 삭제
    if CHECKPOINT_PATH.exists() and fail == 0:
        CHECKPOINT_PATH.unlink()
        logging.info("체크포인트 삭제 완료")

    logging.info("\n" + "=" * 60)
    logging.info(f"완료! 성공:{success}  스킵:{skipped}  실패:{fail}")
    logging.info("=" * 60)


if __name__ == "__main__":
    main()

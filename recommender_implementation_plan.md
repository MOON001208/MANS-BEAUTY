# 남성화장품 AI 추천 시스템 구현 계획

> 기존 `implementation_plan.md`(시장 분석 계획)을 기반으로, **Supabase + Gemini + Next.js 기반 실시간 개인화 추천 웹서비스**로 확장한 구현 계획입니다.

---

## 1. 개요

### 1.1 목표
- **기존 목표**: 남성 화장품(쿠션/파운데이션/톤로션) 구매 요인 분석
- **확장 목표**: 분석 결과를 실제 서비스로 구현 — 피부타입·고민 기반 **맞춤 추천 웹앱**

### 1.2 기존 vs 신규 비교

| 구분 | 기존 plan | 신규 plan |
|---|---|---|
| 데이터 저장 | `.plk` / `.csv` 로컬 파일 | **Supabase PostgreSQL** 클라우드 |
| 크롤러 | Selenium (느림, 봇탐지 취약) | **curl_cffi** HTTP 직접 호출 |
| 리뷰 분석 | KoNLPy 키워드 추출 | **Gemini 2.0 Flash Lite** 배치 분석 |
| 시각화 | Streamlit (로컬) | **Next.js** (웹 배포 가능) |
| 추천 방식 | K-Means 군집화 | **피부타입 필터 + AI 점수 기반** |

---

## 2. 데이터 파이프라인

### 2.1 상품·리뷰 수집
- **코드**: `scraper/crawler.py` (curl_cffi 기반)
- **대상**: 올리브영 톤로션/BB + 쿠션/파운데이션 카테고리
- **결과**: 55개 상품, 24,934개 리뷰 (Supabase 저장)

### 2.2 전성분 수집
- **코드**: `scraper/update_ingredients.py` (Selenium)
- **방식**: 올리브영 상품페이지 → 상품정보제공고시 아코디언 → 성분 행 파싱
- **결과**: 55/55 (100%) 수집 완료

### 2.3 상품 변형 통합
- **코드**: `scraper/merge_variants.py`
- **목적**: 리필/기획세트를 본품으로 통합, 리뷰 remapping
- **결과**: 61개 → 55개 (리뷰 전량 유지)

### 2.4 AI 프로필 생성
- **코드**: `pipeline/build_profiles.py`
- **처리 흐름**:
  ```
  Supabase에서 제품·리뷰 로드
      → Gemini 배치 분석 (10개씩)
         · coverage / longevity / lightweight 점수 (1~5)
         · skin_concerns / shade / sentiment
      → 구조 데이터 직접 활용
         · skin_type → suitable_skin_types
         · option_name → suitable_shades (호수)
      → 전성분 분석
         · 자극/자연유래 성분 분류
         · compat_oily / compat_dry / compat_sensitive
      → products 테이블 UPDATE
  ```

---

## 3. Supabase DB 스키마

### `products` 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | text PK | 올리브영 goodsNo |
| `name` | text | 상품명 |
| `brand` | text | 브랜드명 |
| `category` | text | 쿠션/파운데이션 or 톤로션/BB |
| `product_type` | text | cushion / liquid / stick / tone_lotion |
| `price` | numeric | 판매가 |
| `original_price` | numeric | 정가 |
| `star_rating` | numeric | 올리브영 평점 |
| `review_count` | integer | 총 리뷰 수 |
| `thumbnail_url` | text | 이미지 URL |
| `product_url` | text | 올리브영 링크 |
| `ingredients_raw` | text | 전성분 원문 |
| `ingredient_level` | text | 자연유래 / 저자극 / 일반 |
| `coverage_score` | numeric | 커버력 1~5 (Gemini) |
| `longevity_score` | numeric | 지속력 1~5 (Gemini) |
| `lightweight_score` | numeric | 착용감 1~5 (Gemini) |
| `suitable_shades` | jsonb | ["21","23","25"] |
| `suitable_skin_types` | jsonb | ["oily","dry","combination","sensitive"] |
| `suitable_concerns` | jsonb | ["acne","pore","redness","spots","wrinkle"] |
| `compat_oily` | numeric | 지성 피부 호환성 0~1 |
| `compat_dry` | numeric | 건성 피부 호환성 0~1 |
| `compat_sensitive` | numeric | 민감성 피부 호환성 0~1 |
| `compat_combination` | numeric | 복합성 피부 호환성 0~1 |

### `reviews` 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | text PK | 리뷰 ID |
| `product_id` | text FK | 상품 ID |
| `content` | text | 리뷰 내용 |
| `rating` | integer | 별점 1~5 |
| `skin_type` | text | 작성자 피부타입 |
| `skin_trouble` | text | 피부고민 |
| `skin_tone` | text | 피부톤 |
| `option_name` | text | 구매 옵션 (호수) |
| `is_best` | boolean | 베스트 리뷰 여부 |
| `created_at` | timestamptz | 작성일 |

---

## 4. 웹 추천 서비스 (Next.js)

### 4.1 기술 스택
- **Framework**: Next.js 15 + TypeScript
- **Database**: Supabase (클라이언트 직접 연결)
- **Styling**: Vanilla CSS (다크모드 + 글래스모피즘)
- **배포**: Vercel (예정)

### 4.2 추천 UX 흐름

```
[퀴즈 Step 1] 피부타입 선택
  건성 / 지성 / 복합성 / 민감성
        ↓
[퀴즈 Step 2] 피부고민 선택 (복수 가능)
  여드름 · 모공 · 홍조 · 잡티 · 주름
        ↓
[퀴즈 Step 3] 원하는 특성 선택
  커버력 중시 / 지속력 중시 / 가벼운 착용감
        ↓
[퀴즈 Step 4] 호수 선택 (선택사항)
  21호(밝은) / 23호(보통) / 25호(진한) / 잘 모름
        ↓
Supabase 쿼리 → 추천 결과 카드 (최대 12개)
```

### 4.3 주요 컴포넌트

| 컴포넌트 | 역할 |
|---|---|
| `SkinTypeQuiz` | 4단계 퀴즈 UI |
| `RecommendResult` | 추천 상품 그리드 |
| `ProductCard` | 점수바 + 태그 + 이미지 카드 |
| `ProductModal` | 상세 모달 (성분등급, AI점수, 리뷰) |
| `ScoreBar` | 커버력/지속력/착용감 시각화 |
| `IngredientBadge` | 자연유래/저자극/일반 배지 |

---

## 5. 검증 현황

| 항목 | 목표 | 현황 |
|---|---|---|
| 전성분 수집률 | 90%+ | ✅ 100% (55/55) |
| 리뷰 수집량 | 상품당 200건+ | ✅ 평균 453건 (총 24,934건) |
| 상품 변형 통합 | 리필/세트 제거 | ✅ 61 → 55개 |
| 스틱 타입 분류 | 정확한 product_type | ✅ 수동 검증 완료 |
| AI 프로필 생성 | 55개 전 상품 | 🔄 진행 중 |
| 웹 추천 서비스 | 추천 정확도 검증 | 📋 예정 |

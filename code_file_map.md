# 프로젝트 코드 및 데이터 파일 매핑 (Project Code & Data File Mapping)

현재 프로젝트의 데이터 파이프라인 흐름에 따른 코드 파일과 입출력 데이터 파일의 관계도입니다.

## 1. 데이터 수집 (Data Collection)

| 단계 | 코드 파일 (`/code`) | 주요 출입 데이터 | 비고 |
|:---:|:---|:---|:---|
| 기본 정보 | `화장품정보수집.ipynb` | (출) `data/화장품정보all.plk` | 상품명, 가격, 링크 등 기초 정보 |
| 리뷰 수 | `웹크롤링.qmd` | (출) `code/리뷰수all.csv` | 올리브영 웹사이트에서 리뷰 수 수집 |
| 전성분 | `전성분수집.py` | (입) `data/final_review.plk`<br>(출) `data/product_ingredients.csv` | 상품 링크를 통한 전성분 텍스트 수집 |
| 리뷰 상세 | `리뷰수집.ipynb` | (출) `data/화장품리뷰all.plk` | 리뷰 내용, 별점, 작성자 피부정보 등 |

---

## 2. 데이터 전처리 및 정제 (Refinement & Cleaning)

| 단계 | 코드 파일 (`/code`) | 주요 출입 데이터 | 비고 |
|:---:|:---|:---|:---|
| 중복 제거 | `데이터병합,중복데이터제거.ipynb` | (입) `화장품정보all.plk`, `리뷰수all.csv`<br>(출) `code/중복데이터제거.plk` | 중복 상품 제거 및 데이터 정규화 |
| 텍스트 정규화 | `run_gemini_normalization.py`<br>`gemini_text_normalizer.py` | (입) `data/analysis_master.plk`<br>(출) `data/reviews_normalized.plk` | **Gemini API** 사용 맞춤법 및 텍스트 교정 |
| 성분 전처리 | `preprocess_ingredients.py` | (입) `data/product_ingredients.csv`<br>(출) `data/product_ingredients_clean.plk` | 복합 구성품 분리 및 성분 리스트화 |
| 메타데이터 | `preprocess_metadata.py` | (입) `review_with_influencers_clean.plk`<br>(출) `review_processed_metadata.plk` | 피부타입 원핫인코딩, 호수 표준화, Brand Tier 구분 |

---

## 3. 데이터 풍부화 및 통합 (Enrichment & Integration)

| 단계 | 코드 파일 (`/code`) | 주요 출입 데이터 | 비고 |
|:---:|:---|:---|:---|
| 인플루언서 | `process_influencers.py` | (입) `data/final_review.plk`<br>(출) `data/review_with_influencers.plk` | 덱스, 스완 등 뷰티 유튜버 언급 태깅 |
| 타임라인 | `influencer_timeline.ipynb` | (입) `review_with_influencers.plk`<br>(출) `review_with_influencers_clean.plk` | 언급 시점 시각화 및 최종 클리닝 |
| 1차 마스터 | `전성분_리뷰통합.py` | (입) `review_with_influencers_clean.plk`, `product_ingredients_clean.plk`<br>(출) `data/product_master_final.plk` | 리뷰 데이터에 전성분 정보 병합 |
| **최종 마스터** | `merge_master_tables.py` | (입) `product_master_final.plk`, `review_processed_metadata.plk`<br>(출) `data/analysis_master.plk` | **분석용 최종 데이터셋** (17,444개 리뷰) |

---

## 4. 데이터 분석 및 시각화 (Analysis)

### 📊 시장 가설 검증
*   **코드 파일**: `code/hypothesis_analysis.ipynb`
*   **핵심 데이터**: `data/analysis_master.plk`
*   **분석 항목**:
    *   남성 뷰티 리뷰 증가 추세 (2019~2025)
    *   브랜드 Tier별(Major/Minor) 구매 및 선호도 차이
    *   호수(Shade) 다양성이 구매력에 미치는 영향
    *   인플루언서(유튜버) 홍보 효과 측정
    *   제품 전성분 및 피부타입별 만족도 상관분석

### 📉 가설 검증 보완 (V2)
*   **코드 파일**: `code/hypothesis_analysis_v2.py`, `code/hypothesis_analysis_v2_part2.py`
*   **기능**: 통계적 가설 검정 및 시각화 자동화

### 🎯 종합 시장 분석
*   **코드 파일**: `code/final_market_analysis.ipynb`
*   **핵심 데이터**: `data/reviews_normalized.plk`
*   **특이사항**: `데이터_불균형_분석_전략.md`를 반영하여 Top 2 브랜드 제외 분석 및 효율 지표 중심 분석 수행

---

## 📂 주요 데이터 파일 가이드

| 파일명 | 용도 | 핵심 컬럼 |
|:---|:---|:---|
| `analysis_master.plk` | **최종 분석용 마스터** | `브랜드`, `별점`, `피부타입`, `Brand_Tier`, `ingredients_list`, `is_dry` 등 |
| `reviews_normalized.plk` | Gemini 정제 데이터 | `리뷰내용`, `gemini_normalized` (정정된 텍스트) |
| `product_master_final.plk` | 전성분 병합 데이터 | `상품이름`, `전성분`, `ingredient_count` |
| `product_ingredients_clean.plk` | 정제된 성분 리스트 | `product_name`, `ingredients_clean_str` |

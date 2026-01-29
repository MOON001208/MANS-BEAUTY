# 남성 화장품 시장 분석 텍스트 마이닝 워크플로우 정리

이 문서는 '남성 화장품 시장 분석 프로젝트'에서 수행된 텍스트 마이닝(Text Mining)의 전체 과정, 사용된 코드, 그리고 생성된 핵심 데이터 구조를 정리한 것입니다.

## 1. 텍스트 마이닝 개요 (Overview)

본 프로젝트는 전통적인 자연어 처리 방식(형태소 분석)과 최신 LLM(Gemini API)을 결합한 **하이브리드 텍스트 마이닝** 방식을 채택했습니다.

*   **전통적 방식 (Kiwi/Mecab)**: 빠른 속도로 대량의 텍스트에서 명사/형용사 빈도 추출.
*   **AI 기반 방식 (Gemini)**: 문맥(Context)을 이해하여 정확한 속성 점수(발림성, 지속력) 측정 및 미묘한 구매 의도(선물 여부) 파악.

---

## 2. 분석 파이프라인 (Pipeline)

### 단계 1: 데이터 수집 및 전처리 (Collection & Preprocessing)
*   **원본 데이터**: 올리브영, 화해 어플 등에서 크롤링한 리뷰 데이터 (`oy_data.csv`)
*   **정제 작업**:
    *   HTML 태그 및 특수문자 제거.
    *   `Gemini`를 활용한 오탈자 및 띄어쓰기 교정 (`run_gemini_normalization.py`).
*   **결과물**: 정제된 리뷰 텍스트 데이터 (`reviews_normalized.plk`).

### 단계 2: 피처 추출 (Feature Extraction) - *핵심 단계*
텍스트를 분석 가능한 수치나 구조화된 데이터로 변환하는 과정입니다.

#### A. 핵심 키워드 추출 (Keyword Extraction)
*   **코드**: `code/extract_keywords_gemini_full.py`
*   **기능**: AI가 리뷰 전체를 읽고 가장 중요한 단어 5개를 선정.
*   **차별점**: 단순 빈도 기반이 아니라, 의미적으로 중요한 단어(예: '남자친구 선물', '촉촉함')를 추출.
*   **산출물**: `data/review_keywords_gemini.pkl`

#### B. 리뷰 속성 평가 (Attribute Extraction)
*   **코드**: `code/recommendation_system/extract_review_attributes_gemini.py`
*   **기능**: 비정형 텍스트를 정형 데이터(점수)로 변환.
*   **추출 속성**:
    *   `coverage` (커버력): 1~5점
    *   `longevity` (지속력): 1~5점
    *   `skin_type` (피부타입): 지성, 건성 등
    *   `persona` (구매자 유형): 선물용, 본인용 등
*   **산출물**: `data/review_attributes_gemini.plk`

### 단계 3: 심층 분석 및 데이터 마트 구성 (Analysis & Datamart)
*   **코드**: `code/advanced_analysis_gemini.py`
*   **기능**: 
    1. **형태소 분석**: Kiwi 라이브러리를 사용해 명사(NN), 형용사(VA) 추출.
    2. **통계 분석**: 페르소나별 키워드 빈도 차이 분석, 부정 리뷰 원인 추적.
    3. **데이터 병합**: 키워드, 속성, 형태소 분석 결과를 하나의 마스터 파일로 통합.
*   **산출물**: `data/gemini_analysis_results.csv`

### 단계 4: 시각화 및 모델링 (Visualization & Modeling)
*   **코드**: `code/Data_Visualization_Topic_Modeling.ipynb`
*   **기능**: LDA 토픽 모델링, 워드클라우드, 속성별 만족도 그래프 생성.

---

## 3. 핵심 산출물 상세 설명 (Key Deliverables)

분석 과정에서 생성된 3가지 주요 파일의 역할과 용도는 다음과 같습니다.

| 파일명 | 생성 코드 | 용도 및 특징 |
| :--- | :--- | :--- |
| **review_keywords_gemini.pkl** | `extract_keywords_gemini_full.py` | **[트렌드 파악용]**<br>- AI가 엄선한 리뷰별 5개 핵심 키워드 리스트.<br>- 워드클라우드, 감성 키워드 매핑에 활용. |
| **review_attributes_gemini.plk** | `extract_review_attributes_gemini.py` | **[추천 시스템/정량 분석용]**<br>- 텍스트가 숫자로 변환된 파일 (커버력 5점, 지속력 3점 등).<br>- 제품 필터링, 스펙 비교, 평점 산출에 필수적. |
| **gemini_analysis_results.csv** | `advanced_analysis_gemini.py` | **[최종 시각화용]**<br>- 위 두 파일의 정보를 합치고 통계 분석을 마친 최종본.<br>- Tableau, Excel, Python 시각화 도구에서 즉시 사용 가능.<br>- '선물 구매자(Gifter)' 등 분류 태그가 포함됨. |

---

## 4. 분석 방법론 심화 (Methodology Details)

### 페르소나 분류 (Persona Classification)
단순한 텍스트 매칭이 아닌, 문맥 분석을 통해 구매자를 4가지 그룹으로 분류했습니다.
1.  **Gifter (선물 구매자)**: '남친', '아빠', '선물' 등의 맥락이 있는 경우.
2.  **Newbie (입문자)**: '처음', '입문', '잘 몰라서' 등의 맥락.
3.  **Loyalist (충성 고객)**: '재구매', '정착', 'n통째' 등의 맥락.
4.  **User (일반 사용자)**: 기타 직접 구매자.

### 부정 리뷰 원인 분석 (Aspect-Based Sentiment Analysis)
전체 평점이 낮아도 구체적인 이유가 다를 수 있음을 고려했습니다.
*   **Coverage Group**: 커버력 점수가 낮은(1~2점) 리뷰 집단 → 주요 키워드: '안가려짐', '연함', '잡티보임'
*   **Longevity Group**: 지속력 점수가 낮은(1~2점) 리뷰 집단 → 주요 키워드: '무너짐', '기름짐', '다크닝'

---

## 5. 결론 및 활용 가이드

*   시장 전체의 트렌드를 보고 싶다면 **`Data_Visualization_Topic_Modeling.ipynb`**에서 시각화를 수행하십시오.
*   개별 제품의 스펙을 기반으로 추천 시스템을 구현하려면 **`product_profiles.plk`** (최종 제품 프로필)을 사용하십시오.
*   분석 로직을 수정하거나 새로운 관점을 추가하려면 **`advanced_analysis_gemini.py`**를 수정하십시오.

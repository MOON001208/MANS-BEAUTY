 # 남성 화장품 시장 분석 프로젝트 구현 계획 (Implementation Plan)

## 1. 개요 (Overview)
### 1.1 프로젝트 목표
- **남성 화장품(쿠션/파운데이션) 구매 요인 분석**: 남성 소비자가 화장품 선택 시 중요하게 고려하는 요소(키워드, 성분, 가격 등) 파악.
- **맞춤형 제품 추천 시스템 구현**: 단순 인기도 순이 아닌, 피부 타입 및 선호 특성(커버력, 자연스러움 등)에 기반한 군집화 및 추천.

### 1.2 문제 정의 (Problem Redefinition)
- **기존 문제**: 단순 "영향 요인" 나열은 인과관계 설명에 한계가 있음.
- **개선 방향**: "소비자 리뷰 키워드"와 "만족도/재구매의사"의 연관성을 분석하고, 이를 바탕으로 **유저 세그먼트별 맞춤 추천** 제공.
- **가설 검증**:
    - 특정 부정 키워드(개기름, 트러블)와 특정 성분의 상관관계 분석.
    - 유튜브 마케팅(Viral) 여부가 실제 리뷰 수 및 평점에 미치는 영향 분석.

---

## 2. 데이터 수집 (Data Collection)
`code_file_map.md`에 정의된 데이터 파이프라인 흐름을 따릅니다.

### 2.1 기본 정보 및 리뷰 수 수집
- **코드**: `화장품정보수집.ipynb`
- **산출물**: `화장품정보all.plk` (상품명, 브랜드, 가격, 썸네일 등)

- **코드**: `웹크롤링.qmd`
- **산출물**: 
    - `리뷰수all.csv` (상품별 리뷰 개수)
    - `화장품최종본all.plk` (`화장품정보all.plk` + `리뷰수all.csv` 병합)

### 2.2 리뷰 상세 수집
- **코드**: `리뷰수집.ipynb`
- **산출물**: `화장품리뷰all.plk` (작성자, 평점, 리뷰 텍스트, 옵션, 날짜 등)

### 2.3 성분 정보 수집
- **코드**: `전성분수집.py` (Selenium 기반)
- **산출물**: `data/product_ingredients.csv` (상품별 전성분 텍스트)

---

## 3. 데이터 테이블 정의 (Data Table Definitions)
분석의 핵심이 되는 통합 마스터 테이블(`product_analysis_master`) 스키마입니다.

### 3.1 Master Table Schema (`product_analysis_master.plk`)
- **기준**: Product ID (1행 1상품)

| 구분 | 컬럼명 | 데이터 타입 | 설명 |
| :--- | :--- | :--- | :--- |
| **식별자** | `product_id` | String | 상품 고유 ID |
| | `brand` | String | 브랜드명 (예: 비레디, 오브제) |
| | `product_name` | String | 상품명 |
| **기본정보**| `price` | Integer | 정가 |
| | `category` | String | 카테고리 (쿠션/파운데이션 등) |
| **리뷰 요약**| `review_count` | Integer | 총 리뷰 수 |
| | `rating_avg` | Float | 평균 평점 |
| | `sentiment_score`| Float | 긍정/부정 감성 점수 평균 |
| **키워드** | `top_keywords` | List | 주요 키워드 Top 5 (예: ["커버력", "지속력"]) |
| **성분** | `ingredients_all`| String | 전성분 전체 텍스트 |
| | `trouble_count` | Integer | 주의 성분 개수 |
| | `key_ingredients`| List | 핵심 효능 성분 리스트 |
| **마케팅** | `is_viral` | Boolean | 유튜버 홍보 여부 |
| | `viral_period` | String | 홍보 집중 기간 |

---

## 4. 데이터 전처리 및 분석 과정 (Preprocessing & Analysis)

### 4.1 데이터 병합 및 정제 (Cleaning)
- **코드**: `데이터병합,중복데이터제거.ipynb`
- **입력**: `화장품정보all.plk`, `화장품최종본all.plk`, `화장품리뷰all.plk`
- **로직**: 데이터 병합 후 중복 리뷰(도배성) 제거.
- **출력**: `중복데이터제거.plk`

### 4.2 파생변수 생성 (Feature Engineering)
- **코드**: `리뷰정보추가.ipynb`
- **기능**: 가격 정제, 옵션 표준화, 필터링.
- **출력**: `final_review.plk`

### 4.3 심화 분석 (Advanced Analysis)
- **코드**: `analysis_clustering.ipynb` (신규 개발 예정)
- **내용**:
    1.  **키워드 추출**: KoNLPy (Okt/Mecab) 활용 리뷰 텍스트 명사/형용사 추출.
    2.  **성분 분석**: `product_ingredients.csv`와 매핑하여 트러블 유발 가능성 등 분석.
    3.  **군집화 (Clustering)**:
        - Feature: [가격, 평점, 키워드 벡터, 성분 벡터]
        - 알고리즘: K-Means 또는 DBSCAN
        - 목적: 유사 특성 제품 그룹핑 (예: "가성비 트러블 케어", "고가 프리미엄 커버")
    4.  **인플루언서 영향력**: `is_viral` 변수와 평점/리뷰 증가율 간 상관분석.

---

## 5. 시각화 및 대시보드 (Visualization & Dashboard)
- **도구**: Streamlit (`app.py`)
- **주요 페이지 구성**:
    1.  **Market Overview**: 시장 전체 트렌드, 브랜드 점유율.
    2.  **Product Explorer**: 필터(가격, 피부타입, 고민) 기반 제품 탐색 및 군집 시각화.
    3.  **Ingredient & Keyword Engine**: "이 성분이 들어간 제품 찾기", "특정 키워드(예: 개기름)가 많은 제품 분석".

---

## 6. 검증 계획 (Verification Plan)

### 6.1 자동화 테스트 (Automated Tests)
- `pytest`를 활용한 데이터 무결성 검사.
- 예: 전성분 수집 완료된 상품 비율 90% 이상 유지 확인.

### 6.2 수동 검증 (Manual Verification)
- **대시보드 Usability**: Streamlit 앱 실행 후 필터 작동 여부 확인.
- **데이터 정확성**: 랜덤 샘플링한 상품(예: 오브제 쿠션)의 실제 올리브영 평점과 수집 데이터 일치 여부 확인.

# 종합 코드 분석 및 추적 보고서

이 문서는 `code/` 폴더 및 루트 디렉토리에 위치한 현재 코드베이스를 감사(Audit)하고, `implementation_plan.md`와의 정합성을 확인하기 위해 작성되었습니다. 이 보고서는 프로젝트의 로직, 데이터 흐름, 파일 의존성을 파악하는 중심 자료로 활용됩니다.

---

## 1. 프로젝트 구조 및 계획 대조

다음 표는 `implementation_plan.md`에 정의된 각 단계와 실제 작업 공간에 존재하는 코드 파일을 매핑한 결과입니다.

| 단계 | 구현 계획 (Task) | 해당 코드 파일 | 상태 |
| :--- | :--- | :--- | :--- |
| **데이터 수집** | 2.1 기본 정보 및 리뷰 수 | `code/화장품정보수집.ipynb`<br>`code/웹크롤링.qmd` | ✅ 존재함 |
| | 2.2 리뷰 상세 수집 | `code/리뷰수집.ipynb` | ✅ 존재함 |
| | 2.3 성분 정보 수집 | `code/전성분수집.py` | ✅ 존재함 |
| **데이터 전처리** | 4.1 병합 및 정제 | `code/데이터병합,중복데이터제거.ipynb` | ✅ 존재함 |
| | 4.2 파생변수 생성 | `code/리뷰정보추가.ipynb` | ✅ 존재함 |
| | **4.3 성분 데이터 파싱** | **`preprocess_ingredients.py`** | **✅ 신규 생성됨** |
| **심화 분석** | 4.3 마케팅/바이럴 분석 | `code/process_influencers.py`<br>`code/influencer_analysis.ipynb` | ✅ 존재함 (계획서에 명시되지 않았으나 구현됨) |
| | 4.3 군집화 (Clustering) | `analysis_clustering.ipynb` | 🚧 개발 예정 |
| **시각화** | 5. 대시보드 | `app.py` | 🚧 개발 예정 |

---

## 2. 상세 코드 분석 및 로직 추적

### 2.1 성분 데이터 파싱 (신규 구현)
*   **파일**: `preprocess_ingredients.py`
*   **역할**: 원본 `data/product_ingredients.csv` 파일을 분석 가능한 형태로 전처리합니다.
*   **로직 (Logic)**:
    1.  **문제점**: 원본 데이터에 메인 상품 외 증정품 성분이 섞여 있음 (예: `[본품] ... [증정] ...`).
    2.  **해결**: "[...]" 라벨과 상품명 간의 유사도 점수(단어 교집합)를 계산하는 휴리스틱 알고리즘을 적용하여 메인 상품의 성분만 추출합니다.
    3.  **출력**: `data/product_ingredients_clean.plk` (제품별 정제된 성분 리스트 저장).

### 2.2 인플루언서 분석 (기존 코드)
*   **파일**: `code/process_influencers.py`, `code/influencer_analysis.ipynb`
*   **역할**: 리뷰 텍스트에서 특정 인플루언서(스완, 관하살, 티벳동생 등) 언급을 추출합니다.
*   **로직 (Logic)**:
    *   인플루언서 이름과 관련 키워드 딕셔너리를 활용하여 매핑합니다.
    *   리뷰 내 언급 여부를 통해 `is_viral` 변수를 생성합니다.
    *   인플루언서 언급과 평점/리뷰 수 간의 상관관계를 분석합니다.

### 2.3 데이터 수집 (레거시 코드)
*   **스크립트**: `화장품정보수집.ipynb`, `리뷰수집.ipynb`, `전성분수집.py`
*   **역할**: 올리브영 웹사이트 크롤링.
*   **참고**: 이 스크립트들은 `data/` 폴더 내의 원본 `.plk` 파일들을 생성하며, `전성분수집.py`는 Selenium을 통해 성분 데이터를 가져와 `preprocess_ingredients.py`의 입력 데이터를 만듭니다.

---

## 3. 권장 실행 파이프라인 (Execution Pipeline)

분석을 처음부터 재현하기 위한 코드 실행 순서는 다음과 같습니다:

1.  **데이터 수집 (Collection)**:
    *   `화장품정보수집.ipynb` 실행 -> `data/화장품정보all.plk` 생성
    *   `웹크롤링.qmd` 실행 -> `data/리뷰수all.csv` 생성
    *   `리뷰수집.ipynb` 실행 -> `data/화장품리뷰all.plk` 생성
    *   `전성분수집.py` 실행 -> `data/product_ingredients.csv` 생성

2.  **데이터 전처리 (Preprocessing)**:
    *   `데이터병합,중복데이터제거.ipynb` 실행 -> `data/중복데이터제거.plk` 생성
    *   `리뷰정보추가.ipynb` 실행 -> `data/final_review.plk` 생성
    *   **`preprocess_ingredients.py` 실행** -> `data/product_ingredients_clean.plk` 생성

3.  **변수 확장 (Feature Augmentation)**:
    *   `code/process_influencers.py` 실행 -> `data/review_with_influencers.plk` 생성

4.  **최종 분석 (Next Steps)**:
    *   `analysis_clustering.ipynb` 생성 및 실행 (성분 특성 + 바이럴 데이터 + 제품 정보 병합).
    *   Streamlit 앱 `app.py` 구축.

---

## 4. 관찰 및 향후 계획
*   **통합 필요성**: 현재 `product_ingredients_clean.plk`의 성분 데이터와 `review_with_influencers.plk`의 리뷰/바이럴 데이터가 분리되어 있습니다.
*   **조치 사항**: 다음 단계인 군집화 분석(`analysis_clustering.ipynb`)에서 이 두 피클 파일을 불러와 `product_name`(상품명)을 기준으로 병합(Merge)하여 최종 마스터 테이블을 생성해야 합니다.

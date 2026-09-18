# 남성 베이스 메이크업 수집·추천 파이프라인

현재 운영 코드는 이 디렉터리의 Python 파이프라인과 `web`입니다. 이전 단계의 노트북·Gemini 실험 코드는 운영 작업에서 실행하지 않습니다.

## 실행 환경

Python 3.13, Node.js 24. 저장소 루트에서 가상환경을 만들고 설치합니다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r code/7_advanced_recommender/requirements.txt
```

이 디렉터리의 `.env.example`을 `.env`로 복사한 뒤 서버 전용 `SUPABASE_SECRET_KEY`를 설정합니다. `web/.env.local`에는 URL과 공개용 publishable 키만 넣습니다. 실제 `.env`는 Git에 포함하지 않습니다.

처음 연결하는 DB에는 `migrations/20260917_pipeline_security.sql`을 Supabase SQL Editor에서 먼저 적용합니다. 상품·리뷰 행은 삭제하지 않으며, 공개 계정의 쓰기 권한과 리뷰 작성자 닉네임 조회 권한을 제거합니다. 노출된 관리자 키 자체는 별도 폐기해야 합니다.

## 수집과 갱신

아래 명령은 저장소 루트 기준입니다. 기본 실행은 DB에 쓰지 않는 dry-run입니다.

```powershell
# 특정 상품의 연결·응답 확인
.venv/Scripts/python.exe code/7_advanced_recommender/run_pipeline.py --product A000000198001 --max-review-pages 3
# 신상품 탐색, 리뷰 적재, 추천 프로필 갱신
.venv/Scripts/python.exe code/7_advanced_recommender/run_pipeline.py --write
# 기존 저장 리뷰만 다시 분석
.venv/Scripts/python.exe code/7_advanced_recommender/run_pipeline.py --write --profiles-only
```

- 현재 베이스 메이크업 카테고리를 신상품순·인기순으로 탐색하고 상품 상세의 `menCategoryFlag`와 분류를 확인합니다. 모든 남성 스킨케어 카테고리까지 확장한 수집기는 아닙니다.
- 리뷰는 모바일 웹의 공개 cursor API에서 최신순·도움순·높은 평점순·낮은 평점순으로 수집합니다. 공식 제공 SDK나 보장된 외부 API가 아니므로 사이트 변경 시 점검이 필요합니다.
- 리뷰 ID로 중복 제거합니다. 기존 ID가 나왔다고 탐색을 끝내지 않습니다. 세트·리필의 연결 리뷰는 원본 상품 ID를 보존하고, 해당 상품을 확인한 뒤 저장합니다. 이미 저장된 ID의 내용·귀속은 자동 덮어쓰지 않습니다.
- 페이지 저장 성공 후 커서를 기록합니다. 다음 실행은 최신 첫 페이지를 확인한 다음 이전 커서부터 이어갑니다. 오래 갱신하지 않은 상품을 먼저 처리해 특정 상품에 실행 시간이 계속 소모되지 않게 합니다.
- 기본 요청 간격은 2초, 수집 시간 예산은 90분입니다. 401/403, 반복된 429, 로그인 요구, 반복 커서를 감지합니다. 접근 제한을 우회하지 않습니다. 사이트 제한으로 전체 리뷰를 확보하지 못할 수 있습니다.
- `.pipeline-cache`에 커서·탐색 캐시·실행 보고서를 기록합니다. Git에 포함하지 않습니다. `--fresh`는 저장 커서 대신 처음부터 탐색합니다.
- 성분표가 차단되거나 여러 옵션의 성분이 섞이면 추정하지 않습니다. 확인된 성분표가 없으면 성분 관련 판정을 제공하지 않습니다.

GitHub Actions `Scheduled Crawler Update`는 매주 월요일 09:00 KST에 **저장된 리뷰의 프로필만 갱신**합니다. GitHub 호스팅 서버의 올리브영 요청이 403으로 차단되어, 수집은 사용자가 PC에서 위 명령으로 수동 실행하는 구성입니다. PC에 자동 작업은 등록하지 않습니다. `SUPABASE_URL`, `SUPABASE_SECRET_KEY` Secrets가 필요합니다. 수동 Actions 실행의 `collect_reviews`는 기본 false이며 접근 가능한 실행 환경에서만 사용합니다. 실패해도 커서와 보고서를 보관합니다. 장기 비활성 저장소는 GitHub가 스케줄을 중지할 수 있으므로 Actions의 활성 상태를 확인하세요.

## 추천 점수의 의미

Gemini 호출 없이 한국어 리뷰의 명시적인 긍정·부정 표현을 집계하는 `rules-ko-v1` 기준입니다. 모델 정확도가 검증된 학습 추천기는 아니며, 문맥·반어·복잡한 부정을 놓칠 수 있습니다.

항목별 근거가 3건 미만이면 점수는 `null`입니다. 피부타입 지표는 같은 피부타입 작성자의 평점을 표본 수에 따라 보정한 값이며 의학적 안전성·적합 확률이 아닙니다. 피부 고민이 있다는 자기소개를 제품 효능으로 계산하지 않습니다. 호수는 명시된 21/23/25만 사용하고, 현재 옵션을 확보했다면 과거 리뷰 옵션보다 우선합니다.

프로필에 분석 버전·리뷰 수·항목별 근거 수·근거 리뷰 ID·입력 해시·분석 시각을 저장합니다. 점수와 고민 태그는 각각 근거가 된 리뷰 ID를 함께 저장하므로, 상세 화면에서 "근거 리뷰 보기"로 그 주장이 어떤 리뷰에서 나왔는지 확인할 수 있습니다. 입력이 동일하면 재계산을 생략합니다. 저장하는 메타데이터의 형태가 바뀌면 `METADATA_REVISION`을 올려 재계산을 유도합니다. 점수 산출 규칙이 그대로일 때 `VERSION`은 유지되므로 배포된 화면이 구버전 프로필로 잘못 표시되는 구간이 생기지 않습니다. 중요도 1은 해당 항목의 가중치 0이며 낮은 품질을 선호한다는 의미가 아닙니다.

## 검증

```powershell
.venv/Scripts/python.exe -m unittest discover -s code/7_advanced_recommender/tests -v
cd code/7_advanced_recommender/web
npm ci
npm test
npm run eval
npm run lint
npm run build
```

`npm run eval`은 `tests/fixtures/personas.json`의 페르소나 12명을 실제 화면과 같은 `selectRecommendations`로 정렬해, 사용자가 건 조건을 결과가 지키는지 측정합니다. 관련도 정답이나 클릭 로그가 없으므로 NDCG·Recall이 아니라 **제약조건 충족률**과 **근거 추적률**을 봅니다. 하드 조건(구버전 프로필, 분석 리뷰 최소치, 사용 방식 필터) 위반이나 결과 0건이면 실패하고, 나머지 비율은 변경 전후 비교용으로 보고만 합니다. 커밋된 `tests/fixtures/catalog-snapshot.json`으로 돌기 때문에 CI에서 DB 접근이 필요 없습니다. 스냅샷 갱신은 `npm run snapshot`(공개 키 필요)입니다.

웹 빌드 전 환경변수와 빌드 후 정적 파일에서 관리자 키를 검사합니다. CI에는 실제 DB 키 대신 공개용 형식의 테스트 값을 사용합니다. 상품 삭제와 리뷰 재귀속을 수행하던 `merge_variants.py`는 중지했습니다.

보안 참고: [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys).

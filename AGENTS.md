# AGENTS.md — 이 저장소에서 작업하는 규칙

여러 에이전트(Codex, Claude Code, Antigravity)가 같은 저장소를 번갈아 작업한다.
이 파일이 공통 계약이다. 도구별 설정 파일은 이 문서를 가리키기만 하고 내용을 복제하지 않는다.

작업 시작 전 이 문서와 `docs/작업보드.md`를 읽는다.

## 1. 이 프로젝트가 하는 일

올리브영에서 **남성 베이스 메이크업** 상품과 리뷰를 수집해 Supabase에 적재하고,
리뷰에 실제로 적힌 표현만 근거로 추천하는 정적 웹을 배포한다.

핵심 가치는 하나다. **근거 없는 것을 아는 척하지 않는다.**
점수·호수·적합성은 모두 "리뷰에 이렇게 적혀 있다"까지만 말하고, 그 이상을 추정하지 않는다.
사용자는 화장 티 나는 걸 싫어하는 남성이고, 틀린 호수 추천은 정보가 없는 것보다 나쁘다.

## 2. 지도

```
code/7_advanced_recommender/     ← 유일한 운영 대상
  ops.py                         검증·상태 점검 진입점
  run_pipeline.py                수집 → 프로필 생성 한 번에
  shared.py                      DB 연결, 페이지네이션, 공통 유틸
  scraper/crawler.py             올리브영 수집 (상품·리뷰·성분)
  pipeline/profiles.py           리뷰 → 프로필 규칙 (핵심 로직)
  pipeline/build_profiles.py     프로필 생성·저장
  pipeline/shade_coverage.py     호수 구분 현황 집계
  pipeline/shade_mapping.py      브랜드 호수 ↔ 21/23/25 매핑 (리포트만)
  pipeline/youtube_shades.py     유튜브 텍스트 수집 (선택)
  migrations/                    Supabase SQL (RLS·권한 포함)
  tests/                         파이썬 회귀 테스트
  web/                           Next.js 정적 사이트 (GitHub Pages)
    src/lib/recommendation.ts    점수·정렬 (화면과 평가가 공유)
    scripts/evaluate-*.mjs       추천 제약조건 평가
    tests/fixtures/              페르소나·카탈로그 스냅샷

code/1_..._6_*                   2026-01~02 레거시. 건드리지 않는다.
docs/작업보드.md                  진행 중·다음 작업
docs/작업인계_*.md                세션 인계 기록
```

## 3. 깨면 안 되는 것

아래는 전부 실제로 한 번씩 문제가 됐던 지점이다. 바꾸려면 이유를 커밋 메시지에 남긴다.

**호수(톤)**
- 브랜드 자체 호수를 21/23/25로 **환산하지 않는다.** `1호`가 `21호`라는 보장이 없다.
  말할 수 있는 건 "이 제품의 옵션 중 밝은 쪽"까지다 (`shade_lineup`).
- 옵션명에 근거가 없으면 순서를 만들지 않는다. `살몬 베이지`/`그린 베이지`는 밝기가 아니라
  색 보정 목적이고, `01 코어썸`은 번호가 붙은 제품 변형이다.
- 명시된 21/23/25 가점(+15)이 상대 순서 가점(최대 +10)보다 항상 커야 한다. 근거의 강도가 다르다.
- 품절 옵션은 라인업에서 뺀다. 살 수 없는 호수를 추천하지 않는다.

**프로필 버전**
- `VERSION`은 점수 산출 규칙의 버전이다. 웹의 `hasCurrentProfile`이 이 값으로 게이트한다.
  **규칙이 안 바뀌었으면 올리지 않는다.** 올리면 재생성 전까지 사이트 전체가 "정보 부족"이 된다.
- 저장하는 메타데이터의 **형태**만 바뀌었으면 `METADATA_REVISION`을 올린다.
  `input_hash`에 들어가 있어 자동 재생성되고, 배포된 화면은 계속 정상 동작한다.

**근거**
- 리뷰 작성자의 자기소개를 제품 효능으로 세지 않는다.
  "저는 여드름 피부입니다" ≠ 여드름에 좋다. "저는 23호를 씁니다" ≠ 이 제품이 23호다.
- 항목별 근거가 3건 미만이면 점수는 `null`이다. 0점이 아니다.
- 화면에 표시하는 주장에는 근거 리뷰 ID가 붙어 있어야 한다 (`evidence_review_ids`, `concern_evidence_ids`).

**보안**
- 서버 키(`sb_secret_`)는 `.env`에만 있고 `NEXT_PUBLIC_`으로 나가지 않는다.
  빌드 전후로 `scripts/check-public-env.mjs`, `scripts/check-bundle.mjs`가 검사한다.
- 키를 코드에 하드코딩하지 않는다. 환경변수로만 읽는다.
- 공개 키로 리뷰 작성자(`author`)가 읽히면 안 된다. `ops.py health`가 검사한다.

**평가**
- `selectRecommendations`는 `lib/recommendation.ts`에 있고 화면과 평가가 **같은 함수**를 쓴다.
  `page.tsx`로 인라인하면 평가가 실제 동작을 측정하지 못한다.
- 관련도 정답 라벨이 없으므로 NDCG/Recall을 쓰지 않는다. 제약조건 충족률만 본다.
- 매핑된 절대 호수를 사람 검토 없이 DB에 쓰지 않는다.

## 4. 넘기기 전에 통과해야 하는 것

```
cd code/7_advanced_recommender
python ops.py verify      # 파이썬 테스트 · 웹 테스트 · 평가 · 린트 · 빌드
```

DB나 배포를 건드렸으면 추가로:

```
python ops.py health      # DB 연결 · 공개 키 권한 · 배포 사이트 · 번들 키 검사
python ops.py status      # 상품 수 · 프로필 버전 일치 · 신선도
```

`verify`가 실패한 채로 다른 에이전트에게 넘기지 않는다. CI(`quality.yml`)가 같은 것을 돌린다.

## 5. 에이전트끼리의 작업 규칙

**작업 보드**: `docs/작업보드.md`에 진행 중·다음 작업이 있다.
- 시작할 때 해당 항목에 자기 이름과 시각을 적고 커밋한다 (`- [ ] (claude, 09-19 02:10) ...`).
- 끝나면 `[x]`로 바꾸고 결과 한 줄을 남긴다.
- 다른 에이전트가 점유한 항목은 건드리지 않는다.

**동시 작업**: 서로 다른 항목이면 같은 브랜치(`main`)에서 작업해도 된다. 단 파일이 겹치면 안 된다.
겹칠 수밖에 없으면 브랜치를 판다 (`agent/<이름>/<항목>`).

**커밋**: 무엇을 왜 바꿨는지 쓴다. 판단이 갈릴 수 있는 선택은 이유를 남긴다.
측정값을 근거로 삼았으면 수치를 적는다. 단위(리뷰/문장/쌍)를 섞지 않는다.

**모르면 추정하지 않는다.** 데이터로 확인하고, 확인 못 했으면 확인 못 했다고 쓴다.
이 프로젝트에서 가장 많이 난 사고가 "확인 안 하고 추론한 것"이다.

## 6. 자주 쓰는 명령

```
cd code/7_advanced_recommender

# 수집 (올리브영. 기본은 dry-run, --write 해야 저장)
python -m scraper.crawler --products-only --write      # 상품·옵션만, 리뷰 건너뜀
python run_pipeline.py --write                         # 수집 + 프로필 한 번에
python run_pipeline.py --write --profiles-only         # 저장된 리뷰로 프로필만

# 분석
python pipeline/shade_coverage.py                      # 호수 구분 현황
python pipeline/shade_mapping.py                       # 브랜드 호수 매핑 리포트

# 웹
cd web && npm ci && npm run dev                        # 개발 서버
npm run snapshot                                       # 평가용 카탈로그 스냅샷 갱신
```

`.pipeline-cache/`에 커서·캐시·실행 리포트가 쌓인다. Git에 넣지 않는다.
수집은 중단돼도 캐시로 이어서 진행된다.

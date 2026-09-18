# AGENTS.md — 이 저장소에서 작업하는 규칙

여러 에이전트(Codex, Claude Code, Antigravity)가 같은 저장소를 번갈아 작업한다.
이 파일이 공통 계약이다. 도구별 설정 파일은 이 문서를 가리키기만 하고 내용을 복제하지 않는다.

작업 시작 전 이 문서와 `docs/작업보드.md`를 읽는다.

```
cd code/7_advanced_recommender
python ops.py status      # 지금 데이터가 어떤 상태인지
python ops.py verify      # 넘겨받은 코드가 통과 상태인지
```

`verify`가 실패한 채로 넘어왔으면 그것부터 고친다. 새 작업을 얹지 않는다.

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

도구끼리 직접 통신하지 않는다. 조율은 **저장소에 남긴 상태**로만 한다.
공유되는 것은 Git 저장소와 Supabase DB 두 개뿐이다.

### 5.1 기본은 직렬 릴레이

한 번에 한 에이전트가 작업하고 넘긴다. 이 저장소의 일은 대체로 순서가 있고
(수집 → 측정 → 조정), 공유 상태(DB, 올리브영 레이트 리밋)가 병렬에 맞지 않는다.
병렬은 아래 5.4 조건을 만족할 때만 한다.

### 5.2 교대 절차

```
받을 때   git pull
          python ops.py status         # 데이터가 어떤 상태인지
          python ops.py verify         # 넘겨받은 코드가 통과 상태인지
          docs/작업보드.md 에서 항목 점유 → 커밋·푸시

작업 중   ...

넘길 때   python ops.py verify         # 통과해야 넘긴다
          커밋·푸시
          보드 [x] + 결과 한 줄 (수치가 있으면 수치로)
```

`verify` 실패 상태로 넘기지 않는다. 받았는데 실패 상태면 그것부터 고치고 새 작업을 얹지 않는다.

### 5.3 같이 하면 안 되는 것

- **올리브영 수집 두 개 동시** — 레이트 리밋에 걸려 둘 다 죽는다. 수집은 항상 한 번에 하나
- **`build_profiles.py --write` 동시** — 같은 행에 경쟁 쓰기가 난다
- **같은 파일 편집** — 보드에 항목마다 건드리는 파일을 적어 두었으니 먼저 확인한다

### 5.4 병렬로 해도 되는 조건

세 가지가 모두 참일 때만: ① 보드 항목이 다르고 ② 파일 집합이 겹치지 않고 ③ DB에 쓰지 않는다.
이때는 같은 `main`에서 작업해도 된다. 하나라도 어긋나면 브랜치를 판다 (`agent/<이름>/<항목>`).

### 5.5 `.pipeline-cache/`는 공유되지 않는다

수집 커서·상세 캐시·실행 리포트는 **그 PC의 로컬 디스크**에 있고 Git에 들어가지 않는다.
다른 PC에서 수집을 이어받으면 캐시가 없어 처음부터 다시 훑는다. 수집은 가급적 같은 PC에서 이어서 한다.

### 5.6 검수는 작성한 에이전트가 아닌 쪽이 한다

이 프로젝트에서 가장 많이 난 사고는 **확인하지 않고 추론한 것**이다
("이 카테고리는 원래 호수가 없다" 같은 것). 같은 에이전트는 자기 추론을 다시 의심하지 않는다.
교대 시 받는 쪽이 앞 작업의 주장 중 데이터로 확인되지 않은 것을 먼저 찾아본다.

### 5.7 사람 없이 교대하기 (Claude ↔ Codex)

두 CLI는 서로를 호출할 수 있다. 사람이 한 번 요청하면 나머지는 자동으로 돌 수 있다.

```
python ops.py crosscheck              # Claude가 Codex에게 이 변경의 검수를 맡긴다
python ops.py crosscheck --base main  # 기준 변경
```

`codex review --base <기준>`을 실행한다. Codex는 `AGENTS.md`를 스스로 읽으므로 위 3장의
불변조건이 그대로 검수 기준이 된다 (`codex review`는 `--base`와 커스텀 프롬프트를 같이 못 받는다).
검수 결과는 참고용이라 실패로 처리하지 않는다. Codex 한도가 소진됐으면 그 사실을 알리고 넘어간다.

반대 방향도 같다. Codex 쪽에서는 `claude -p "<프롬프트>"`로 호출한다.

`.mcp.json`에 `codex mcp-server`를 등록해 두었다. Claude Code를 다시 시작하면 Codex가
네이티브 도구로 잡힌다 (첫 사용 시 승인을 묻는다). 아직 실제로 붙여서 확인하지는 않았다.

**Antigravity는 이 고리에 들어오지 못한다.** `antigravity chat --mode agent "<프롬프트>"`는
GUI 창에 프롬프트를 던질 뿐 결과를 호출자에게 돌려주지 않는다. VS Code 포크라 헤드리스
에이전트 모드가 없다. 사람이 직접 쓰는 IDE로만 참여한다.

권장 고리: **Claude가 작업 → `ops.py verify` → `ops.py crosscheck`로 Codex 검수 →
지적사항 반영 → 다시 `verify` → 커밋·푸시.** 작성자와 검수자가 다른 모델이라 5.6의 목적이 자동으로 달성된다.

### 5.8 커밋

무엇을 왜 바꿨는지 쓴다. 판단이 갈릴 수 있는 선택은 이유를 남긴다.
측정값을 근거로 삼았으면 수치를 적고, 단위(리뷰 수·문장 수·추출 쌍 수)를 섞지 않는다.

**모르면 추정하지 않는다.** 데이터로 확인하고, 확인 못 했으면 확인 못 했다고 쓴다.

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

# CLAUDE.md

작업 규칙은 [AGENTS.md](AGENTS.md)에 있다. 시작 전에 그것과 `docs/작업보드.md`를 읽는다.
여기에는 Claude Code에서만 해당되는 것만 적는다. 규칙을 복제하지 않는다 — 두 벌이 되면 갈라진다.

## 환경

Windows 11 + PowerShell이 기본이고 Bash 도구도 쓸 수 있다. 각각 문법이 다르니 섞지 않는다.
Python은 `C:\Users\USER\miniconda3\python.exe`, Node는 24.x다.

경로에 한글이 들어간다(`남성화장품시장분석`). 이것 때문에:
- `next build`는 Turbopack에서 UTF-8 경계 패닉이 난다. `package.json`의 `build`가 `--webpack`으로 고정돼 있다. 되돌리지 않는다.
- 셸에서 경로를 넘길 때는 따옴표로 감싼다.
- `urllib`로 한글이 든 URL을 만들 때 `urllib.parse.quote`를 거치지 않으면 `UnicodeEncodeError`가 난다.

## 오래 걸리는 작업

올리브영 전체 수집은 1시간이 넘는다. `run_in_background: true`로 돌리고 완료 알림을 기다린다.
진행 확인은 `.pipeline-cache/catalog-details.json` 크기로 한다.

수집 중에는 올리브영에 추가 요청을 보내지 않는다. 레이트 리밋에 걸려 돌던 작업이 죽는다.
`RateLimited`가 뜨면 delay를 올린다 (1.5초에서 걸린 적 있음, 2.5초는 안정적).

## 파일 편집

`.tsx`/`.ts`의 여러 줄 JSX는 Bash 힐독으로 쓰면 따옴표 때문에 깨진다. Write/Edit 도구를 쓴다.
Python 생성 스크립트로 파일을 쓸 때 정규식의 `\b`, `\s`는 raw 문자열을 쓰거나 `\\`로 이스케이프한다
(`\b`를 놓쳐 백스페이스 문자가 들어간 적 있다).

## 확인 습관

이 프로젝트에서 반복된 실수는 **데이터를 안 보고 추론한 것**이다.
"이 카테고리는 원래 호수가 없다" 같은 판단은 반드시 DB나 API로 확인한 뒤에 말한다.
집계를 보고할 때 리뷰 수·문장 수·추출 쌍 수는 서로 다른 값이다. 라벨을 정확히 붙인다.

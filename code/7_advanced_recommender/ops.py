"""One entry point for checking this project.

The checks sit in three groups because they fail for different reasons and need
different things to be true:

  verify  offline gates. No network, no keys. Mirrors CI, and is what an agent
          must pass before handing work to another agent.
  health  live checks against Supabase and the deployed site. Needs .env.
          Answers "is the thing actually working right now".
  status  what the data looks like: counts, profile currency, freshness.

Exit code is non-zero when a check fails, so this works as a gate.

    python ops.py verify | health | status | all
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
SITE = "https://moon001208.github.io/MANS-BEAUTY/"
STALE_DAYS = 30


class Checks:
    """Collects pass/fail so one run reports everything instead of stopping at the first fault."""

    def __init__(self):
        self.failed = 0

    def record(self, ok, label, detail="", warn_only=False):
        mark = "  OK  " if ok else (" WARN " if warn_only else " FAIL ")
        print(f"[{mark}] {label}" + (f" - {detail}" if detail else ""))
        if not ok and not warn_only:
            self.failed += 1
        return ok


def _run(command, cwd, label, checks):
    result = subprocess.run(command, cwd=cwd, shell=True, capture_output=True, text=True)
    lines = (result.stdout + result.stderr).strip().splitlines()
    detail = "" if result.returncode == 0 else (lines[-1][:120] if lines else f"exit {result.returncode}")
    checks.record(result.returncode == 0, label, detail)


def verify(checks):
    """Offline gates, in the same order quality.yml runs them."""
    print("- 오프라인 검증 (CI와 동일) -")
    _run(f'"{sys.executable}" -m unittest discover -s tests', ROOT, "파이썬 테스트", checks)
    if not (WEB / "node_modules").exists():
        checks.record(False, "웹 의존성", "node_modules 없음 - web에서 npm ci 필요", warn_only=True)
        return
    for command, label in [
        ("npm test", "웹 테스트"),
        ("npm run eval", "추천 평가"),
        ("npm run lint", "린트"),
        ("npm run build", "빌드 + 번들 키 검사"),
    ]:
        _run(command, WEB, label, checks)


def _env():
    """Server keys from .env, public keys from web/.env.local, else the environment."""
    values = {}
    for path in (ROOT / ".env", WEB / ".env.local"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.strip().split("=", 1)
                values[key] = value
    for key in ("SUPABASE_URL", "SUPABASE_SECRET_KEY"):
        values.setdefault(key, os.getenv(key, ""))
    return values


def _get(url, key, path, params=""):
    request = urllib.request.Request(
        f"{url}/rest/v1/{path}?{params}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def health(checks):
    """A green verify with a red health means the data or the deploy drifted, not the code."""
    print("- 라이브 상태 -")
    env = _env()
    url, secret = env.get("SUPABASE_URL"), env.get("SUPABASE_SECRET_KEY")
    public = env.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY") or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not checks.record(bool(url and secret), "DB 자격증명", "" if url and secret else ".env에 SUPABASE_URL/SECRET_KEY 없음"):
        return
    try:
        _get(url, secret, "products", "select=id&limit=1")
        checks.record(True, "DB 연결 (서버 키)")
    except Exception as error:
        checks.record(False, "DB 연결 (서버 키)", type(error).__name__)
        return
    if public:
        try:
            _get(url, public, "products", "select=id&limit=1")
            checks.record(True, "공개 키 조회")
        except Exception as error:
            checks.record(False, "공개 키 조회", type(error).__name__)
        try:
            _get(url, public, "reviews", "select=author&limit=1")
            checks.record(False, "작성자 열 차단", "공개 키로 author가 읽힘 - RLS 권한 확인 필요")
        except Exception:
            checks.record(True, "작성자 열 차단")
    else:
        checks.record(False, "공개 키", "web/.env.local 없음", warn_only=True)
    try:
        request = urllib.request.Request(SITE, headers={"user-agent": "ops-check"})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", "replace")
            status_code = response.status
        checks.record(status_code == 200, "배포 사이트 응답", f"HTTP {status_code}")
        checks.record("sb_secret" not in body and "service_role" not in body, "배포 HTML에 관리자 키 없음")
    except Exception as error:
        checks.record(False, "배포 사이트 응답", type(error).__name__)


def status(checks):
    """Counts and freshness. Stale data fails nothing on its own, so it warns."""
    print("- 데이터 현황 -")
    sys.path.insert(0, str(ROOT))
    from pipeline.profiles import VERSION

    env = _env()
    url, secret = env.get("SUPABASE_URL"), env.get("SUPABASE_SECRET_KEY")
    if not checks.record(bool(url and secret), "DB 자격증명"):
        return
    products, cursor = [], None
    while True:
        params = "select=id,last_updated_at,profile_metadata&order=id&limit=500"
        if cursor:
            params += f"&id=gt.{cursor}"
        page = _get(url, secret, "products", params)
        if not page:
            break
        products.extend(page)
        cursor = page[-1]["id"]
    current = [p for p in products if (p.get("profile_metadata") or {}).get("version") == VERSION]
    analysed = sum((p.get("profile_metadata") or {}).get("analyzed_count", 0) for p in current)
    lineups = sum(1 for p in current if (p.get("profile_metadata") or {}).get("shade_lineup"))
    shaded = lineups + sum(1 for p in current if (p.get("profile_metadata") or {}).get("absolute_shade_source"))
    print(f"   상품 {len(products)}개 · 분석 리뷰 {analysed:,}건 · 호수 라인업 {lineups}개")
    checks.record(len(products) > 0, "상품 존재", f"{len(products)}개")
    checks.record(len(current) == len(products), f"프로필 버전 최신 ({VERSION})", f"{len(current)}/{len(products)}")
    if products:
        checks.record(shaded > 0, "호수 정보 보유", f"{shaded}/{len(products)} ({shaded / len(products) * 100:.0f}%)", warn_only=True)
    stamps = [p.get("last_updated_at") for p in products if p.get("last_updated_at")]
    if stamps:
        newest = max(stamps)
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(newest.replace("Z", "+00:00"))).days
        checks.record(age <= STALE_DAYS, "수집 신선도", f"최근 갱신 {newest[:10]} ({age}일 전)", warn_only=True)


def crosscheck(checks, base):
    """Have Codex review what changed since `base`.

    A second model reading the diff catches this project's recurring failure:
    a confident claim nobody checked against the data. Codex reads AGENTS.md on
    its own, so the invariants reach it without a prompt here -- which is just
    as well, since `codex review` refuses a custom prompt alongside --base.
    Findings are advisory, so an unavailable Codex warns rather than fails.
    """
    print(f"- 교차 검수 (codex, {base} 대비) -")
    # npm installs codex as a .CMD shim on Windows, which only resolves once
    # shutil.which has expanded PATHEXT.
    executable = shutil.which("codex")
    if not executable:
        checks.record(False, "codex 실행", "codex CLI를 PATH에서 찾지 못함", warn_only=True)
        return
    try:
        result = subprocess.run([executable, "review", "--base", base],
                                cwd=ROOT.parent.parent, capture_output=True, text=True, timeout=900)
    except OSError as error:
        checks.record(False, "codex 실행", type(error).__name__, warn_only=True)
        return
    except subprocess.TimeoutExpired:
        checks.record(False, "codex 실행", "15분 초과", warn_only=True)
        return
    output = (result.stdout + result.stderr).strip()
    if "usage limit" in output:
        checks.record(False, "codex 실행", "사용량 한도 소진 - 리셋 후 재시도", warn_only=True)
        return
    checks.record(result.returncode == 0, "codex 실행", "" if result.returncode == 0 else f"exit {result.returncode}", warn_only=True)
    print(output[-4000:] if output else "   (출력 없음)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["verify", "health", "status", "crosscheck", "all"])
    parser.add_argument("--base", default="origin/main", help="crosscheck가 비교할 기준 (기본: origin/main)")
    args = parser.parse_args()
    checks = Checks()
    names = ["verify", "health", "status"] if args.command == "all" else [args.command]
    for name in names:
        if name == "crosscheck":
            crosscheck(checks, args.base)
        else:
            {"verify": verify, "health": health, "status": status}[name](checks)
        print()
    print("모두 통과" if not checks.failed else f"실패 {checks.failed}건")
    return 1 if checks.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

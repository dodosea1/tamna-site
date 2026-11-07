"""검사 → 빌드 → 커밋 → 푸시. 사이트에 올리는 유일한 경로.

사용: python tools/publish.py --message "log: 2026-11-07" [--root <저장소>] [--terms <목록>] [--no-push] [--dry-run]
- 검사(금지어·패턴)에 걸리면 멈춘다. 커밋 메시지도 검사한다.
- data/site.json의 site_url이 자리 표시(example.)면 멈춘다.
- 앞머리에 draft: true가 있는 글은 커밋하지 않는다.
- 이전에 푸시가 실패해 남은 커밋이 있으면, 변경이 없어도 푸시를 다시 시도한다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.lint_public import DEFAULT_TERMS, load_terms, scan_text  # noqa: E402
from tools.sitegen.content import draft_files  # noqa: E402

PUBLISH_PATHS = ("content", "data", "media")


def _run(cmd: list[str], cwd: Path) -> int:
    print("$ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd).returncode


def _git_out(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(["git", *cmd], cwd=cwd, capture_output=True, text=True).stdout.strip()


def _commits_ahead_of_origin(root: Path) -> int:
    """origin에 아직 없는 커밋 수. 원격이 없으면 0, 원격은 있는데 origin/main이 없으면(첫 푸시 실패) main 전체."""
    has_origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, capture_output=True, text=True).returncode == 0
    if not has_origin:
        return 0
    probe = subprocess.run(["git", "rev-parse", "--verify", "-q", "origin/main"], cwd=root, capture_output=True, text=True)
    rng = "origin/main..main" if probe.returncode == 0 else "main"
    count = _git_out(["rev-list", "--count", rng], root)
    return int(count) if count.isdigit() else 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="사이트 게시")
    parser.add_argument("--message", required=True)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--terms", default=str(DEFAULT_TERMS))
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="검사와 빌드만 하고 커밋·푸시는 하지 않는다")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    rc = _run([sys.executable, str(root / "tools" / "lint_public.py"), "--root", str(root), "--terms", args.terms], root)
    if rc != 0:
        print(f"검사 실패(종료 {rc}). 게시를 중단합니다.")
        return rc
    terms = load_terms(Path(args.terms))
    if scan_text(args.message, terms):
        print("커밋 메시지에 비공개 단어나 패턴이 있습니다. 게시를 중단합니다.")
        return 1

    site = json.loads((root / "data" / "site.json").read_text(encoding="utf-8"))
    if "example." in site.get("site_url", ""):
        print("data/site.json의 site_url이 아직 자리 표시(example.)입니다. 실제 주소를 넣은 뒤 게시하세요.")
        return 1

    rc = _run([sys.executable, str(root / "build.py"), "--root", str(root), "--out", str(root / "_site")], root)
    if rc != 0:
        print(f"빌드 실패(종료 {rc}). 게시를 중단합니다.")
        return rc

    status = _git_out(["status", "--porcelain", "--", *PUBLISH_PATHS], root)
    ahead = _commits_ahead_of_origin(root)
    if not status and ahead == 0:
        print("변경 없음. 게시할 것이 없습니다.")
        return 0
    if args.dry_run:
        print("dry-run: 커밋·푸시를 생략합니다.")
        return 0

    if status:
        rc = _run(["git", "add", "-A", "--", *PUBLISH_PATHS], root)
        if rc != 0:
            return rc
        drafts = [str(p.relative_to(root).as_posix()) for p in draft_files(root / "content")]
        if drafts:
            print("초안(draft: true)은 올리지 않습니다: " + ", ".join(drafts))
            _run(["git", "reset", "-q", "--", *drafts], root)
        staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root).returncode
        if staged == 0:
            print("초안을 빼고 나니 올릴 변경이 없습니다.")
        else:
            rc = _run(["git", "commit", "-q", "-m", args.message], root)
            if rc != 0:
                return rc
    else:
        print(f"올리지 못한 커밋 {ahead}개가 있어 푸시만 다시 시도합니다.")

    if args.no_push:
        print("no-push: 커밋만 했습니다.")
        return 0
    rc = _run(["git", "push", "origin", "main"], root)
    if rc != 0:
        print("푸시 실패. 원격 설정과 로그인을 확인하고, 원격에 다른 커밋이 있으면 `git pull --rebase origin main` 뒤 다시 실행하세요.")
        return rc
    print("게시 완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

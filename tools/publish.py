"""검사 → 빌드 → 커밋 → 푸시. 사이트에 올리는 유일한 경로.

사용: python tools/publish.py --message "log: 2026-11-07" [--root <저장소>] [--terms <목록>] [--no-push] [--dry-run]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PUBLISH_PATHS = ("content", "data", "media")


def _run(cmd: list[str], cwd: Path) -> int:
    print("$ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd).returncode


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="사이트 게시")
    parser.add_argument("--message", required=True)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--terms", default=None)
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="검사와 빌드만 하고 커밋·푸시는 하지 않는다")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    lint = [sys.executable, str(root / "tools" / "lint_public.py"), "--root", str(root)]
    if args.terms:
        lint += ["--terms", args.terms]
    rc = _run(lint, root)
    if rc != 0:
        print(f"검사 실패(종료 {rc}). 게시를 중단합니다.")
        return rc

    rc = _run([sys.executable, str(root / "build.py"), "--root", str(root), "--out", str(root / "_site")], root)
    if rc != 0:
        print(f"빌드 실패(종료 {rc}). 게시를 중단합니다.")
        return rc

    status = subprocess.run(["git", "status", "--porcelain", "--", *PUBLISH_PATHS], cwd=root, capture_output=True, text=True)
    if not status.stdout.strip():
        print("변경 없음. 게시할 것이 없습니다.")
        return 0
    if args.dry_run:
        print("dry-run: 커밋·푸시를 생략합니다.")
        return 0

    rc = _run(["git", "add", "-A", "--", *PUBLISH_PATHS], root)
    if rc != 0:
        return rc
    rc = _run(["git", "commit", "-q", "-m", args.message], root)
    if rc != 0:
        return rc
    if args.no_push:
        print("no-push: 커밋만 했습니다.")
        return 0
    rc = _run(["git", "push", "origin", "main"], root)
    if rc != 0:
        print("푸시 실패. 원격 설정과 로그인을 확인하세요.")
        return rc
    print("게시 완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

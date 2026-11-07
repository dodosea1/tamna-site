"""공개 저장소에 비공개 내용이 섞이지 않았는지 검사한다.

사용: python tools/lint_public.py [--root .] [--terms ~/.claude/tamna-private-terms.txt]
종료 코드: 0 깨끗, 1 발견, 2 금지어 목록 파일 없음(실패 닫힘).
검사 범위: git이 아는 파일 전부(추적 중 + 추적 안 된 파일, 무시 파일 제외) 가운데 글자 파일. media/ 아래는 파일 이름만.
맞은 문자열 자체는 출력하지 않는다(경로:줄: 규칙 이름만).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_TERMS = Path.home() / ".claude" / "tamna-private-terms.txt"
TEXT_SUFFIXES = {".md", ".json", ".html", ".css", ".txt", ".yml", ".yaml", ".js", ".py", ".toml", ".cfg", ".ini", ".svg", ".xml"}
SKIP_DIRS = {"_site", "_preview", "__pycache__"}  # 점으로 시작하는 폴더는 .github 빼고 모두 건너뛴다

PATTERNS = {
    "windows-path": re.compile(r"[A-Za-z]:\\"),
    "ip-port": re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"),
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b0\d{1,2}-\d{3,4}-\d{4}\b"),
}


def load_terms(path: Path) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    terms = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line)
    return terms


def scan_text(text: str, terms: list[str]) -> list[str]:
    hits: list[str] = []
    lowered = text.lower()
    for i, term in enumerate(terms, start=1):
        if term.lower() in lowered:
            hits.append(f"term:{i}")
    for name, pattern in PATTERNS.items():
        if pattern.search(text):
            hits.append(name)
    return hits


def _git_files(root: Path) -> list[Path] | None:
    """git이 아는 파일(추적 + 미추적, 무시 제외). git 저장소가 아니면 None."""
    if not (root / ".git").exists():
        return None
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    names = [n for n in proc.stdout.decode("utf-8", errors="replace").split("\0") if n]
    return [root / n for n in names]


def _walk_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS or (part.startswith(".") and part != ".github") for part in parts[:-1]):
            continue
        if path.is_file():
            out.append(path)
    return out


def scan_tree(root: Path, terms: list[str], exclude: tuple[Path, ...] = ()) -> list[tuple[str, int, str]]:
    root = Path(root)
    excluded = {Path(p).resolve() for p in exclude}
    files = _git_files(root)
    if files is None:
        files = _walk_files(root)
    findings: list[tuple[str, int, str]] = []
    for path in files:
        if not path.is_file() or path.resolve() in excluded:
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith("media/"):
            for rule in scan_text(path.name, terms):
                findings.append((rel, 0, rule))
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES or path.name.upper().startswith("OFL"):
            continue  # 글꼴 라이선스 원문(OFL*)은 제3자 공개 문서라 건너뛴다
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            for rule in scan_text(line, terms):
                findings.append((rel, lineno, rule))
    return findings


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="공개 내용 검사")
    parser.add_argument("--root", default=".")
    parser.add_argument("--terms", default=str(DEFAULT_TERMS))
    args = parser.parse_args(argv)
    try:
        terms = load_terms(Path(args.terms))
    except FileNotFoundError:
        print(f"금지어 목록이 없습니다: {args.terms} (검사를 통과시키지 않습니다)")
        return 2
    findings = scan_tree(Path(args.root), terms, exclude=(Path(args.terms),))
    for rel, lineno, rule in findings:
        print(f"{rel}:{lineno}: {rule}")
    if findings:
        print(f"발견 {len(findings)}건. 고친 뒤 다시 검사하세요.")
        return 1
    print("깨끗합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

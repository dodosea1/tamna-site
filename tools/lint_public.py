"""공개 저장소에 비공개 내용이 섞이지 않았는지 검사한다.

사용: python tools/lint_public.py [--root .] [--terms ~/.claude/tamna-private-terms.txt]
종료 코드: 0 깨끗, 1 발견, 2 금지어 목록 파일 없음(실패 닫힘).
맞은 문자열 자체는 출력하지 않는다(경로:줄: 규칙 이름만).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_TERMS = Path.home() / ".claude" / "tamna-private-terms.txt"
SCAN_DIRS = ("content", "data", "templates", "static")
SCAN_SUFFIXES = {".md", ".json", ".html", ".css", ".txt", ".yml", ".yaml", ".js"}

PATTERNS = {
    "windows-path": re.compile(r"[A-Za-z]:\\"),
    "ip-port": re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
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


def _files(root: Path):
    for name in SCAN_DIRS:
        folder = root / name
        if folder.exists():
            for path in sorted(folder.rglob("*")):
                if path.is_file() and path.suffix.lower() in SCAN_SUFFIXES:
                    yield path
    for path in sorted(root.glob("*.md")):
        yield path


def scan_tree(root: Path, terms: list[str]) -> list[tuple[str, int, str]]:
    root = Path(root)
    findings: list[tuple[str, int, str]] = []
    for path in _files(root):
        rel = path.relative_to(root).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            for rule in scan_text(line, terms):
                findings.append((rel, lineno, rule))
    media = root / "media"
    if media.exists():
        for path in sorted(media.rglob("*")):
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                for rule in scan_text(path.name, terms):
                    findings.append((rel, 0, rule))
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
    findings = scan_tree(Path(args.root), terms)
    for rel, lineno, rule in findings:
        print(f"{rel}:{lineno}: {rule}")
    if findings:
        print(f"발견 {len(findings)}건. 고친 뒤 다시 검사하세요.")
        return 1
    print("깨끗합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""기록(log)·페이지·월간 글을 읽어 구조로 만든다."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from tools.sitegen.frontmatter import parse_frontmatter, split_list

REQUIRED_LOG_SECTIONS = ("한 일", "막힌 것", "다음에 손댈 것 (약속 아님)")
DATE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class LogEntry:
    date: str
    title: str
    media: list[str]
    body_md: str
    next_items: list[str] = field(default_factory=list)


@dataclass
class Page:
    slug: str
    title: str
    order: int
    body_md: str


@dataclass
class Monthly:
    month: str
    title: str
    summary_en: str
    body_md: str


def extract_section(body_md: str, heading_prefix: str) -> str:
    """`## <heading_prefix>...` 절의 내용을 다음 `## ` 전까지 돌려준다. 없으면 ''."""
    lines = body_md.split("\n")
    out: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip().startswith(heading_prefix)
            continue
        if inside:
            out.append(line)
    return "\n".join(out)


def bullet_items(section_md: str) -> list[str]:
    return [line[2:].strip() for line in section_md.split("\n") if line.startswith("- ")]


def has_heading(body_md: str, heading: str) -> bool:
    """정확히 `## <heading>`인 줄이 있는지 본다(H3나 본문 속 인용은 안 됨)."""
    return re.search(rf"^## {re.escape(heading)}\s*$", body_md, re.MULTILINE) is not None


def is_draft(meta: dict[str, str]) -> bool:
    return meta.get("draft", "").strip().lower() in ("true", "yes", "1")


def _read(path: Path) -> tuple[dict[str, str], str]:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def load_logs(log_dir: Path) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for path in sorted(log_dir.glob("*.md")):
        meta, body = _read(path)
        if is_draft(meta):
            continue
        for heading in REQUIRED_LOG_SECTIONS:
            if not has_heading(body, heading):
                raise ValueError(f"{path.name}: '## {heading}' 절이 없습니다")
        date = meta.get("date", path.stem)
        if not DATE_NAME.match(path.stem) or date != path.stem:
            raise ValueError(f"{path.name}: 파일 이름은 YYYY-MM-DD.md이고 date와 같아야 합니다 (date: {date})")
        next_items = bullet_items(extract_section(body, "다음에 손댈 것"))
        if not next_items:
            raise ValueError(f"{path.name}: '다음에 손댈 것' 절에 '- ' 항목이 없습니다")
        entries.append(
            LogEntry(
                date=date,
                title=meta.get("title", date),
                media=split_list(meta.get("media", "")),
                body_md=body,
                next_items=next_items,
            )
        )
    entries.sort(key=lambda e: e.date, reverse=True)
    return entries


def load_pages(pages_dir: Path) -> list[Page]:
    pages: list[Page] = []
    for path in sorted(pages_dir.glob("*.md")):
        meta, body = _read(path)
        if is_draft(meta):
            continue
        if "title" not in meta or "order" not in meta:
            raise ValueError(f"{path.name}: title과 order가 필요합니다")
        pages.append(Page(slug=meta.get("slug", path.stem), title=meta["title"], order=int(meta["order"]), body_md=body))
    pages.sort(key=lambda p: p.order)
    return pages


def load_monthly(monthly_dir: Path) -> list[Monthly]:
    posts: list[Monthly] = []
    for path in sorted(monthly_dir.glob("*.md")):
        meta, body = _read(path)
        if is_draft(meta):
            continue
        posts.append(
            Monthly(
                month=path.stem,
                title=meta.get("title", path.stem),
                summary_en=meta.get("summary_en", ""),
                body_md=body,
            )
        )
    posts.sort(key=lambda m: m.month, reverse=True)
    return posts


def draft_files(content_dir: Path) -> list[Path]:
    """content/ 아래에서 draft: true인 글 파일 목록."""
    out: list[Path] = []
    for path in sorted(content_dir.rglob("*.md")):
        meta, _ = _read(path)
        if is_draft(meta):
            out.append(path)
    return out

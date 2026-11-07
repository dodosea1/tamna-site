"""기록(log)·페이지·월간 글을 읽어 구조로 만든다."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tools.sitegen.frontmatter import parse_frontmatter, split_list

REQUIRED_LOG_SECTIONS = ("한 일", "막힌 것", "다음에 손댈 것 (약속 아님)")


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


def _read(path: Path) -> tuple[dict[str, str], str]:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def load_logs(log_dir: Path) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for path in sorted(log_dir.glob("*.md")):
        meta, body = _read(path)
        for heading in REQUIRED_LOG_SECTIONS:
            if f"## {heading}" not in body:
                raise ValueError(f"{path.name}: '{heading}' 절이 없습니다")
        date = meta.get("date", path.stem)
        entries.append(
            LogEntry(
                date=date,
                title=meta.get("title", date),
                media=split_list(meta.get("media", "")),
                body_md=body,
                next_items=bullet_items(extract_section(body, "다음에 손댈 것")),
            )
        )
    entries.sort(key=lambda e: e.date, reverse=True)
    return entries


def load_pages(pages_dir: Path) -> list[Page]:
    pages: list[Page] = []
    for path in sorted(pages_dir.glob("*.md")):
        meta, body = _read(path)
        if "title" not in meta or "order" not in meta:
            raise ValueError(f"{path.name}: title과 order가 필요합니다")
        pages.append(Page(slug=meta.get("slug", path.stem), title=meta["title"], order=int(meta["order"]), body_md=body))
    pages.sort(key=lambda p: p.order)
    return pages


def load_monthly(monthly_dir: Path) -> list[Monthly]:
    posts: list[Monthly] = []
    for path in sorted(monthly_dir.glob("*.md")):
        meta, body = _read(path)
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

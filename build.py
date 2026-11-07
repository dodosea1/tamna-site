"""정적 사이트 생성기.

사용: python build.py [--root .] [--out _site] [--base /tamna-site]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from html import escape
from pathlib import Path

from tools.sitegen.content import LogEntry, Monthly, bullet_items, extract_section, load_logs, load_monthly, load_pages
from tools.sitegen.feed import FeedItem, build_rss
from tools.sitegen.render import fill, md_to_html, render_template
from tools.sitegen.tables import ai_table, feedback_table, roadmap_section, support_section


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _li(items: list[str], empty: str = "아직 없습니다") -> str:
    if not items:
        return f"<li>{empty}</li>"
    return "".join(f"<li>{escape(i)}</li>" for i in items)


def _media_html(base: str, path: str, label: str = "") -> str:
    src = f"{base}/{path}"
    caption = f'<figcaption>{escape(label)}</figcaption>' if label else ""
    if path.lower().endswith(".mp4"):
        tag = f'<video src="{src}" controls muted playsinline preload="metadata"></video>'
    else:
        tag = f'<img src="{src}" alt="{escape(label or path)}" loading="lazy">'
    return f"<figure>{tag}{caption}</figure>"


def _link_or_prep(url: str, label: str) -> str:
    if url:
        return f'<a class="button" href="{escape(url)}" rel="noopener">{escape(label)}</a>'
    return f'<span class="muted">{escape(label)}: 준비 중</span>'


def _email_html(user: str, domain: str) -> str:
    if not user or not domain:
        return '<span class="muted">메일 주소: 준비 중</span>'
    return f'<span class="email" data-u="{escape(user)}" data-d="{escape(domain)}">메일 주소 (스크립트가 켜져 있어야 보입니다)</span>'


def _log_link(base: str, log: LogEntry) -> str:
    return f'<li><a href="{base}/log/{log.date}/">{escape(log.date)} · {escape(log.title)}</a></li>'


def _monthly_link(base: str, m: Monthly) -> str:
    return f'<li><a href="{base}/monthly/{m.month}/">{escape(m.month)} · {escape(m.title)}</a></li>'


def build_site(root: Path, out: Path, base: str | None = None) -> None:
    root = Path(root)
    out = Path(out)
    site = _load_json(root / "data" / "site.json")
    if base is None:
        base = site.get("base_path", "")
    base = base.rstrip("/")
    templates = root / "templates"
    if not templates.exists():
        templates = Path(__file__).parent / "templates"
    static = root / "static"
    if not static.exists():
        static = Path(__file__).parent / "static"

    logs = load_logs(root / "content" / "log")
    pages = load_pages(root / "content" / "pages")
    monthly = load_monthly(root / "content" / "monthly")
    data = {name: _load_json(root / "data" / f"{name}.json") for name in ("feedback", "roadmap", "support", "ai")}

    nav = "".join(f'<a href="{base}/{p.slug}/">{escape(p.title)}</a>' for p in pages if p.slug != "privacy")
    has_privacy = any(p.slug == "privacy" for p in pages)
    common = {
        "base": base,
        "nav": nav,
        "footer_links": f'<a href="{base}/privacy/">개인정보 처리방침</a> · ' if has_privacy else "",
        "site_title": site["title"],
        "tagline": site.get("tagline", ""),
        "author": site.get("author", ""),
        "inspiration": site.get("inspiration", ""),
        "summary_en": site.get("summary_en", ""),
        "year": str(date.today().year),
        "email": _email_html(site.get("email_user", ""), site.get("email_domain", "")),
        "tally_feedback": _link_or_prep(site.get("tally_feedback_url", ""), "의견 보내기 폼 열기"),
        "tally_tester": _link_or_prep(site.get("tally_tester_url", ""), "같이 사냥할 명단에 올리기"),
        "ctee": _link_or_prep(site.get("ctee_url", ""), "크티로 응원하기"),
        "threads": _link_or_prep(site.get("threads_url", ""), "스레드에서 보기"),
        "feedback_table": feedback_table(data["feedback"]),
        "roadmap_section": roadmap_section(data["roadmap"]),
        "support_section": support_section(data["support"]),
        "ai_table": ai_table(data["ai"]),
    }

    def page_html(title: str, content: str) -> str:
        return render_template("base.html", {**common, "title": title, "content": content}, templates)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # 첫 화면
    latest = logs[0] if logs else None
    hero = _media_html(base, site["hero_media"], site.get("hero_label", "")) if site.get("hero_media") else ""
    index_ctx = {
        **common,
        "hero": hero,
        "now_date": latest.date if latest else "",
        "now_items": _li(latest.next_items if latest else []),
        "latest_logs": "".join(_log_link(base, log) for log in logs[:5]) or "<li>아직 없습니다</li>",
        "latest_monthly": _monthly_link(base, monthly[0]) if monthly else "<li>아직 없습니다</li>",
    }
    _write(out / "index.html", page_html("홈", render_template("index.html", index_ctx, templates)))

    # 작업 기록
    for log in logs:
        media = "".join(_media_html(base, m) for m in log.media)
        body = md_to_html(log.body_md)
        content = render_template("log.html", {**common, "date": log.date, "title": log.title, "media": media, "body": body}, templates)
        _write(out / "log" / log.date / "index.html", page_html(f"{log.date} {log.title}", content))
    by_month: dict[str, list[str]] = {}
    for log in logs:
        by_month.setdefault(log.date[:7], []).append(_log_link(base, log))
    groups = "".join(f"<h2>{m}</h2><ul>{''.join(links)}</ul>" for m, links in by_month.items()) or "<p>아직 없습니다.</p>"
    _write(out / "log" / "index.html", page_html("작업 기록", render_template("log_index.html", {**common, "groups": groups}, templates)))

    # 이달의 정리
    for m in monthly:
        content = render_template(
            "monthly.html",
            {**common, "month": m.month, "title": m.title, "summary_en": m.summary_en, "body": md_to_html(m.body_md)},
            templates,
        )
        _write(out / "monthly" / m.month / "index.html", page_html(m.title, content))
    items = "".join(_monthly_link(base, m) for m in monthly) or "<li>아직 없습니다</li>"
    _write(out / "monthly" / "index.html", page_html("이달의 정리", render_template("monthly_index.html", {**common, "items": items}, templates)))

    # 페이지
    for page in pages:
        body = md_to_html(fill(page.body_md, common))
        content = render_template("page.html", {**common, "title": page.title, "body": body}, templates)
        _write(out / page.slug / "index.html", page_html(page.title, content))

    # RSS
    site_url = site.get("site_url", "").rstrip("/")
    feed_items = [
        FeedItem(f"기록 {log.date}: {log.title}", f"{site_url}/log/{log.date}/", log.date, " ".join(bullet_items(extract_section(log.body_md, "한 일"))))
        for log in logs
    ] + [FeedItem(f"정리 {m.month}: {m.title}", f"{site_url}/monthly/{m.month}/", f"{m.month}-01", m.summary_en) for m in monthly]
    feed_items.sort(key=lambda i: i.date, reverse=True)
    _write(out / "feed.xml", build_rss(feed_items, site["title"], site_url, "작업 기록과 이달의 정리"))

    # 정적 파일
    shutil.copytree(static, out / "static")
    media_dir = root / "media"
    if media_dir.exists():
        shutil.copytree(media_dir, out / "media")
    (out / ".nojekyll").write_text("", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="탐라(가제) 사이트 생성기")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="_site")
    parser.add_argument("--base", default=None, help="사이트가 놓이는 경로 접두어. 기본은 data/site.json의 base_path")
    args = parser.parse_args(argv)
    build_site(Path(args.root), Path(args.out), base=args.base)
    print(f"built: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

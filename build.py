"""정적 사이트 생성기.

사용: python build.py [--root .] [--out _site] [--base /tamna-site]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date
from html import escape
from pathlib import Path

from tools.sitegen.donate import donate_block, is_direct, shows_ctee
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


# 위쪽 메뉴에 두는 다섯 곳. 나머지 페이지는 아래쪽(푸터)으로 간다.
MAIN_NAV = ("game", "log", "together", "feedback", "support")
NAV_LABELS = {"log": "작업 기록", "monthly": "이달의 정리"}
# 공유 미리보기 그림. GIF는 수 MB라 미리보기에서 잘리거나 실패해 빼고, 없으면 기본 og.jpg를 쓴다.
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")


def _plain(md: str) -> str:
    """마크다운 한 줄을 설명문용 평문으로."""
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)
    md = re.sub(r"\{\{[^}]*\}\}", "", md)
    md = re.sub(r"[*_`#>]", "", md)
    return re.sub(r"\s+", " ", md).strip()


def _clip(text: str, limit: int = 150) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _first_paragraph(md: str) -> str:
    for line in md.split("\n"):
        line = line.strip()
        if line and not line.startswith(("#", "-", "|", "{{", "<")):
            text = _plain(line)
            if text:
                return text
    return ""


def _play_html(base: str, site: dict) -> str:
    """홈의 실제 게임 화면. 자동 재생·소리 없음·반복. 설정이 없으면 비운다."""
    path = site.get("play_media", "")
    if not path:
        return ""
    label = escape(site.get("play_label", ""))
    if path.lower().endswith(".mp4"):
        tag = (f'<video class="play-video" src="{base}/{path}" autoplay muted loop playsinline preload="metadata" '
               f'tabindex="0" title="누르면 멈추고, 다시 누르면 재생합니다"></video>')
    else:
        tag = f'<img class="play-video" src="{base}/{path}" alt="{label}" loading="lazy">'
    return f'<figure class="play">{tag}<figcaption>{label}</figcaption></figure>'


# 하위 페이지 머리 그림 띠. 페이지 성격에 맞는 그림을 고르고, 없으면 키아트.
PAGE_BANDS = {"game": "scene-hunt", "together": "scene-village", "about": "scene-village", "log": "key-sea", "monthly": "key-sea"}
DEFAULT_BAND = "key-hero"
# 그림마다 띠에 보일 부분(세로 위치). 하늘만 보이지 않게 아래쪽 풍경을 잡는다.
BAND_FOCUS = {"scene-hunt": "40%", "scene-village": "35%", "key-sea": "88%", "key-hero": "68%"}


def _band_html(base: str, path: str) -> str:
    section = path.split("/", 1)[0]
    if not section:
        return ""
    art = PAGE_BANDS.get(section, DEFAULT_BAND)
    return f'<div class="page-band" style="background-image:url(\'{base}/static/art/{art}-1400.webp\');background-position:center {BAND_FOCUS.get(art, "40%")}" aria-hidden="true"></div>\n'


PAGE_ICONS = {"about": "hareubang", "game": "peony", "roadmap": "road", "feedback": "letter", "help-wanted": "knot", "together": "cups", "support": "pouch"}


def _icon(base: str, name: str, cls: str = "ico") -> str:
    """민화풍 아이콘 한 개. 장식이라 alt는 비운다."""
    return f'<img class="{cls}" src="{base}/static/icons/{name}.webp" alt="">' if name else ""


def _hero_html(base: str, site: dict) -> str:
    """첫 화면 그림. 즉시 로드하고, 세로 화면용 그림이 있으면 <picture>로 바꿔 끼운다."""
    if not site.get("hero_media"):
        return ""
    html = _media_html(base, site["hero_media"], site.get("hero_label", "")).replace('loading="lazy"', 'loading="eager" fetchpriority="high"')
    mobile = site.get("hero_media_mobile")
    if mobile and "<img " in html:
        img_start = html.index("<img "); img_end = html.index(">", img_start) + 1
        source = f'<picture><source media="(max-width: 720px)" srcset="{base}/{mobile}">'
        html = html[:img_start] + source + html[img_start:img_end] + "</picture>" + html[img_end:]
    return html


VERIFY_NAMES = ("google-site-verification", "naver-site-verification")


def _verify_meta(site: dict) -> str:
    """검색 등록 소유 확인 태그. 알려진 이름과 영문·숫자·_- 값만 넣는다."""
    found = site.get("site_verification") or {}
    tags = []
    for name in VERIFY_NAMES:
        value = str(found.get(name, ""))
        if value and all(c.isascii() and (c.isalnum() or c in "_-") for c in value):
            tags.append(f'<meta name="{name}" content="{value}">')
    return "\n".join(tags)


def _link_or_prep(url: str, label: str) -> str:
    if url:
        return f'<a class="button" href="{escape(url)}" rel="noopener">{escape(label)}</a>'
    return f'<span class="muted">{escape(label)}: 준비 중</span>'


def _email_html(user: str, domain: str) -> str:
    if not user or not domain:
        return '<span class="muted">메일 주소: 준비 중</span>'
    return f'<span class="email" data-u="{escape(user)}" data-d="{escape(domain)}">메일 주소 (스크립트가 켜져 있어야 보입니다)</span>'


def _excerpt(log: LogEntry) -> str:
    items = bullet_items(extract_section(log.body_md, "한 일"))
    return items[0] if items else ""


def _log_link(base: str, log: LogEntry) -> str:
    return (f'<li><a href="{base}/log/{log.date}/"><span class="d">{escape(log.date)}</span>'
            f'<span class="t">{escape(log.title)}</span><span class="x">{escape(_excerpt(log))}</span></a></li>')


def _monthly_link(base: str, m: Monthly) -> str:
    return f'<li><a href="{base}/monthly/{m.month}/"><span class="d">{escape(m.month)}</span><span class="t">{escape(m.title)}</span></a></li>'


def _guard_out(root: Path, out: Path) -> None:
    root_r, out_r = root.resolve(), out.resolve()
    if out_r == root_r or root_r.is_relative_to(out_r):
        raise ValueError(f"출력 폴더가 저장소 자체이거나 그 상위 폴더입니다: {out_r}")
    if out_r.exists() and any(out_r.iterdir()) and not (out_r / ".nojekyll").exists():
        raise ValueError(f"출력 폴더가 비어 있지 않고 생성기 출력(.nojekyll)도 아닙니다: {out_r}")


def build_site(root: Path, out: Path, base: str | None = None) -> None:
    root = Path(root)
    out = Path(out)
    _guard_out(root, out)
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

    titles = {**{p.slug: p.title for p in pages}, **NAV_LABELS}
    icons = {**PAGE_ICONS, "log": "brush", "monthly": "moon"}
    nav = "".join(f'<a href="{base}/{slug}/">{_icon(base, icons.get(slug, ""), "nico")}{escape(titles[slug])}</a>' for slug in MAIN_NAV if slug in titles)
    footer_slugs = ["monthly"] + [p.slug for p in pages if p.slug not in MAIN_NAV and p.slug != "privacy"]
    footer_nav = " · ".join(f'<a href="{base}/{slug}/">{escape(titles[slug])}</a>' for slug in footer_slugs)
    has_privacy = any(p.slug == "privacy" for p in pages)
    site_url = site.get("site_url", "").rstrip("/")
    threads_url = site.get("threads_url", "")
    common = {
        "base": base,
        "nav": nav,
        "footer_links": f'<a href="{base}/privacy/">개인정보 처리방침</a> · ' if has_privacy else "",
        "footer_nav": footer_nav,
        "header_follow": f'<a class="follow" href="{escape(threads_url)}" rel="noopener">스레드 팔로우</a>' if threads_url else "",
        "site_title": site["title"],
        "og_image": site.get("site_url", "").rstrip("/") + "/static/art/og.jpg",
        "tagline": site.get("tagline", ""),
        "verify_meta": _verify_meta(site),
        "author": site.get("author", ""),
        "inspiration": site.get("inspiration", ""),
        "summary_en": site.get("summary_en", ""),
        "year": str(date.today().year),
        "email": _email_html(site.get("email_user", ""), site.get("email_domain", "")),
        "tally_feedback": _link_or_prep(site.get("tally_feedback_url", ""), "의견 보내기 폼 열기"),
        "tally_tester": _link_or_prep(site.get("tally_tester_url", ""), "같이 사냥할 명단에 올리기"),
        "donate": donate_block(site),
        "threads": _link_or_prep(site.get("threads_url", ""), "스레드에서 보기"),
        "feedback_table": feedback_table(data["feedback"]),
        "roadmap_section": roadmap_section(data["roadmap"]),
        "support_section": support_section(data["support"], direct=is_direct(site), ctee=shows_ctee(site)),
        "ai_table": ai_table(data["ai"]),
        "logo": f'<img class="logo-img" src="{base}/static/art/logo-cream-900.webp" alt="탐라" width="900" height="513">',
        "brand": f'<img src="{base}/static/art/logo-cream-120.webp" alt="탐라" width="120" height="68">',
    }
    for name in ("sun", "brush", "moon", "peony", "hareubang", "bell", "letter", "road", "knot", "cups", "pouch", "magpie"):
        common[f"icon_{name}"] = _icon(base, name)

    def page_html(title: str, content: str, page_title: str = "", *, path: str = "", description: str = "", image: str = "", og_type: str = "website", published: str = "") -> str:
        page_title = page_title or f"{title} · {site['title']}"
        meta = {
            "description": escape(_clip(description or site.get("tagline", ""))),
            "canonical": f"{site_url}/{path}",
            "og_type": og_type,
            "og_image": f"{site_url}/{image}" if image else common["og_image"],
            "published_meta": f'<meta property="article:published_time" content="{escape(published)}">' if published else "",
            "band": _band_html(base, path),
        }
        return render_template("base.html", {**common, **meta, "title": title, "page_title": page_title, "content": content}, templates)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # 첫 화면
    latest = logs[0] if logs else None
    hero = _hero_html(base, site)
    index_ctx = {
        **common,
        "hero": hero,
        "now_date": latest.date if latest else "",
        "now_items": _li(latest.next_items if latest else []),
        "latest_logs": "".join(_log_link(base, log) for log in logs[:5]) or "<li>아직 없습니다</li>",
        "latest_monthly": _monthly_link(base, monthly[0]) if monthly else "<li>아직 없습니다</li>",
        "play": _play_html(base, site),
        "hero_cta": (f'<a class="btn" href="{base}/together/">같이 사냥할 명단 올리기</a>' if any(p.slug == "together" for p in pages)
                     else f'<a class="btn" href="{base}/log/">작업 기록</a>'),
    }
    _write(out / "index.html", page_html("홈", render_template("index.html", index_ctx, templates), site.get("home_title") or site["title"]))

    # 작업 기록
    for log in logs:
        media = "".join(_media_html(base, m) for m in log.media)
        body = md_to_html(log.body_md)
        content = render_template("log.html", {**common, "date": log.date, "title": log.title, "media": media, "body": body}, templates)
        image = next((m for m in log.media if m.lower().endswith(IMAGE_EXT)), "")
        _write(out / "log" / log.date / "index.html",
               page_html(f"{log.date} {log.title}", content, path=f"log/{log.date}/", description=_plain(_excerpt(log)), image=image, og_type="article", published=log.date))
    by_month: dict[str, list[str]] = {}
    for log in logs:
        by_month.setdefault(log.date[:7], []).append(_log_link(base, log))
    groups = "".join(f"<h2>{m}</h2><ul>{''.join(links)}</ul>" for m, links in by_month.items()) or "<p>아직 없습니다.</p>"
    _write(out / "log" / "index.html", page_html("작업 기록", render_template("log_index.html", {**common, "groups": groups}, templates), path="log/",
                                                 description="날마다 자동으로 올라오는 개발 기록. 무엇을 했고, 어디서 막혔고, 다음에 무엇을 볼지 적습니다. 약속이 아닙니다."))

    # 이달의 정리
    for m in monthly:
        content = render_template(
            "monthly.html",
            {**common, "month": m.month, "title": m.title, "summary_en": m.summary_en, "body": md_to_html(m.body_md)},
            templates,
        )
        _write(out / "monthly" / m.month / "index.html", page_html(m.title, content, path=f"monthly/{m.month}/", description=_first_paragraph(m.body_md), og_type="article"))
    items = "".join(_monthly_link(base, m) for m in monthly) or "<li>아직 없습니다</li>"
    _write(out / "monthly" / "index.html", page_html("이달의 정리", render_template("monthly_index.html", {**common, "items": items}, templates), path="monthly/",
                                                     description="한 달 동안의 개발을 사람이 읽고 정리한 글. 받은 의견에 대한 답도 여기에 적습니다."))

    # 페이지
    for page in pages:
        body = md_to_html(fill(page.body_md, common))
        content = render_template("page.html", {**common, "title": page.title, "body": body, "page_icon": _icon(base, PAGE_ICONS.get(page.slug, ""))}, templates)
        _write(out / page.slug / "index.html", page_html(page.title, content, path=f"{page.slug}/", description=_first_paragraph(fill(page.body_md, common))))

    # RSS
    feed_items = [
        FeedItem(f"기록 {log.date}: {log.title}", f"{site_url}/log/{log.date}/", log.date, " ".join(bullet_items(extract_section(log.body_md, "한 일"))))
        for log in logs
    ] + [FeedItem(f"정리 {m.month}: {m.title}", f"{site_url}/monthly/{m.month}/", f"{m.month}-01", m.summary_en) for m in monthly]
    feed_items.sort(key=lambda i: i.date, reverse=True)
    _write(out / "feed.xml", build_rss(feed_items, site["title"], site_url, "작업 기록과 이달의 정리"))

    # 사이트맵: 쓴 HTML 페이지를 빠짐없이 싣는다. 기록과 월간 글은 날짜를 함께 적는다.
    dated = {f"log/{log.date}/": log.date for log in logs}
    dated.update({f"monthly/{m.month}/": f"{m.month}-01" for m in monthly})
    locs = []
    for page_file in sorted(out.rglob("index.html")):
        rel = page_file.parent.relative_to(out).as_posix()
        rel = "" if rel == "." else rel + "/"
        lastmod = f"<lastmod>{dated[rel]}</lastmod>" if rel in dated else ""
        locs.append(f"<url><loc>{escape(site_url + '/' + rel)}</loc>{lastmod}</url>")
    sitemap_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', *locs, "</urlset>", ""]
    _write(out / "sitemap.xml", chr(10).join(sitemap_lines))

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

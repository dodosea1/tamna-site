"""ORN Studio 정적 사이트 생성기. 스튜디오 첫 화면, 게임별 페이지, 게임별·전체 개발 기록, 옛 주소 넘김 쪽.

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
from tools.sitegen.studio import GAME_STATUS, cheer_line, follow_block, game_card, live_line, now_lines, other_games_rail
from tools.sitegen.tables import ai_table, feedback_table, roadmap_section, support_section


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _media_html(base: str, path: str, label: str = "") -> str:
    src = f"{base}/{path}"
    caption = f'<figcaption>{escape(label)}</figcaption>' if label else ""
    if path.lower().endswith(".mp4"):
        tag = f'<video src="{src}" controls muted playsinline preload="metadata"></video>'
    else:
        tag = f'<img src="{src}" alt="{escape(label or path)}" loading="lazy">'
    return f"<figure>{tag}{caption}</figure>"


# 위쪽 메뉴에 두는 다섯 곳. 나머지 페이지는 아래쪽(푸터)으로 간다.
MAIN_NAV = ("games", "log", "feedback", "support", "about")
NAV_LABELS = {"games": "게임", "log": "개발 기록", "monthly": "이달의 정리"}
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
# 스튜디오 공통 페이지는 띠를 두지 않는다(탐라 그림이라). 탐라 페이지와 탐라 기록에만 둔다.
PAGE_BANDS = {"games/tamna/together": "scene-village", "games/tamna/roadmap": "scene-village", "log/tamna": "key-sea"}
# 그림마다 띠에 보일 부분(세로 위치). 하늘만 보이지 않게 아래쪽 풍경을 잡는다.
BAND_FOCUS = {"scene-hunt": "40%", "scene-village": "35%", "key-sea": "88%", "key-hero": "68%"}


def _band_html(base: str, path: str) -> str:
    key = path.strip("/")
    art = PAGE_BANDS.get(key) or (PAGE_BANDS["log/tamna"] if key.startswith("log/tamna/") else "")
    if not art:
        return ""
    return f'<div class="page-band" style="background-image:url(\'{base}/static/art/{art}-1400.webp\');background-position:center {BAND_FOCUS.get(art, "40%")}" aria-hidden="true"></div>\n'


def _article_ld(title: str, published: str, url: str, image: str, site: dict) -> str:
    """기록 글의 구조화 데이터(schema.org Article). 검색엔진이 날짜·제목·작성자를 읽게 한다."""
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "datePublished": published,
        "url": url,
        "image": image,
        "author": {"@type": "Organization", "name": site.get("author", "")},
        "inLanguage": "ko",
    }
    text = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{text}</script>'


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


def _analytics(site: dict) -> str:
    """방문 집계(GoatCounter). 쿠키를 쓰지 않는다. 코드 이름은 영문 소문자·숫자·-만 받는다."""
    code = str(site.get("goatcounter_code", ""))
    if not code or not all(c.isascii() and (c.islower() or c.isdigit() or c == "-") for c in code):
        return ""
    return f'<script data-goatcounter="https://{code}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'


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


def _log_link(base: str, log: LogEntry, game_names: dict[str, str] | None = None, *, thumb: bool = False, excerpt: bool = True) -> str:
    """기록 목록의 한 줄. thumb이면 기록의 멈춘 그림을 작게 붙인다(GIF는 수 MB라 뺀다)."""
    tag = f'<span class="g">{escape(game_names[log.game])}</span>' if game_names and log.game in game_names else ""
    still = next((m for m in log.media if m.lower().endswith(IMAGE_EXT)), "") if thumb else ""
    pic = f'<img class="thumb" src="{base}/{escape(still)}" alt="" loading="lazy">' if still else ""
    cls = ' class="has-thumb"' if still else ""
    x = f'<span class="x">{escape(_excerpt(log))}</span>' if excerpt else ""
    return (f'<li><a{cls} href="{base}/{log.path}"><span class="d">{escape(log.date)}</span>'
            f'<span class="t">{tag}{escape(log.title)}</span>{x}{pic}</a></li>')


def _first_sentence(text: str) -> str:
    """긴 항목의 첫 문장만. 문장 끝(. ! ? 뒤 공백)이 없으면 그대로."""
    m = re.match(r"(.+?[.!?])\s", text)
    return m.group(1) if m else text


def _now_block(lines: list[tuple[str, str]]) -> str:
    """'지금 어디까지' 칸. 근거는 최근 공개 기록의 '한 일'이고 날짜를 붙인다. 줄이 없으면 칸을 두지 않는다."""
    if not lines:
        return ""
    items = "".join(f'<li><time datetime="{escape(d)}">{escape(d)}</time> {escape(_first_sentence(text))}</li>' for d, text in lines)
    return f'<section class="now-block"><p class="eyebrow">지금 어디까지</p><ul>{items}</ul><p class="muted small">개발 기록 기준 · 약속 아님</p></section>'


def _slides_html(base: str, g: dict) -> str:
    """개발 중 화면 여러 장을 겹쳐 두고 site.js가 천천히 바꾼다. 첫 장만 바로 받는다."""
    slides = g.get("slides") or []
    if not slides:
        return ""
    imgs = "".join(f'<img src="{base}/{escape(s)}" alt="" loading="{"eager" if i == 0 else "lazy"}"{" class=\"on\"" if i == 0 else ""}>' for i, s in enumerate(slides))
    return f'<figure class="game-shot"><div class="slides" data-slides>{imgs}</div><figcaption>개발 중 화면 · 바뀔 수 있습니다</figcaption></figure>'


def _game_tags(g: dict) -> str:
    status = g.get("status", "개발 중")
    tags = f'<span class="tag {GAME_STATUS.get(status, "dev")}">{escape(status)}</span>'
    if g.get("platform"):
        tags += f'<span class="tag">{escape(g["platform"])}</span>'
    return f'<p class="tags">{tags}</p>'


def _redirect_html(base: str, site_url: str, target: str) -> str:
    """옛 주소에 남기는 넘김 쪽. GitHub Pages는 서버 넘김이 없어 meta refresh + canonical로 한다."""
    url = f"{site_url}/{target}"
    href = f"{base}/{target}"
    return (
        '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8">'
        f'<title>옮겼습니다</title><meta name="robots" content="noindex">'
        f'<link rel="canonical" href="{escape(url)}">'
        f'<meta http-equiv="refresh" content="0; url={escape(href)}">'
        f'</head><body><p>이 페이지는 옮겼습니다: <a href="{escape(href)}">{escape(url)}</a></p></body></html>\n'
    )


def _monthly_link(base: str, m: Monthly) -> str:
    return f'<li><a href="{base}/monthly/{m.month}/"><span class="d">{escape(m.month)}</span><span class="t">{escape(m.title)}</span></a></li>'


def _guard_out(root: Path, out: Path) -> None:
    root_r, out_r = root.resolve(), out.resolve()
    if out_r == root_r or root_r.is_relative_to(out_r):
        raise ValueError(f"출력 폴더가 저장소 자체이거나 그 상위 폴더입니다: {out_r}")
    if out_r.exists() and any(out_r.iterdir()) and not (out_r / ".nojekyll").exists():
        raise ValueError(f"출력 폴더가 비어 있지 않고 생성기 출력(.nojekyll)도 아닙니다: {out_r}")


def _load_games(root: Path) -> list[dict]:
    games = _load_json(root / "data" / "games.json")
    slugs = set()
    for g in games:
        for key in ("slug", "name"):
            if not g.get(key):
                raise ValueError(f"data/games.json: 게임마다 {key}가 필요합니다: {g}")
        if g["slug"] in slugs:
            raise ValueError(f"data/games.json: slug가 겹칩니다: {g['slug']}")
        if g.get("status", "개발 중") not in GAME_STATUS:
            raise ValueError(f"data/games.json: status는 {', '.join(GAME_STATUS)} 중 하나: {g['slug']}")
        slugs.add(g["slug"])
    return games


def _check_game_media(games: list[dict], root: Path, static: Path) -> None:
    """선택 키 검사. card_video는 media/ 아래 .mp4, slides는 static/ 아래 그림 2개 이상. 없는 파일을 가리키면 멈춘다."""
    for g in games:
        video = g.get("card_video")
        if video is not None:
            ok = isinstance(video, str) and video.startswith("media/") and video.lower().endswith(".mp4") and ".." not in video.split("/")
            if not ok or not (root / video).is_file():
                raise ValueError(f"data/games.json: card_video는 media/ 아래에 있는 .mp4 파일이어야 합니다: {g['slug']}: {video}")
        slides = g.get("slides")
        if slides is not None:
            if not isinstance(slides, list) or len(slides) < 2:
                raise ValueError(f"data/games.json: slides는 그림 2개 이상의 목록이어야 합니다: {g['slug']}")
            for s in slides:
                ok = isinstance(s, str) and s.startswith("static/") and ".." not in s.split("/")
                if not ok or not (static / s[len("static/"):]).is_file():
                    raise ValueError(f"data/games.json: slides의 그림은 static/ 아래에 있어야 합니다: {g['slug']}: {s}")


def _log_filters(base: str, games: list[dict], logs: list[LogEntry], current: str) -> str:
    """개발 기록 게임 고르기. 기록이 있는 게임만 링크."""
    has = {log.game for log in logs}
    items = [f'<a class="{"on" if not current else ""}" href="{base}/log/">전체</a>']
    for g in games:
        if g["slug"] in has:
            items.append(f'<a class="{"on" if current == g["slug"] else ""}" href="{base}/log/{g["slug"]}/">{escape(g["name"])}</a>')
    return '<nav class="filters">' + "".join(items) + "</nav>"


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

    games = _load_games(root)
    _check_game_media(games, root, static)
    game_by_slug = {g["slug"]: g for g in games}
    game_names = {g["slug"]: g["name"] for g in games}
    logs = load_logs(root / "content" / "log")
    for log in logs:
        if log.game not in game_by_slug:
            raise ValueError(f"기록 {log.game}/{log.date}: data/games.json에 없는 게임입니다")
    pages = load_pages(root / "content" / "pages")
    game_pages = {g["slug"]: load_pages(root / "content" / "games" / g["slug"]) for g in games}
    monthly = load_monthly(root / "content" / "monthly")
    data = {name: _load_json(root / "data" / f"{name}.json") for name in ("feedback", "roadmap", "support", "ai")}
    redirects_path = root / "data" / "redirects.json"
    redirects = _load_json(redirects_path) if redirects_path.exists() else {}

    titles = {**{p.slug: p.title for p in pages}, **NAV_LABELS}
    nav = "".join(f'<a href="{base}/{slug}/">{escape(titles[slug])}</a>' for slug in MAIN_NAV if slug in titles)
    footer_slugs = ["monthly"] + [p.slug for p in pages if p.slug not in MAIN_NAV and p.slug != "privacy"]
    footer_nav = " · ".join(f'<a href="{base}/{slug}/">{escape(titles[slug])}</a>' for slug in footer_slugs)
    has_privacy = any(p.slug == "privacy" for p in pages)
    site_url = site.get("site_url", "").rstrip("/")
    threads_url = site.get("threads_url", "")
    tamna = game_by_slug.get("tamna", {})
    common = {
        "base": base,
        "nav": nav,
        "footer_links": f'<a href="{base}/privacy/">개인정보 처리방침</a> · ' if has_privacy else "",
        "footer_nav": footer_nav,
        "header_follow": f'<a class="follow" href="{escape(threads_url)}" rel="noopener">스레드 팔로우</a>' if threads_url else "",
        "site_title": site["title"],
        "og_image": site.get("site_url", "").rstrip("/") + "/static/art/og-studio.jpg",
        "tagline": site.get("tagline", ""),
        "verify_meta": _verify_meta(site),
        "analytics": _analytics(site),
        "author": site.get("author", ""),
        # 영감 문장은 게임마다 다르다. 공통 페이지의 {{inspiration}}은 탐라 문장이다.
        "inspiration": tamna.get("inspiration", ""),
        "summary_en": site.get("summary_en", ""),
        "year": str(date.today().year),
        "email": _email_html(site.get("email_user", ""), site.get("email_domain", "")),
        "tally_feedback": _link_or_prep(site.get("tally_feedback_url", ""), "의견 보내기 폼 열기"),
        "tally_tester": _link_or_prep(tamna.get("tally_tester_url", ""), "같이 사냥할 명단에 올리기"),
        "donate": donate_block(site),
        "threads": _link_or_prep(site.get("threads_url", ""), "스레드에서 보기"),
        "feedback_table": feedback_table(data["feedback"]),
        "roadmap_section": roadmap_section(data["roadmap"]),
        "support_section": support_section(data["support"], direct=is_direct(site), ctee=shows_ctee(site)),
        "ai_table": ai_table(data["ai"]),
        "latest_monthly": _monthly_link(base, monthly[0]) if monthly else "<li>아직 없습니다</li>",
        "logo": f'<img class="logo-img" src="{base}/static/art/logo-cream-900.webp" alt="탐라" width="900" height="513">',
        # D-44 로고: 기호 A 모루와 불티 + Archivo(글자는 외곽선), 원본은 _preview/studio/final
        "brand": f'<img class="brand-logo" src="{base}/static/brand/logo-horizontal.svg" alt="{escape(site["title"])}" width="146" height="27">',
    }
    for name in ("sun", "brush", "moon", "peony", "hareubang", "bell", "letter", "road", "knot", "cups", "pouch", "magpie"):
        common[f"icon_{name}"] = _icon(base, name)

    def page_html(title: str, content: str, page_title: str = "", *, path: str = "", description: str = "", image: str = "", og_type: str = "website", published: str = "") -> str:
        page_title = page_title or f"{title} · {site['title']}"
        og_image = f"{site_url}/{image}" if image else common["og_image"]
        meta = {
            "description": escape(_clip(description or site.get("tagline", ""))),
            "canonical": f"{site_url}/{path}",
            "og_type": og_type,
            "og_image": og_image,
            "published_meta": (f'<meta property="article:published_time" content="{escape(published)}">\n' + _article_ld(title, published, f"{site_url}/{path}", og_image, site)) if published else "",
            "band": _band_html(base, path),
        }
        return render_template("base.html", {**common, **meta, "title": title, "page_title": page_title, "content": content}, templates)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    written: set[str] = set()

    def write_page(path: str, html: str) -> None:
        if path in written:
            raise ValueError(f"같은 주소에 페이지가 두 번 쓰였습니다: /{path}")
        written.add(path)
        _write(out / path / "index.html", html)

    cards = "".join(game_card(base, g) for g in games)
    has_tester = any(p.slug == "together" for p in game_pages.get("tamna", []))

    # 스튜디오 첫 화면
    # 다음 소식: 테스트 알림은 탐라 것(같이하기 페이지가 있을 때), 스레드는 스튜디오 계정.
    home_follow = (follow_block(base, tamna, threads_url, has_tester) if tamna else "") + cheer_line(base, "support" in titles)
    index_ctx = {
        **common,
        "cards": cards,
        "latest_logs": "".join(_log_link(base, log, game_names, thumb=True) for log in logs[:6]) or "<li>아직 없습니다</li>",
        "live": live_line(logs, date.today()),
        # 후원은 상자 대신 아래쪽 한 줄만 둔다(설계 5-5). 둘 다 없으면 구역을 두지 않는다.
        "home_follow": f'<section class="wrap home-follow">{home_follow}</section>' if home_follow else "",
        "studio_boxes": "".join(box for slug, box in (
            ("feedback", f'<div class="box"><p class="eyebrow">의견</p><p>어느 게임에 대한 의견인지 골라서 남길 수 있습니다.</p><a class="btn ghost small" href="{base}/feedback/">의견 보내기</a></div>'),
        ) if slug in titles),
        "hero_cta": (f'<a class="btn" href="{base}/games/tamna/together/">탐라 테스터 신청</a>' if has_tester
                     else f'<a class="btn" href="{base}/games/">게임 보기</a>'),
    }
    write_page("", page_html("홈", render_template("index.html", index_ctx, templates), site.get("home_title") or site["title"]))

    # 게임 목록과 게임 페이지
    write_page("games/", page_html("게임", render_template("games_index.html", {**common, "cards": cards}, templates), path="games/",
                                   description=f"{site['title']}가 만드는 게임 목록. 개발 중인 게임과 운영 중인 프로젝트."))
    for g in games:
        if g.get("url"):
            continue  # 바깥 사이트로 나가는 카드(고향 등)는 이 사이트에 페이지를 두지 않는다.
        slug = g["slug"]
        gfill = {**common, "inspiration": g.get("inspiration", "")}
        subpages = game_pages.get(slug, [])
        index_page = next((p for p in subpages if p.slug == "index"), None)
        g_logs = [log for log in logs if log.game == slug]
        has_together = any(p.slug == "together" for p in subpages)
        subnav = " · ".join(f'<a href="{base}/games/{slug}/{p.slug}/">{escape(p.title)}</a>' for p in subpages if p.slug != "index")
        # 맨 위 그림: 첫 화면 그림(hero_media) → 그림 넘김(slides) → 카드 그림 순. 아무것도 없으면 칸을 두지 않는다.
        shot = _hero_html(base, g) or _slides_html(base, g)
        if not shot and g.get("card_image"):
            shot = f'<figure class="game-shot"><img src="{base}/{escape(g["card_image"])}" alt="" loading="eager"></figure>'
        log_items = "".join(_log_link(base, log, thumb=True, excerpt=False) for log in g_logs[:3])
        log_more = f'<a class="more" href="{base}/log/{slug}/">{escape(g["name"])} 기록 전체</a>' if g_logs else ""
        ctx = {
            **gfill,
            "game_name": g["name"],
            "game_summary": g.get("summary", ""),
            "game_slug": slug,
            # 근거가 없는 칸은 빈 문자열로 두어 통째로 숨긴다("준비 중"·"아직 없습니다"를 띄우지 않는다).
            "game_tags": _game_tags(g),
            "body": md_to_html(fill(index_page.body_md, gfill)) if index_page else "",
            "subnav": f'<p class="muted small">{subnav}</p>' if subnav else "",
            "latest_logs": log_items,
            "log_more": log_more,
            "logs_block": f'<h2>최근 기록</h2><ul class="log-list">{log_items}</ul>{log_more}' if g_logs else "",
            "now_block": _now_block(now_lines(g_logs)),
            "follow": follow_block(base, g, threads_url, has_together),
            "other_games": other_games_rail(base, games, slug),
            "cheer": cheer_line(base, "support" in titles),
            "hero": _hero_html(base, g),
            "shot": shot,
            "play": _play_html(base, g),
            "hero_cta": (f'<a class="btn" href="{base}/games/{slug}/together/">같이 사냥할 명단 올리기</a>' if has_together
                         else (f'<a class="btn" href="{base}/log/{slug}/">개발 기록 보기</a>' if g_logs else "")),
        }
        tpl = f"game_{slug}.html" if (templates / f"game_{slug}.html").exists() else "game.html"
        description = g.get("summary", "") or (_first_paragraph(index_page.body_md) if index_page else "")
        tamna_og = "static/art/og.jpg" if slug == "tamna" else ""   # 탐라 페이지 공유 그림은 탐라 그림 그대로
        write_page(f"games/{slug}/", page_html(g["name"], render_template(tpl, ctx, templates), path=f"games/{slug}/", description=description, image=tamna_og))
        for p in subpages:
            if p.slug == "index":
                continue
            body = md_to_html(fill(p.body_md, gfill))
            content = render_template("page.html", {**gfill, "title": p.title, "body": body, "page_icon": _icon(base, PAGE_ICONS.get(p.slug, "")),
                                                    "crumbs": f'<p class="crumbs"><a href="{base}/games/{slug}/">{escape(g["name"])}</a></p>'}, templates)
            write_page(f"games/{slug}/{p.slug}/", page_html(f"{p.title} · {g['name']}", content, path=f"games/{slug}/{p.slug}/",
                                                           description=_first_paragraph(fill(p.body_md, gfill))))

    # 개발 기록: 글, 전체 목록, 게임별 목록
    for log in logs:
        media = "".join(_media_html(base, m) for m in log.media)
        body = md_to_html(log.body_md)
        content = render_template("log.html", {**common, "date": log.date, "title": log.title, "media": media, "body": body,
                                               "game_name": game_names[log.game], "game_slug": log.game,
                                               "other_games": other_games_rail(base, games, log.game)}, templates)
        image = next((m for m in log.media if m.lower().endswith(IMAGE_EXT)), "")
        write_page(log.path, page_html(f"{log.date} {log.title}", content, path=log.path, description=_plain(_excerpt(log)), image=image, og_type="article", published=log.date))

    def groups_html(items: list[LogEntry], show_game: bool) -> str:
        by_month: dict[str, list[str]] = {}
        for log in items:
            by_month.setdefault(log.date[:7], []).append(_log_link(base, log, game_names if show_game else None))
        return "".join(f"<h2>{m}</h2><ul>{''.join(links)}</ul>" for m, links in by_month.items()) or "<p>아직 없습니다.</p>"

    write_page("log/", page_html("개발 기록", render_template("log_index.html", {**common, "heading": "개발 기록", "filters": _log_filters(base, games, logs, ""),
                                                                              "groups": groups_html(logs, True)}, templates), path="log/",
                                 description="게임별 개발 기록을 한곳에 모았습니다. 무엇을 했고, 어디서 막혔고, 다음에 무엇을 볼지 적습니다. 약속이 아닙니다."))
    for g in games:
        g_logs = [log for log in logs if log.game == g["slug"]]
        if not g_logs:
            continue
        write_page(f"log/{g['slug']}/", page_html(f"{g['name']} 개발 기록", render_template("log_index.html", {
            **common, "heading": f"{g['name']} 개발 기록", "filters": _log_filters(base, games, logs, g["slug"]), "groups": groups_html(g_logs, False)}, templates),
            path=f"log/{g['slug']}/", description=f"{g['name']} 개발 기록. 무엇을 했고, 어디서 막혔고, 다음에 무엇을 볼지 적습니다. 약속이 아닙니다."))

    # 이달의 정리
    for m in monthly:
        content = render_template(
            "monthly.html",
            {**common, "month": m.month, "title": m.title, "summary_en": m.summary_en, "body": md_to_html(m.body_md)},
            templates,
        )
        write_page(f"monthly/{m.month}/", page_html(m.title, content, path=f"monthly/{m.month}/", description=_first_paragraph(m.body_md), og_type="article"))
    items = "".join(_monthly_link(base, m) for m in monthly) or "<li>아직 없습니다</li>"
    write_page("monthly/", page_html("이달의 정리", render_template("monthly_index.html", {**common, "items": items}, templates), path="monthly/",
                                     description="한 달 동안의 개발을 사람이 읽고 정리한 글. 받은 의견에 대한 답도 여기에 적습니다."))

    # 스튜디오 공통 페이지
    for page in pages:
        body = md_to_html(fill(page.body_md, common))
        content = render_template("page.html", {**common, "title": page.title, "body": body, "page_icon": _icon(base, PAGE_ICONS.get(page.slug, "")), "crumbs": ""}, templates)
        write_page(f"{page.slug}/", page_html(page.title, content, path=f"{page.slug}/", description=_first_paragraph(fill(page.body_md, common))))

    # 옛 주소 넘김 쪽. 탐라 옛 기록(/log/<날짜>/)은 자동, 나머지는 data/redirects.json(옛 경로 → 새 경로).
    stubs = {f"log/{log.date}/": log.path for log in logs if log.legacy}
    stubs.update(redirects)
    for old, new in stubs.items():
        if old in written:
            raise ValueError(f"넘김 쪽 /{old}가 실제 페이지와 겹칩니다")
        if new not in written:
            raise ValueError(f"넘김 쪽 /{old} → /{new}: 새 주소에 페이지가 없습니다")
        _write(out / old / "index.html", _redirect_html(base, site_url, new))

    # RSS: 전체 하나. 제목 앞에 게임 이름.
    feed_items = [
        FeedItem(f"{game_names[log.game]} {log.date}: {log.title}", f"{site_url}/{log.path}", log.date, " ".join(bullet_items(extract_section(log.body_md, "한 일"))))
        for log in logs
    ] + [FeedItem(f"정리 {m.month}: {m.title}", f"{site_url}/monthly/{m.month}/", f"{m.month}-01", m.summary_en) for m in monthly]
    feed_items.sort(key=lambda i: i.date, reverse=True)
    _write(out / "feed.xml", build_rss(feed_items, site["title"], site_url, "게임별 개발 기록과 이달의 정리"))

    # 사이트맵: 실제 페이지만(넘김 쪽 제외). 기록과 월간 글은 날짜를 함께 적는다.
    dated = {log.path: log.date for log in logs}
    dated.update({f"monthly/{m.month}/": f"{m.month}-01" for m in monthly})
    locs = []
    for rel in sorted(written):
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
    parser = argparse.ArgumentParser(description="ORN Studio 사이트 생성기")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="_site")
    parser.add_argument("--base", default=None, help="사이트가 놓이는 경로 접두어. 기본은 data/site.json의 base_path")
    args = parser.parse_args(argv)
    build_site(Path(args.root), Path(args.out), base=args.base)
    print(f"built: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

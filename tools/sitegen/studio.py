"""스튜디오 화면의 HTML 조각: 게임 카드, 다른 게임 줄, 살아 있음 줄, 지금 어디까지, 다음 소식, 응원 한 줄.

값은 모두 html.escape를 거친다. 근거가 없는 조각은 빈 문자열을 돌려줘 칸이 통째로 사라지게 한다.
"""

from __future__ import annotations

from datetime import date, timedelta
from html import escape

from tools.sitegen.content import LogEntry, bullet_items, extract_section

# 게임 상태 표시. games.json의 status 값이 이 중 하나여야 한다.
GAME_STATUS = {"개발 중": "dev", "운영 중": "live", "쉬는 중": "rest"}


def game_card(base: str, g: dict, event: str = "card") -> str:
    """첫 화면·게임 목록·다른 게임 줄의 게임 카드. 바깥 주소(url)가 있으면 그리로, 없으면 게임 페이지로.

    event는 누름 집계 이름의 앞머리다(첫 화면·게임 목록은 card-, '다른 게임' 줄은 other-로 따로 센다).
    card_video가 있으면 그림 자리에 영상을 둔다. 처음에는 포스터 그림만 받고, 영상 파일은 site.js가 화면에 들어올 때 받는다.
    """
    external = g.get("url", "")
    href = escape(external) if external else f"{base}/games/{escape(g['slug'])}/"
    rel = ' rel="noopener"' if external else ""
    img = g.get("card_image", "")
    video = g.get("card_video", "")
    if video:
        poster = f' poster="{base}/{escape(img)}"' if img else ""
        pic = (f'<video class="card-video" data-src="{base}/{escape(video)}"{poster} muted loop playsinline '
               f'preload="none" aria-hidden="true" tabindex="-1"></video>')
    elif img:
        pic = f'<img src="{base}/{escape(img)}" alt="" loading="lazy">'
    else:
        pic = '<span class="pic-empty">그림 준비 중</span>'
    status = g.get("status", "개발 중")
    tags = f'<span class="tag {GAME_STATUS.get(status, "dev")}">{escape(status)}</span>'
    if g.get("platform"):
        tags += f'<span class="tag">{escape(g["platform"])}</span>'
    if external:
        tags += f'<span class="tag">{escape(external.split("//", 1)[-1].rstrip("/"))} ↗</span>'
    return (f'<a class="game-card" href="{href}"{rel} data-goatcounter-click="{event}-{escape(g["slug"])}"><div class="pic">{pic}</div>'
            f'<div class="body"><h3>{escape(g["name"])}</h3><p>{escape(g.get("summary", ""))}</p><p class="tags">{tags}</p></div></a>')


def other_games_rail(base: str, games: list[dict], current: str) -> str:
    """'ORN의 다른 게임' 작은 병풍. 지금 보는 게임은 빼고 games.json 순서대로. 남는 게임이 없으면 ''."""
    others = [g for g in games if g["slug"] != current]
    if not others:
        return ""
    cards = ""
    for g in others:
        href, rel = _game_href(base, g)
        img = g.get("card_image", "")
        pic = f'<img src="{base}/{escape(img)}" alt="" loading="lazy">' if img else ""
        head, _ = split_name(g["name"])
        cards += (f'<a class="mini-panel" href="{href}"{rel} data-goatcounter-click="other-{escape(g["slug"])}">{pic}'
                  f'<span class="vt" aria-hidden="true">{escape(head)}</span><span class="seal">{escape(g.get("status", "개발 중"))}</span>'
                  f'<span class="name">{escape(g["name"])}</span></a>')
    return f'<section class="other-games"><p class="eyebrow">ORN의 다른 게임</p><div class="rail">{cards}</div></section>'


def cheer_line(base: str, has_support: bool) -> str:
    """응원 한 줄. 후원 페이지가 없으면 ''."""
    if not has_support:
        return ""
    return f'<p class="cheer"><a href="{base}/support/" data-goatcounter-click="cheer">개발 응원하기</a> · 받은 금액과 쓴 곳은 공개합니다</p>'


def live_line(logs: list[LogEntry], today: date) -> str:
    """살아 있다는 신호: 지난 7일(오늘 포함) 기록 수와 마지막 기록 날짜. 날짜는 site.js가 '오늘/어제/N일 전'으로 바꾼다."""
    if not logs:
        return ""
    since = (today - timedelta(days=6)).isoformat()
    week = sum(1 for log in logs if since <= log.date <= today.isoformat())
    last = escape(max(log.date for log in logs))
    stamp = f'마지막 기록 <time data-rel datetime="{last}">{last}</time>'
    if week:
        # 기록 수는 빌드 때 센 값이라, 마지막 기록이 7일 넘게 지나면 site.js가 data-week 조각을 지운다.
        return f'<p class="live"><span data-week>이번 주 기록 {week}개 · </span>{stamp}</p>'
    return f'<p class="live">{stamp}</p>'


def now_lines(game_logs: list[LogEntry], n: int = 3) -> list[tuple[str, str]]:
    """'지금 어디까지': 최신 기록부터 (날짜, '한 일' 첫 항목). 항목이 없는 기록은 건너뛴다."""
    out: list[tuple[str, str]] = []
    for log in game_logs:
        items = bullet_items(extract_section(log.body_md, "한 일"))
        if items:
            out.append((log.date, items[0]))
        if len(out) == n:
            break
    return out


def follow_block(base: str, g: dict, threads_url: str, has_together: bool) -> str:
    """'다음 소식 받기': 테스트 알림(같이하기 페이지가 있는 게임만)과 스레드 팔로우. 둘 다 없으면 ''."""
    slug = escape(g["slug"])
    buttons = ""
    if has_together:
        buttons += f'<a class="btn" href="{base}/games/{slug}/together/" data-goatcounter-click="tester-{slug}">테스트 알림 받기</a>'
    if threads_url:
        buttons += f'<a class="btn ghost" href="{escape(threads_url)}" rel="noopener">스레드 팔로우</a>'
    if not buttons:
        return ""
    return f'<div class="follow-box"><p class="eyebrow">다음 소식 받기</p><div class="actions">{buttons}</div></div>'


# ── 대개편 A. 오방색 병풍 (2026-11-26) ──

def split_name(name: str) -> tuple[str, str]:
    """'탐라(가제)' → ('탐라', '가제'). 끝의 괄호 한 쌍만 가른다. 없으면 (이름, '')."""
    if name.endswith(")") and "(" in name:
        head, _, tail = name[:-1].rpartition("(")
        if head.strip() and tail.strip():
            return head.strip(), tail.strip()
    return name, ""


def _vt(name: str, tag: str) -> str:
    """세로 제목. 화면 읽기 도구에는 원래 이름 그대로 읽힌다."""
    head, tail = split_name(name)
    small = f'<small aria-hidden="true">{escape(tail)}</small>' if tail else ""
    return f'<{tag} class="vt" aria-label="{escape(name)}"><span aria-hidden="true">{escape(head)}</span>{small}</{tag}>'


def _game_href(base: str, g: dict) -> tuple[str, str]:
    """(주소, rel 속성). 바깥 주소(url)가 있으면 그리로."""
    external = g.get("url", "")
    if external:
        return escape(external), ' rel="noopener"'
    return f"{base}/games/{escape(g['slug'])}/", ""


def panel(base: str, g: dict, *, heading: str = "h2", eager: bool = False, cta: str | None = None) -> str:
    """병풍 한 폭: 그림 화면 가득, 세로 제목, 도장, 한 줄 소개.

    그림은 세로 화면용(hero_media_mobile)이 있으면 가득 채우고(cover), 카드 그림만 있으면 같은 그림을 흐리게 깐 위에
    또렷하게 한 번 더 둔다(frame). 그림이 없으면 먹 바탕만(bare) 두고 '준비 중' 같은 글을 띄우지 않는다.
    """
    slug = escape(g["slug"])
    load = 'loading="eager" fetchpriority="high"' if eager else 'loading="lazy"'
    tall, card = g.get("hero_media_mobile", ""), g.get("card_image", "")
    if tall:
        mode, pics = "cover", f'<img class="panel-pic" src="{base}/{escape(tall)}" alt="" {load}>'
    elif card:
        src = f"{base}/{escape(card)}"
        mode = "frame"
        pics = (f'<img class="panel-blur" src="{src}" alt="" aria-hidden="true" loading="{"eager" if eager else "lazy"}">'
                f'<img class="panel-pic" src="{src}" alt="" {load}>')
    else:
        mode, pics = "bare", ""
    clip = ""
    if g.get("card_video"):
        still = g.get("clip_poster") or card   # clip_poster는 build.py가 채운다(영상의 한 장면이 있으면 그것)
        poster = f' poster="{base}/{escape(still)}"' if still else ""
        clip = (f'<video class="card-video panel-clip" data-src="{base}/{escape(g["card_video"])}"{poster} muted loop playsinline '
                f'preload="none" aria-hidden="true" tabindex="-1"></video>')
    if cta is None:
        href, rel = _game_href(base, g)
        external = g.get("url", "")
        label = f'{escape(external.split("//", 1)[-1].rstrip("/"))} ↗' if external else "이 게임 보기"
        cta = f'<a class="btn" href="{href}" data-goatcounter-click="card-{slug}"{rel}>{label}</a>'
    platform = f'<small>{escape(g["platform"])}</small>' if g.get("platform") else ""
    return (f'<section class="panel panel-{mode}" id="p-{slug}">{pics}{_vt(g["name"], heading)}'
            f'<span class="seal">{escape(g.get("status", "개발 중"))}</span>'
            f'<div class="cap">{clip}{platform}<p>{escape(g.get("summary", ""))}</p>{cta}</div></section>')


def date_seal(day: str) -> str:
    """날짜 도장. '2026-11-25' → 11.25 / 2026."""
    year, _, rest = day.partition("-")
    return f'<time class="seal seal-date" datetime="{escape(day)}"><b>{escape(rest.replace("-", "."))}</b><i>{escape(year)}</i></time>'


def patch_list(base: str, logs: list[LogEntry], game_names: dict[str, str] | None = None) -> str:
    """패치 노트 꼴 기록 목록: 날짜 도장 · 제목 (· 게임 이름). 기록이 없으면 ''."""
    if not logs:
        return ""
    rows = []
    for log in logs:
        game = f'<span class="g">{escape(game_names[log.game])}</span>' if game_names and log.game in game_names else ""
        rows.append(f'<li><a href="{base}/{log.path}">{date_seal(log.date)}<span class="t">{escape(log.title)}</span>{game}</a></li>')
    return f'<ul class="patch">{"".join(rows)}</ul>'


def latest_card(base: str, log: LogEntry | None, game_name: str, picture: str = "") -> str:
    """가장 최근 기록 카드: 날짜 도장 + 게임 이름 + 제목 + 읽기. 기록이 없으면 ''."""
    if log is None:
        return ""
    pic = f'<img src="{base}/{escape(picture)}" alt="" loading="lazy" width="640" height="360">' if picture else ""
    return (f'<a class="latest" href="{base}/{log.path}">{date_seal(log.date)}<span class="g">{escape(game_name)}</span>'
            f'<strong class="sf">{escape(log.title)}</strong>{pic}<span class="more">읽기</span></a>')

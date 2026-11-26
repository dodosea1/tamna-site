"""스튜디오 화면의 HTML 조각: 게임 카드, 다른 게임 줄, 살아 있음 줄, 지금 어디까지, 다음 소식, 응원 한 줄.

값은 모두 html.escape를 거친다. 근거가 없는 조각은 빈 문자열을 돌려줘 칸이 통째로 사라지게 한다.
"""

from __future__ import annotations

from datetime import date, timedelta
from html import escape

from tools.sitegen.content import LogEntry, bullet_items, extract_section

# 게임 상태 표시. games.json의 status 값이 이 중 하나여야 한다.
GAME_STATUS = {"개발 중": "dev", "운영 중": "live", "쉬는 중": "rest"}


def game_card(base: str, g: dict) -> str:
    """첫 화면·게임 목록·다른 게임 줄의 게임 카드. 바깥 주소(url)가 있으면 그리로, 없으면 게임 페이지로.

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
    return (f'<a class="game-card" href="{href}"{rel} data-goatcounter-click="card-{escape(g["slug"])}"><div class="pic">{pic}</div>'
            f'<div class="body"><h3>{escape(g["name"])}</h3><p>{escape(g.get("summary", ""))}</p><p class="tags">{tags}</p></div></a>')


def other_games_rail(base: str, games: list[dict], current: str) -> str:
    """'ORN의 다른 게임' 줄. 지금 보는 게임은 빼고 games.json 순서대로. 남는 게임이 없으면 ''."""
    others = [g for g in games if g["slug"] != current]
    if not others:
        return ""
    cards = "".join(game_card(base, g) for g in others)
    return f'<section class="other-games wrap"><p class="eyebrow">ORN의 다른 게임</p><div class="rail">{cards}</div></section>'


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
        return f'<p class="live">이번 주 기록 {week}개 · {stamp}</p>'
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

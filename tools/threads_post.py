"""공개된 작업 기록을 하루 한 편 스레드에 올린다(공식 Threads API).

글 고르기: content/threads/YYYY-MM-DD.md(직접 쓴 글)가 있으면 그것을, 없으면 같은 날 기록에서 만든다.
오늘 날짜는 기록이 아직 늘 수 있어 기다린다. 가장 오래된 안 올린 날부터 한 편씩 올린다.

비밀 값과 상태는 저장소 밖 ~/.claude/tamna-threads/ 에만 둔다. 토큰이 없거나 꺼져 있으면 아무것도 올리지 않는다.

사용:
  python tools/threads_post.py --set-token    토큰 저장(입력 내용이 화면과 기록에 남지 않는다)
  python tools/threads_post.py --dry-run      올릴 글만 보여 준다
  python tools/threads_post.py --enable       자동 게시 켜기 (--disable 끄기)
  python tools/threads_post.py --run          한 번 실행(예약 작업이 부른다)
  python tools/threads_post.py --status       상태 보기
"""

from __future__ import annotations

import argparse
import getpass
import http.client
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.lint_public import DEFAULT_TERMS, load_terms, scan_text  # noqa: E402
from tools.sitegen.content import bullet_items, extract_section, is_draft  # noqa: E402
from tools.sitegen.frontmatter import parse_frontmatter  # noqa: E402

KST = timezone(timedelta(hours=9))
MAX_TEXT = 500
MAX_LINKS = 5
REFRESH_AFTER = timedelta(days=30)
PENDING_GIVE_UP = timedelta(hours=24)
WAIT_SECONDS = 30
WAIT_TRIES = 10
API = "https://graph.threads.com"
HOME = Path.home() / ".claude" / "tamna-threads"
DEFAULT_CONFIG = {"enabled": False, "start_date": "2026-11-08", "username": "ornstudio.official"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
VIDEO_SUFFIXES = {".mp4", ".mov"}
IMAGE_MAX = 8 * 1024 * 1024
VIDEO_MAX = 1024 * 1024 * 1024
DATE_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ThreadsError(Exception):
    pass


@dataclass
class Post:
    date: str
    text: str
    media: str = ""
    link: str = ""
    source: str = ""


def text_length(text: str) -> int:
    """API는 이모지를 UTF-8 바이트 수로 센다. 넘치면 안 되므로 기호류도 바이트로 넉넉히 센다."""
    total = 0
    for ch in text:
        emoji = ord(ch) > 0xFFFF or unicodedata.category(ch) == "So"
        total += len(ch.encode("utf-8")) if emoji else 1
    return total


def compose_from_log(title: str, body_md: str, link: str) -> str | None:
    for item in bullet_items(extract_section(body_md, "한 일")):
        text = f"{title}\n\n{item}\n\n{link}"
        if text_length(text) <= MAX_TEXT:
            return text
    return None


def _dates(root: Path, start: str, today: str) -> list[str]:
    found = set()
    for folder in ("log", "threads"):
        for path in (root / "content" / folder).glob("*.md"):
            if DATE_FILE.match(path.stem) and start <= path.stem < today:
                found.add(path.stem)
    return sorted(found)


def load_due_post(root: Path, start: str, posted: set[str], now: datetime) -> Post | None:
    site_url = json.loads((root / "data" / "site.json").read_text(encoding="utf-8")).get("site_url", "").rstrip("/")
    today = now.astimezone(KST).date().isoformat()
    for day in _dates(root, start, today):
        if day in posted:
            continue
        hand = root / "content" / "threads" / f"{day}.md"
        if hand.exists():
            meta, body = parse_frontmatter(hand.read_text(encoding="utf-8"))
            if is_draft(meta):
                continue
            return Post(day, body.strip(), meta.get("media", ""), source=hand.relative_to(root).as_posix())
        log = root / "content" / "log" / f"{day}.md"
        meta, body = parse_frontmatter(log.read_text(encoding="utf-8"))
        if is_draft(meta):
            continue
        link = f"{site_url}/log/{day}/"
        text = compose_from_log(meta.get("title", day), body, link)
        if text:
            return Post(day, text, link=link, source=log.relative_to(root).as_posix())
    return None


def validate_post(post: Post, root: Path, terms: list[str]) -> list[str]:
    """올리면 안 되는 이유 목록. 비어 있어야 올린다. 맞은 비공개 단어 자체는 적지 않는다."""
    problems = []
    if not post.text.strip():
        problems.append("글이 비어 있다")
    if text_length(post.text) > MAX_TEXT:
        problems.append(f"{MAX_TEXT}자를 넘는다")
    if len(set(re.findall(r"https?://\S+", post.text))) > MAX_LINKS:
        problems.append(f"링크가 {MAX_LINKS}개를 넘는다")
    problems += [f"공개 검사: {rule}" for rule in scan_text(post.text, terms)]
    if post.media:
        problems += _media_problems(post.media, root)
    return problems


def _media_problems(media: str, root: Path) -> list[str]:
    parts = Path(media).parts
    if Path(media).is_absolute() or ".." in parts or not parts or parts[0] not in ("media", "static"):
        return ["미디어 경로는 media/ 또는 static/ 아래여야 한다"]
    suffix = Path(media).suffix.lower()
    if suffix not in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
        return ["미디어는 JPEG, PNG, MP4, MOV만 된다"]
    path = root / media
    if not path.is_file():
        return ["미디어 파일이 없다"]
    limit = IMAGE_MAX if suffix in IMAGE_SUFFIXES else VIDEO_MAX
    return ["미디어 용량이 너무 크다"] if path.stat().st_size > limit else []


class Store:
    def __init__(self, home: Path = HOME):
        self.home = Path(home)
        self.config_path = self.home / "config.json"
        self.token_path = self.home / "token.json"
        self.state_path = self.home / "state.json"
        self.log_path = self.home / "run.log"

    def _write_json(self, path: Path, value: dict) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def _read_json(self, path: Path, default: dict) -> dict:
        return {**default, **json.loads(path.read_text(encoding="utf-8"))} if path.exists() else dict(default)

    def load_config(self) -> dict:
        return self._read_json(self.config_path, DEFAULT_CONFIG)

    def save_config(self, value: dict) -> None:
        self._write_json(self.config_path, value)

    def load_token(self) -> dict | None:
        return json.loads(self.token_path.read_text(encoding="utf-8")) if self.token_path.exists() else None

    def save_token(self, token: str, now: datetime) -> None:
        self._write_json(self.token_path, {"token": token, "refreshed_at": now.isoformat()})

    def load_state(self) -> dict:
        return self._read_json(self.state_path, {"posted": {}, "pending": None, "last_post_day": ""})

    def save_state(self, value: dict) -> None:
        self._write_json(self.state_path, value)

    def log(self, now: datetime, message: str, echo: bool = True) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(f"{now.isoformat(timespec='seconds')} {message}\n")
        if echo and sys.stdout:
            print(message)


class Api:
    """실제 호출. 토큰은 오류 문구에서 지운다."""

    def __init__(self, token: str):
        self.token = token

    def _call(self, method: str, path: str, params: dict | None = None) -> dict:
        params = {**(params or {}), "access_token": self.token}
        data = urllib.parse.urlencode(params)
        url = f"{API}{path}"
        body = None
        if method == "GET":
            url += "?" + data
        else:
            body = data.encode("utf-8")
        request = urllib.request.Request(url, data=body, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ThreadsError(self._clean(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")) from None
        except (OSError, http.client.HTTPException, ValueError) as e:
            raise ThreadsError(self._clean(f"연결 실패: {e}")) from None

    def _clean(self, message: str) -> str:
        return message.replace(self.token, "***") if self.token else message

    def me(self) -> dict:
        return self._call("GET", "/v1.0/me", {"fields": "id,username"})

    def create(self, user_id: str, post: Post, media_url: str) -> str:
        params = {"text": post.text, "media_type": "TEXT"}
        if media_url:
            is_video = Path(post.media).suffix.lower() in VIDEO_SUFFIXES
            params["media_type"] = "VIDEO" if is_video else "IMAGE"
            params["video_url" if is_video else "image_url"] = media_url
        return self._call("POST", f"/v1.0/{user_id}/threads", params)["id"]

    def status(self, container: str) -> str:
        return self._call("GET", f"/v1.0/{container}", {"fields": "status,error_message"}).get("status", "")

    def publish(self, user_id: str, container: str) -> str:
        return self._call("POST", f"/v1.0/{user_id}/threads_publish", {"creation_id": container})["id"]

    def refresh(self) -> str:
        return self._call("GET", "/refresh_access_token", {"grant_type": "th_refresh_token"})["access_token"]

    def exchange(self, app_secret: str) -> str:
        params = {"grant_type": "th_exchange_token", "client_secret": app_secret}
        return self._call("GET", "/access_token", params)["access_token"]

    def url_ok(self, url: str) -> bool:
        request = urllib.request.Request(url, method="HEAD")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status == 200
        except (OSError, http.client.HTTPException):
            return False


def _finish(state: dict, store: Store, day: str, post_id: str, now: datetime) -> None:
    state["posted"][day] = post_id
    state["pending"] = None
    state["last_post_day"] = now.astimezone(KST).date().isoformat()
    store.save_state(state)
    store.log(now, f"게시 완료: {day}")


def _publish(api, user_id: str, container: str, day: str, state: dict, store: Store, now: datetime) -> int:
    state["pending"] = {"date": day, "container": container, "at": now.isoformat()}
    store.save_state(state)  # 올리는 도중 끊겨도 다음 실행이 상태를 확인하고 두 번 올리지 않는다
    try:
        post_id = api.publish(user_id, container)
    except ThreadsError as e:
        store.log(now, f"게시 결과 모름, 다음 실행에서 확인: {day}: {e}")
        return 1
    _finish(state, store, day, post_id, now)
    return 0


def _resolve_pending(api, user_id: str, state: dict, store: Store, now: datetime) -> int | None:
    """끊긴 게시를 정리한다. 이번 실행을 끝내야 하면 종료 코드를, 이어 가도 되면 None을 돌려준다."""
    pending = state["pending"]
    try:
        status = api.status(pending["container"])
    except ThreadsError as e:
        if now - datetime.fromisoformat(pending["at"]) <= PENDING_GIVE_UP:
            raise
        # 올라갔는지 끝내 알 수 없다. 두 번 올리는 것보다 한 편 빠지는 편이 낫다.
        store.log(now, f"결과를 몰라 건너뜀, 스레드에서 직접 확인: {pending['date']}: {e}")
        state["posted"][pending["date"]] = "unknown"
        state["pending"] = None
        store.save_state(state)
        return 1
    if status == "PUBLISHED":
        _finish(state, store, pending["date"], "published", now)
        return 0
    if status == "FINISHED":
        return _publish(api, user_id, pending["container"], pending["date"], state, store, now)
    if status == "IN_PROGRESS":
        store.log(now, f"아직 처리 중: {pending['date']}")
        return 0
    store.log(now, f"끊긴 게시를 지우고 다시 시도: {pending['date']} ({status})")
    state["pending"] = None
    store.save_state(state)
    return None


def _dry_run(root: Path, store: Store, now: datetime, terms: list[str]) -> int:
    config, state = store.load_config(), store.load_state()
    post = load_due_post(root, config["start_date"], set(state["posted"]), now)
    if not post:
        store.log(now, "시험 실행: 올릴 글 없음")
        return 0
    problems = validate_post(post, root, terms)
    store.log(now, f"시험 실행: {post.date} ({text_length(post.text)}자) 미디어={post.media or '없음'} 문제={problems or '없음'}")
    if sys.stdout:
        print("-" * 40 + "\n" + post.text + "\n" + "-" * 40)
    return 0


def run(root, store: Store, api, now: datetime, terms: list[str], sleep=time.sleep, dry_run: bool = False, is_published=lambda path: True) -> int:
    root = Path(root)
    if dry_run:
        return _dry_run(root, store, now, terms)
    config = store.load_config()
    token = store.load_token()
    if not config["enabled"] or not token:
        store.log(now, "꺼져 있거나 토큰이 없어 올리지 않음")
        return 0
    code = 0
    try:
        if now - datetime.fromisoformat(token["refreshed_at"]) >= REFRESH_AFTER:
            try:
                store.save_token(api.refresh(), now)
                store.log(now, "토큰 갱신")
            except ThreadsError as e:
                store.log(now, f"토큰 갱신 실패, 60일 안에 다시 받아야 함: {e}")
                code = 1
        me = api.me()
        if me.get("username") != config["username"]:
            store.log(now, "연결된 계정이 설정과 달라 멈춤")
            return 1
        user_id = me["id"]
        state = store.load_state()
        if state["pending"]:
            result = _resolve_pending(api, user_id, state, store, now)
            if result is not None:
                return result or code
        if state["last_post_day"] == now.astimezone(KST).date().isoformat():
            return code
        post = load_due_post(root, config["start_date"], set(state["posted"]), now)
        if not post:
            store.log(now, "올릴 글 없음")
            return code
        if not is_published(post.source):
            store.log(now, f"공개 저장소에 없어 멈춤, publish.py로 올려야 뒤의 글도 나감: {post.date}")
            return 1
        problems = validate_post(post, root, terms)
        if problems:
            store.log(now, f"올리지 않음: {post.date}: {problems}")
            return 1
        site_url = json.loads((root / "data" / "site.json").read_text(encoding="utf-8")).get("site_url", "").rstrip("/")
        media_url = f"{site_url}/{post.media}" if post.media else ""
        for url in filter(None, (media_url, post.link)):
            if not api.url_ok(url):
                store.log(now, f"공개 주소가 아직 안 열려 기다림: {post.date}")
                return 1
        container = api.create(user_id, post, media_url)
        for attempt in range(WAIT_TRIES):
            sleep(WAIT_SECONDS)
            status = api.status(container)
            if status != "IN_PROGRESS":
                break
        if status == "FINISHED":
            return _publish(api, user_id, container, post.date, state, store, now) or code
        if status == "IN_PROGRESS":
            state["pending"] = {"date": post.date, "container": container, "at": now.isoformat()}
            store.save_state(state)
            store.log(now, f"처리가 길어져 다음 실행에서 이어 감: {post.date}")
            return 1
        store.log(now, f"쓰레드가 글을 거절함: {post.date} ({status})")
        return 1
    except ThreadsError as e:
        store.log(now, f"실패: {e}")
        return 1
    except Exception as e:  # 예약 실행은 화면이 없다. 비밀이 섞일 수 있으니 종류만 남긴다.
        store.log(now, f"예상 못 한 오류: {type(e).__name__}")
        return 1


def next_post(root, store: Store, now: datetime, terms: list[str], is_published, url_ok) -> tuple[int, dict]:
    """Chrome 예약용. 오늘 예약할 글 하나를 검사까지 마쳐 돌려준다. 하루 한 편, 오늘 기록은 다음 날."""
    root = Path(root)
    config, state = store.load_config(), store.load_state()
    if state["last_post_day"] == now.astimezone(KST).date().isoformat():
        return 0, {"due": False, "reason": "오늘은 이미 예약함"}
    post = load_due_post(root, config["start_date"], set(state["posted"]), now)
    if not post:
        return 0, {"due": False, "reason": "올릴 글 없음"}
    reason = ""
    if not is_published(post.source):
        reason = f"공개 저장소에 없음, publish.py로 올려야 함: {post.date}"
    elif problems := validate_post(post, root, terms):
        reason = f"올리지 않음: {post.date}: {problems}"
    else:
        site_url = json.loads((root / "data" / "site.json").read_text(encoding="utf-8")).get("site_url", "").rstrip("/")
        urls = [u for u in (f"{site_url}/{post.media}" if post.media else "", post.link) if u]
        if not all(url_ok(u) for u in urls):
            reason = f"공개 주소가 아직 안 열림: {post.date}"
    if reason:
        store.log(now, reason, echo=False)
        return 1, {"due": False, "reason": reason}
    media_path = str((root / post.media).resolve()) if post.media else ""
    return 0, {"due": True, "date": post.date, "text": post.text, "media_path": media_path, "account": config["username"]}


def mark_scheduled(store: Store, day: str, now: datetime) -> int:
    """Chrome으로 예약을 마친 기록 날짜를 적는다. 같은 날을 두 번 적지 않는다."""
    state = store.load_state()
    if not DATE_FILE.match(day) or day in state["posted"]:
        store.log(now, f"예약 표시 거절: {day}")
        return 1
    state["posted"][day] = "chrome"
    state["last_post_day"] = now.astimezone(KST).date().isoformat()
    store.save_state(state)
    store.log(now, f"Chrome 예약 완료: {day}")
    return 0


def _git_published(root: Path):
    """파일이 origin/main에 내용까지 같게 올라가 있는지 본다."""

    def check(rel: str) -> bool:
        proc = subprocess.run(["git", "-C", str(root), "show", f"origin/main:{rel}"], capture_output=True)
        if proc.returncode != 0:
            return False
        norm = lambda b: b.replace(b"\r\n", b"\n")  # noqa: E731
        return norm(proc.stdout) == norm((root / rel).read_bytes())

    return check


def first_refresh_time(now: datetime) -> datetime:
    """붙여 넣은 토큰은 언제 발급됐는지 모른다. 갱신 가능해지는 24시간 뒤에 한 번 갱신하게 한다."""
    return now - REFRESH_AFTER + timedelta(days=1)


def _set_token(store: Store) -> int:
    now = datetime.now(KST)
    token = getpass.getpass("토큰을 붙여 넣고 Enter (화면에 보이지 않습니다): ").strip()
    secret = getpass.getpass("단기 토큰이면 앱 시크릿을 넣고, 장기 토큰이면 그냥 Enter: ").strip()
    if not token:
        print("토큰이 비어 있어 저장하지 않았습니다.")
        return 1
    try:
        if secret:
            token = Api(token).exchange(secret)
        me = Api(token).me()
    except ThreadsError as e:
        print(f"토큰 확인 실패: {e}")
        return 1
    expected = store.load_config()["username"]
    if me.get("username") != expected:
        print(f"이 토큰의 계정이 {expected}가 아닙니다. 저장하지 않았습니다.")
        return 1
    store.save_token(token, first_refresh_time(now))
    if not store.config_path.exists():
        store.save_config(store.load_config())
    print(f"저장했습니다. 계정: {expected}")
    return 0


def _set_enabled(store: Store, enabled: bool) -> int:
    if enabled and not store.load_token():
        print("토큰이 없어 켜지 않았습니다. 먼저 --set-token을 실행하세요.")
        return 1
    store.save_config({**store.load_config(), "enabled": enabled})
    print("자동 게시를 켰습니다." if enabled else "자동 게시를 껐습니다.")
    return 0


def _status(store: Store) -> int:
    config, state, token = store.load_config(), store.load_state(), store.load_token()
    print(f"켜짐: {config['enabled']}  계정: {config['username']}  시작일: {config['start_date']}")
    print(f"토큰: {'있음, 다음 갱신 ' + (datetime.fromisoformat(token['refreshed_at']) + REFRESH_AFTER).date().isoformat() if token else '없음'}")
    print(f"올린 날: {sorted(state['posted'])}  끊긴 게시: {state['pending'] or '없음'}")
    if store.log_path.exists():
        print("최근 기록:\n" + "\n".join(store.log_path.read_text(encoding="utf-8").splitlines()[-5:]))
    return 0


def main(argv: list[str] | None = None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="스레드 자동 게시")
    group = parser.add_mutually_exclusive_group(required=True)
    for flag in ("--run", "--dry-run", "--status", "--set-token", "--enable", "--disable", "--next"):
        group.add_argument(flag, action="store_true")
    group.add_argument("--mark", metavar="YYYY-MM-DD", help="Chrome으로 예약을 마친 기록 날짜")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--terms", default=str(DEFAULT_TERMS))
    args = parser.parse_args(argv)
    store = Store()
    if args.status:
        return _status(store)
    if args.set_token:
        return _set_token(store)
    if args.enable or args.disable:
        return _set_enabled(store, args.enable)
    if args.mark:
        return mark_scheduled(store, args.mark, datetime.now(KST))
    root = Path(args.root)
    now = datetime.now(KST)
    try:
        terms = load_terms(Path(args.terms))
    except FileNotFoundError:
        store.log(now, "금지어 목록이 없어 올리지 않음")
        return 2
    if args.next:
        code, out = next_post(root, store, now, terms, _git_published(root), Api("").url_ok)
        print(json.dumps(out, ensure_ascii=False))
        return code
    token = store.load_token()
    api = Api(token["token"] if token else "")
    return run(root, store, api, now, terms, dry_run=args.dry_run, is_published=_git_published(root))


if __name__ == "__main__":
    raise SystemExit(main())

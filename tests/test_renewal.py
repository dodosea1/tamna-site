"""인터랙티브 리뉴얼(A안, 2026-11-26): 다른 게임 줄, 살아 있음 줄, 지금 어디까지, 다음 소식, 응원 한 줄, 움직임."""
import json
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from build import build_site
from tools.sitegen.content import LogEntry
from tools.sitegen.studio import cheer_line, follow_block, game_card, live_line, now_lines, other_games_rail

FX = Path("tests/fixtures/site")
B = "/tamna-site"
TAMNA = {"slug": "tamna", "name": "탐라(가제)", "status": "개발 중", "summary": "섬 사냥"}
CURVY = {"slug": "curvy", "name": "curvy(가칭)", "status": "개발 중", "summary": "슬라임"}
GOHYANG = {"slug": "gohyang", "name": "고향", "status": "운영 중", "summary": "따로", "url": "https://gohyang.town"}


def log(day: str, body: str = "## 한 일\n- 가\n- 나\n", game: str = "tamna") -> LogEntry:
    return LogEntry(date=day, title=f"제목 {day}", media=[], body_md=body, game=game)


class PiecesTest(unittest.TestCase):
    def test_other_games_rail_excludes_current_and_keeps_external(self):
        html = other_games_rail(B, [TAMNA, CURVY, GOHYANG], "tamna")
        self.assertIn("ORN의 다른 게임", html)
        self.assertNotIn("/games/tamna/", html)
        self.assertIn(f'href="{B}/games/curvy/"', html)
        self.assertIn('href="https://gohyang.town" rel="noopener"', html)
        self.assertLess(html.index("/games/curvy/"), html.index("gohyang.town"))  # games.json 순서
        self.assertEqual(other_games_rail(B, [TAMNA], "tamna"), "")

    def test_cards_count_clicks_by_slug(self):
        self.assertIn('data-goatcounter-click="card-curvy"', game_card(B, CURVY))
        self.assertIn('data-goatcounter-click="card-gohyang"', game_card(B, GOHYANG))

    def test_live_line_counts_last_seven_days(self):
        html = live_line([log("2026-11-26"), log("2026-11-21"), log("2026-11-19")], date(2026, 11, 26))
        self.assertIn("이번 주 기록 2개", html)
        self.assertIn('<time data-rel datetime="2026-11-26">2026-11-26</time>', html)
        # 7일 창의 끝: 오늘 포함 7일이면 11-20까지
        self.assertIn("이번 주 기록 2개", live_line([log("2026-11-26"), log("2026-11-20")], date(2026, 11, 26)))

    def test_live_line_without_recent_logs(self):
        html = live_line([log("2026-11-10")], date(2026, 11, 26))
        self.assertNotIn("이번 주 기록", html)
        self.assertIn("마지막 기록", html)
        self.assertIn('datetime="2026-11-10"', html)
        self.assertEqual(live_line([], date(2026, 11, 26)), "")

    def test_now_lines_takes_first_done_item(self):
        logs = [log("2026-11-26"), log("2026-11-25", "## 막힌 것\n- 없음\n"), log("2026-11-24", "## 한 일\n- 다\n")]
        self.assertEqual(now_lines(logs), [("2026-11-26", "가"), ("2026-11-24", "다")])
        self.assertEqual(len(now_lines([log(f"2026-11-{d:02d}") for d in range(20, 26)])), 3)

    def test_cheer_and_follow(self):
        self.assertEqual(cheer_line(B, False), "")
        cheer = cheer_line(B, True)
        self.assertIn(f'<a href="{B}/support/" data-goatcounter-click="cheer">개발 응원하기</a>', cheer)
        threads = "https://www.threads.com/@x"
        both = follow_block(B, TAMNA, threads, True)
        self.assertIn("다음 소식 받기", both)
        self.assertIn(f'href="{B}/games/tamna/together/"', both)
        self.assertIn('data-goatcounter-click="tester-tamna"', both)
        self.assertIn(f'href="{threads}" rel="noopener"', both)
        for args, count in (((threads, True), 2), ((threads, False), 1), (("", True), 1)):
            self.assertEqual(follow_block(B, TAMNA, *args).count("<a "), count, args)
        self.assertEqual(follow_block(B, TAMNA, "", False), "")

    def test_card_video_uses_poster_and_no_src(self):
        g = {**TAMNA, "card_image": "static/art/k.webp", "card_video": "media/previews/tamna.mp4"}
        html = game_card(B, g)
        self.assertIn(f'data-src="{B}/media/previews/tamna.mp4"', html)
        self.assertIn(f'poster="{B}/static/art/k.webp"', html)
        self.assertIn('preload="none"', html)
        self.assertNotIn(" src=", html)
        self.assertNotIn("<img", html)

    def test_pieces_escape_values(self):
        g = {"slug": "x", "name": "<b>이름</b>", "summary": 'a"b', "url": 'https://e.com/?a="b"'}
        html = game_card(B, g)
        self.assertNotIn("<b>", html)
        self.assertNotIn('a"b', html)


class SiteTest(unittest.TestCase):
    def make(self, edit=None):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "root"; shutil.copytree(FX, root)
        if edit:
            edit(root)
        return root, Path(tmp.name) / "out"

    def build(self, edit=None):
        root, out = self.make(edit)
        build_site(root, out, base=B)
        return out

    def read(self, out, rel):
        return (out / rel).read_text(encoding="utf-8")

    @staticmethod
    def games(root, change):
        path = root / "data/games.json"
        games = json.loads(path.read_text(encoding="utf-8"))
        change({g["slug"]: g for g in games})
        path.write_text(json.dumps(games, ensure_ascii=False), encoding="utf-8")


class GameKeysTest(SiteTest):
    def test_games_json_optional_keys_validated(self):
        bad = (
            ("card_video", "media/x.mp4"),                      # 파일 없음
            ("card_video", "media/log/2026-11-07-hunter-sweep.gif"),  # mp4 아님
            ("slides", ["static/art/cards/curvy-800.webp"]),    # 1개
            ("slides", ["static/art/cards/curvy-800.webp", "static/art/none.webp"]),  # 없는 그림
            ("slides", ["static/art/cards/curvy-800.webp", "media/log/2026-11-07-hunter-sweep.gif"]),  # static 밖
            ("slides", ["static/art/cards/curvy-800.webp", "static/../build.py"]),
        )
        for key, value in bad:
            root, out = self.make(lambda r, key=key, value=value: self.games(r, lambda g: g["tamna"].update({key: value})))
            with self.assertRaises(ValueError, msg=f"{key}={value}") as caught:
                build_site(root, out, base=B)
            self.assertIn(key, str(caught.exception))

    def test_valid_optional_keys_build(self):
        def ok(root):
            (root / "media/previews").mkdir(parents=True)
            (root / "media/previews/t.mp4").write_bytes(b"0")
            self.games(root, lambda g: g["tamna"].update({"card_video": "media/previews/t.mp4"}))
            self.games(root, lambda g: g["curvy"].update({"slides": ["static/art/cards/curvy-800.webp", "static/art/cards/iyagi-800.webp"]}))
        home = self.read(self.build(ok), "index.html")
        self.assertIn(f'data-src="{B}/media/previews/t.mp4"', home)


THREADS = "https://www.threads.com/@x"


def full(root):
    """스레드 주소, 후원 페이지, 탐라 같이하기 페이지가 있는 사이트."""
    path = root / "data/site.json"
    site = json.loads(path.read_text(encoding="utf-8"))
    site["threads_url"] = THREADS
    path.write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")
    (root / "content/pages/support.md").write_text("---\ntitle: 후원\norder: 5\n---\n후원 안내.\n", encoding="utf-8")
    (root / "content/games/tamna/together.md").write_text("---\ntitle: 같이하기\norder: 1\n---\n명단.\n", encoding="utf-8")


def rail_of(html: str) -> str:
    start = html.index('<section class="other-games')
    return html[start:html.index("</section>", start)]


class GamePageTest(SiteTest):
    def test_game_page_has_rail_follow_cheer(self):
        page = self.read(self.build(full), "games/tamna/index.html")
        rail = rail_of(page)
        self.assertIn("ORN의 다른 게임", rail)
        self.assertIn(f'href="{B}/games/curvy/"', rail)
        self.assertIn("gohyang.town", rail)
        self.assertNotIn(f"{B}/games/tamna/", rail)
        self.assertIn("다음 소식 받기", page)
        self.assertIn('data-goatcounter-click="tester-tamna"', page)
        self.assertIn(f'href="{THREADS}" rel="noopener">스레드 팔로우', page)
        self.assertEqual(page.count("개발 응원하기"), 1)
        # 순서: 다음 소식 → 다른 게임 → 응원
        self.assertLess(page.index("다음 소식 받기"), page.index("ORN의 다른 게임"))
        self.assertLess(page.index("ORN의 다른 게임"), page.index("개발 응원하기"))

    def test_game_page_hides_empty_sections(self):
        # 기록도, 소개 글도, 스레드 주소도, 후원 페이지도 없는 게임
        page = self.read(self.build(lambda root: shutil.rmtree(root / "content/log/curvy")), "games/curvy/index.html")
        own = page[page.index("<main>"):page.index('<section class="other-games')]  # 다른 게임 카드 앞까지가 이 게임의 칸
        for gone in ("아직 기록이 없습니다", "준비 중", "준비하고", "지금 어디까지", "최근 기록", "다음 소식 받기",
                     '<ul class="log-list', '<p class="muted small"></p>', "<figure"):
            self.assertNotIn(gone, own)
        self.assertNotIn("개발 응원하기", page)
        self.assertIn("ORN의 다른 게임", page)
        self.assertIn(f'href="{B}/games/tamna/"', rail_of(page))

    def test_now_block_lists_dated_done_items(self):
        page = self.read(self.build(), "games/tamna/index.html")
        start = page.index('<section class="now-block">')
        block = page[start:page.index("</section>", start)]
        self.assertIn("지금 어디까지", block)
        self.assertIn('<li><time datetime="2026-11-07">2026-11-07</time> 사례 7개 범위를 조사했다.</li>', block)
        self.assertLess(block.index("2026-11-07"), block.index("2026-11-06"))
        self.assertIn("약속 아님", block)
        # 옛 '다음에 손댈 것' 칸은 이 칸으로 바뀌었다
        self.assertNotIn("다음에 손댈 것 ·", page)

    def test_game_page_logs_are_latest_three_and_link_to_all(self):
        def more(root):
            for day in ("2026-11-08", "2026-11-09"):
                (root / f"content/log/{day}.md").write_text(
                    f"---\ndate: {day}\ntitle: 제목 {day}\n---\n## 한 일\n- 일\n## 막힌 것\n- 없음\n## 다음에 손댈 것 (약속 아님)\n- 다음\n", encoding="utf-8")
        page = self.read(self.build(more), "games/tamna/index.html")
        self.assertIn(f'href="{B}/log/tamna/2026-11-09/"', page)
        self.assertIn(f'href="{B}/log/tamna/2026-11-07/"', page)
        self.assertNotIn(f'href="{B}/log/tamna/2026-11-06/"', page)
        self.assertIn(f'href="{B}/log/tamna/">', page)

    def test_slides_render_as_crossfade(self):
        pics = ["static/art/cards/curvy-800.webp", "static/art/cards/iyagi-800.webp"]
        page = self.read(self.build(lambda root: self.games(root, lambda g: g["curvy"].update({"slides": pics}))), "games/curvy/index.html")
        start = page.index('<div class="slides" data-slides>')
        block = page[start:page.index("</div>", start)]
        self.assertEqual(block.count("<img"), 2)
        self.assertEqual(block.count('loading="eager"'), 1)
        self.assertEqual(block.count('loading="lazy"'), 1)
        self.assertLess(block.index('loading="eager"'), block.index('loading="lazy"'))
        self.assertIn(f'src="{B}/static/art/cards/curvy-800.webp"', block)

    def test_game_page_shows_status_and_card_picture_when_nothing_else(self):
        def card(root):
            self.games(root, lambda g: g["curvy"].update({"card_image": "static/art/cards/curvy-800.webp", "platform": "2D 도트"}))
        page = self.read(self.build(card), "games/curvy/index.html")
        self.assertIn('<span class="tag dev">개발 중</span><span class="tag">2D 도트</span>', page)
        self.assertIn(f'<figure class="game-shot"><img src="{B}/static/art/cards/curvy-800.webp" alt="" loading="eager"></figure>', page)


class LogPageTest(SiteTest):
    def test_log_page_ends_with_other_games(self):
        out = self.build()
        page = self.read(out, "log/tamna/2026-11-07/index.html")
        rail = rail_of(page)
        self.assertIn("ORN의 다른 게임", rail)
        self.assertIn(f'href="{B}/games/curvy/"', rail)
        self.assertNotIn(f'href="{B}/games/tamna/"', rail)
        self.assertLess(page.index("</article>"), page.index("ORN의 다른 게임"))
        # 다른 게임의 기록에서는 그 게임이 빠지고 탐라가 들어온다
        curvy = rail_of(self.read(out, "log/curvy/2026-11-07/index.html"))
        self.assertIn(f'href="{B}/games/tamna/"', curvy)
        self.assertNotIn(f'href="{B}/games/curvy/"', curvy)
        # 옛 주소 넘김 쪽은 그대로
        self.assertNotIn("ORN의 다른 게임", self.read(out, "log/2026-11-07/index.html"))


class HomeTest(SiteTest):
    def test_home_live_line_rail_and_cheer(self):
        home = self.read(self.build(full), "index.html")
        self.assertIn('<p class="live">', home)
        self.assertIn('<time data-rel datetime="2026-11-07">', home)
        start = home.index('<div class="rail')
        rail = home[start:home.index("</section>", start)]
        for slug in ("tamna", "curvy", "gohyang"):
            self.assertIn(f'data-goatcounter-click="card-{slug}"', rail)
        self.assertIn("다음 소식 받기", home)
        self.assertIn('data-goatcounter-click="tester-tamna"', home)
        # 응원은 한 줄만. 옛 후원 상자는 없다.
        self.assertEqual(home.count("개발 응원하기"), 1)
        self.assertNotIn("만드는 시간을 응원해 주세요", home)
        self.assertNotIn("후원 방법 보기", home)
        # 살아 있음 줄은 카드보다 위
        self.assertLess(home.index('<p class="live">'), start)

    def test_home_without_threads_or_support_hides_follow_and_cheer(self):
        home = self.read(self.build(), "index.html")
        self.assertNotIn("다음 소식 받기", home)
        self.assertNotIn("개발 응원하기", home)
        self.assertNotIn("home-follow", home)  # 빈 칸(여백만 있는 구역)을 남기지 않는다
        self.assertIn("의견 보내기", home)  # 의견 상자는 그대로


class MotionTest(SiteTest):
    def test_reveal_hidden_only_under_js_class(self):
        """JS가 꺼져도 글과 카드가 보인다: 완전히 숨기는 규칙(opacity: 0)은 html.js 아래에서만 건다."""
        css = re.sub(r"/\*.*?\*/", "", Path("static/style.css").read_text(encoding="utf-8"), flags=re.S)
        hidden = [m.group(1).strip() for m in re.finditer(r"([^{}]+)\{[^{}]*opacity:\s*0(?![.\d])[^{}]*\}", css)]
        self.assertTrue(hidden, "올라오며 나타나는 규칙이 있어야 한다")
        for selectors in hidden:
            for selector in selectors.split(","):
                self.assertTrue(selector.strip().startswith(".js "), selector)

    def test_base_loads_site_js_deferred(self):
        out = self.build()
        pages = [p for p in out.rglob("index.html") if 'http-equiv="refresh"' not in p.read_text(encoding="utf-8")]
        self.assertGreater(len(pages), 8)
        for p in pages:
            html = p.read_text(encoding="utf-8")
            self.assertIn(f'<script src="{B}/static/site.js" defer></script>', html, p)
            # 본문보다 먼저 html.js를 붙인다(본문이 그려지기 전에 CSS가 알 수 있게).
            self.assertIn("<body>\n<script>document.documentElement.classList.add('js')</script>", html.replace("\r\n", "\n"), p)
            self.assertNotIn("addEventListener", html, p)  # 인라인 동작 스크립트는 site.js로 옮겼다
        self.assertTrue((out / "static/site.js").exists())

    def test_play_clip_waits_for_view_and_shows_poster(self):
        def clip(root):
            (root / "media/previews").mkdir(parents=True)
            (root / "media/previews/clip.jpg").write_bytes(b"0")
            self.games(root, lambda g: g["tamna"].update({"play_media": "media/clip.mp4", "play_label": "화면"}))
        page = self.read(self.build(clip), "games/tamna/index.html")
        self.assertIn(f'<video class="play-video" src="{B}/media/clip.mp4" poster="{B}/media/previews/clip.jpg" muted loop playsinline preload="none" controls', page)
        self.assertNotIn("autoplay", page)

    def test_full_font_file_is_not_imported(self):
        """글꼴 전체(2MB)를 CSS @import로 받지 않는다. 쓰는 글자 묶음만 받는 스타일시트를 head에서 부른다."""
        self.assertNotIn("@import", Path("static/style.css").read_text(encoding="utf-8"))
        home = self.read(self.build(), "index.html")
        head = home[:home.index("</head>")]
        font = "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        # 휴대폰 폭에서는 웹 글꼴을 받지 않고 기기 글꼴을 쓴다(글꼴 조각 500KB와 조각마다 다시 그리는 일을 없앤다).
        self.assertIn(f'<link rel="stylesheet" href="{font}" media="(min-width: 901px)">', head)
        self.assertEqual(head.count("dynamic-subset"), 1)


class ThumbTest(SiteTest):
    @staticmethod
    def still(root):
        from PIL import Image
        Image.new("RGB", (1600, 900), (200, 120, 40)).save(root / "media/log/a.jpg", quality=95)
        path = root / "content/log/2026-11-06.md"
        path.write_text(path.read_text(encoding="utf-8").replace("title:", "media: media/log/a.jpg\ntitle:", 1), encoding="utf-8")

    def test_list_thumbnail_is_a_small_copy_not_the_original(self):
        out = self.build(self.still)
        for rel in ("index.html", "games/tamna/index.html"):
            page = self.read(out, rel)
            self.assertIn(f'<img class="thumb" src="{B}/thumbs/log/a.jpg" alt="" loading="lazy" width="176" height="124">', page, rel)
            self.assertNotIn(f'class="thumb" src="{B}/media/', page, rel)
        from PIL import Image
        with Image.open(out / "thumbs/log/a.jpg") as small:
            self.assertEqual(small.size, (176, 124))
        self.assertLess((out / "thumbs/log/a.jpg").stat().st_size, 20_000)
        # 기록 글 본문은 원본 그림 그대로
        self.assertIn(f'src="{B}/media/log/a.jpg"', self.read(out, "log/tamna/2026-11-06/index.html"))

    def test_gif_and_missing_picture_get_no_thumbnail(self):
        page = self.read(self.build(), "games/tamna/index.html")  # 픽스처의 11-07 기록은 GIF
        self.assertNotIn('class="thumb"', page)

    def test_without_pillow_lists_simply_have_no_pictures(self):
        import tools.sitegen.thumbs as thumbs
        original = thumbs.make_thumb
        thumbs.make_thumb = lambda src, dst: False
        self.addCleanup(setattr, thumbs, "make_thumb", original)
        out = self.build(self.still)
        self.assertNotIn('class="thumb"', self.read(out, "index.html"))
        self.assertFalse((out / "thumbs").exists())


if __name__ == "__main__":
    unittest.main()

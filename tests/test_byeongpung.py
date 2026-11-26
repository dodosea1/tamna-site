"""대개편 A. 오방색 병풍(2026-11-26): 게임 하나가 병풍 한 폭, 한지 읽는 페이지, 도장, 패치 노트 목록."""
import json
import re
import shutil
import unittest
from pathlib import Path
from urllib.parse import unquote

from tests.test_renewal import B, CURVY, GOHYANG, TAMNA, SiteTest, full, log
from tools.sitegen.studio import date_seal, latest_card, other_games_rail, panel, patch_list, split_name


class PanelTest(unittest.TestCase):
    def test_panel_title_splits_tentative_mark_and_keeps_full_name(self):
        self.assertEqual(split_name("탐라(가제)"), ("탐라", "가제"))
        self.assertEqual(split_name("고향"), ("고향", ""))
        self.assertEqual(split_name("a(b) c(가칭)"), ("a(b) c", "가칭"))
        html = panel(B, TAMNA)
        self.assertIn('<h2 class="vt" aria-label="탐라(가제)"><span aria-hidden="true">탐라</span><small aria-hidden="true">가제</small></h2>', html)
        self.assertIn(f'<a class="btn" href="{B}/games/tamna/" data-goatcounter-click="card-tamna">이 게임 보기</a>', html)
        out = panel(B, GOHYANG)
        self.assertNotIn("<small aria-hidden", out)
        self.assertIn('<a class="btn" href="https://gohyang.town" data-goatcounter-click="card-gohyang" rel="noopener">gohyang.town ↗</a>', out)
        self.assertIn('<span class="seal">운영 중</span>', out)

    def test_panel_picture_modes(self):
        cover = panel(B, {**TAMNA, "hero_media_mobile": "static/art/m.webp", "card_image": "static/art/c.webp"}, eager=True)
        self.assertIn('<section class="panel panel-cover" id="p-tamna">', cover)
        self.assertIn(f'src="{B}/static/art/m.webp"', cover)
        self.assertNotIn("panel-blur", cover)
        self.assertEqual(cover.count('fetchpriority="high"'), 1)
        frame = panel(B, {**CURVY, "card_image": "static/art/c.webp", "platform": "2D 도트"})
        self.assertIn('class="panel panel-frame"', frame)
        self.assertEqual(frame.count(f'src="{B}/static/art/c.webp"'), 2)
        self.assertIn('<img class="panel-blur"', frame)
        self.assertIn('<img class="panel-pic"', frame)
        self.assertNotIn("fetchpriority", frame)
        self.assertEqual(frame.count('loading="lazy"'), 2)
        self.assertIn("<small>2D 도트</small>", frame)

    def test_panel_without_picture_has_no_placeholder_text(self):
        html = panel(B, CURVY)
        self.assertIn('class="panel panel-bare"', html)
        self.assertNotIn("<img", html)
        self.assertNotIn("준비", html)
        self.assertIn('class="vt"', html)
        self.assertIn('<span class="seal">개발 중</span>', html)
        self.assertNotIn("<small>", html)  # 플랫폼이 없으면 그 줄도 없다

    def test_panel_heading_and_cta(self):
        self.assertIn('<h1 class="vt" aria-label="탐라(가제)">', panel(B, TAMNA, heading="h1"))
        self.assertNotIn('class="btn"', panel(B, TAMNA, cta=""))
        own = panel(B, TAMNA, cta='<a class="btn" href="#x">가</a>')
        self.assertIn('<a class="btn" href="#x">가</a>', own)
        self.assertNotIn("이 게임 보기", own)

    def test_panel_clip_has_no_src(self):
        html = panel(B, {**TAMNA, "card_image": "static/art/k.webp", "card_video": "media/previews/tamna.mp4"})
        self.assertIn(f'<video class="card-video panel-clip" data-src="{B}/media/previews/tamna.mp4" poster="{B}/static/art/k.webp"', html)
        self.assertIn('preload="none"', html)
        video = html[html.index("<video"):html.index("</video>")]
        self.assertNotIn(" src=", video)

    def test_pieces_escape_values(self):
        g = {"slug": "x", "name": "<b>이름</b>", "summary": 'a"b<i>', "status": "개발 중", "url": 'https://e.com/?a="b"'}
        for html in (panel(B, g), other_games_rail(B, [g, TAMNA], "tamna")):
            self.assertNotIn("<b>", html)
            self.assertNotIn("<i>", html)
            self.assertNotIn('a="b"', html)


class ListPiecesTest(unittest.TestCase):
    def test_date_seal_and_patch_list(self):
        self.assertEqual(date_seal("2026-11-25"), '<time class="seal seal-date" datetime="2026-11-25"><b>11.25</b><i>2026</i></time>')
        logs = [log("2026-11-26"), log("2026-11-24", game="curvy")]
        html = patch_list(B, logs)
        self.assertTrue(html.startswith('<ul class="patch">'))
        self.assertEqual(html.count("<li>"), 2)
        self.assertLess(html.index("2026-11-26"), html.index("2026-11-24"))
        self.assertIn(f'<a href="{B}/log/curvy/2026-11-24/">', html)
        self.assertIn('<span class="t">제목 2026-11-26</span>', html)
        self.assertNotIn('class="g"', html)
        named = patch_list(B, logs, {"tamna": "탐라(가제)", "curvy": "curvy(가칭)"})
        self.assertIn('<span class="g">curvy(가칭)</span>', named)
        self.assertEqual(patch_list(B, []), "")

    def test_latest_card(self):
        self.assertEqual(latest_card(B, None, ""), "")
        html = latest_card(B, log("2026-11-26"), "탐라(가제)")
        self.assertIn(f'<a class="latest" href="{B}/log/tamna/2026-11-26/">', html)
        self.assertIn('<strong class="sf">제목 2026-11-26</strong>', html)
        self.assertIn('<span class="g">탐라(가제)</span>', html)
        self.assertIn("seal-date", html)
        self.assertIn("읽기", html)
        self.assertNotIn("<img", html)
        self.assertIn(f'<img src="{B}/thumbs/card/a.jpg" alt="" loading="lazy" width="640" height="360">', latest_card(B, log("2026-11-26"), "탐라", "thumbs/card/a.jpg"))

    def test_mini_byeongpung_keeps_rail_contract(self):
        html = other_games_rail(B, [TAMNA, {**CURVY, "card_image": "static/art/c.webp"}, GOHYANG], "tamna")
        self.assertIn("ORN의 다른 게임", html)
        self.assertEqual(html.count('class="mini-panel"'), 2)
        self.assertIn(f'<a class="mini-panel" href="{B}/games/curvy/" data-goatcounter-click="other-curvy">', html)
        self.assertIn('<a class="mini-panel" href="https://gohyang.town" rel="noopener" data-goatcounter-click="other-gohyang">', html)
        self.assertNotIn("/games/tamna/", html)
        self.assertIn(f'<img src="{B}/static/art/c.webp" alt="" loading="lazy">', html)
        self.assertIn('<span class="name">curvy(가칭)</span>', html)
        self.assertEqual(other_games_rail(B, [TAMNA], "tamna"), "")


class TitleFontTest(SiteTest):
    def test_serif_chars_collects_headings_and_marked_elements(self):
        from tools.sitegen.fonts import serif_chars
        html = '<h1>가나</h1><p>다</p><span class="seal x">라 a</span><h2>나<b>마</b></h2><img alt="바"><style>.vt{}</style>'
        self.assertEqual(serif_chars(html), "a가나라마")
        self.assertEqual(serif_chars("<p>글</p>"), "")
        # 닫지 않는 태그(img, br)가 끼어도 범위가 어긋나지 않는다
        self.assertEqual(serif_chars('<h2>가<br>나</h2><p>다</p>'), "가나")

    def test_title_font_link_encodes_only_needed_chars(self):
        from tools.sitegen.fonts import title_font_link
        html = title_font_link("a가")
        self.assertIn("https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@700&amp;display=swap&amp;text=a%EA%B0%80", html)
        self.assertIn('media="print"', html)
        self.assertIn("<noscript><link", html)

    def test_title_font_link_is_dropped_when_too_many_chars(self):
        from tools.sitegen.fonts import MAX_FONT_CHARS, title_font_link
        self.assertEqual(MAX_FONT_CHARS, 600)
        self.assertEqual(title_font_link("가" * 601), "")
        self.assertNotEqual(title_font_link("가" * 600), "")
        self.assertEqual(title_font_link(""), "")

    def test_every_page_asks_for_its_own_title_glyphs(self):
        out = self.build()
        page = self.read(out, "log/tamna/2026-11-07/index.html")
        head = page[:page.index("</head>")]
        found = re.search(r'fonts\.googleapis\.com/css2\?family=Gowun\+Batang:wght@700&amp;display=swap&amp;text=([^"]+)"', head)
        self.assertIsNotNone(found)
        glyphs = unquote(found.group(1))
        for ch in "사이트설계와사례조사":
            self.assertIn(ch, glyphs)
        self.assertLess(len(glyphs), 200)
        self.assertNotIn("fonts.googleapis.com", self.read(out, "log/2026-11-07/index.html"))  # 넘김 쪽


def real_pages(out: Path) -> list[Path]:
    """넘김 쪽을 뺀 실제 페이지."""
    return [p for p in out.rglob("index.html") if 'http-equiv="refresh"' not in p.read_text(encoding="utf-8")]


class FrameTest(SiteTest):
    def test_body_kind_per_page(self):
        out = self.build()
        for rel, kind in (("index.html", "home"), ("games/tamna/index.html", "game"), ("games/curvy/index.html", "game"),
                          ("about/index.html", "paper"), ("log/tamna/2026-11-07/index.html", "paper"), ("log/index.html", "paper"),
                          ("games/index.html", "paper"), ("monthly/2026-10/index.html", "paper")):
            self.assertIn(f'<body class="k-{kind}">', self.read(out, rel), rel)

    def test_footer_has_every_menu_link(self):
        out = self.build()
        pages = real_pages(out)
        self.assertGreater(len(pages), 8)
        for p in pages:
            html = p.read_text(encoding="utf-8")
            footer = html[html.index("<footer"):html.index("</footer>")]
            for href in ("/games/", "/log/", "/feedback/", "/about/", "/monthly/", "/feed.xml"):
                self.assertIn(f'href="{B}{href}"', footer, f"{p}: {href}")
            self.assertIn('<div class="obang" aria-hidden="true"></div>', footer, p)

    def test_home_has_one_dot_per_game_and_others_have_none(self):
        out = self.build()
        home = self.read(out, "index.html")
        start = home.index('<nav class="dots"')
        dots = home[start:home.index("</nav>", start)]
        self.assertEqual(dots.count("<a "), 3)
        self.assertIn('<a href="#p-tamna" aria-label="탐라(가제)"></a>', dots)
        for rel in ("about/index.html", "games/tamna/index.html", "log/index.html"):
            self.assertNotIn('class="dots"', self.read(out, rel), rel)

    def test_header_keeps_menu_button_and_nav_contract(self):
        home = self.read(self.build(full), "index.html")
        self.assertIn('<button class="menu-toggle" type="button" aria-label="메뉴 열기" aria-expanded="false" aria-controls="site-nav">메뉴</button>', home)
        nav = home[home.index('<nav class="site-nav" id="site-nav">'):home.index("</nav>", home.index('<nav class="site-nav"'))]
        self.assertIn(f'<a href="{B}/games/">게임</a>', nav)
        self.assertIn('rel="noopener">스레드 팔로우</a>', nav)

    def test_site_js_has_no_reveal_and_handles_menu_and_panels(self):
        js = Path("static/site.js").read_text(encoding="utf-8")
        self.assertNotIn("reveal", js)
        for needle in ("menu-open", "Escape", ".panel", "k-home", "solid"):
            self.assertIn(needle, js)


def between(html: str, start: str, end: str) -> str:
    i = html.index(start)
    return html[i:html.index(end, i)]


class HomeTest(SiteTest):
    def test_home_is_a_byeongpung_of_all_games(self):
        home = self.read(self.build(full), "index.html")
        self.assertEqual(home.count('<section class="panel '), 3)
        self.assertLess(home.index('id="p-tamna"'), home.index('id="p-curvy"'))
        self.assertLess(home.index('id="p-curvy"'), home.index('id="p-gohyang"'))
        self.assertLessEqual(home.count('fetchpriority="high"'), 1)
        self.assertLess(home.index('id="p-gohyang"'), home.index('<div class="obang" aria-hidden="true"></div>'))
        self.assertLess(home.index('<div class="obang"'), home.index('<section class="end paper">'))
        for slug in ("tamna", "curvy", "gohyang"):
            self.assertIn(f'data-goatcounter-click="card-{slug}"', home)
        for old in ("studio-hero", 'class="game-card"', 'class="box"', "log-list"):
            self.assertNotIn(old, home)
        self.assertEqual(home.count("<h1"), 1)

    def test_home_end_shows_latest_card_patch_follow_cheer_once(self):
        home = self.read(self.build(full), "index.html")
        end = between(home, '<section class="end paper">', "</section>")
        self.assertIn('<h1 class="sf">', end)
        self.assertEqual(end.count('class="latest"'), 1)
        self.assertIn(f'<a class="latest" href="{B}/log/tamna/2026-11-07/">', end)   # 같은 날이면 정렬 첫째
        patch = between(end, '<ul class="patch">', "</ul>")
        self.assertEqual(patch.count("<li>"), 2)
        self.assertNotIn(f'href="{B}/log/tamna/2026-11-07/"', patch)   # 카드로 보여 준 기록은 목록에서 뺀다
        self.assertIn(f'href="{B}/log/"', end)
        self.assertIn("다음 소식 받기", end)
        self.assertIn('data-goatcounter-click="tester-tamna"', end)
        self.assertEqual(home.count("개발 응원하기"), 1)
        self.assertIn('<p class="live">', end)
        self.assertIn('class="summary-en"', end)

    def test_home_end_hides_empty_log_parts(self):
        def empty(root):
            shutil.rmtree(root / "content/log")
            (root / "content/log").mkdir()
        home = self.read(self.build(empty), "index.html")
        for gone in ('class="latest"', 'class="patch"', "아직 없습니다", 'class="live"', "전체 기록"):
            self.assertNotIn(gone, home)
        self.assertEqual(home.count('<section class="panel '), 3)

    def test_home_latest_card_picture_is_a_small_copy(self):
        def still(root):
            from PIL import Image
            Image.new("RGB", (1600, 900), (200, 120, 40)).save(root / "media/log/a.jpg", quality=95)
            path = root / "content/log/2026-11-07.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("media: media/log/2026-11-07-hunter-sweep.gif", "media: media/log/a.jpg"), encoding="utf-8")
        out = self.build(still)
        self.assertIn(f'<img src="{B}/thumbs/card/log/a.jpg" alt="" loading="lazy" width="640" height="360">', self.read(out, "index.html"))
        from PIL import Image
        with Image.open(out / "thumbs/card/log/a.jpg") as small:
            self.assertEqual(small.size, (640, 360))


class GamePageTest(SiteTest):
    def test_game_page_opens_with_its_own_panel(self):
        out = self.build(full)
        for slug, name in (("tamna", "탐라(가제)"), ("curvy", "curvy(가칭)")):
            page = self.read(out, f"games/{slug}/index.html")
            self.assertEqual(page.count('<section class="panel '), 1, slug)
            self.assertIn(f'<h1 class="vt" aria-label="{name}">', page)
            self.assertEqual(page.count("<h1"), 1, slug)
            self.assertLess(page.index('<section class="panel '), page.index('class="paper"'), slug)
            self.assertNotIn("이 게임 보기", page)

    def test_game_page_order_and_single_cheer(self):
        page = self.read(self.build(full), "games/tamna/index.html")
        order = [page.index(s) for s in ("지금 어디까지", "다음 소식 받기", "ORN의 다른 게임", "개발 응원하기")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(page.count("개발 응원하기"), 1)
        panel_html = between(page, '<section class="panel ', "</section>")
        self.assertIn('data-goatcounter-click="tester-tamna"', panel_html)
        self.assertEqual(page.count('data-goatcounter-click="tester-tamna"'), 2)

    def test_now_block_uses_date_seals(self):
        page = self.read(self.build(), "games/tamna/index.html")
        block = between(page, '<section class="now-block">', "</section>")
        self.assertIn('<time class="seal seal-date" datetime="2026-11-07">', block)
        self.assertIn("사례 7개 범위를 조사했다.", block)
        self.assertIn("약속 아님", block)

    def test_game_screen_section_only_when_there_is_a_screen(self):
        self.assertNotIn("실제 게임 화면", self.read(self.build(), "games/curvy/index.html"))
        pics = ["static/art/cards/curvy-800.webp", "static/art/cards/iyagi-800.webp"]
        with_slides = self.read(self.build(lambda root: self.games(root, lambda g: g["curvy"].update({"slides": pics}))), "games/curvy/index.html")
        self.assertIn("data-slides", with_slides)
        self.assertIn("실제 게임 화면", with_slides)
        with_clip = self.read(self.build(lambda root: self.games(root, lambda g: g["tamna"].update({"play_media": "media/clip.mp4", "play_label": "화면"}))), "games/tamna/index.html")
        self.assertIn('class="play-video"', with_clip)
        self.assertIn("실제 게임 화면", with_clip)

    def test_game_logs_are_three_patch_rows(self):
        page = self.read(self.build(), "games/tamna/index.html")
        self.assertIn('<ul class="patch">', page)
        self.assertIn(f'href="{B}/log/tamna/">', page)
        self.assertNotIn("log-list", page)

    def test_tamna_page_has_no_css_background_pictures(self):
        page = self.read(self.build(), "games/tamna/index.html")
        self.assertNotIn("background-image", page)
        self.assertRegex(page, r'<img[^>]*src="/tamna-site/static/art/scene-hunt-1400\.webp"[^>]*loading="lazy"')
        self.assertIn("1990년대 후반 한국 2D 온라인 RPG들에서 영감을 받았고", page)


class ReadingPagesTest(SiteTest):
    def test_log_article_head_has_seal_game_strip_and_title(self):
        page = self.read(self.build(), "log/tamna/2026-11-07/index.html")
        head = between(page, '<header class="log-head">', "</header>")
        self.assertIn('<time class="seal seal-date" datetime="2026-11-07">', head)
        self.assertIn(f'<a class="game-strip" href="{B}/log/tamna/">탐라(가제)</a>', head)
        self.assertIn("<h1>사이트 설계와 사례 조사</h1>", head)
        self.assertEqual(page.count("<h1"), 1)
        self.assertLess(page.index("</article>"), page.index("ORN의 다른 게임"))
        self.assertNotIn("page-band", page)

    def test_log_lists_are_patch_notes(self):
        out = self.build()
        everything = self.read(out, "log/index.html")
        self.assertIn('<ul class="patch">', everything)
        self.assertIn('<time class="seal seal-date" datetime="2026-11-07">', everything)
        self.assertIn('<span class="g">curvy(가칭)</span>', everything)
        self.assertIn("<h2>2026-11</h2>", everything)
        self.assertNotIn('<span class="d">', everything)
        self.assertNotIn('<span class="g">', between(self.read(out, "log/curvy/index.html"), "<main>", "</main>"))

    def test_every_plain_page_is_paper(self):
        out = self.build()
        for rel in ("about/index.html", "feedback/index.html", "monthly/index.html", "monthly/2026-10/index.html", "games/index.html", "log/index.html"):
            main = between(self.read(out, rel), "<main>", "</main>")
            self.assertIn('<div class="paper">', main, rel)
            self.assertEqual(main.count("<h1"), 1, rel)
            self.assertLess(main.index('<div class="paper">'), main.index("<h1"), rel)


if __name__ == "__main__":
    unittest.main()

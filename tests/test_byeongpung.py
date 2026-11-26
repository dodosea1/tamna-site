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
        self.assertEqual(frame.count('loading="late"'), 2)   # 화면 가까이 올 때 받는다(late_images가 바꾼다)
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

    def test_panel_clip_prefers_a_frame_of_the_clip_as_poster(self):
        g = {**TAMNA, "card_image": "static/art/k.webp", "card_video": "media/previews/t.mp4", "clip_poster": "media/previews/t.jpg"}
        self.assertIn(f'poster="{B}/media/previews/t.jpg"', panel(B, g))

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
        self.assertIn(f'<img src="{B}/static/art/c.webp" alt="" loading="late">', html)
        self.assertIn('<span class="name">curvy(가칭)</span>', html)
        self.assertEqual(other_games_rail(B, [TAMNA], "tamna"), "")
        # 세로 화면용 그림이 있으면 세로로 선 작은 폭에는 그 그림을 쓴다
        tall = other_games_rail(B, [{**TAMNA, "card_image": "static/art/wide.webp", "hero_media_mobile": "static/art/tall.webp"}, CURVY], "curvy")
        self.assertIn(f'<img src="{B}/static/art/tall.webp" alt="" loading="late">', tall)
        self.assertNotIn("wide.webp", tall)


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
        # 넘김 점은 지금 몇 번째 폭인지 보여 주는 표시다(누르는 것이 아니다. 폭은 밀어서 넘긴다).
        start = home.index('<div class="dots" aria-hidden="true">')
        dots = home[start:home.index("</div>", start)]
        self.assertEqual(dots.count("<i "), 3)
        self.assertIn('<i data-for="p-tamna" class="on"></i>', dots)
        self.assertEqual(dots.count('class="on"'), 1)
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
        self.assertLess(home.index('<div class="obang"'), home.index('<section class="end paper" id="end">'))
        for slug in ("tamna", "curvy", "gohyang"):
            self.assertIn(f'data-goatcounter-click="card-{slug}"', home)
        for old in ("studio-hero", 'class="game-card"', 'class="box"', "log-list"):
            self.assertNotIn(old, home)
        self.assertEqual(home.count("<h1"), 1)

    def test_home_clip_poster_is_the_clip_frame_when_one_exists(self):
        def clip(root, with_frame):
            (root / "media/previews").mkdir(parents=True)
            (root / "media/previews/t.mp4").write_bytes(b"0")
            if with_frame:
                (root / "media/previews/t.jpg").write_bytes(b"0")
            self.games(root, lambda g: g["tamna"].update({"card_video": "media/previews/t.mp4", "card_image": "static/art/cards/curvy-800.webp"}))
        self.assertIn(f'poster="{B}/media/previews/t.jpg"', self.read(self.build(lambda r: clip(r, True)), "index.html"))
        self.assertIn(f'poster="{B}/static/art/cards/curvy-800.webp"', self.read(self.build(lambda r: clip(r, False)), "index.html"))

    def test_home_end_shows_latest_card_patch_follow_cheer_once(self):
        home = self.read(self.build(full), "index.html")
        end = between(home, '<section class="end paper" id="end">', "</section>")
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
        self.assertRegex(page, r'<img[^>]*data-src="/tamna-site/static/art/scene-hunt-1400[.]webp"')
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


class StyleTest(unittest.TestCase):
    def setUp(self):
        self.css = re.sub(r"/[*].*?[*]/", "", Path("static/style.css").read_text(encoding="utf-8"), flags=re.S)

    def test_css_uses_the_five_colors_and_no_old_palette(self):
        for color in ("#1f4f8a", "#c7402d", "#e3b43c", "#f3eee2", "#101a2e"):
            self.assertIn(color, self.css)
        for old in ("#14132b", "#e3b24f", "999px", ".reveal", ".game-card:hover { border-color: rgba(227"):
            self.assertNotIn(old, self.css)
        self.assertIn("writing-mode: vertical-rl", self.css)
        self.assertIn("scroll-snap-type: y mandatory", self.css)
        self.assertIn('"Gowun Batang"', self.css)

    def test_hiding_rules_only_under_js(self):
        """스크립트가 꺼져도 글과 링크가 보인다: 숨기는 규칙은 html.js 아래(또는 스크립트 없을 때 대신 보여 주는 규칙)에서만."""
        # 내용이 아닌 것만 예외: 넓은 화면의 메뉴 버튼·넘김 점, 스크롤 막대
        allowed = {".menu-toggle", ".dots", ".rail::-webkit-scrollbar"}
        hiding = re.compile(r"opacity[ ]?:[ ]?0(?![.\d])|visibility[ ]?:[ ]?hidden|display[ ]?:[ ]?none")
        found = 0
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", self.css):
            if not hiding.search(m.group(2)):
                continue
            for selector in (s.strip() for s in m.group(1).split(",")):
                if re.fullmatch(r"from|to|\d+%", selector) or selector in allowed:
                    continue
                found += 1
                self.assertRegex(selector, r"^(\.js[ .]|html:not\(\.js\) )", selector)
        self.assertGreater(found, 2)

    def test_reduced_motion_block_exists(self):
        start = self.css.index("@media (prefers-reduced-motion: reduce)")
        block = self.css[start:start + 400]
        self.assertIn("animation: none", block)
        self.assertIn("transition: none", block)

    def test_title_font_classes_match_the_collector(self):
        from tools.sitegen.fonts import SERIF_CLASSES
        rule = re.search(r"([^{}]+)\{[^{}]*font-family[ ]?:[ ]*var\(--serif\)", self.css)
        self.assertIsNotNone(rule)
        for cls in SERIF_CLASSES:
            self.assertRegex(rule.group(1), rf"\.{cls}\b")
        for tag in ("h1", "h2", "h3"):
            self.assertRegex(rule.group(1), rf"(^|[\s,]){tag}\b")


class ReviewFixTest(SiteTest):
    """가지 전체 검토(2026-11-26, 병풍)에서 나온 것."""

    def test_menu_button_comes_before_the_menu_and_page_goes_inert(self):
        # 메뉴를 열면 다음 Tab이 메뉴 안으로 가야 한다: 버튼이 목록보다 앞. 열린 동안 뒤의 본문은 inert.
        home = self.read(self.build(), "index.html")
        self.assertLess(home.index('<button class="menu-toggle"'), home.index('<nav class="site-nav"'))
        js = Path("static/site.js").read_text(encoding="utf-8")
        self.assertIn("inert", js)

    def test_game_page_panel_uses_wide_art_on_wide_screens(self):
        g = {**TAMNA, "hero_media": "static/art/wide.webp", "hero_media_mobile": "static/art/tall.webp"}
        html = panel(B, g, heading="h1", eager=True, wide=True)
        self.assertIn(f'<picture><source media="(min-width: 901px)" srcset="{B}/static/art/wide.webp">'
                      f'<img class="panel-pic" src="{B}/static/art/tall.webp" alt="" loading="eager" fetchpriority="high"></picture>', html)
        self.assertNotIn("<picture>", panel(B, g))                       # 첫 화면의 좁은 폭은 세로 그림 그대로
        self.assertNotIn("<picture>", panel(B, {**TAMNA, "hero_media_mobile": "static/art/tall.webp"}, wide=True))

        def art(root):
            self.games(root, lambda games: games["tamna"].update({"hero_media": "static/art/key-hero-2400.webp", "hero_media_mobile": "static/art/key-hero-m-1000.webp"}))
        out = self.build(art)
        self.assertIn(f'<source media="(min-width: 901px)" srcset="{B}/static/art/key-hero-2400.webp">', self.read(out, "games/tamna/index.html"))
        self.assertNotIn("key-hero-2400.webp", self.read(out, "index.html"))

    def test_panel_says_when_the_picture_is_key_art(self):
        g = {**TAMNA, "hero_media_mobile": "static/art/tall.webp", "hero_label": "키아트 (민화풍 그림)"}
        self.assertIn('<span class="art-note">키아트 (민화풍 그림)</span>', panel(B, g))
        self.assertNotIn("art-note", panel(B, {**TAMNA, "card_image": "static/art/c.webp", "hero_label": "키아트"}))   # 세로 그림을 쓸 때만
        self.assertNotIn("art-note", panel(B, TAMNA))

    def test_home_with_one_log_has_no_empty_recent_label(self):
        def one(root):
            (root / "content/log/2026-11-06.md").unlink()
            shutil.rmtree(root / "content/log/curvy")
        home = self.read(self.build(one), "index.html")
        self.assertEqual(home.count('class="latest"'), 1)
        self.assertNotIn("최근 기록", home)
        self.assertNotIn('class="patch"', home)
        self.assertIn(f'<a class="more" href="{B}/log/">전체 기록 보기</a>', home)

    def test_footer_also_has_the_threads_link(self):
        home = self.read(self.build(full), "index.html")
        footer = home[home.index("<footer"):home.index("</footer>")]
        self.assertIn('rel="noopener">스레드 팔로우</a>', footer)
        self.assertNotIn("스레드", self.read(self.build(), "index.html").split("<footer")[1])

    def test_title_font_request_sends_no_referrer(self):
        from tools.sitegen.fonts import title_font_link
        self.assertEqual(title_font_link("가").count('referrerpolicy="no-referrer"'), 2)

    def test_long_words_wrap_and_short_screens_keep_room(self):
        css = Path("static/style.css").read_text(encoding="utf-8")
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertRegex(css, r"[.]panel [{][^}]*min-height: 5[0-9]{2}px")

    def test_ready_mark_is_set_right_before_the_first_panel_check(self):
        js = Path("static/site.js").read_text(encoding="utf-8")
        ready = js.index("classList.add('ready')")
        self.assertLess(js.index("var checkPanels"), ready)
        self.assertLess(ready, js.index("/* 영상:"))


class PolishTest(SiteTest):
    """다듬기(2026-11-26): 사용자가 병풍 미리 보기를 보고 '맞아, 다듬어'라고 한 뒤."""

    def setUp(self):
        self.css = re.sub(r"/[*].*?[*]/", "", Path("static/style.css").read_text(encoding="utf-8"), flags=re.S)
        self.js = Path("static/site.js").read_text(encoding="utf-8")

    def test_tester_button_says_which_game(self):
        from tools.sitegen.studio import follow_block
        self.assertIn('data-goatcounter-click="tester-tamna">탐라 테스트 알림 받기</a>', follow_block(B, TAMNA, "", True))
        home = self.read(self.build(full), "index.html")
        self.assertIn(">탐라 테스트 알림 받기</a>", home)
        self.assertNotIn(">테스트 알림 받기</a>", home)

    def test_late_images_wait_for_the_script_and_keep_a_noscript_copy(self):
        from tools.sitegen.studio import late_images
        html = late_images(f'<p><img class="x" src="{B}/static/art/a.webp" alt="" loading="late" width="1400" height="780">'
                           '<img src="b.webp" alt="" loading="lazy"></p>')
        self.assertIn(f'data-src="{B}/static/art/a.webp"', html)
        self.assertIn("viewBox='0 0 1400 780'", html)
        self.assertIn(f'<noscript><img class="x" src="{B}/static/art/a.webp" alt="" loading="lazy" width="1400" height="780"></noscript>', html)
        self.assertNotIn('loading="late"', html)
        self.assertEqual(html.count('<img src="b.webp" alt="" loading="lazy">'), 1)   # 다른 그림은 그대로
        outside = re.sub(r"<noscript>.*?</noscript>", "", html)
        self.assertNotIn(f' src="{B}/static/art/a.webp"', outside)
        self.assertIn(' src="data:image/svg+xml,', outside)
        # 크기를 적지 않은 그림(폭을 가득 채우는 그림)도 된다
        self.assertIn('data-src="c.webp"', late_images('<img src="c.webp" alt="" loading="late">'))

    def test_tamna_pictures_below_the_first_screen_are_late(self):
        page = self.read(self.build(), "games/tamna/index.html")
        outside = re.sub(r"<noscript>.*?</noscript>", "", page, flags=re.S)
        for pic in ("scene-hunt-1400.webp", "por-hunter-900.webp", "por-simbang-900.webp", "por-kkot-900.webp", "por-chasa-900.webp"):
            self.assertIn(f'data-src="{B}/static/art/{pic}"', outside, pic)
            self.assertNotIn(f' src="{B}/static/art/{pic}"', outside, pic)
            self.assertIn(f'<noscript><img src="{B}/static/art/{pic}"', page, pic)

    def test_no_page_keeps_the_late_mark(self):
        def pictured(root):
            full(root)
            self.games(root, lambda g: g["curvy"].update({"card_image": "static/art/cards/curvy-800.webp"}))
        out = self.build(pictured)
        for page in real_pages(out):
            self.assertNotIn('loading="late"', page.read_text(encoding="utf-8"), page)
        home = self.read(out, "index.html")
        first = between(home, 'id="p-tamna"', "</section>")
        self.assertNotIn("data-src", first.split("<video")[0])      # 첫 폭의 그림은 바로 받는다
        self.assertIn("data-src", between(home, 'id="p-curvy"', "</section>"))

    def test_site_js_brings_late_pictures_in_near_the_screen(self):
        self.assertIn("img[data-src]", self.js)
        self.assertIn("rootMargin", self.js)
        self.assertIn("html:not(.js) img[data-src]", self.css)

    def test_slides_can_carry_a_description(self):
        from build import build_site
        ok = "static/art/cards/iyagi-800.webp"
        pics = [{"src": "static/art/cards/curvy-800.webp", "alt": "첫 <장면>"}, ok]
        page = self.read(self.build(lambda root: self.games(root, lambda g: g["curvy"].update({"slides": pics}))), "games/curvy/index.html")
        block = between(page, '<div class="slides" data-slides>', "</figure>")
        self.assertIn(f'<img src="{B}/static/art/cards/curvy-800.webp" alt="첫 &lt;장면&gt;" loading="eager" class="on">', block)
        self.assertIn(f'<img src="{B}/{ok}" alt="" loading="lazy">', block)
        self.assertIn('<span class="slide-note" data-slide-note>첫 &lt;장면&gt;</span>', block)
        for bad in ([{"alt": "그림 없음"}, ok], [{"src": "static/art/none.webp"}, ok], [{"src": "static/art/cards/curvy-800.webp", "alt": 3}, ok]):
            root, out = self.make(lambda r, bad=bad: self.games(r, lambda g: g["curvy"].update({"slides": bad})))
            with self.assertRaises(ValueError, msg=str(bad)) as caught:
                build_site(root, out, base=B)
            self.assertIn("slides", str(caught.exception))

    def test_slides_without_motion_show_every_picture(self):
        # 스크립트가 없거나 움직임을 줄이면 겹쳐 바꾸지 않고 전부 차례로 보여 준다(본문에서 같은 그림을 뺐으므로).
        self.assertNotIn(".slides img + img { display: none", self.css)
        self.assertIn(".js .slides:not(.still)", self.css)
        self.assertIn("classList.add('still')", self.js)
        self.assertIn("data-slide-note", self.js)

    def test_real_game_text_does_not_repeat_its_slide_pictures(self):
        checked = 0
        for g in json.loads(Path("data/games.json").read_text(encoding="utf-8")):
            text = Path(f"content/games/{g['slug']}/index.md")
            for s in g.get("slides") or []:
                checked += 1
                self.assertNotIn(s if isinstance(s, str) else s["src"], text.read_text(encoding="utf-8") if text.exists() else "", g["slug"])
        self.assertGreater(checked, 0)

    def test_style_and_script_addresses_change_with_their_contents(self):
        """게시 직후 브라우저에 남은 옛 style.css·site.js가 새 HTML과 어긋나지 않게(늦게 받는 그림이 안 뜨는 일), 주소에 내용 지문을 붙인다."""
        def marks(html):
            return (re.search(r'href="/tamna-site/static/style[.]css[?]v=([0-9a-f]{8})"', html),
                    re.search(r'src="/tamna-site/static/site[.]js[?]v=([0-9a-f]{8})" defer', html))
        before = marks(self.read(self.build(), "index.html"))
        self.assertTrue(all(before))

        def touched(root):
            shutil.copytree("static", root / "static")
            with open(root / "static/style.css", "a", encoding="utf-8") as f:
                f.write("\n/* 바뀜 */\n")
        after = marks(self.read(self.build(touched), "about/index.html"))
        self.assertTrue(all(after))
        self.assertNotEqual(before[0].group(1), after[0].group(1))
        self.assertEqual(before[1].group(1), after[1].group(1))

    def test_log_nav_links_the_neighbouring_records(self):
        from tools.sitegen.studio import log_nav
        older, newer = log("2026-11-23"), log("2026-11-25")
        html = log_nav(B, older, newer)
        self.assertIn('<nav class="log-nav" aria-label="기록 넘기기">', html)
        self.assertIn(f'<a class="older" href="{B}/log/tamna/2026-11-23/"><small>이전 기록 · 11.23</small><span>제목 2026-11-23</span></a>', html)
        self.assertIn(f'<a class="newer" href="{B}/log/tamna/2026-11-25/"><small>다음 기록 · 11.25</small><span>제목 2026-11-25</span></a>', html)
        self.assertNotIn("newer", log_nav(B, older, None))
        self.assertNotIn("older", log_nav(B, None, newer))
        self.assertEqual(log_nav(B, None, None), "")

    def test_log_article_leads_to_neighbours_of_the_same_game_and_back_to_the_game(self):
        out = self.build()
        first, last = self.read(out, "log/tamna/2026-11-06/index.html"), self.read(out, "log/tamna/2026-11-07/index.html")
        self.assertIn(f'<a class="newer" href="{B}/log/tamna/2026-11-07/">', first)
        self.assertNotIn('class="older"', first)
        self.assertIn(f'<a class="older" href="{B}/log/tamna/2026-11-06/">', last)
        self.assertNotIn('class="newer"', last)
        self.assertIn(f'<a class="more" href="{B}/games/tamna/">탐라(가제) 게임 페이지</a>', last)
        # 다른 게임의 기록으로는 넘어가지 않는다. 기록이 하나뿐이면 넘김 줄이 없다.
        only = self.read(out, "log/curvy/2026-11-07/index.html")
        self.assertNotIn("log-nav", only)
        self.assertIn(f'<a class="more" href="{B}/games/curvy/">curvy(가칭) 게임 페이지</a>', only)

    def test_pages_fade_into_each_other_where_the_browser_can(self):
        self.assertIn("@view-transition { navigation: auto; }", self.css)

    def test_korean_text_breaks_between_words(self):
        self.assertRegex(self.css, r"body [{][^}]*word-break: keep-all")
        self.assertRegex(self.css, r"body [{][^}]*overflow-wrap: break-word")

    def test_dots_step_aside_on_paper(self):
        self.assertRegex(self.css, r"[.]js [.]site-header[.]solid [.]dots [{][^}]*opacity: 0")


if __name__ == "__main__":
    unittest.main()

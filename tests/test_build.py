import re
import tempfile
import unittest
from pathlib import Path

from build import build_site

FX = Path("tests/fixtures/site")


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        build_site(FX, self.out, base="/tamna-site")

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_writes_core_files(self):
        for p in [
            "index.html",
            "log/index.html",
            "log/tamna/2026-11-07/index.html",
            "log/tamna/index.html",
            "log/curvy/2026-11-07/index.html",
            "games/index.html",
            "games/tamna/index.html",
            "games/curvy/index.html",
            "monthly/index.html",
            "monthly/2026-10/index.html",
            "about/index.html",
            "feed.xml",
            ".nojekyll",
            "static/style.css",
            "media/log/2026-11-07-hunter-sweep.gif",
        ]:
            self.assertTrue((self.out / p).exists(), p)

    def test_index_shows_now_items_from_latest_log(self):
        # 영감 문장, 첫 화면 그림은 탐라 페이지에 있다. '다음에 손댈 것' 칸은 2026-11-26 리뉴얼에서
        # '지금 어디까지'(최근 기록의 한 일)로 바뀌었다. 다음에 손댈 것은 기록 글에 그대로 있다.
        html = (self.out / "games/tamna/index.html").read_text(encoding="utf-8")
        self.assertIn("사례 7개 범위를 조사했다.", html)
        self.assertNotIn("사이트 생성기 뼈대.", html)
        self.assertIn("사이트 생성기 뼈대.", (self.out / "log/tamna/2026-11-07/index.html").read_text(encoding="utf-8"))
        self.assertIn("1990년대 후반 한국 2D 온라인 RPG들에서 영감을 받았고", html)
        # 2026-11-26 대개편: 큰 첫 화면 그림(hero_media) 대신 게임의 병풍 폭이 맨 위에 온다.
        self.assertIn('<h1 class="vt" aria-label="탐라(가제)">', html)

    def test_page_tokens_are_replaced(self):
        about = (self.out / "about/index.html").read_text(encoding="utf-8")
        self.assertIn("<td>코드</td>", about)
        for f in self.out.rglob("*.html"):
            self.assertNotIn("{{", f.read_text(encoding="utf-8"), str(f))

    def test_internal_links_resolve_with_base_path(self):
        for f in self.out.rglob("*.html"):
            for href in re.findall(r'(?:href|src)="(/tamna-site/[^"#]+)"', f.read_text(encoding="utf-8")):
                target = self.out / href[len("/tamna-site/") :].split("?")[0]   # ?v=는 style.css·site.js의 내용 지문
                self.assertTrue(target.exists() or (target / "index.html").exists(), f"{f}: {href}")

    def test_korean_roundtrip_utf8(self):
        self.assertIn("탐라(가제)", (self.out / "index.html").read_bytes().decode("utf-8"))

    def test_build_refuses_out_that_is_root_or_contains_root(self):
        with self.assertRaises(ValueError):
            build_site(FX, FX, base="")
        with self.assertRaises(ValueError):
            build_site(FX, FX.parent, base="")

    def test_build_refuses_existing_non_output_folder(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "keep.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_site(FX, Path(d), base="")

    def test_feed_lists_logs_and_monthly(self):
        xml = (self.out / "feed.xml").read_text(encoding="utf-8")
        self.assertIn("https://example.github.io/tamna-site/log/tamna/2026-11-07/", xml)
        self.assertIn("https://example.github.io/tamna-site/monthly/2026-10/", xml)


if __name__ == "__main__":
    unittest.main()


class HeroMobileTest(unittest.TestCase):
    def test_hero_uses_mobile_source_when_configured(self):
        import json, shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"; shutil.copytree(FX, root)
            games = json.loads((root / "data" / "games.json").read_text(encoding="utf-8"))
            games[0]["hero_media"] = "static/art/key-hero-2400.webp"; games[0]["hero_media_mobile"] = "static/art/key-hero-m-1000.webp"
            (root / "data" / "games.json").write_text(json.dumps(games, ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "out"; build_site(root, out, base="/tamna-site")
            html = (out / "games/tamna/index.html").read_text(encoding="utf-8")
            # 2026-11-26 대개편: 게임 페이지 맨 위의 폭. 휴대폰은 세로 화면용 그림, 넓은 화면(901px 이상)은 가로 그림.
            self.assertIn('<picture><source media="(min-width: 901px)" srcset="/tamna-site/static/art/key-hero-2400.webp">'
                          '<img class="panel-pic" src="/tamna-site/static/art/key-hero-m-1000.webp" alt="" loading="eager" fetchpriority="high"></picture>', html)
            self.assertIn('loading="eager"', html)


class IconTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name)
        build_site(FX, self.out, base="/tamna-site")

    def tearDown(self):
        self.tmp.cleanup()

    def test_pages_sections_nav_and_hero_carry_minhwa_icons_and_logo(self):
        about = (self.out / "about/index.html").read_text(encoding="utf-8")
        # 2026-11-26 대개편: 제목 옆 민화 아이콘과 탐라 로고 그림은 빼고, 제목은 바탕체 글자로 쓴다.
        self.assertNotIn('class="ico"', about[about.index("<main>"):about.index("</main>")].split("</h1>")[0])
        tamna = (self.out / "games/tamna/index.html").read_text(encoding="utf-8")
        self.assertIn('<h1 class="vt" aria-label="탐라(가제)">', tamna)
        index = (self.out / "index.html").read_text(encoding="utf-8")
        # 머리 로고는 스튜디오 글자 로고, 메뉴는 글자만.
        self.assertIn('<a class="brand" href="/tamna-site/"><img class="brand-logo" src="/tamna-site/static/brand/logo-horizontal.svg"', index)
        self.assertIn('<a href="/tamna-site/games/">게임</a>', index)
        self.assertIn('<a href="/tamna-site/log/">개발 기록</a>', index)
        footer = index[index.index("<footer"):index.index("</footer>")]
        self.assertIn('<a href="/tamna-site/monthly/">이달의 정리</a>', footer)
        log_index = (self.out / "log/index.html").read_text(encoding="utf-8")
        self.assertIn("<h1>개발 기록</h1>", log_index)


class SharePreviewAndHomeTest(unittest.TestCase):
    """2026-11-13 1단계: 위 메뉴 5곳, 글마다 공유 미리보기, 홈의 실제 게임 화면."""

    def build(self, edit=None, games_edit=None):
        import json, shutil
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "root"; shutil.copytree(FX, root)
        if edit:
            site = json.loads((root / "data/site.json").read_text(encoding="utf-8")); edit(site)
            (root / "data/site.json").write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")
        if games_edit:
            games = json.loads((root / "data/games.json").read_text(encoding="utf-8")); games_edit(games)
            (root / "data/games.json").write_text(json.dumps(games, ensure_ascii=False), encoding="utf-8")
        out = Path(tmp.name) / "out"; build_site(root, out, base="/tamna-site")
        return out

    def test_log_pages_carry_their_own_description_url_and_image(self):
        out = self.build()
        html = (out / "log/tamna/2026-11-07/index.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="description" content="사례 7개 범위를 조사했다.">', html)
        self.assertIn('<meta property="og:type" content="article">', html)
        self.assertIn('<link rel="canonical" href="https://example.github.io/tamna-site/log/tamna/2026-11-07/">', html)
        self.assertIn('<meta property="og:url" content="https://example.github.io/tamna-site/log/tamna/2026-11-07/">', html)
        self.assertIn('<meta property="article:published_time" content="2026-11-07">', html)
        import json as _json
        ld = _json.loads(html.split('<script type="application/ld+json">')[1].split("</script>")[0])
        self.assertEqual((ld["@type"], ld["datePublished"], ld["url"]), ("Article", "2026-11-07", "https://example.github.io/tamna-site/log/tamna/2026-11-07/"))
        # GIF는 수 MB라 미리보기 그림으로 쓰지 않는다.
        self.assertIn('<meta property="og:image" content="https://example.github.io/tamna-site/static/art/og-studio.jpg">', html)

    def test_pages_without_media_fall_back_to_site_image_and_first_paragraph(self):
        out = self.build()
        html = (out / "games/tamna/index.html").read_text(encoding="utf-8")
        self.assertIn('content="https://example.github.io/tamna-site/static/art/og.jpg"', html)
        # 게임 페이지 설명은 games.json의 한 줄 소개
        self.assertIn('<meta name="description" content="제주 신화 섬에서 네 직업이 파티로 사냥하는 온라인 RPG, 혼자 AI와 만드는 중">', html)
        about = (out / "about/index.html").read_text(encoding="utf-8")
        self.assertIn('content="https://example.github.io/tamna-site/static/art/og-studio.jpg"', about)

    def test_header_follow_button_only_when_threads_url_set(self):
        self.assertNotIn('class="follow"', (self.build() / "index.html").read_text(encoding="utf-8"))
        out = self.build(lambda s: s.update(threads_url="https://www.threads.com/@x"))
        self.assertIn('<a class="follow" href="https://www.threads.com/@x" rel="noopener">스레드 팔로우</a>', (out / "index.html").read_text(encoding="utf-8"))

    def test_home_play_clip_is_muted_looping_and_labelled(self):
        self.assertNotIn('class="play"', (self.build() / "games/tamna/index.html").read_text(encoding="utf-8"))
        out = self.build(games_edit=lambda g: g[0].update(play_media="media/clip.mp4", play_label="실제 게임 화면(개발 중)"))
        html = (out / "games/tamna/index.html").read_text(encoding="utf-8")
        # 2026-11-26 리뉴얼: 페이지를 열 때 영상을 받지 않고(preload none), 화면에 들어오면 site.js가 재생한다.
        self.assertIn('<video class="play-video" src="/tamna-site/media/clip.mp4" muted loop playsinline preload="none" controls', html)
        self.assertIn("<figcaption>실제 게임 화면(개발 중)</figcaption>", html)

    def test_no_page_carries_the_old_art_band(self):
        # 2026-11-26 대개편: 하위 페이지 머리의 탐라 그림 띠(page-band)를 없앴다. 탐라 그림은 탐라 페이지 안에만 있다.
        out = self.build()
        for rel in ("index.html", "about/index.html", "log/curvy/2026-11-07/index.html", "log/tamna/2026-11-07/index.html"):
            html = (out / rel).read_text(encoding="utf-8")
            self.assertNotIn("page-band", html, rel)
            self.assertNotIn("background-image", html, rel)
        game = (out / "games/tamna/index.html").read_text(encoding="utf-8")
        src = game.split('static/art/scene-hunt-1400.webp')[0].rsplit('src="/tamna-site/', 1)[1] + "static/art/scene-hunt-1400.webp"
        self.assertTrue((out / src).exists(), src)

    def test_analytics_tag_only_with_a_valid_code(self):
        # 집계 스크립트가 없어야 한다. 카드의 data-goatcounter-click 속성은 스크립트 없이는 아무 일도 하지 않는다.
        self.assertNotIn("gc.zgo.at", (self.build() / "index.html").read_text(encoding="utf-8"))
        out = self.build(lambda s: s.update(goatcounter_code="tamna"))
        self.assertIn('<script data-goatcounter="https://tamna.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>', (out / "games/tamna/index.html").read_text(encoding="utf-8"))
        bad = self.build(lambda s: s.update(goatcounter_code='x" onload="alert(1)'))
        self.assertNotIn("gc.zgo.at", (bad / "index.html").read_text(encoding="utf-8"))
        self.assertNotIn("alert(1)", (bad / "index.html").read_text(encoding="utf-8"))

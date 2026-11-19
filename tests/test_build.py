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
        # '다음에 손댈 것'과 영감 문장, 첫 화면 그림은 이제 탐라 페이지에 있다.
        html = (self.out / "games/tamna/index.html").read_text(encoding="utf-8")
        self.assertIn("사이트 생성기 뼈대.", html)
        self.assertIn("1990년대 후반 한국 2D 온라인 RPG들에서 영감을 받았고", html)
        self.assertIn("실제 플레이 화면(개발 중)", html)

    def test_page_tokens_are_replaced(self):
        about = (self.out / "about/index.html").read_text(encoding="utf-8")
        self.assertIn("<td>코드</td>", about)
        for f in self.out.rglob("*.html"):
            self.assertNotIn("{{", f.read_text(encoding="utf-8"), str(f))

    def test_internal_links_resolve_with_base_path(self):
        for f in self.out.rglob("*.html"):
            for href in re.findall(r'(?:href|src)="(/tamna-site/[^"#]+)"', f.read_text(encoding="utf-8")):
                target = self.out / href[len("/tamna-site/") :]
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
            self.assertIn('<picture><source media="(max-width: 720px)" srcset="/tamna-site/static/art/key-hero-m-1000.webp">', html)
            self.assertIn('src="/tamna-site/static/art/key-hero-2400.webp"', html)
            self.assertIn('loading="eager"', html)


class IconTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name)
        build_site(FX, self.out, base="/tamna-site")

    def tearDown(self):
        self.tmp.cleanup()

    def test_pages_sections_nav_and_hero_carry_minhwa_icons_and_logo(self):
        about = (self.out / "about/index.html").read_text(encoding="utf-8")
        self.assertIn('<h1><img class="ico" src="/tamna-site/static/icons/hareubang.webp" alt="">', about)
        tamna = (self.out / "games/tamna/index.html").read_text(encoding="utf-8")
        self.assertIn('<p class="eyebrow"><img class="ico" src="/tamna-site/static/icons/sun.webp" alt="">지금 게임 화면', tamna)
        self.assertIn('<img class="logo-img" src="/tamna-site/static/art/logo-cream-900.webp" alt="탐라"', tamna)
        index = (self.out / "index.html").read_text(encoding="utf-8")
        # 머리 로고는 스튜디오 글자 로고, 메뉴는 글자만.
        self.assertIn('<a class="brand" href="/tamna-site/"><span class="brand-text">', index)
        self.assertIn('<a href="/tamna-site/games/">게임</a>', index)
        self.assertIn('<a href="/tamna-site/log/">개발 기록</a>', index)
        self.assertIn('<p class="footer-nav"><a href="/tamna-site/monthly/">이달의 정리</a></p>', index)
        log_index = (self.out / "log/index.html").read_text(encoding="utf-8")
        self.assertIn('<h1><img class="ico" src="/tamna-site/static/icons/brush.webp" alt="">개발 기록</h1>', log_index)


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
        self.assertIn('<meta property="og:image" content="https://example.github.io/tamna-site/static/art/og.jpg">', html)

    def test_pages_without_media_fall_back_to_site_image_and_first_paragraph(self):
        out = self.build()
        html = (out / "games/tamna/index.html").read_text(encoding="utf-8")
        self.assertIn('content="https://example.github.io/tamna-site/static/art/og.jpg"', html)
        # 게임 페이지 설명은 games.json의 한 줄 소개
        self.assertIn('<meta name="description" content="제주 신화 섬에서 네 직업이 파티로 사냥하는 온라인 RPG, 혼자 AI와 만드는 중">', html)
        about = (out / "about/index.html").read_text(encoding="utf-8")
        self.assertIn('content="https://example.github.io/tamna-site/static/art/og.jpg"', about)

    def test_header_follow_button_only_when_threads_url_set(self):
        self.assertNotIn('class="follow"', (self.build() / "index.html").read_text(encoding="utf-8"))
        out = self.build(lambda s: s.update(threads_url="https://www.threads.com/@x"))
        self.assertIn('<a class="follow" href="https://www.threads.com/@x" rel="noopener">스레드 팔로우</a>', (out / "index.html").read_text(encoding="utf-8"))

    def test_home_play_clip_is_muted_looping_and_labelled(self):
        self.assertNotIn('class="play"', (self.build() / "games/tamna/index.html").read_text(encoding="utf-8"))
        out = self.build(games_edit=lambda g: g[0].update(play_media="media/clip.mp4", play_label="실제 게임 화면(개발 중)"))
        html = (out / "games/tamna/index.html").read_text(encoding="utf-8")
        self.assertIn('<video class="play-video" src="/tamna-site/media/clip.mp4" autoplay muted loop playsinline', html)
        self.assertIn("<figcaption>실제 게임 화면(개발 중)</figcaption>", html)

    def test_sub_pages_get_an_art_band_and_home_does_not(self):
        out = self.build()
        self.assertNotIn('class="page-band"', (out / "index.html").read_text(encoding="utf-8"))
        # 스튜디오 공통 페이지와 다른 게임 기록에는 탐라 그림 띠를 두지 않는다.
        self.assertNotIn('class="page-band"', (out / "about/index.html").read_text(encoding="utf-8"))
        self.assertNotIn('class="page-band"', (out / "log/curvy/2026-11-07/index.html").read_text(encoding="utf-8"))
        game = (out / "games/tamna/index.html").read_text(encoding="utf-8")
        self.assertIn("static/art/scene-hunt-1400.webp", game)
        log = (out / "log/tamna/2026-11-07/index.html").read_text(encoding="utf-8")
        self.assertIn("static/art/key-sea-1400.webp", log)
        self.assertIn('aria-hidden="true"', log)
        # 그림 띠가 가리키는 파일이 실제로 있어야 한다.
        for html in (game, log):
            src = html.split("background-image:url('/tamna-site/")[1].split("'")[0]
            self.assertTrue((out / src).exists(), src)

    def test_analytics_tag_only_with_a_valid_code(self):
        self.assertNotIn("goatcounter", (self.build() / "index.html").read_text(encoding="utf-8"))
        out = self.build(lambda s: s.update(goatcounter_code="tamna"))
        self.assertIn('<script data-goatcounter="https://tamna.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>', (out / "games/tamna/index.html").read_text(encoding="utf-8"))
        bad = self.build(lambda s: s.update(goatcounter_code='x" onload="alert(1)'))
        self.assertNotIn("goatcounter", (bad / "index.html").read_text(encoding="utf-8"))

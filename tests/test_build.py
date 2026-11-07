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
            "log/2026-11-07/index.html",
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
        html = (self.out / "index.html").read_text(encoding="utf-8")
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
        self.assertIn("https://example.github.io/tamna-site/log/2026-11-07/", xml)
        self.assertIn("https://example.github.io/tamna-site/monthly/2026-10/", xml)


if __name__ == "__main__":
    unittest.main()


class HeroMobileTest(unittest.TestCase):
    def test_hero_uses_mobile_source_when_configured(self):
        import json, shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"; shutil.copytree(FX, root)
            site = json.loads((root / "data" / "site.json").read_text(encoding="utf-8"))
            site["hero_media"] = "static/art/key-hero-2400.webp"; site["hero_media_mobile"] = "static/art/key-hero-m-1000.webp"
            (root / "data" / "site.json").write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "out"; build_site(root, out, base="/tamna-site")
            html = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn('<picture><source media="(max-width: 720px)" srcset="/tamna-site/static/art/key-hero-m-1000.webp">', html)
            self.assertIn('src="/tamna-site/static/art/key-hero-2400.webp"', html)
            self.assertIn('loading="eager"', html)

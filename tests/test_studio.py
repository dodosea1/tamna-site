"""스튜디오 개편(2026-11-20, D-40~42): 게임별 페이지·기록, 바깥 카드, 옛 주소 넘김 쪽."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from build import build_site

FX = Path("tests/fixtures/site")


class StudioTest(unittest.TestCase):
    def make(self, edit=None):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "root"; shutil.copytree(FX, root)
        if edit:
            edit(root)
        out = Path(tmp.name) / "out"
        return root, out

    def build(self, edit=None):
        root, out = self.make(edit)
        build_site(root, out, base="/tamna-site")
        return out

    def read(self, out, rel):
        return (out / rel).read_text(encoding="utf-8")

    def test_old_log_and_page_addresses_forward_to_new_ones(self):
        out = self.build()
        stub = self.read(out, "log/2026-11-07/index.html")
        self.assertIn('<meta http-equiv="refresh" content="0; url=/tamna-site/log/tamna/2026-11-07/">', stub)
        self.assertIn('<link rel="canonical" href="https://example.github.io/tamna-site/log/tamna/2026-11-07/">', stub)
        self.assertIn('<meta name="robots" content="noindex">', stub)
        self.assertIn("/tamna-site/games/tamna/", self.read(out, "game/index.html"))
        sitemap = self.read(out, "sitemap.xml")
        self.assertNotIn("/log/2026-11-07/<", sitemap)
        self.assertNotIn("/game/<", sitemap)
        self.assertIn("/log/tamna/2026-11-07/", sitemap)

    def test_game_folder_logs_get_their_own_list_and_label(self):
        out = self.build()
        self.assertIn("슬라임 첫 그림", self.read(out, "log/curvy/index.html"))
        self.assertNotIn("슬라임 첫 그림", self.read(out, "log/tamna/index.html"))
        all_logs = self.read(out, "log/index.html")
        self.assertIn('<span class="g">curvy(가칭)</span>', all_logs)
        self.assertIn('<a class="" href="/tamna-site/log/curvy/">curvy(가칭)</a>', all_logs)
        # 같은 날짜라도 게임마다 다른 주소
        self.assertIn("curvy(가칭)", self.read(out, "log/curvy/2026-11-07/index.html"))

    def test_external_card_links_out_and_gets_no_page(self):
        out = self.build()
        home = self.read(out, "index.html")
        self.assertIn('<a class="game-card" href="https://gohyang.town" rel="noopener">', home)
        self.assertFalse((out / "games/gohyang").exists())
        self.assertIn('<a class="game-card" href="/tamna-site/games/curvy/">', home)
        # 그림이 없는 게임은 지어내지 않고 자리만
        self.assertIn("그림 준비 중", home)

    def test_home_is_studio_and_brand_is_text_logo(self):
        out = self.build()
        home = self.read(out, "index.html")
        self.assertIn('class="wrap studio-hero"', home)
        self.assertIn('<span class="brand-text">', home)
        self.assertNotIn("logo-cream-900", home)  # 탐라 로고 그림은 탐라 페이지에만

    def test_same_day_in_old_place_and_game_folder_is_refused(self):
        def dup(root):
            (root / "content/log/tamna").mkdir()
            shutil.copy(root / "content/log/2026-11-07.md", root / "content/log/tamna/2026-11-07.md")
        root, out = self.make(dup)
        with self.assertRaises(ValueError):
            build_site(root, out, base="")

    def test_log_folder_for_unknown_game_is_refused(self):
        def unknown(root):
            (root / "content/log/nope").mkdir()
            shutil.copy(root / "content/log/curvy/2026-11-07.md", root / "content/log/nope/2026-11-07.md")
        root, out = self.make(unknown)
        with self.assertRaises(ValueError):
            build_site(root, out, base="")

    def test_redirect_to_missing_page_or_over_real_page_is_refused(self):
        for table in ({"old/": "games/none/"}, {"about/": "games/tamna/"}):
            def bad(root, table=table):
                (root / "data/redirects.json").write_text(json.dumps(table), encoding="utf-8")
            root, out = self.make(bad)
            with self.assertRaises(ValueError, msg=str(table)):
                build_site(root, out, base="")

    def test_unknown_status_is_refused(self):
        def bad(root):
            games = json.loads((root / "data/games.json").read_text(encoding="utf-8"))
            games[1]["status"] = "곧"
            (root / "data/games.json").write_text(json.dumps(games, ensure_ascii=False), encoding="utf-8")
        root, out = self.make(bad)
        with self.assertRaises(ValueError):
            build_site(root, out, base="")


class RealSiteRedirectTest(unittest.TestCase):
    """실제 사이트: 옛 주소(스레드·검색·후원 QR에 걸린 것)가 하나도 404가 되지 않는다."""

    def test_every_old_address_still_answers(self):
        root = Path(".")
        old_pages = ["game/", "together/", "roadmap/", "support/", "feedback/", "about/", "help-wanted/", "privacy/", "log/", "monthly/", ""]
        old_logs = [f"log/{p.stem}/" for p in (root / "content/log").glob("*.md")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            build_site(root, out, base="/tamna-site")
            for rel in old_pages + old_logs:
                self.assertTrue((out / rel / "index.html").exists(), rel)
            self.assertTrue(old_logs)


if __name__ == "__main__":
    unittest.main()

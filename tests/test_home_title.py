"""첫 화면 제목이 검색 결과에 '홈'이 아니라 무엇을 하는 사이트인지 보이게."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from build import build_site

FX = Path("tests/fixtures/site")


class HomeTitleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "site"
        shutil.copytree(FX, self.root)
        self.out = Path(self.tmp.name) / "out"

    def build(self, home_title):
        path = self.root / "data" / "site.json"
        site = json.loads(path.read_text(encoding="utf-8"))
        if home_title is not None:
            site["home_title"] = home_title
        path.write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")
        build_site(self.root, self.out, base="/tamna-site")
        return site["title"]

    def page(self, rel):
        return (self.out / rel).read_text(encoding="utf-8").split("</head>")[0]

    def test_home_uses_home_title(self):
        self.build("탐라 · 제주 신화 RPG 개발 기록")
        head = self.page("index.html")
        self.assertIn("<title>탐라 · 제주 신화 RPG 개발 기록</title>", head)
        self.assertIn('<meta property="og:title" content="탐라 · 제주 신화 RPG 개발 기록">', head)
        self.assertNotIn("홈 ·", head)

    def test_without_setting_home_falls_back_to_site_title(self):
        site_title = self.build(None)
        self.assertIn(f"<title>{site_title}</title>", self.page("index.html"))

    def test_other_pages_keep_page_then_site_title(self):
        site_title = self.build("탐라 · 제주 신화 RPG 개발 기록")
        log = next((self.out / "log").glob("*/index.html"))
        self.assertIn(f" · {site_title}</title>", log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

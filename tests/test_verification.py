"""검색 등록 소유 확인 태그(구글·네이버)가 페이지 머리에 들어가는지."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from build import build_site

FX = Path("tests/fixtures/site")


class VerificationMetaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "site"
        shutil.copytree(FX, self.root)
        self.out = Path(self.tmp.name) / "out"

    def build(self, verification):
        path = self.root / "data" / "site.json"
        site = json.loads(path.read_text(encoding="utf-8"))
        if verification is not None:
            site["site_verification"] = verification
        path.write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")
        build_site(self.root, self.out, base="/tamna-site")
        return (self.out / "index.html").read_text(encoding="utf-8")

    def head(self, html):
        return html.split("</head>")[0]

    def test_no_setting_no_tag(self):
        self.assertNotIn("site-verification", self.build(None))

    def test_google_and_naver_tags_in_head(self):
        head = self.head(self.build({"google-site-verification": "Hb_USD46-x", "naver-site-verification": "abc123"}))
        self.assertIn('<meta name="google-site-verification" content="Hb_USD46-x">', head)
        self.assertIn('<meta name="naver-site-verification" content="abc123">', head)

    def test_unknown_name_and_odd_value_are_dropped(self):
        head = self.head(self.build({"evil": "x", "google-site-verification": '"><script>'}))
        self.assertNotIn("evil", head)
        self.assertNotIn("<script>", head)
        self.assertNotIn("site-verification", head)


if __name__ == "__main__":
    unittest.main()

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from build import build_site
from tools.sitegen.donate import donate_block
from tools.sitegen.tables import support_section

FX = Path("tests/fixtures/site")
URL = "https://toss.me/example"
DATA = {"cap_krw": 100, "notice": ["공통"], "notice_ctee": ["크티 안내"], "notice_direct": ["송금 안내"], "ledger": [], "thanks": []}


class DonateBlockTest(unittest.TestCase):
    def test_direct_link_shows_qr_and_button_for_phone_viewers(self):
        html = donate_block({"donate_url": URL, "donate_app": "토스", "ctee_url": "https://ctee.kr/x"})
        self.assertIn("<svg", html)
        self.assertIn(f'href="{URL}"', html)
        self.assertIn("토스로 보내기", html)
        self.assertNotIn("ctee.kr", html)

    def test_without_direct_link_falls_back_to_ctee(self):
        html = donate_block({"donate_url": "", "ctee_url": "https://ctee.kr/x"})
        self.assertIn('href="https://ctee.kr/x"', html)
        self.assertNotIn("<svg", html)

    def test_without_any_link_says_not_ready(self):
        self.assertIn("준비 중", donate_block({}))

    def test_non_https_link_is_refused(self):
        with self.assertRaises(ValueError):
            donate_block({"donate_url": "javascript:alert(1)", "donate_app": "토스"})

    def test_block_has_no_blank_line_so_markdown_keeps_it_raw(self):
        html = donate_block({"donate_url": URL, "donate_app": "토스"})
        self.assertNotIn("\n\n", html)


class SupportNoticeTest(unittest.TestCase):
    def test_direct_mode_uses_direct_notices_only(self):
        html = support_section(DATA, direct=True)
        self.assertIn("공통", html)
        self.assertIn("송금 안내", html)
        self.assertNotIn("크티 안내", html)

    def test_default_mode_uses_ctee_notices_only(self):
        html = support_section(DATA)
        self.assertIn("크티 안내", html)
        self.assertNotIn("송금 안내", html)


class BuiltPageTest(unittest.TestCase):
    def _build(self, **site_changes):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "site"
        shutil.copytree(FX, root)
        (root / "content/pages/support.md").write_text(
            "---\ntitle: 후원\norder: 7\n---\n소개\n\n{{donate}}\n\n{{support_section}}\n", encoding="utf-8")
        path = root / "data/site.json"
        site = json.loads(path.read_text(encoding="utf-8"))
        site.update(site_changes)
        path.write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")
        out = Path(tmp.name) / "out"
        build_site(root, out, base="/tamna-site")
        return (out / "support/index.html").read_text(encoding="utf-8")

    def test_page_with_direct_link_has_qr_outside_paragraph(self):
        html = self._build(donate_url=URL, donate_app="토스")
        self.assertIn("<svg", html)
        self.assertNotIn("<p><div", html)

    def test_page_without_direct_link_has_no_qr(self):
        self.assertNotIn("<svg", self._build(donate_url=""))


if __name__ == "__main__":
    unittest.main()

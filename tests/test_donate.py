import json
import shutil
import tempfile
import unittest
from pathlib import Path

from build import build_site
from tools.sitegen.donate import donate_block, is_direct, shows_ctee
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


class AccountBlockTest(unittest.TestCase):
    ACCOUNT = {"donate_bank": "토스뱅크", "donate_account": "1002-2516-1071", "ctee_url": "https://ctee.kr/x"}

    def test_account_shows_bank_number_and_copy_button_without_ctee(self):
        html = donate_block(self.ACCOUNT)
        self.assertIn("토스뱅크", html)
        self.assertIn("1002-2516-1071", html)
        self.assertIn('data-copy="100225161071"', html)
        self.assertNotIn("ctee.kr", html)
        self.assertNotIn("<svg", html)

    def test_account_counts_as_direct_mode(self):
        self.assertTrue(is_direct(self.ACCOUNT))

    def test_account_and_link_show_both(self):
        html = donate_block({**self.ACCOUNT, "donate_url": URL, "donate_app": "카카오페이"})
        self.assertIn("<svg", html)
        self.assertIn("1002-2516-1071", html)
        self.assertIn("카카오페이로 보내기", html)

    def test_account_with_other_characters_is_refused(self):
        with self.assertRaises(ValueError):
            donate_block({"donate_bank": "토스뱅크", "donate_account": "<script>"})

    def test_account_needs_bank_name(self):
        with self.assertRaises(ValueError):
            donate_block({"donate_account": "1002-2516-1071"})

    def test_block_stays_on_one_paragraph_for_markdown(self):
        self.assertNotIn(chr(10)*2, donate_block(self.ACCOUNT))


class CteeAlongsideTest(unittest.TestCase):
    SITE = {"donate_bank": "토스뱅크", "donate_account": "1002-2516-1071", "ctee_url": "https://ctee.kr/x"}

    def test_ctee_button_stays_hidden_until_registration_is_marked_done(self):
        self.assertNotIn("ctee.kr", donate_block({**self.SITE, "ctee_ready": False}))
        self.assertFalse(shows_ctee({**self.SITE, "ctee_ready": False}))

    def test_ctee_button_joins_account_when_ready(self):
        html = donate_block({**self.SITE, "ctee_ready": True})
        self.assertIn("1002-2516-1071", html)
        self.assertIn('href="https://ctee.kr/x"', html)
        self.assertTrue(shows_ctee({**self.SITE, "ctee_ready": True}))

    def test_ready_flag_without_url_shows_no_button(self):
        site = {"donate_bank": "토스뱅크", "donate_account": "1002-2516-1071", "ctee_ready": True}
        self.assertNotIn("크티", donate_block(site))
        self.assertFalse(shows_ctee(site))

    def test_ctee_only_site_keeps_showing_button(self):
        self.assertTrue(shows_ctee({"ctee_url": "https://ctee.kr/x"}))

    def test_both_notices_appear_when_both_methods_show(self):
        html = support_section(DATA, direct=True, ctee=True)
        self.assertIn("송금 안내", html)
        self.assertIn("크티 안내", html)


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

    def test_page_with_account_has_copy_button_and_script(self):
        html = self._build(donate_bank="토스뱅크", donate_account="1002-2516-1071")
        self.assertIn('class="button copy"', html)
        self.assertIn("navigator.clipboard", html)
        self.assertNotIn("<p><div", html)

    def test_page_without_direct_link_has_no_qr(self):
        self.assertNotIn("<svg", self._build(donate_url=""))


if __name__ == "__main__":
    unittest.main()

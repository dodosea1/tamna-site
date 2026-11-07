import tempfile
import unittest
from pathlib import Path

from tools.lint_public import load_terms, main, scan_text, scan_tree


class LintTest(unittest.TestCase):
    def test_detects_term_case_insensitive(self):
        self.assertEqual(scan_text("이 글은 SecretGame 얘기", ["secretgame"]), ["term:1"])

    def test_detects_windows_path_ip_email_phone(self):
        sample = "C:" + "\\Users\\x " + "192.168" + ".0.2:7777 " + "a@" + "b.co " + "010-1234" + "-5678"
        hits = scan_text(sample, [])
        self.assertEqual(set(hits), {"windows-path", "ip-port", "email", "phone"})

    def test_clean_text_has_no_hits(self):
        self.assertEqual(scan_text("2026-11-07에 사례 7개 범위를 조사했다. 가격은 10,000원.", ["secretgame"]), [])

    def test_scans_data_templates_and_media_names(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            for sub in ("data", "media", "templates", "content"):
                (r / sub).mkdir()
            (r / "data/site.json").write_text('{"a": "SecretGame"}', encoding="utf-8")
            (r / "media/secretgame-clip.gif").write_bytes(b"x")
            (r / "templates/base.html").write_text("<p>" + "010-1234" + "-5678</p>", encoding="utf-8")
            rules = {rule for _, _, rule in scan_tree(r, ["secretgame"])}
            self.assertEqual(rules, {"term:1", "phone"})

    def test_scan_tree_covers_tracked_and_untracked_but_not_ignored(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            subprocess.run(["git", "init", "-q", str(r)], check=True)
            (r / ".gitignore").write_text("_site/\n", encoding="utf-8")
            (r / "tools").mkdir()
            (r / "content").mkdir()
            (r / "_site").mkdir()
            (r / "tools/x.py").write_text("PHONE = '" + "010-1234" + "-5678'\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(r), "add", "tools/x.py"], check=True)
            (r / "content/new.md").write_text("secretgame", encoding="utf-8")
            (r / "_site/index.html").write_text("secretgame", encoding="utf-8")
            found = {(path, rule) for path, _, rule in scan_tree(r, ["secretgame"])}
            self.assertIn(("tools/x.py", "phone"), found)
            self.assertIn(("content/new.md", "term:1"), found)
            self.assertFalse(any(path.startswith("_site/") for path, _ in found))

    def test_terms_file_inside_root_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d, "terms.txt")
            t.write_text("secretgame\n", encoding="utf-8")
            Path(d, "content").mkdir()
            Path(d, "content/x.md").write_text("깨끗", encoding="utf-8")
            self.assertEqual(main(["--root", d, "--terms", str(t)]), 0)

    def test_load_terms_skips_comments_and_blank(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d, "terms.txt")
            t.write_text("# 주석\n\nsecretgame\n  Other Name \n", encoding="utf-8")
            self.assertEqual(load_terms(t), ["secretgame", "Other Name"])
            with self.assertRaises(FileNotFoundError):
                load_terms(Path(d, "none.txt"))

    def test_missing_terms_file_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(main(["--root", d, "--terms", str(Path(d, "none.txt"))]), 2)

    def test_findings_exit_1_and_clean_tree_exit_0(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "content").mkdir()
            Path(d, "content/x.md").write_text("깨끗", encoding="utf-8")
            t = Path(d, "terms.txt")
            t.write_text("# 주석\nsecretgame\n", encoding="utf-8")
            self.assertEqual(main(["--root", d, "--terms", str(t)]), 0)
            Path(d, "content/y.md").write_text("secretgame 얘기", encoding="utf-8")
            self.assertEqual(main(["--root", d, "--terms", str(t)]), 1)


if __name__ == "__main__":
    unittest.main()

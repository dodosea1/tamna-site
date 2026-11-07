import tempfile
import unittest
from pathlib import Path

from tools.sitegen.content import bullet_items, extract_section, load_logs, load_monthly, load_pages

FX = Path("tests/fixtures/site/content")


class ContentTest(unittest.TestCase):
    def test_extract_section_returns_text_until_next_heading(self):
        body = "## 한 일\n- a\n## 막힌 것\n- b\n## 다음에 손댈 것 (약속 아님)\n- c\n- d\n"
        self.assertEqual(extract_section(body, "다음에 손댈 것").strip(), "- c\n- d")
        self.assertEqual(extract_section(body, "없는 절"), "")

    def test_bullet_items(self):
        self.assertEqual(bullet_items("- c\n- d\n글\n"), ["c", "d"])

    def test_load_logs_sorted_newest_first_with_next_items(self):
        logs = load_logs(FX / "log")
        self.assertEqual([log.date for log in logs], ["2026-11-07", "2026-11-06"])
        self.assertEqual(logs[0].next_items, ["사이트 생성기 뼈대."])
        self.assertEqual(logs[0].media, ["media/log/2026-11-07-hunter-sweep.gif"])
        self.assertEqual(logs[1].media, [])

    def test_load_logs_requires_three_sections(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "2026-01-01.md").write_text("---\ndate: 2026-01-01\n---\n## 한 일\n- x\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_logs(Path(d))

    def test_load_logs_rejects_h3_heading_and_empty_next_items(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "2026-01-01.md").write_text("---\ndate: 2026-01-01\n---\n### 한 일\n- x\n## 막힌 것\n- y\n## 다음에 손댈 것 (약속 아님)\n- z\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_logs(Path(d))
        with tempfile.TemporaryDirectory() as d:
            Path(d, "2026-01-01.md").write_text("---\ndate: 2026-01-01\n---\n## 한 일\n- x\n## 막힌 것\n- y\n## 다음에 손댈 것 (약속 아님)\n1. 번호 목록\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_logs(Path(d))

    def test_load_logs_rejects_date_filename_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "2026-01-01.md").write_text("---\ndate: 2026-01-40\n---\n## 한 일\n- x\n## 막힌 것\n- y\n## 다음에 손댈 것 (약속 아님)\n- z\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_logs(Path(d))

    def test_loaders_skip_drafts(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "2026-01-01.md").write_text("---\ndate: 2026-01-01\ndraft: true\n---\n## 한 일\n- x\n## 막힌 것\n- y\n## 다음에 손댈 것 (약속 아님)\n- z\n", encoding="utf-8")
            self.assertEqual(load_logs(Path(d)), [])
        with tempfile.TemporaryDirectory() as d:
            Path(d, "2026-11.md").write_text("---\ndate: 2026-11-01\ntitle: 초안\ndraft: true\n---\n## 이달에 한 일\n- x\n", encoding="utf-8")
            self.assertEqual(load_monthly(Path(d)), [])

    def test_load_pages_sorted_by_order(self):
        pages = load_pages(FX / "pages")
        self.assertEqual([p.slug for p in pages], ["about", "game", "feedback"])
        self.assertEqual(pages[0].title, "만드는 사람과 AI")

    def test_load_monthly_newest_first(self):
        monthly = load_monthly(FX / "monthly")
        self.assertEqual(monthly[0].month, "2026-10")
        self.assertTrue(monthly[0].summary_en)


if __name__ == "__main__":
    unittest.main()

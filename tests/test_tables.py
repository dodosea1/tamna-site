import json
import unittest
from pathlib import Path

from tools.sitegen.tables import ai_table, feedback_table, roadmap_section, support_section

FX = Path("tests/fixtures/site/data")


def load(name: str):
    return json.loads((FX / name).read_text(encoding="utf-8"))


class TablesTest(unittest.TestCase):
    def test_feedback_table_has_status_and_no_name_column(self):
        html = feedback_table(load("feedback.json"))
        self.assertIn("<th>상태</th>", html)
        self.assertNotIn("이름", html)
        self.assertIn("📢 ", html)

    def test_feedback_table_rejects_unknown_status(self):
        with self.assertRaises(ValueError):
            feedback_table([{"period": "2026-11", "category": "전투", "summary": "x", "status": "대기", "reason": "", "applied": ""}])

    def test_feedback_table_empty(self):
        self.assertIn("아직 받은 의견이 없습니다", feedback_table([]))

    def test_roadmap_section_contains_no_promise_note_and_updated(self):
        html = roadmap_section(load("roadmap.json"))
        self.assertIn("빠짐없는 목록이 아니며 약속이 아닙니다.", html)
        self.assertIn("갱신 2026-11-07", html)
        self.assertIn("장르·핵심 루프 확정", html)

    def test_roadmap_rejects_unknown_status(self):
        with self.assertRaises(ValueError):
            roadmap_section({"updated": "2026-11-07", "note": "n", "items": [{"topic": "t", "status": "예정", "note": ""}], "steam_checklist": []})

    def test_support_section_total_and_cap(self):
        html = support_section(load("support.json"))
        self.assertIn("누적 30,000원", html)
        self.assertIn("상한 10,000,000원", html)
        self.assertIn("환불은 되지 않습니다", html)
        self.assertNotIn("계좌", html)

    def test_ai_table_rows(self):
        html = ai_table(load("ai.json"))
        self.assertIn("<td>코드</td>", html)
        self.assertIn("<th>바뀐 날</th>", html)

    def test_values_are_escaped(self):
        html = ai_table([{"area": "<b>", "who": "", "tool": "", "changed": ""}])
        self.assertIn("&lt;b&gt;", html)


if __name__ == "__main__":
    unittest.main()

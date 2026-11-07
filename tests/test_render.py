import unittest
from pathlib import Path

from tools.sitegen.render import md_to_html, render_template


class RenderTest(unittest.TestCase):
    def test_md_table_and_heading(self):
        html = md_to_html("## 제목\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
        self.assertIn("<h2>제목</h2>", html)
        self.assertIn("<table>", html)

    def test_render_template_replaces_and_rejects_missing(self):
        d = Path("tests/fixtures/templates")
        self.assertEqual(render_template("t.html", {"x": "1"}, d).strip(), "<p>1</p>")
        with self.assertRaises(KeyError):
            render_template("t.html", {}, d)


if __name__ == "__main__":
    unittest.main()

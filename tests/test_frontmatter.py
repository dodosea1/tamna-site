import unittest

from tools.sitegen.frontmatter import parse_frontmatter, split_list


class FrontmatterTest(unittest.TestCase):
    def test_parses_keys_and_body(self):
        meta, body = parse_frontmatter("---\ndate: 2026-11-07\ntitle: 첫 기록\n---\n## 한 일\n- 했다\n")
        self.assertEqual(meta, {"date": "2026-11-07", "title": "첫 기록"})
        self.assertEqual(body, "## 한 일\n- 했다\n")

    def test_no_frontmatter_returns_empty_dict(self):
        self.assertEqual(parse_frontmatter("본문만"), ({}, "본문만"))

    def test_split_list(self):
        self.assertEqual(split_list("a.gif, b.mp4 ,,"), ["a.gif", "b.mp4"])


if __name__ == "__main__":
    unittest.main()

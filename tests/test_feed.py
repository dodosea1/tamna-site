import unittest
import xml.etree.ElementTree as ET

from tools.sitegen.feed import FeedItem, build_rss


class FeedTest(unittest.TestCase):
    def setUp(self):
        self.xml = build_rss(
            [FeedItem("기록 2026-11-07", "https://u.github.io/tamna-site/log/2026-11-07/", "2026-11-07", "한 일 <b>")],
            "탐라(가제)",
            "https://u.github.io/tamna-site",
            "작업 기록",
        )

    def test_rss_is_valid_xml_with_items(self):
        root = ET.fromstring(self.xml)
        self.assertEqual(root.tag, "rss")
        self.assertEqual(len(root.findall("./channel/item")), 1)
        self.assertEqual(root.find("./channel/title").text, "탐라(가제)")

    def test_rss_links_absolute_and_pubdate_kst(self):
        item = ET.fromstring(self.xml).find("./channel/item")
        self.assertTrue(item.find("link").text.startswith("https://"))
        self.assertTrue(item.find("pubDate").text.endswith("+0900"))
        self.assertIn("&lt;b&gt;", self.xml)


if __name__ == "__main__":
    unittest.main()

import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from build import build_site

FX = Path("tests/fixtures/site")
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class SitemapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        build_site(FX, self.out, base="/tamna-site")
        self.urls = [e.text for e in ET.parse(self.out / "sitemap.xml").getroot().iter(f"{NS}loc")]
        self.site_url = re.search(r"<link>(.*?)</link>", (self.out / "feed.xml").read_text(encoding="utf-8")).group(1).rstrip("/")

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_html_page_is_listed_exactly_once(self):
        expected = set()
        for f in self.out.rglob("index.html"):
            rel = f.parent.relative_to(self.out).as_posix()
            expected.add(self.site_url + "/" + ("" if rel == "." else rel + "/"))
        self.assertEqual(set(self.urls), expected)
        self.assertEqual(len(self.urls), len(set(self.urls)))

    def test_urls_are_absolute_and_inside_the_site(self):
        for url in self.urls:
            self.assertTrue(url.startswith(self.site_url + "/"), url)

    def test_log_pages_carry_their_date(self):
        root = ET.parse(self.out / "sitemap.xml").getroot()
        dated = {u.find(f"{NS}loc").text: u.find(f"{NS}lastmod") for u in root.iter(f"{NS}url")}
        entry = dated[self.site_url + "/log/2026-11-07/"]
        self.assertEqual(entry.text, "2026-11-07")


if __name__ == "__main__":
    unittest.main()

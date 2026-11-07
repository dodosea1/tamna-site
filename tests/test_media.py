import re
import unittest
from pathlib import Path

MEDIA = Path(__file__).resolve().parent.parent / "media"
MAX_FILE = 20 * 1024 * 1024
MAX_TOTAL = 300 * 1024 * 1024
NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class MediaTest(unittest.TestCase):
    def files(self):
        return [p for p in MEDIA.rglob("*") if p.is_file()] if MEDIA.exists() else []

    def test_media_folder_has_hero_and_clips(self):
        names = {p.name for p in self.files()}
        self.assertIn("hero.gif", names)
        self.assertIn("concept-64s-720p.mp4", names)

    def test_each_file_under_20mb(self):
        for p in self.files():
            self.assertLessEqual(p.stat().st_size, MAX_FILE, f"{p.name} is {p.stat().st_size} bytes")

    def test_total_under_300mb(self):
        self.assertLessEqual(sum(p.stat().st_size for p in self.files()), MAX_TOTAL)

    def test_names_are_plain_ascii(self):
        for p in self.files():
            self.assertRegex(p.name, NAME)


if __name__ == "__main__":
    unittest.main()

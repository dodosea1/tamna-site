"""Chrome 예약용 명령: 다음 글 꺼내기(next_post)와 예약 표시(mark_scheduled)."""
import unittest
from datetime import timedelta

from tests.test_threads_post import NOW, Base
from tools.threads_post import mark_scheduled, next_post


class NextPostTest(Base):
    def nxt(self, now=NOW, published=True, url_ok=True):
        return next_post(self.root, self.store, now, ["비밀어"], lambda p: published, lambda u: url_ok)

    def test_returns_oldest_unposted_log_with_text_and_link(self):
        self.log("2026-11-09")
        self.log("2026-11-08")
        code, out = self.nxt()
        self.assertEqual(code, 0)
        self.assertTrue(out["due"])
        self.assertEqual(out["date"], "2026-11-08")
        self.assertIn("https://example.test/site/log/2026-11-08/", out["text"])
        self.assertEqual(out["media_path"], "")

    def test_media_path_is_absolute_local_file(self):
        (self.root / "media/a.png").write_bytes(b"x")
        self.thread("2026-11-09", "직접 쓴 글", head="media: media/a.png\n")
        code, out = self.nxt()
        self.assertEqual(code, 0)
        self.assertEqual(out["media_path"], str((self.root / "media/a.png").resolve()))

    def test_nothing_due_is_not_an_error(self):
        code, out = self.nxt()
        self.assertEqual((code, out["due"]), (0, False))

    def test_already_scheduled_today_gives_nothing(self):
        self.log("2026-11-08")
        self.log("2026-11-09")
        mark_scheduled(self.store, "2026-11-08", NOW)
        code, out = self.nxt()
        self.assertEqual((code, out["due"]), (0, False))
        code, out = self.nxt(now=NOW + timedelta(days=1))
        self.assertEqual(out["date"], "2026-11-09")

    def test_private_term_blocks_with_error(self):
        self.thread("2026-11-09", "비밀어가 들어간 글")
        code, out = self.nxt()
        self.assertEqual((code, out["due"]), (1, False))
        self.assertNotIn("비밀어", out["reason"])

    def test_unpublished_source_blocks(self):
        self.log("2026-11-09")
        code, out = self.nxt(published=False)
        self.assertEqual((code, out["due"]), (1, False))

    def test_dead_link_blocks(self):
        self.log("2026-11-09")
        code, out = self.nxt(url_ok=False)
        self.assertEqual((code, out["due"]), (1, False))


class MarkTest(Base):
    def test_mark_records_day_and_rejects_repeat(self):
        self.assertEqual(mark_scheduled(self.store, "2026-11-09", NOW), 0)
        state = self.store.load_state()
        self.assertEqual(state["posted"]["2026-11-09"], "chrome")
        self.assertEqual(state["last_post_day"], "2026-11-10")
        self.assertEqual(mark_scheduled(self.store, "2026-11-09", NOW), 1)

    def test_mark_rejects_bad_date(self):
        self.assertEqual(mark_scheduled(self.store, "11/09", NOW), 1)
        self.assertEqual(self.store.load_state()["posted"], {})


if __name__ == "__main__":
    unittest.main()

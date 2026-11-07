import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.threads_post import (
    MAX_TEXT, Post, Store, ThreadsError, compose_from_log, load_due_post, run, text_length, validate_post,
)

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 10, 21, 0, tzinfo=KST)
SITE = "https://example.test/site"
LOG = "---\ndate: {d}\ntitle: 제목 {d}\n---\n## 한 일\n- 첫 줄을 했다.\n- 둘째 줄을 했다.\n\n## 막힌 것\n- 없음\n\n## 다음에 손댈 것 (약속 아님)\n- 다음\n"


class FakeApi:
    def __init__(self, username="tamna", statuses=None):
        self.username = username
        self.statuses = list(statuses or ["FINISHED"])
        self.created = []
        self.published = []
        self.refreshed = 0

    def me(self):
        return {"id": "42", "username": self.username}

    def create(self, user_id, post, media_url):
        self.created.append((user_id, post.text, media_url))
        return "c1"

    def status(self, container):
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def publish(self, user_id, container):
        self.published.append(container)
        return "p1"

    def refresh(self):
        self.refreshed += 1
        return "new-token"

    def url_ok(self, url):
        return True


class Boom(FakeApi):
    def publish(self, user_id, container):
        raise ThreadsError("network")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "site"
        for d in ("content/log", "content/threads", "media", "data"):
            (self.root / d).mkdir(parents=True)
        (self.root / "data/site.json").write_text(json.dumps({"site_url": SITE}), encoding="utf-8")
        self.store = Store(base / "home")
        self.store.save_config({"enabled": True, "start_date": "2026-11-08", "username": "tamna"})
        self.store.save_token("old-token", NOW)

    def log(self, d):
        (self.root / f"content/log/{d}.md").write_text(LOG.format(d=d), encoding="utf-8")

    def thread(self, d, body, head=""):
        (self.root / f"content/threads/{d}.md").write_text(f"---\n{head}---\n{body}\n", encoding="utf-8")

    def go(self, api=None, **kw):
        api = api or FakeApi()
        code = run(self.root, self.store, api, NOW, terms=["비밀어"], sleep=lambda s: None, **kw)
        return code, api


class TextLengthTest(unittest.TestCase):
    def test_korean_counts_one_each_and_emoji_by_bytes(self):
        self.assertEqual(text_length("탐라"), 2)
        self.assertEqual(text_length("😀"), 4)


class DueTest(Base):
    def test_hand_written_post_wins_over_log(self):
        self.log("2026-11-09")
        self.thread("2026-11-09", "직접 쓴 글")
        self.assertEqual(load_due_post(self.root, "2026-11-08", set(), NOW).text, "직접 쓴 글")

    def test_log_becomes_post_with_title_first_item_and_link(self):
        self.log("2026-11-09")
        post = load_due_post(self.root, "2026-11-08", set(), NOW)
        self.assertIn("제목 2026-11-09", post.text)
        self.assertIn("첫 줄을 했다.", post.text)
        self.assertIn(f"{SITE}/log/2026-11-09/", post.text)

    def test_oldest_unposted_comes_first(self):
        self.log("2026-11-08")
        self.log("2026-11-09")
        self.assertEqual(load_due_post(self.root, "2026-11-08", set(), NOW).date, "2026-11-08")
        self.assertEqual(load_due_post(self.root, "2026-11-08", {"2026-11-08"}, NOW).date, "2026-11-09")

    def test_today_waits_because_the_log_may_still_grow(self):
        self.log("2026-11-10")
        self.assertIsNone(load_due_post(self.root, "2026-11-08", set(), NOW))

    def test_dates_before_start_are_never_posted(self):
        self.log("2026-11-07")
        self.assertIsNone(load_due_post(self.root, "2026-11-08", set(), NOW))

    def test_draft_blocks_that_date_and_does_not_fall_back_to_log(self):
        self.log("2026-11-09")
        self.thread("2026-11-09", "초안", "draft: true\n")
        self.assertIsNone(load_due_post(self.root, "2026-11-08", set(), NOW))

    def test_compose_skips_an_item_too_long_for_the_limit(self):
        body = "## 한 일\n- " + "가" * 600 + "\n- 짧은 줄.\n"
        text = compose_from_log("제목", body, f"{SITE}/log/x/")
        self.assertIn("짧은 줄.", text)
        self.assertLessEqual(text_length(text), MAX_TEXT)

    def test_compose_returns_none_when_nothing_fits(self):
        self.assertIsNone(compose_from_log("제목", "## 한 일\n- " + "가" * 600 + "\n", "u"))


class ValidateTest(Base):
    def post(self, text="글", media=""):
        return Post("2026-11-09", text, media)

    def test_ok(self):
        self.assertEqual(validate_post(self.post(), self.root, ["비밀어"]), [])

    def test_private_word_and_patterns_are_blocked(self):
        self.assertTrue(validate_post(self.post("이건 비밀어다"), self.root, ["비밀어"]))
        self.assertTrue(validate_post(self.post("연락 010" + "-1234-5678"), self.root, []))

    def test_too_long_is_blocked_not_trimmed(self):
        self.assertTrue(validate_post(self.post("가" * (MAX_TEXT + 1)), self.root, []))

    def test_empty_is_blocked(self):
        self.assertTrue(validate_post(self.post("  "), self.root, []))

    def test_gif_outside_paths_and_missing_media_are_blocked(self):
        (self.root / "media/a.gif").write_bytes(b"x")
        for media in ("media/a.gif", "../secret.png", "media/none.png", "C:/x.png", "media/../../x.png"):
            self.assertTrue(validate_post(self.post(media=media), self.root, []), media)

    def test_existing_mp4_passes(self):
        (self.root / "media/a.mp4").write_bytes(b"x")
        self.assertEqual(validate_post(self.post(media="media/a.mp4"), self.root, []), [])


class RunTest(Base):
    def test_posts_one_and_records_it(self):
        self.log("2026-11-08")
        self.log("2026-11-09")
        code, api = self.go()
        self.assertEqual(code, 0)
        self.assertEqual(len(api.published), 1)
        self.assertEqual(self.store.load_state()["posted"]["2026-11-08"], "p1")

    def test_second_run_same_day_posts_nothing(self):
        self.log("2026-11-08")
        self.log("2026-11-09")
        self.go()
        _, api = self.go()
        self.assertEqual(api.published, [])

    def test_disabled_posts_nothing(self):
        self.log("2026-11-09")
        self.store.save_config({"enabled": False, "start_date": "2026-11-08", "username": "tamna"})
        _, api = self.go()
        self.assertEqual(api.created, [])

    def test_no_token_posts_nothing(self):
        self.log("2026-11-09")
        self.store.token_path.unlink()
        code, api = self.go()
        self.assertEqual(api.created, [])
        self.assertEqual(code, 0)

    def test_wrong_account_stops_before_creating(self):
        self.log("2026-11-09")
        code, api = self.go(FakeApi(username="someone_else"))
        self.assertEqual(api.created, [])
        self.assertNotEqual(code, 0)

    def test_blocked_post_is_not_sent_and_later_dates_wait(self):
        self.thread("2026-11-08", "비밀어 포함")
        self.log("2026-11-09")
        code, api = self.go()
        self.assertEqual(api.created, [])
        self.assertNotEqual(code, 0)

    def test_dry_run_sends_nothing_and_records_nothing(self):
        self.log("2026-11-09")
        code, api = self.go(dry_run=True)
        self.assertEqual((code, api.created, api.published), (0, [], []))
        self.assertEqual(self.store.load_state()["posted"], {})

    def test_dry_run_works_without_token_or_enable(self):
        self.log("2026-11-09")
        self.store.token_path.unlink()
        self.store.save_config({"enabled": False, "start_date": "2026-11-08", "username": "tamna"})
        code, api = self.go(dry_run=True)
        self.assertEqual((code, api.created), (0, []))
        self.assertIn("2026-11-09", self.store.log_path.read_text(encoding="utf-8"))

    def test_container_error_is_reported_and_not_marked_posted(self):
        self.log("2026-11-09")
        code, api = self.go(FakeApi(statuses=["ERROR"]))
        self.assertNotEqual(code, 0)
        self.assertEqual(api.published, [])
        self.assertNotIn("2026-11-09", self.store.load_state()["posted"])

    def test_crash_during_publish_never_double_posts(self):
        self.log("2026-11-09")
        code, _ = self.go(Boom())
        self.assertNotEqual(code, 0)
        self.assertEqual(self.store.load_state()["pending"]["date"], "2026-11-09")
        code, api = self.go(FakeApi(statuses=["PUBLISHED"]))
        self.assertEqual(code, 0)
        self.assertEqual((api.created, api.published), ([], []))
        self.assertIn("2026-11-09", self.store.load_state()["posted"])

    def test_pending_finished_container_is_published_without_recreating(self):
        self.log("2026-11-09")
        self.go(Boom())
        code, api = self.go(FakeApi(statuses=["FINISHED"]))
        self.assertEqual(code, 0)
        self.assertEqual((api.created, api.published), ([], ["c1"]))

    def test_expired_pending_is_cleared_and_retried(self):
        self.log("2026-11-09")
        self.go(Boom())
        code, api = self.go(FakeApi(statuses=["EXPIRED", "FINISHED"]))
        self.assertEqual(code, 0)
        self.assertEqual(len(api.created), 1)

    def test_token_refreshes_after_30_days_and_stays_otherwise(self):
        self.store.save_token("old-token", NOW - timedelta(days=31))
        _, api = self.go()
        self.assertEqual(api.refreshed, 1)
        self.assertEqual(self.store.load_token()["token"], "new-token")
        self.store.save_token("old-token", NOW - timedelta(days=5))
        _, api = self.go()
        self.assertEqual(api.refreshed, 0)

    def test_refresh_failure_keeps_old_token_and_is_reported(self):
        class NoRefresh(FakeApi):
            def refresh(self):
                raise ThreadsError("refused")

        self.store.save_token("old-token", NOW - timedelta(days=31))
        code, _ = self.go(NoRefresh())
        self.assertNotEqual(code, 0)
        self.assertEqual(self.store.load_token()["token"], "old-token")

    def test_token_is_never_written_to_the_run_log(self):
        self.log("2026-11-09")
        self.go()
        self.assertNotIn("old-token", self.store.log_path.read_text(encoding="utf-8"))

    def test_unreachable_media_is_not_sent(self):
        (self.root / "media/a.png").write_bytes(b"x")
        self.thread("2026-11-09", "그림 글", "media: media/a.png\n")

        class NoUrl(FakeApi):
            def url_ok(self, url):
                return False

        code, api = self.go(NoUrl())
        self.assertNotEqual(code, 0)
        self.assertEqual(api.created, [])

    def test_media_url_is_built_from_site_url(self):
        (self.root / "media/a.png").write_bytes(b"x")
        self.thread("2026-11-09", "그림 글", "media: media/a.png\n")
        _, api = self.go()
        self.assertEqual(api.created[0][2], f"{SITE}/media/a.png")


if __name__ == "__main__":
    unittest.main()

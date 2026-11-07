import io
import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from tests.test_threads_post import LOG, NOW, SITE, Boom, FakeApi
from tools.threads_post import REFRESH_AFTER, Api, Store, ThreadsError, first_refresh_time, run

KST = timezone(timedelta(hours=9))


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

    def go(self, api=None, now=NOW, **kw):
        api = api or FakeApi()
        return run(self.root, self.store, api, now, terms=[], sleep=lambda s: None, **kw), api


class GoneContainer(FakeApi):
    def status(self, container):
        raise ThreadsError("HTTP 400: gone")


class StuckPendingTest(Base):
    def test_recent_status_failure_keeps_pending_for_the_next_run(self):
        self.log("2026-11-09")
        self.go(Boom())
        code, api = self.go(GoneContainer(), now=NOW + timedelta(hours=1))
        self.assertEqual(code, 1)
        self.assertEqual(api.created, [])
        self.assertTrue(self.store.load_state()["pending"])

    def test_old_unknown_pending_is_skipped_never_reposted_and_queue_moves_on(self):
        self.log("2026-11-09")
        self.go(Boom())
        self.log("2026-11-10")
        later = NOW + timedelta(days=2)
        code, api = self.go(GoneContainer(), now=later)
        state = self.store.load_state()
        self.assertIsNone(state["pending"])
        self.assertEqual(state["posted"]["2026-11-09"], "unknown")
        self.assertEqual(code, 1)
        self.assertEqual(api.created, [])
        self.assertIn("2026-11-09", self.store.log_path.read_text(encoding="utf-8"))

    def test_in_progress_pending_waits_without_new_post(self):
        self.log("2026-11-09")
        self.go(Boom())
        code, api = self.go(FakeApi(statuses=["IN_PROGRESS"]))
        self.assertEqual((code, api.created, api.published), (0, [], []))


class UnpublishedSourceTest(Base):
    def test_unpushed_post_is_not_sent_and_is_reported_as_a_problem(self):
        self.log("2026-11-09")
        code, api = self.go(is_published=lambda path: False)
        self.assertEqual(code, 1)
        self.assertEqual(api.created, [])


class SecretBoomApi(FakeApi):
    def me(self):
        raise RuntimeError("old-token leaked in message")


class UnexpectedErrorTest(Base):
    def test_unexpected_error_is_logged_by_type_only(self):
        code, _ = self.go(SecretBoomApi())
        self.assertEqual(code, 1)
        text = self.store.log_path.read_text(encoding="utf-8")
        self.assertIn("RuntimeError", text)
        self.assertNotIn("old-token", text)


class RealApiErrorTest(unittest.TestCase):
    def test_http_error_body_has_token_removed(self):
        error = urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(b'{"error":"sekret-token bad"}'))
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(ThreadsError) as caught:
                Api("sekret-token").me()
        self.assertNotIn("sekret-token", str(caught.exception))
        self.assertIn("400", str(caught.exception))

    def test_connection_reset_while_reading_becomes_threads_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=ConnectionResetError("reset sekret-token")):
            with self.assertRaises(ThreadsError) as caught:
                Api("sekret-token").me()
        self.assertNotIn("sekret-token", str(caught.exception))

    def test_url_ok_is_false_on_connection_reset(self):
        with mock.patch("urllib.request.urlopen", side_effect=ConnectionResetError()):
            self.assertFalse(Api("t").url_ok("https://example.test/"))


class FirstRefreshTest(Base):
    def test_new_token_of_unknown_age_refreshes_one_day_later(self):
        saved_at = first_refresh_time(NOW)
        self.store.save_token("pasted", saved_at)
        _, api = self.go(now=NOW + timedelta(hours=23))
        self.assertEqual(api.refreshed, 0)
        _, api = self.go(now=NOW + timedelta(hours=25))
        self.assertEqual(api.refreshed, 1)
        self.assertLess(saved_at, NOW - REFRESH_AFTER + timedelta(days=2))


if __name__ == "__main__":
    unittest.main()

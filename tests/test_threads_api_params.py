"""실제 API 호출에 넣는 값: 영상 종류와 주제 태그(docs/63)."""
import unittest

from tools.threads_post import Api, Post


class CreateParamsTest(unittest.TestCase):
    def capture(self, post, media_url):
        api = Api("tok")
        seen = {}

        def fake(method, path, params=None):
            seen.update(method=method, path=path, params=params)
            return {"id": "c1"}

        api._call = fake
        self.assertEqual(api.create("u1", post, media_url), "c1")
        return seen

    def test_video_with_topic(self):
        seen = self.capture(Post("2026-11-13", "글", media="media/threads/a.mp4", topic="Game Dev"), "https://x/media/threads/a.mp4")
        self.assertEqual(seen["path"], "/v1.0/u1/threads")
        self.assertEqual(seen["params"]["media_type"], "VIDEO")
        self.assertEqual(seen["params"]["video_url"], "https://x/media/threads/a.mp4")
        self.assertEqual(seen["params"]["topic_tag"], "Game Dev")

    def test_no_topic_sends_no_tag(self):
        seen = self.capture(Post("2026-11-13", "글"), "")
        self.assertEqual(seen["params"]["media_type"], "TEXT")
        self.assertNotIn("topic_tag", seen["params"])


if __name__ == "__main__":
    unittest.main()

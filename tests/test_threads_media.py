"""스레드 영상 크기 상한(Chrome 업로드 10MB, 2026-11-24)."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.threads_media import TARGET_MAX, fit_size

HAS_FFMPEG = bool(shutil.which("ffmpeg"))


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg 없음")
class FitSizeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.video = self.tmp / "noise.mp4"
        # 잡음 화면은 압축이 잘 안 돼서 일부러 큰 파일이 된다.
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "nullsrc=s=640x360:d=3:r=30,geq=random(1)*255:128:128",
                        "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(self.video)], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_target_is_under_chrome_limit(self):
        self.assertLess(TARGET_MAX, 10 * 1024 * 1024)

    def test_big_video_is_shrunk_under_limit(self):
        limit = self.video.stat().st_size // 3
        changed = fit_size(self.video, limit)
        self.assertTrue(changed)
        self.assertLessEqual(self.video.stat().st_size, limit)

    def test_small_video_is_left_alone(self):
        before = self.video.read_bytes()
        self.assertFalse(fit_size(self.video, self.video.stat().st_size + 1))
        self.assertEqual(self.video.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

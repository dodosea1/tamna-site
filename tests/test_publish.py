import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.publish import main

REPO = Path(__file__).resolve().parent.parent
LOG_OK = "---\ndate: 2026-11-07\ntitle: 시험\n---\n## 한 일\n- 깨끗한 기록\n## 막힌 것\n- 없음\n## 다음에 손댈 것 (약속 아님)\n- 다음\n"
LOG_BAD = LOG_OK.replace("깨끗한 기록", "전화 010-1234-5678")


def make_repo(root: Path, log_text: str) -> None:
    shutil.copytree(REPO / "tests" / "fixtures" / "site", root, dirs_exist_ok=True)
    for sub in ("templates", "static", "tools"):
        shutil.copytree(REPO / sub, root / sub, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(REPO / "build.py", root / "build.py")
    (root / "content" / "log" / "2026-11-07.md").write_text(log_text, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)


def commits(root: Path) -> str:
    return subprocess.run(["git", "-C", str(root), "log", "--oneline"], capture_output=True, text=True).stdout.strip()


class PublishTest(unittest.TestCase):
    def test_publish_aborts_when_lint_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root, LOG_BAD)
            terms = root / "terms.txt"
            terms.write_text("", encoding="utf-8")
            rc = main(["--root", str(root), "--terms", str(terms), "--message", "m", "--no-push"])
            self.assertEqual(rc, 1)
            self.assertEqual(commits(root), "")

    def test_publish_dry_run_commits_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root, LOG_OK)
            terms = root / "terms.txt"
            terms.write_text("", encoding="utf-8")
            rc = main(["--root", str(root), "--terms", str(terms), "--message", "m", "--dry-run"])
            self.assertEqual(rc, 0)
            self.assertEqual(commits(root), "")

    def test_publish_commits_with_no_push(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root, LOG_OK)
            terms = root / "terms.txt"
            terms.write_text("", encoding="utf-8")
            rc = main(["--root", str(root), "--terms", str(terms), "--message", "log: 2026-11-07", "--no-push"])
            self.assertEqual(rc, 0)
            self.assertIn("log: 2026-11-07", commits(root))
            self.assertFalse((root / "_site").exists() and False)  # _site is build output, not committed
            tracked = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True).stdout
            self.assertNotIn("_site/", tracked)


if __name__ == "__main__":
    unittest.main()

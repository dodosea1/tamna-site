import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.publish import main

REPO = Path(__file__).resolve().parent.parent
LOG_OK = "---\ndate: 2026-11-07\ntitle: 시험\n---\n## 한 일\n- 깨끗한 기록\n## 막힌 것\n- 없음\n## 다음에 손댈 것 (약속 아님)\n- 다음\n"
PHONE = "010-1234" + "-5678"  # 검사 패턴이 이 파일 자체를 잡지 않도록 실행 때 조립
LOG_BAD = LOG_OK.replace("깨끗한 기록", "전화 " + PHONE)
DRAFT = "---\ndate: 2026-11-01\ntitle: 초안\ndraft: true\nsummary_en: Draft.\n---\n## 이달에 한 일\n- 아직\n"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False).stdout.strip()


def make_repo(root: Path, log_text: str) -> None:
    shutil.copytree(REPO / "tests" / "fixtures" / "site", root, dirs_exist_ok=True)
    for sub in ("templates", "static", "tools"):
        shutil.copytree(REPO / sub, root / sub, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(REPO / "build.py", root / "build.py")
    (root / "content" / "log" / "2026-11-07.md").write_text(log_text, encoding="utf-8")
    site = root / "data" / "site.json"
    data = json.loads(site.read_text(encoding="utf-8"))
    data["site_url"] = "https://someone.github.io/tamna-site"
    site.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (root / ".gitignore").write_text("_site/\n__pycache__/\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@" + "example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)


def commits(root: Path) -> str:
    return git(root, "log", "--oneline")


def publish(root: Path, terms: Path, *extra: str) -> int:
    return main(["--root", str(root), "--terms", str(terms), *extra])


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.terms = Path(self.tmp.name) / "terms.txt"
        self.terms.write_text("", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_publish_aborts_when_lint_fails(self):
        make_repo(self.root, LOG_BAD)
        self.assertEqual(publish(self.root, self.terms, "--message", "m", "--no-push"), 1)
        self.assertEqual(commits(self.root), "")

    def test_publish_dry_run_commits_nothing(self):
        make_repo(self.root, LOG_OK)
        self.assertEqual(publish(self.root, self.terms, "--message", "m", "--dry-run"), 0)
        self.assertEqual(commits(self.root), "")

    def test_publish_commits_with_no_push(self):
        make_repo(self.root, LOG_OK)
        self.assertEqual(publish(self.root, self.terms, "--message", "log: 2026-11-07", "--no-push"), 0)
        self.assertIn("log: 2026-11-07", commits(self.root))
        self.assertNotIn("_site/", git(self.root, "ls-files"))

    def test_publish_pushes_pending_commit_after_failed_push(self):
        make_repo(self.root, LOG_OK)
        self.assertEqual(publish(self.root, self.terms, "--message", "first", "--no-push"), 0)
        bare = Path(self.tmp.name) / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
        git(self.root, "remote", "add", "origin", str(bare))
        # 작업 트리는 깨끗하지만 origin에 없는 커밋이 있다 → 다시 실행하면 푸시해야 한다
        self.assertEqual(publish(self.root, self.terms, "--message", "retry"), 0)
        self.assertEqual(git(self.root, "rev-list", "--count", "origin/main..main"), "0")

    def test_publish_excludes_draft_files(self):
        make_repo(self.root, LOG_OK)
        (self.root / "content" / "monthly" / "2026-11.md").write_text(DRAFT, encoding="utf-8")
        self.assertEqual(publish(self.root, self.terms, "--message", "m", "--no-push"), 0)
        tracked = git(self.root, "ls-files")
        self.assertIn("content/log/2026-11-07.md", tracked)
        self.assertNotIn("content/monthly/2026-11.md", tracked)

    def test_publish_rejects_message_with_private_pattern(self):
        make_repo(self.root, LOG_OK)
        self.assertEqual(publish(self.root, self.terms, "--message", "전화 " + PHONE, "--no-push"), 1)
        self.assertEqual(commits(self.root), "")

    def test_publish_refuses_placeholder_site_url(self):
        make_repo(self.root, LOG_OK)
        site = self.root / "data" / "site.json"
        data = json.loads(site.read_text(encoding="utf-8"))
        data["site_url"] = "https://example.github.io/tamna-site"
        site.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(publish(self.root, self.terms, "--message", "m", "--no-push"), 1)
        self.assertEqual(commits(self.root), "")


if __name__ == "__main__":
    unittest.main()

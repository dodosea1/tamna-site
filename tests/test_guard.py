import json
import subprocess
import sys
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "tools" / "guard_push.py"


def run_guard(command: str) -> int:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run([sys.executable, str(GUARD)], input=payload, text=True, capture_output=True).returncode


class GuardPushTest(unittest.TestCase):
    def test_blocks_git_push_forms(self):
        for cmd in ["git push", "git push origin main", "cd x && git push", "git -C C:/x push", "git -c push.default=current push", "git 'push' origin main"]:
            self.assertEqual(run_guard(cmd), 2, cmd)

    def test_allows_other_commands_and_publish_script(self):
        for cmd in ["git status", "git log --oneline", "python tools/publish.py --message x", "echo push"]:
            self.assertEqual(run_guard(cmd), 0, cmd)

    def test_malformed_input_blocks(self):
        rc = subprocess.run([sys.executable, str(GUARD)], input="not json", text=True, capture_output=True).returncode
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()

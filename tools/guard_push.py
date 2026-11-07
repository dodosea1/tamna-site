"""Claude Code PreToolUse 훅: Bash 명령에 git push가 있으면 막는다(publish.py는 예외).

표준 입력으로 훅 JSON을 받는다. 종료 2 = 차단(이유는 표준 오류로), 0 = 허용. 입력을 못 읽어도 차단한다.
"""

from __future__ import annotations

import json
import re
import sys

PUSH = re.compile(r"(?:^|[\s;&|(`])git\b[^|&;\n]*?\bpush\b")


def decide(command: str) -> int:
    if "publish.py" in command:
        return 0
    plain = command.replace("'", "").replace('"', "")
    if PUSH.search(plain):
        return 2
    return 0


def main() -> int:
    try:
        data = json.load(sys.stdin)
        command = str(data["tool_input"]["command"])
    except Exception:  # noqa: BLE001
        print("guard_push: 훅 입력을 읽지 못해 차단합니다.", file=sys.stderr)
        return 2
    rc = decide(command)
    if rc:
        print("git push는 직접 쓰지 않습니다. 사이트는 tools/publish.py로만 올립니다.", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

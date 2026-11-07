"""글 앞머리(`---` 블록)를 읽는다."""

from __future__ import annotations


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """앞머리 `key: value` 줄을 dict로, 나머지를 본문으로 돌려준다. 앞머리가 없으면 ({}, text)."""
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return {}, text
    meta: dict[str, str] = {}
    for i in range(1, len(lines)):
        line = lines[i]
        if line.strip() == "---":
            body = "\n".join(lines[i + 1 :])
            return meta, body
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return {}, text


def split_list(value: str) -> list[str]:
    """쉼표로 나누고 공백을 지우며 빈 항목은 버린다."""
    return [item.strip() for item in value.split(",") if item.strip()]

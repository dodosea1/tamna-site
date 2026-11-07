"""Markdown을 HTML로 바꾸고, `{{key}}` 템플릿을 채운다."""

from __future__ import annotations

import re
from pathlib import Path

import markdown

_TOKEN = re.compile(r"\{\{(\w+)\}\}")


def md_to_html(md: str) -> str:
    return markdown.markdown(md, extensions=["tables", "fenced_code"])


def fill(template_text: str, ctx: dict[str, str]) -> str:
    """`{{key}}`를 ctx 값으로 바꾼다. ctx에 없는 키가 남으면 KeyError."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in ctx:
            raise KeyError(key)
        return ctx[key]

    return _TOKEN.sub(repl, template_text)


def render_template(name: str, ctx: dict[str, str], templates_dir: Path) -> str:
    text = (templates_dir / name).read_text(encoding="utf-8")
    return fill(text, ctx)

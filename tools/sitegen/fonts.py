"""제목 글꼴(Gowun Batang)을 그 페이지 제목에 쓰인 글자만 받게 한다.

한글 글꼴 전체는 수 MB다. Google Fonts의 text= 인자는 적어 준 글자만 담은 작은 글꼴 파일 하나를 돌려준다.
그래서 페이지마다 제목·세로 제목·도장에 쓰인 글자를 모아 주소에 넣는다.
"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import quote

# 제목 글꼴을 쓰는 요소: h1~h3와 아래 class 중 하나를 가진 요소. static/style.css의 --serif 규칙과 맞춘다.
SERIF_TAGS = {"h1", "h2", "h3"}
SERIF_CLASSES = {"vt", "seal", "sf", "name"}
# 이보다 글자가 많으면 주소가 너무 길어진다. 그때는 글꼴을 받지 않고 기기의 바탕체로 보인다.
MAX_FONT_CHARS = 600
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
SKIP_TAGS = {"script", "style"}


class _SerifText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[bool, bool]] = []   # 열린 요소마다: (제목 글꼴 요소인가, 건너뛸 요소인가)
        self.inside = 0
        self.skip = 0
        self.chars: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in VOID_TAGS:
            return
        classes = set((dict(attrs).get("class") or "").split())
        serif = tag in SERIF_TAGS or bool(classes & SERIF_CLASSES)
        skip = tag in SKIP_TAGS
        self.stack.append((serif, skip))
        self.inside += serif
        self.skip += skip

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS or not self.stack:
            return
        serif, skip = self.stack.pop()
        self.inside -= serif
        self.skip -= skip

    def handle_data(self, data: str) -> None:
        if self.inside and not self.skip:
            self.chars.update(data)


def serif_chars(html: str) -> str:
    """제목 글꼴 요소 안의 글자(공백 제외)를 중복 없이 정렬해 돌려준다."""
    parser = _SerifText()
    parser.feed(html)
    parser.close()
    return "".join(sorted(c for c in parser.chars if not c.isspace()))


def title_font_link(chars: str) -> str:
    """제목 글꼴 스타일시트 링크. 화면 그리기를 막지 않게 print로 받아 두고 다 받으면 켠다."""
    if not chars or len(chars) > MAX_FONT_CHARS:
        return ""
    href = f"https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@700&amp;display=swap&amp;text={quote(chars, safe='')}"
    # 글꼴 서버에 어느 페이지에서 왔는지(리퍼러)는 보내지 않는다.
    return (f'<link rel="stylesheet" href="{href}" referrerpolicy="no-referrer" media="print" onload="this.media=\'all\'">'
            f'<noscript><link rel="stylesheet" href="{href}" referrerpolicy="no-referrer"></noscript>')

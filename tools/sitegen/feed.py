"""RSS 2.0 피드."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

KST = timezone(timedelta(hours=9))


@dataclass
class FeedItem:
    title: str
    link: str
    date: str  # YYYY-MM-DD
    description: str


def _pubdate(date: str) -> str:
    year, month, day = (int(part) for part in date.split("-"))
    return format_datetime(datetime(year, month, day, 9, 0, tzinfo=KST))


def build_rss(items: list[FeedItem], site_title: str, site_url: str, description: str) -> str:
    entries = []
    for item in items:
        entries.append(
            "<item>"
            f"<title>{escape(item.title)}</title>"
            f"<link>{escape(item.link)}</link>"
            f"<guid>{escape(item.link)}</guid>"
            f"<pubDate>{_pubdate(item.date)}</pubDate>"
            f"<description>{escape(item.description)}</description>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        f"<title>{escape(site_title)}</title>"
        f"<link>{escape(site_url)}</link>"
        f"<description>{escape(description)}</description>"
        "<language>ko</language>"
        + "".join(entries)
        + "</channel></rss>\n"
    )

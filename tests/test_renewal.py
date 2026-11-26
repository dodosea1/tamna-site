"""인터랙티브 리뉴얼(A안, 2026-11-26): 다른 게임 줄, 살아 있음 줄, 지금 어디까지, 다음 소식, 응원 한 줄, 움직임."""
import json
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from build import build_site
from tools.sitegen.content import LogEntry
from tools.sitegen.studio import cheer_line, follow_block, game_card, live_line, now_lines, other_games_rail

FX = Path("tests/fixtures/site")
B = "/tamna-site"
TAMNA = {"slug": "tamna", "name": "탐라(가제)", "status": "개발 중", "summary": "섬 사냥"}
CURVY = {"slug": "curvy", "name": "curvy(가칭)", "status": "개발 중", "summary": "슬라임"}
GOHYANG = {"slug": "gohyang", "name": "고향", "status": "운영 중", "summary": "따로", "url": "https://gohyang.town"}


def log(day: str, body: str = "## 한 일\n- 가\n- 나\n", game: str = "tamna") -> LogEntry:
    return LogEntry(date=day, title=f"제목 {day}", media=[], body_md=body, game=game)


class PiecesTest(unittest.TestCase):
    def test_other_games_rail_excludes_current_and_keeps_external(self):
        html = other_games_rail(B, [TAMNA, CURVY, GOHYANG], "tamna")
        self.assertIn("ORN의 다른 게임", html)
        self.assertNotIn("/games/tamna/", html)
        self.assertIn(f'href="{B}/games/curvy/"', html)
        self.assertIn('href="https://gohyang.town" rel="noopener"', html)
        self.assertLess(html.index("/games/curvy/"), html.index("gohyang.town"))  # games.json 순서
        self.assertEqual(other_games_rail(B, [TAMNA], "tamna"), "")

    def test_cards_count_clicks_by_slug(self):
        self.assertIn('data-goatcounter-click="card-curvy"', game_card(B, CURVY))
        self.assertIn('data-goatcounter-click="card-gohyang"', game_card(B, GOHYANG))

    def test_live_line_counts_last_seven_days(self):
        html = live_line([log("2026-11-26"), log("2026-11-21"), log("2026-11-19")], date(2026, 11, 26))
        self.assertIn("이번 주 기록 2개", html)
        self.assertIn('<time data-rel datetime="2026-11-26">2026-11-26</time>', html)
        # 7일 창의 끝: 오늘 포함 7일이면 11-20까지
        self.assertIn("이번 주 기록 2개", live_line([log("2026-11-26"), log("2026-11-20")], date(2026, 11, 26)))

    def test_live_line_without_recent_logs(self):
        html = live_line([log("2026-11-10")], date(2026, 11, 26))
        self.assertNotIn("이번 주 기록", html)
        self.assertIn("마지막 기록", html)
        self.assertIn('datetime="2026-11-10"', html)
        self.assertEqual(live_line([], date(2026, 11, 26)), "")

    def test_now_lines_takes_first_done_item(self):
        logs = [log("2026-11-26"), log("2026-11-25", "## 막힌 것\n- 없음\n"), log("2026-11-24", "## 한 일\n- 다\n")]
        self.assertEqual(now_lines(logs), [("2026-11-26", "가"), ("2026-11-24", "다")])
        self.assertEqual(len(now_lines([log(f"2026-11-{d:02d}") for d in range(20, 26)])), 3)

    def test_cheer_and_follow(self):
        self.assertEqual(cheer_line(B, False), "")
        cheer = cheer_line(B, True)
        self.assertIn(f'<a href="{B}/support/" data-goatcounter-click="cheer">개발 응원하기</a>', cheer)
        threads = "https://www.threads.com/@x"
        both = follow_block(B, TAMNA, threads, True)
        self.assertIn("다음 소식 받기", both)
        self.assertIn(f'href="{B}/games/tamna/together/"', both)
        self.assertIn('data-goatcounter-click="tester-tamna"', both)
        self.assertIn(f'href="{threads}" rel="noopener"', both)
        for args, count in (((threads, True), 2), ((threads, False), 1), (("", True), 1)):
            self.assertEqual(follow_block(B, TAMNA, *args).count("<a "), count, args)
        self.assertEqual(follow_block(B, TAMNA, "", False), "")

    def test_card_video_uses_poster_and_no_src(self):
        g = {**TAMNA, "card_image": "static/art/k.webp", "card_video": "media/previews/tamna.mp4"}
        html = game_card(B, g)
        self.assertIn(f'data-src="{B}/media/previews/tamna.mp4"', html)
        self.assertIn(f'poster="{B}/static/art/k.webp"', html)
        self.assertIn('preload="none"', html)
        self.assertNotIn(" src=", html)
        self.assertNotIn("<img", html)

    def test_pieces_escape_values(self):
        g = {"slug": "x", "name": "<b>이름</b>", "summary": 'a"b', "url": 'https://e.com/?a="b"'}
        html = game_card(B, g)
        self.assertNotIn("<b>", html)
        self.assertNotIn('a"b', html)


if __name__ == "__main__":
    unittest.main()

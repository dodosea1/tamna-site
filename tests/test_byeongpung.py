"""대개편 A. 오방색 병풍(2026-11-26): 게임 하나가 병풍 한 폭, 한지 읽는 페이지, 도장, 패치 노트 목록."""
import json
import re
import shutil
import unittest
from pathlib import Path
from urllib.parse import unquote

from tests.test_renewal import B, CURVY, GOHYANG, TAMNA, SiteTest, full, log
from tools.sitegen.studio import date_seal, latest_card, other_games_rail, panel, patch_list, split_name


class PanelTest(unittest.TestCase):
    def test_panel_title_splits_tentative_mark_and_keeps_full_name(self):
        self.assertEqual(split_name("탐라(가제)"), ("탐라", "가제"))
        self.assertEqual(split_name("고향"), ("고향", ""))
        self.assertEqual(split_name("a(b) c(가칭)"), ("a(b) c", "가칭"))
        html = panel(B, TAMNA)
        self.assertIn('<h2 class="vt" aria-label="탐라(가제)"><span aria-hidden="true">탐라</span><small aria-hidden="true">가제</small></h2>', html)
        self.assertIn(f'<a class="btn" href="{B}/games/tamna/" data-goatcounter-click="card-tamna">이 게임 보기</a>', html)
        out = panel(B, GOHYANG)
        self.assertNotIn("<small aria-hidden", out)
        self.assertIn('<a class="btn" href="https://gohyang.town" data-goatcounter-click="card-gohyang" rel="noopener">gohyang.town ↗</a>', out)
        self.assertIn('<span class="seal">운영 중</span>', out)

    def test_panel_picture_modes(self):
        cover = panel(B, {**TAMNA, "hero_media_mobile": "static/art/m.webp", "card_image": "static/art/c.webp"}, eager=True)
        self.assertIn('<section class="panel panel-cover" id="p-tamna">', cover)
        self.assertIn(f'src="{B}/static/art/m.webp"', cover)
        self.assertNotIn("panel-blur", cover)
        self.assertEqual(cover.count('fetchpriority="high"'), 1)
        frame = panel(B, {**CURVY, "card_image": "static/art/c.webp", "platform": "2D 도트"})
        self.assertIn('class="panel panel-frame"', frame)
        self.assertEqual(frame.count(f'src="{B}/static/art/c.webp"'), 2)
        self.assertIn('<img class="panel-blur"', frame)
        self.assertIn('<img class="panel-pic"', frame)
        self.assertNotIn("fetchpriority", frame)
        self.assertEqual(frame.count('loading="lazy"'), 2)
        self.assertIn("<small>2D 도트</small>", frame)

    def test_panel_without_picture_has_no_placeholder_text(self):
        html = panel(B, CURVY)
        self.assertIn('class="panel panel-bare"', html)
        self.assertNotIn("<img", html)
        self.assertNotIn("준비", html)
        self.assertIn('class="vt"', html)
        self.assertIn('<span class="seal">개발 중</span>', html)
        self.assertNotIn("<small>", html)  # 플랫폼이 없으면 그 줄도 없다

    def test_panel_heading_and_cta(self):
        self.assertIn('<h1 class="vt" aria-label="탐라(가제)">', panel(B, TAMNA, heading="h1"))
        self.assertNotIn('class="btn"', panel(B, TAMNA, cta=""))
        own = panel(B, TAMNA, cta='<a class="btn" href="#x">가</a>')
        self.assertIn('<a class="btn" href="#x">가</a>', own)
        self.assertNotIn("이 게임 보기", own)

    def test_panel_clip_has_no_src(self):
        html = panel(B, {**TAMNA, "card_image": "static/art/k.webp", "card_video": "media/previews/tamna.mp4"})
        self.assertIn(f'<video class="card-video panel-clip" data-src="{B}/media/previews/tamna.mp4" poster="{B}/static/art/k.webp"', html)
        self.assertIn('preload="none"', html)
        video = html[html.index("<video"):html.index("</video>")]
        self.assertNotIn(" src=", video)

    def test_pieces_escape_values(self):
        g = {"slug": "x", "name": "<b>이름</b>", "summary": 'a"b<i>', "status": "개발 중", "url": 'https://e.com/?a="b"'}
        for html in (panel(B, g), other_games_rail(B, [g, TAMNA], "tamna")):
            self.assertNotIn("<b>", html)
            self.assertNotIn("<i>", html)
            self.assertNotIn('a="b"', html)


class ListPiecesTest(unittest.TestCase):
    def test_date_seal_and_patch_list(self):
        self.assertEqual(date_seal("2026-11-25"), '<time class="seal seal-date" datetime="2026-11-25"><b>11.25</b><i>2026</i></time>')
        logs = [log("2026-11-26"), log("2026-11-24", game="curvy")]
        html = patch_list(B, logs)
        self.assertTrue(html.startswith('<ul class="patch">'))
        self.assertEqual(html.count("<li>"), 2)
        self.assertLess(html.index("2026-11-26"), html.index("2026-11-24"))
        self.assertIn(f'<a href="{B}/log/curvy/2026-11-24/">', html)
        self.assertIn('<span class="t">제목 2026-11-26</span>', html)
        self.assertNotIn('class="g"', html)
        named = patch_list(B, logs, {"tamna": "탐라(가제)", "curvy": "curvy(가칭)"})
        self.assertIn('<span class="g">curvy(가칭)</span>', named)
        self.assertEqual(patch_list(B, []), "")

    def test_latest_card(self):
        self.assertEqual(latest_card(B, None, ""), "")
        html = latest_card(B, log("2026-11-26"), "탐라(가제)")
        self.assertIn(f'<a class="latest" href="{B}/log/tamna/2026-11-26/">', html)
        self.assertIn('<strong class="sf">제목 2026-11-26</strong>', html)
        self.assertIn('<span class="g">탐라(가제)</span>', html)
        self.assertIn("seal-date", html)
        self.assertIn("읽기", html)
        self.assertNotIn("<img", html)
        self.assertIn(f'<img src="{B}/thumbs/card/a.jpg" alt="" loading="lazy" width="640" height="360">', latest_card(B, log("2026-11-26"), "탐라", "thumbs/card/a.jpg"))

    def test_mini_byeongpung_keeps_rail_contract(self):
        html = other_games_rail(B, [TAMNA, {**CURVY, "card_image": "static/art/c.webp"}, GOHYANG], "tamna")
        self.assertIn("ORN의 다른 게임", html)
        self.assertEqual(html.count('class="mini-panel"'), 2)
        self.assertIn(f'<a class="mini-panel" href="{B}/games/curvy/" data-goatcounter-click="other-curvy">', html)
        self.assertIn('<a class="mini-panel" href="https://gohyang.town" rel="noopener" data-goatcounter-click="other-gohyang">', html)
        self.assertNotIn("/games/tamna/", html)
        self.assertIn(f'<img src="{B}/static/art/c.webp" alt="" loading="lazy">', html)
        self.assertIn('<span class="name">curvy(가칭)</span>', html)
        self.assertEqual(other_games_rail(B, [TAMNA], "tamna"), "")


if __name__ == "__main__":
    unittest.main()

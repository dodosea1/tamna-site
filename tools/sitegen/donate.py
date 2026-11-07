"""후원 화면의 받는 방법. 송금 링크가 있으면 QR과 버튼을, 없으면 크티 버튼을 보여 준다."""

from __future__ import annotations

from html import escape

import segno


def is_direct(site: dict) -> bool:
    return bool(site.get("donate_url"))


def donate_block(site: dict) -> str:
    url = site.get("donate_url", "")
    if not url:
        ctee = site.get("ctee_url", "")
        if ctee:
            return f'<a class="button" href="{escape(ctee)}" rel="noopener">크티로 응원하기</a>'
        return '<span class="muted">후원 방법: 준비 중</span>'
    if not url.startswith("https://"):
        raise ValueError("donate_url은 https:// 주소여야 합니다")
    app = escape(site.get("donate_app", "송금 앱"))
    link = escape(url)
    # 어두운 화면에서도 읽히도록 흰 바탕과 여백을 QR에 함께 그린다.
    svg = segno.make(url, error="m").svg_inline(scale=6, border=4, dark="#000", light="#fff", omitsize=True)
    return (
        '<div class="donate">'
        f'<div class="donate-qr" role="img" aria-label="{app} 송금 QR 코드">{svg}</div>'
        '<div class="donate-text">'
        f'<p>휴대폰 카메라로 찍으면 {app} 송금 화면이 열립니다.</p>'
        f'<p><a class="button" href="{link}" rel="noopener">{app}로 보내기</a></p>'
        '<p class="muted small">휴대폰으로 보고 있다면 버튼을 누르세요.</p>'
        '</div></div>'
    )

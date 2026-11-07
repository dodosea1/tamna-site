"""후원 화면의 받는 방법. 계좌나 송금 링크가 있으면 그것을, 없으면 크티 버튼을 보여 준다."""

from __future__ import annotations

import re
from html import escape

import segno


def is_direct(site: dict) -> bool:
    return bool(site.get("donate_url") or site.get("donate_account"))


def _link_part(site: dict) -> str:
    url = site["donate_url"]
    if not url.startswith("https://"):
        raise ValueError("donate_url은 https:// 주소여야 합니다")
    app = escape(site.get("donate_app", "송금 앱"))
    # 어두운 화면에서도 읽히도록 흰 바탕과 여백을 QR에 함께 그린다.
    svg = segno.make(url, error="m").svg_inline(scale=6, border=4, dark="#000", light="#fff", omitsize=True)
    return (
        f'<div class="donate-qr" role="img" aria-label="{app} 송금 QR 코드">{svg}</div>'
        '<div class="donate-text">'
        f'<p>휴대폰 카메라로 찍으면 {app} 송금 화면이 열립니다.</p>'
        f'<p><a class="button" href="{escape(url)}" rel="noopener">{app}로 보내기</a></p>'
        '</div>'
    )


def _account_part(site: dict) -> str:
    number = site["donate_account"]
    bank = site.get("donate_bank", "")
    if not re.fullmatch(r"[0-9-]+", number):
        raise ValueError("donate_account는 숫자와 - 만 쓸 수 있습니다")
    if not bank:
        raise ValueError("donate_account에는 donate_bank가 필요합니다")
    digits = number.replace("-", "")
    return (
        '<div class="donate-account">'
        f'<p class="donate-number">{escape(bank)} <strong>{number}</strong></p>'
        f'<p><button class="button copy" type="button" data-copy="{digits}">계좌번호 복사</button></p>'
        '</div>'
    )


def donate_block(site: dict) -> str:
    if not is_direct(site):
        ctee = site.get("ctee_url", "")
        if ctee:
            return f'<a class="button" href="{escape(ctee)}" rel="noopener">크티로 응원하기</a>'
        return '<span class="muted">후원 방법: 준비 중</span>'
    parts = []
    if site.get("donate_url"):
        parts.append(_link_part(site))
    if site.get("donate_account"):
        parts.append(_account_part(site))
    return '<div class="donate">' + "".join(parts) + "</div>"

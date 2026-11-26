"""기록 카드에 붙이는 작은 그림. 원본(수백 KB)을 그대로 쓰지 않으려고 빌드할 때 줄여 둔다.

Pillow가 없거나 그림을 읽지 못하면 False를 돌려주고, 목록은 그림 없이 나온다(빌드는 멈추지 않는다).
"""

from __future__ import annotations

from pathlib import Path

THUMB_SIZE = (176, 124)
# 첫 화면의 가장 최근 기록 카드. 휴대폰에서 폭 320px쯤으로 보이므로 두 배로 만든다.
CARD_SIZE = (640, 360)


def make_thumb(src: Path, dst: Path, size: tuple[int, int] = THUMB_SIZE) -> bool:
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return False
    try:
        with Image.open(src) as im:
            small = ImageOps.fit(ImageOps.exif_transpose(im).convert("RGB"), size, Image.Resampling.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        small.save(dst, "JPEG", quality=72, optimize=True)
    except (OSError, ValueError):
        return False
    return True

"""기록 목록에 붙이는 작은 그림. 원본(수백 KB)을 목록에 그대로 쓰지 않으려고 빌드할 때 줄여 둔다.

Pillow가 없거나 그림을 읽지 못하면 False를 돌려주고, 목록은 그림 없이 나온다(빌드는 멈추지 않는다).
"""

from __future__ import annotations

from pathlib import Path

# 화면에는 88×62로 보인다. 화소가 촘촘한 휴대폰 화면에 맞춰 두 배로 만든다.
THUMB_SIZE = (176, 124)


def make_thumb(src: Path, dst: Path) -> bool:
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return False
    try:
        with Image.open(src) as im:
            small = ImageOps.fit(ImageOps.exif_transpose(im).convert("RGB"), THUMB_SIZE, Image.Resampling.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        small.save(dst, "JPEG", quality=72, optimize=True)
    except (OSError, ValueError):
        return False
    return True

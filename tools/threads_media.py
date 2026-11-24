"""스레드에 붙일 영상을 만든다(docs/63). 스레드는 GIF를 못 올리므로 MP4(H.264)로 바꾼다.

입력: GIF·MP4·MOV 파일 하나(--src), 또는 게임 캡처 PNG 묶음 폴더(--frames, 파일 이름순).
출력: media/threads/ 아래 MP4와, 눈으로 확인할 낱장 모음 JPG(--sheet).

사용:
  python tools/threads_media.py --src C:/.../play.gif --out media/threads/2026-11-13-skill.mp4 --sheet C:/tmp/sheet.jpg
  python tools/threads_media.py --frames C:/.../shots --fps 20 --out media/threads/2026-11-15-week.mp4
  python tools/threads_media.py --shrink media/threads/2026-11-22-week.mp4   # 이미 있는 영상을 상한 아래로

만든 영상이 TARGET_MAX(9.5MB)를 넘으면 목표 비트레이트 2패스로 다시 줄인다. 스레드 예약은 Chrome 업로드라
10MB까지만 받기 때문이다(2026-11-22 12.97MB 영상으로 이틀 예약 못 함).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_SECONDS = 30
MAX_WIDTH = 1080
MIN_SECONDS = 2.0
TARGET_MAX = int(9.5 * 1024 * 1024)  # Chrome 업로드 한도 10MB보다 여유를 둔다
ROOT = Path(__file__).resolve().parent.parent


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    stream = data["streams"][0]
    return {"width": int(stream["width"]), "height": int(stream["height"]),
            "duration": float(data.get("format", {}).get("duration") or 0)}


def scale_filter() -> str:
    # 너비는 1080 이하로 줄이기만 하고, H.264가 요구하는 짝수 크기로 맞춘다.
    return f"scale='min({MAX_WIDTH},iw)':-2:flags=lanczos,format=yuv420p"


def convert(src: Path | None, frames: Path | None, fps: float, out: Path, max_seconds: float) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    with tempfile.TemporaryDirectory() as tmp:
        if frames:
            pngs = sorted(frames.glob("*.png"))
            if len(pngs) < 2:
                raise SystemExit(f"PNG가 두 장 미만이다: {frames}")
            listing = Path(tmp) / "list.txt"
            listing.write_text("".join(f"file '{p.as_posix()}'\nduration {1 / fps:.6f}\n" for p in pngs), encoding="utf-8")
            cmd += ["-f", "concat", "-safe", "0", "-i", str(listing)]
        else:
            cmd += ["-i", str(src)]
        cmd += ["-t", str(max_seconds), "-an", "-vf", f"{scale_filter()},fps=30", "-c:v", "libx264",
                "-preset", "slow", "-crf", "20", "-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True)


def fit_size(video: Path, limit: int = TARGET_MAX, tries: int = 3) -> bool:
    """video가 limit 바이트를 넘으면 같은 해상도·fps로 목표 비트레이트 2패스 인코딩해 그 자리에 바꿔 넣는다.
    바꿨으면 True. 세 번 줄여도 넘으면 SystemExit."""
    if video.stat().st_size <= limit:
        return False
    duration = probe(video)["duration"] or 1.0
    kbps = int(limit * 8 * 0.92 / duration / 1000)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src.mp4"
        shutil.copyfile(video, src)
        out = Path(tmp) / "out.mp4"
        log = str(Path(tmp) / "pass")
        for _ in range(tries):
            base = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-an", "-c:v", "libx264", "-preset", "slow",
                    "-b:v", f"{kbps}k", "-pix_fmt", "yuv420p", "-passlogfile", log]
            subprocess.run(base + ["-pass", "1", "-f", "null", "-"], check=True)
            subprocess.run(base + ["-maxrate", f"{int(kbps * 1.2)}k", "-bufsize", f"{kbps * 2}k", "-pass", "2",
                                   "-movflags", "+faststart", str(out)], check=True)
            if out.stat().st_size <= limit:
                shutil.copyfile(out, video)
                return True
            kbps = int(kbps * 0.85)
    raise SystemExit(f"{tries}번 줄여도 {limit} 바이트를 넘는다: {video}")


def sheet(video: Path, dest: Path, tiles: int = 6) -> None:
    info = probe(video)
    step = max(info["duration"] / tiles, 0.1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf",
                    f"fps=1/{step:.3f},scale=480:-2,tile=3x2", "-frames:v", "1", str(dest)], check=True)


def main(argv: list[str] | None = None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="스레드용 MP4 만들기")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--shrink", type=Path, help="이미 있는 media/threads/ 영상을 상한 아래로 줄인다")
    src.add_argument("--src", type=Path, help="GIF·MP4·MOV 파일")
    src.add_argument("--frames", type=Path, help="PNG 묶음 폴더")
    p.add_argument("--fps", type=float, default=20.0, help="--frames의 초당 장수(게임 로그에서 잰 값)")
    p.add_argument("--out", type=Path, help="tamna-site 기준 media/threads/....mp4")
    p.add_argument("--max-seconds", type=float, default=MAX_SECONDS)
    p.add_argument("--sheet", type=Path, help="확인용 낱장 모음 JPG 경로")
    args = p.parse_args(argv)
    if not shutil.which("ffmpeg"):
        print("ffmpeg가 없다")
        return 2
    if args.shrink:
        target = args.shrink if args.shrink.is_absolute() else ROOT / args.shrink
        before = target.stat().st_size
        changed = fit_size(target)
        print(json.dumps({"out": str(target), "changed": changed, "mb_before": round(before / 1024 / 1024, 2),
                          "mb": round(target.stat().st_size / 1024 / 1024, 2)}, ensure_ascii=False))
        return 0
    if not args.out:
        print("--out이 필요하다")
        return 2
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if out.suffix.lower() != ".mp4" or "threads" not in out.parts:
        print("출력은 media/threads/ 아래 .mp4여야 한다")
        return 2
    convert(args.src, args.frames, args.fps, out, args.max_seconds)
    fit_size(out)
    info = probe(out)
    if info["duration"] < MIN_SECONDS:
        out.unlink()
        print(f"영상이 {MIN_SECONDS}초보다 짧아 지웠다")
        return 1
    if args.sheet:
        sheet(out, args.sheet)
    size_mb = out.stat().st_size / 1024 / 1024
    print(json.dumps({"out": str(out), "width": info["width"], "height": info["height"],
                      "seconds": round(info["duration"], 2), "mb": round(size_mb, 2),
                      "sheet": str(args.sheet) if args.sheet else ""}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

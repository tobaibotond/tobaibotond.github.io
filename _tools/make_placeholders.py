#!/usr/bin/env python3
"""Generate PLACEHOLDER media for the home grid from the project images.

Creates
  _content/home/strips/  film strips for the right-hand gallery on the home page
  _content/home/loops/   short looping clips used as moving covers (left side)
These only demonstrate the layout; replace them with real material later
(drop new strips into the folder; set "cover_loop" per project in content.json).

Usage:  python _tools/make_placeholders.py
"""
import json
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "_content"
EXT = {".jpg", ".jpeg", ".png", ".webp"}


def project_images(content, slug):
    p = next(p for p in content["projects"] if p["slug"] == slug)
    src = Path(p["source"])
    if not src.is_absolute():
        src = CONTENT / src
    return sorted(f for f in src.iterdir() if f.suffix.lower() in EXT)


def load(path):
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def film_strip(files, out, frames=5, fw=600, fh=450, border=76, start=0):
    """Vertical 16mm-style strip: frames stacked between black perforated borders."""
    gap = 20
    w = fw + border * 2
    h = frames * fh + (frames + 1) * gap
    strip = Image.new("RGB", (w, h), (12, 12, 12))
    d = ImageDraw.Draw(strip)
    for i in range(frames):
        frame = ImageOps.fit(load(files[(start + i) % len(files)]), (fw, fh))
        strip.paste(frame, (border, gap + i * (fh + gap)))
    # Sprocket holes on both sides
    step = 64
    for y in range(16, h - 32, step):
        for x in (20, w - border + 20):
            d.rounded_rectangle([x, y, x + 36, y + 28], radius=6, fill=(236, 236, 230))
    strip.save(out, quality=86)


def loop_video(files, out, seconds=4, fps=12, width=480, ratio=3 / 4):
    """Flickering slideshow loop (muted mp4) built with ffmpeg."""
    if not shutil.which("ffmpeg"):
        print("  ! ffmpeg not found, skipping", out.name)
        return
    rng = random.Random(out.name)
    w, h = width, round(width * ratio)
    with tempfile.TemporaryDirectory() as tmp:
        imgs = [ImageOps.fit(load(f), (w + 24, h + 24)) for f in files]
        for n in range(seconds * fps):
            im = imgs[(n // 3) % len(imgs)]
            dx, dy = rng.randint(0, 24), rng.randint(0, 24)  # gate weave
            im.crop((dx, dy, dx + w, dy + h)).save(Path(tmp) / f"{n:04d}.jpg", quality=90)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(Path(tmp) / "%04d.jpg"),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "28", "-preset", "slow",
             "-movflags", "+faststart", "-an", str(out)],
            check=True,
        )


def main():
    content = json.loads((CONTENT / "content.json").read_text(encoding="utf-8"))
    strips = CONTENT / "home" / "strips"
    loops = CONTENT / "home" / "loops"
    strips.mkdir(parents=True, exist_ok=True)
    loops.mkdir(parents=True, exist_ok=True)

    # Strips of varying length, cycling through the projects
    slugs = [p["slug"] for p in content["projects"]]
    rng = random.Random(7)
    for n in range(18):
        slug = slugs[n % len(slugs)]
        name = f"PLACEHOLDER-strip-{n + 1:02d}.jpg"
        print("-", name)
        film_strip(project_images(content, slug), strips / name, frames=rng.randint(3, 8), start=rng.randint(0, 5))

    # Moving covers for a few projects
    for slug in ("film-01", "film-04", "installation-02", "projekt-01"):
        name = f"PLACEHOLDER-loop-{slug}.mp4"
        print("-", name)
        loop_video(project_images(content, slug), loops / name)


if __name__ == "__main__":
    main()

import json, sys
from pathlib import Path
from PIL import Image, ImageOps

SRC = Path(r"E:/Stuff/SocMed")
OUT = Path(r"E:/Stuff/web")
EXT = {".jpg", ".jpeg", ".png", ".webp"}

PROJECTS = [
    ("film-01", "Film 01", "Films", "Red/Red_001", 2026),
    ("film-02", "Film 02", "Films", "Red/Red_002", 2026),
    ("film-03", "Film 03", "Films", "Red/Red_003", 2025),
    ("film-04", "Film 04", "Films", "Red/Red_004", 2025),
    ("film-05", "Film 05", "Films", "1956-2026/1956_01", 2024),
    ("film-06", "Film 06", "Films", "1956-2026/1956_02", 2024),
    ("installation-01", "Installation 01", "Installation", "Blacks/Black_001", 2026),
    ("installation-02", "Installation 02", "Installation", "Blacks/Black_002", 2025),
    ("installation-03", "Installation 03", "Installation", "Blacks/Black_003", 2024),
    ("installation-04", "Installation 04", "Installation", "Blacks/Black_004", 2023),
    ("projekt-01", "Projekt 01", "Projektek", "Blacks/Black_005", 2026),
    ("projekt-02", "Projekt 02", "Projektek", "Blacks/Black_006", 2025),
    ("projekt-03", "Projekt 03", "Projektek", "Blacks/Black_007", 2024),
]

def save(src, slug, i):
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    name = f"{slug}-{i:02d}.jpg"
    full = im.copy(); full.thumbnail((1600, 1600))
    full.save(OUT / "img/full" / name, quality=84, optimize=True, progressive=True)
    th = im.copy(); th.thumbnail((420, 420))
    th.save(OUT / "img/thumb" / name, quality=78, optimize=True, progressive=True)
    return {"src": name, "w": full.width, "h": full.height}

(OUT / "img/full").mkdir(parents=True, exist_ok=True)
(OUT / "img/thumb").mkdir(parents=True, exist_ok=True)
data = []
for slug, title, cat, folder, year in PROJECTS:
    files = sorted(p for p in (SRC / folder).iterdir() if p.suffix.lower() in EXT)
    imgs = [save(f, slug, i + 1) for i, f in enumerate(files)]
    data.append({"slug": slug, "title": title, "category": cat, "year": year, "images": imgs})
    print(slug, len(imgs))

js = "// Generated portfolio data. Edit titles/texts here.\nwindow.PROJECTS = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"
(OUT / "js").mkdir(exist_ok=True)
(OUT / "js/data.js").write_text(js, encoding="utf-8")

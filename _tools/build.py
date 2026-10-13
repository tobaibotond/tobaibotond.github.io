#!/usr/bin/env python3
"""Build the static portfolio site from _content/content.json.

Generates:
  index.html, info/, <slug>/            first language in site.languages (English)
  hu/index.html, hu/info/, hu/<slug>/   other languages under their code
  404.html, sitemap.xml, robots.txt
  img/   WebP images in 3 sizes (s=420, m=800, l=1600), film strips, og/ share images
  media/ moving covers (home page, left) and local project videos

Maintenance mode (content.json -> "maintenance": {"enabled": true}):
  the public root only gets a temporary "under construction" page (index.html + 404.html)
  with a random project image; the full site is built into _preview/ for local viewing
  (_preview/ is git-ignored, so it is never published).

Images are only re-encoded when the source is newer than the output.
Files in img/, media/ and generated page folders that are no longer produced are removed.

Usage:  python _tools/build.py
"""
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "_content"
MANIFEST = ROOT / "_tools" / ".generated.json"
PREVIEW = "_preview/"
PREFIX = ""  # PREVIEW in maintenance mode: the full site is written there
SIZES = {"s": 420, "m": 800, "l": 1600}
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

# UI strings per language
UI = {
    "hu": {
        "info": "BIO", "email": "E-mail", "other_lang": "English",
        "screenings": "nyilvános vetítések", "play": "Videó lejátszása: {t} (külső lejátszó töltődik be)",
        "img_alt": "{t}, {n}. kép", "open_img": "{t}, {n}. kép nagyítása", "menu": "Index",
        "strip_alt": "Filmszalag {n}", "open_strip": "Filmszalag {n} nagyítása",
        "not_found": "Az oldal nem található.", "back_home": "Vissza a kezdőlapra",
        "info_title": "BIO",
    },
    "en": {
        "info": "BIO", "email": "Email", "other_lang": "Magyar",
        "screenings": "public screenings", "play": "Play video: {t} (loads an external player)",
        "img_alt": "{t}, image {n}", "open_img": "Enlarge {t}, image {n}", "menu": "Index",
        "strip_alt": "Film strip {n}", "open_strip": "Enlarge film strip {n}",
        "not_found": "Page not found.", "back_home": "Back to the home page",
        "info_title": "BIO",
    },
}

produced: set[Path] = set()
e = html.escape


# ---------------------------------------------------------------- helpers
def tr(value, lang):
    """Pick the language variant of a value ({"hu":..,"en":..} or plain)."""
    if isinstance(value, dict):
        return value.get(lang) or value.get("hu") or next(iter(value.values()), "")
    return value if value is not None else ""


def resolve_src(path):
    p = Path(path)
    return p if p.is_absolute() else CONTENT_DIR / p


def out(rel, root=False):
    """Path for a generated file; full-site files go under PREFIX, root=True files to the site root."""
    p = ROOT / (rel if root else PREFIX + rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    produced.add(p.resolve())
    return p


def fresh(src, dst):
    return dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime


def load_image(src):
    return ImageOps.exif_transpose(Image.open(src)).convert("RGB")


def variants(src: Path, base: str, root=False):
    """Write WebP size variants for one image. Returns {key: {src,w,h}}."""
    im = load_image(src)
    w, h = im.size
    res, last_w = {}, None
    for key, maxw in SIZES.items():
        tw = min(maxw, w)
        if tw == last_w:  # source smaller than this size: reuse previous file
            res[key] = res[prev_key]
            continue
        th = round(h * tw / w)
        rel = f"{base}-{key}.webp"
        dst = out(rel, root)
        if not fresh(src, dst):
            im.resize((tw, th), Image.LANCZOS).save(dst, "WEBP", quality=80, method=6)
        res[key] = {"src": rel, "w": tw, "h": th}
        last_w, prev_key = tw, key
    return res


def og_image(src: Path, slug):
    rel = f"img/og/{slug}.jpg"
    dst = out(rel)
    if not fresh(src, dst):
        ImageOps.fit(load_image(src), (1200, 630)).save(dst, quality=84, optimize=True)
    return rel


def srcset(v):
    seen, parts = set(), []
    for item in v.values():
        if item["src"] not in seen:
            seen.add(item["src"])
            parts.append(f'{{R}}{item["src"]} {item["w"]}w')
    return ", ".join(parts)


def img_tag(v, alt, sizes, lazy=True, cls=""):
    s = v["s"]
    lazy_attr = ' loading="lazy"' if lazy else ""
    cls_attr = f' class="{cls}"' if cls else ""
    return (f'<img src="{{R}}{s["src"]}" srcset="{srcset(v)}" sizes="{sizes}" width="{s["w"]}" height="{s["h"]}" '
            f'alt="{e(alt)}"{lazy_attr} decoding="async"{cls_attr}>')


def embed_for(url):
    """Return (kind, src) for a video reference: Vimeo, YouTube or a local file."""
    if not url:
        return None
    m = re.search(r"vimeo\.com/(?:video/)?(\d+)", url)
    if m:
        return "iframe", f"https://player.vimeo.com/video/{m.group(1)}?autoplay=1&dnt=1&title=0&byline=0&portrait=0"
    m = re.search(r"(?:youtu\.be/|v=|embed/)([\w-]{11})", url)
    if m:
        return "iframe", f"https://www.youtube-nocookie.com/embed/{m.group(1)}?autoplay=1&rel=0"
    if url.startswith("http"):
        return "iframe", url
    return "file", url


# ---------------------------------------------------------------- paths
def lang_prefix(lang, default):
    return "" if lang == default else f"{lang}/"


def page_path(kind, lang, default, slug=None):
    """Folder path of a page relative to the site root ('' = root)."""
    pre = lang_prefix(lang, default)
    if kind == "home":
        return pre
    if kind == "info":
        return f"{pre}info/"
    return f"{pre}{slug}/"


# ---------------------------------------------------------------- templates
def head(c, lang, title, desc, path, og, alternates, extra=""):
    site = c["site"]
    base = site["url"].rstrip("/") + "/"
    alt_links = "".join(
        f'\n  <link rel="alternate" hreflang="{l}" href="{base}{p}">' for l, p in alternates.items()
    )
    gc = site.get("goatcounter")
    analytics = (f'\n  <script data-goatcounter="https://{e(gc)}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'
                 if gc else "")
    return f"""<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)}</title>
  <meta name="description" content="{e(desc)}">
  <link rel="canonical" href="{base}{path}">{alt_links}
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{e(tr(site["name"], lang))}">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(desc)}">
  <meta property="og:url" content="{base}{path}">
  <meta property="og:image" content="{base}{og}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="{{R}}favicon.svg" type="image/svg+xml">
  <link rel="icon" href="{{R}}favicon-32.png" sizes="32x32" type="image/png">
  <link rel="apple-touch-icon" href="{{R}}apple-touch-icon.png">
  <link rel="preload" href="{{R}}fonts/hanken-grotesk-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{{R}}css/style.css">
  <script>document.documentElement.classList.add("js")</script>{analytics}{extra}
</head>"""


def nav(c, lang, default, current=None, kind="home", slug=None):
    ui = UI[lang]
    site = c["site"]
    parts = [f"""<header class="nav">
  <div class="nav-top">
    <h1><a href="{{R}}{page_path("home", lang, default)}">{e(tr(site["name"], lang))}</a></h1>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav-menu">{ui["menu"]}</button>
  </div>
  <nav id="nav-menu" class="nav-menu" aria-label="{ui["menu"]}">"""]
    for cat in c["categories"]:
        items = [p for p in c["projects"] if p["category"] == cat["id"]]
        if not items:
            continue
        active = ' class="active" aria-current="page"'
        lis = "".join(
            f'\n        <li><a href="{{R}}{page_path("project", lang, default, p["slug"])}" data-slug="{p["slug"]}"'
            f'{active if p["slug"] == current else ""}>{e(p["title"])}</a></li>'
            for p in items
        )
        parts.append(f"""
    <details data-cat="{cat["id"]}">
      <summary>&nbsp; &nbsp;{e(tr(cat["label"], lang))}</summary>
      <ul>{lis}
      </ul>
    </details>""")
    langs = site["languages"]
    other = next((l for l in langs if l != lang), None)
    info_cur = ' aria-current="page"' if kind == "info" else ""
    lang_link = (f'<br>\n      <a href="{{R}}{page_path(kind, other, default, slug)}" hreflang="{other}" lang="{other}">{ui["other_lang"]}</a>'
                 if other else "")
    parts.append(f"""
    <div class="links">
      <a href="{{R}}{page_path("info", lang, default)}"{info_cur}>{ui["info"]}</a><br>
      <a href="{e(site["instagram"])}" target="_blank" rel="noopener">Instagram</a><br>
      <a href="mailto:{e(site["email"])}">{ui["email"]}</a>{lang_link}
    </div>
  </nav>""")
    parts.append("\n</header>")
    return "".join(parts)


FOOT = """
<footer class="footer">©{year}</footer>
<script src="{{R}}js/main.js" defer></script>
</body>
</html>
"""


def finish(doc, rel_file):
    """Fill the relative-root placeholder and write the page."""
    depth = rel_file.count("/")
    doc = doc.replace("{R}", "../" * depth)
    out(rel_file).write_text(doc, encoding="utf-8")


# ---------------------------------------------------------------- build
def main():
    c = json.loads((CONTENT_DIR / "content.json").read_text(encoding="utf-8"))
    site = c["site"]
    langs = site["languages"]
    default = langs[0]
    year = date.today().year
    global PREFIX
    maintenance = c.get("maintenance", {}).get("enabled", False)
    PREFIX = PREVIEW if maintenance else ""
    if maintenance:
        print("Maintenance mode: public root = temporary page, full site -> _preview/")

    # --- images per project
    print("Images...")
    for p in c["projects"]:
        src_dir = resolve_src(p["source"])
        files = sorted(f for f in src_dir.iterdir() if f.suffix.lower() in IMG_EXT)
        if not files:
            sys.exit(f"No images in {src_dir}")
        p["_files"] = files
        p["_images"] = [variants(f, f"img/{p['slug']}/{i + 1:02d}") for i, f in enumerate(files)]
        p["_og"] = og_image(files[0], p["slug"])
        poster = p.get("video_poster")
        p["_poster"] = variants(resolve_src(poster), f"img/{p['slug']}/poster") if poster else p["_images"][0]
        emb = embed_for(p.get("video"))
        if emb and emb[0] == "file":
            vsrc = resolve_src(emb[1])
            rel = f"media/{p['slug']}/{vsrc.name}"
            dst = out(rel)
            if not fresh(vsrc, dst):
                shutil.copy2(vsrc, dst)
            emb = ("file", rel)
        p["_embed"] = emb
        print(f"  {p['slug']}: {len(files)}")

    home_og = c["projects"][0]["_og"]

    # --- moving covers (left side of the home page)
    for p in c["projects"]:
        p["_loop"] = None
        if p.get("cover_loop"):
            src = resolve_src(p["cover_loop"])
            if not src.exists():
                print(f"  ! missing cover_loop: {src}")
                continue
            rel = f"media/loops/{src.name}"
            dst = out(rel)
            if not fresh(src, dst):
                shutil.copy2(src, dst)
            p["_loop"] = rel

    # --- film strips (right side of the home page): every image in the folder, by file name
    strips = []
    strip_dir = resolve_src(c.get("home", {}).get("strips", "home/strips"))
    if strip_dir.exists():
        files = sorted(f for f in strip_dir.iterdir() if f.suffix.lower() in IMG_EXT)
        strips = [variants(f, f"img/strips/{f.stem}") for f in files]
    print(f"  strips: {len(strips)}")

    # --- static assets
    favicons()
    if PREFIX:
        copy_static()

    for lang in langs:
        ui = UI[lang]
        alts = lambda kind, slug=None: {l: page_path(kind, l, default, slug) for l in langs}

        # Home
        def tile(p, inner, cls="tile"):
            return (f'<a class="{cls}" href="{{R}}{page_path("project", lang, default, p["slug"])}" '
                    f'data-slug="{p["slug"]}" data-label="{e(p["title"])}, {p["year"]}">{inner}</a>')

        def cover(p):
            alt = ui["img_alt"].format(t=p["title"], n=1)
            if p["_loop"]:
                # Muted loop; JS plays it only while visible. Poster = the still cover.
                inner = (f'<video muted loop playsinline preload="none" poster="{{R}}{p["_images"][0]["m"]["src"]}" '
                         f'aria-label="{e(alt)}"><source src="{{R}}{p["_loop"]}" type="video/mp4"></video>')
            else:
                inner = img_tag(p["_images"][0], alt, "(max-width: 760px) 50vw, 13vw", lazy=False)
            return tile(p, inner)

        covers = "\n      ".join(cover(p) for p in c["projects"])
        grid_html = "\n      ".join(
            f'<button type="button" class="zoom strip" data-full="{{R}}{v["l"]["src"]}" '
            f'aria-label="{e(ui["open_strip"].format(n=n + 1))}">'
            f'{img_tag(v, ui["strip_alt"].format(n=n + 1), "(max-width: 760px) 33vw, 10vw")}</button>'
            for n, v in enumerate(strips)
        )

        path = page_path("home", lang, default)
        doc = head(c, lang, tr(site["name"], lang), tr(site["description"], lang), path, home_og, alts("home"))
        doc += f"""
<body data-page="home">
{nav(c, lang, default, kind="home")}
<main>
  <div class="home">
    <div class="index-grid">
      {covers}
    </div>
    <div class="grid">
      {grid_html}
    </div>
  </div>
</main>""" + FOOT.format(year=year)
        finish(doc, path + "index.html")

        # Projects
        for i, p in enumerate(c["projects"]):
            nxt = c["projects"][(i + 1) % len(c["projects"])]
            prv = c["projects"][i - 1]
            t = p["title"]
            desc = tr(p.get("description"), lang)
            details = "<br>\n        ".join(
                (f'<i><b>{e(tr(d["label"], lang))}:</b> {e(tr(d["value"], lang))}</i>' if d.get("italic")
                 else f'<b>{e(tr(d["label"], lang))}:</b> {e(tr(d["value"], lang))}')
                for d in p.get("details", [])
            )
            screenings = "<br>\n        ".join(f"- {e(tr(s, lang))}" for s in p.get("screenings", []))
            text = [f"<b>{e(t)}</b>"]
            if desc:
                text.append(e(desc))
            if details:
                text.append(details)
            if screenings:
                text.append(f'<b>{ui["screenings"]}:</b><br>\n        {screenings}')

            text_html = "<br><br>\n        ".join(text)
            poster = img_tag(p["_poster"], t, "(max-width: 760px) 100vw, 38vw", lazy=False)
            if p["_embed"]:
                kind, src = p["_embed"]
                src_attr = src if kind == "iframe" else "{R}" + src
                media = (f'<div class="video" data-kind="{kind}" data-src="{e(src_attr)}" data-title="{e(t)}">\n'
                         f'        <button type="button" class="video-play" aria-label="{e(ui["play"].format(t=t))}">'
                         f'{poster}<span class="play-icon" aria-hidden="true"></span></button>\n      </div>')
            else:
                media = f'<div class="video still">{poster}</div>'

            figs = "\n    ".join(
                f'<figure id="{n + 1}"><button type="button" class="zoom" data-full="{{R}}{v["l"]["src"]}" '
                f'aria-label="{e(ui["open_img"].format(t=t, n=n + 1))}">'
                f'{img_tag(v, ui["img_alt"].format(t=t, n=n + 1), "(max-width: 760px) 50vw, 19vw")}</button></figure>'
                for n, v in enumerate(p["_images"])
            )
            path = page_path("project", lang, default, p["slug"])
            meta_desc = desc or tr(site["description"], lang)
            doc = head(c, lang, f"{t} — {tr(site['name'], lang)}", meta_desc, path, p["_og"], alts("project", p["slug"]))
            doc += f"""
<body data-page="project">
{nav(c, lang, default, current=p["slug"], kind="project", slug=p["slug"])}
<main>
  <article>
    <section class="project-top">
      {media}
      <div class="project-text">
        {text_html}
      </div>
    </section>
    <div class="stack">
    {figs}
    </div>
  </article>
  <nav class="pager" aria-label="{ui["menu"]}">
    <a href="{{R}}{page_path("project", lang, default, prv["slug"])}">← {e(prv["title"])}</a>
    <a href="{{R}}{page_path("project", lang, default, nxt["slug"])}">{e(nxt["title"])} →</a>
  </nav>
</main>""" + FOOT.format(year=year)
            finish(doc, path + "index.html")

        # Info
        path = page_path("info", lang, default)
        doc = head(c, lang, f"{ui['info_title']} — {tr(site['name'], lang)}", tr(site["description"], lang), path, home_og, alts("info"))
        doc += f"""
<body data-page="info">
{nav(c, lang, default, kind="info")}
<main>
  <section class="info">
    {tr(c.get("info"), lang)}
    <p><a href="mailto:{e(site["email"])}">{e(site["email"])}</a></p>
  </section>
</main>""" + FOOT.format(year=year)
        finish(doc, path + "index.html")

    # 404 (served from any URL depth, so links are absolute to the site root)
    ui = UI[default]
    base_path = urlparse(site["url"]).path.rstrip("/") + "/"
    doc = head(c, default, f"404 — {tr(site['name'], default)}", ui["not_found"], "404.html", home_og, {},
               extra=f'\n  <base href="{base_path}">')
    doc += f"""
<body data-page="404">
{nav(c, default, default, kind="home")}
<main>
  <section class="info">
    <p>{ui["not_found"]}</p>
    <p><a href="./">{ui["back_home"]}</a></p>
  </section>
</main>""" + FOOT.format(year=year)
    out("404.html").write_text(doc.replace("{R}", ""), encoding="utf-8")

    # CNAME for GitHub Pages when the site runs on its own domain
    host = urlparse(site["url"]).hostname or ""
    if host and not host.endswith("github.io") and host != "example.com":
        out("CNAME", root=True).write_text(host + "\n", encoding="utf-8")

    # sitemap + robots
    base = site["url"].rstrip("/") + "/"
    urls = []
    for lang in langs:
        urls.append(page_path("home", lang, default))
        urls.append(page_path("info", lang, default))
        urls += [page_path("project", lang, default, p["slug"]) for p in c["projects"]]
    if maintenance:
        out("robots.txt", root=True).write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
        build_soon(c)
    else:
        out("sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"  <url><loc>{base}{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
        out("robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8")

    cleanup(c, langs, default)
    print(f"Done: {len(c['projects'])} projects x {len(langs)} languages.")


def favicons():
    """Simple mark: a filled circle. Replace favicon.svg / the PNGs with your own if you like."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
           '<style>circle{fill:#000}@media (prefers-color-scheme:dark){circle{fill:#fff}}</style>'
           '<circle cx="16" cy="16" r="11"/></svg>\n')
    dst = out("favicon.svg", root=True)
    if not dst.exists():
        dst.write_text(svg, encoding="utf-8")
    for name, size, pad in (("favicon-32.png", 32, 5), ("apple-touch-icon.png", 180, 40)):
        dst = out(name, root=True)
        if dst.exists():
            continue
        from PIL import ImageDraw
        im = Image.new("RGB", (size * 4, size * 4), "white")
        ImageDraw.Draw(im).ellipse([pad * 4, pad * 4, (size - pad) * 4, (size - pad) * 4], fill="black")
        im.resize((size, size), Image.LANCZOS).save(dst)


def copy_static():
    """The preview in _preview/ needs its own copy of the hand-written assets."""
    files = [f for d in ("css", "js", "fonts") for f in (ROOT / d).rglob("*") if f.is_file()]
    files += [ROOT / n for n in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png")]
    for f in files:
        dst = out(str(f.relative_to(ROOT)).replace("\\", "/"))
        if not fresh(f, dst):
            shutil.copy2(f, dst)


SOON_TEXT = "This website is under construction. Please check back soon."

INSTAGRAM_ICON = ('<svg viewBox="0 0 24 24" width="1em" height="1em" aria-hidden="true" fill="none" '
                  'stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5"/>'
                  '<circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1.2" fill="currentColor" stroke="none"/></svg>')


def build_soon(c):
    """Temporary public page: a random project image (links to Instagram) with an under-construction note."""
    site, m = c["site"], c.get("maintenance", {})
    name = tr(site["name"], "en")
    pool = [f for p in c["projects"] for f in p["_files"]]
    count = m.get("count", 24)
    chosen = pool[:: max(1, len(pool) // count)][:count]
    imgs = [variants(f, f"img/soon/{i + 1:02d}", root=True) for i, f in enumerate(chosen)]
    data = json.dumps([{"src": v["m"]["src"], "srcset": srcset(v).replace("{R}", ""),
                        "w": v["m"]["w"], "h": v["m"]["h"]} for v in imgs])
    text = tr(m.get("text", SOON_TEXT), "en")
    insta = site.get("instagram", "")
    has_insta = insta.rstrip("/") not in ("", "https://instagram.com", "https://www.instagram.com")
    handle = urlparse(insta).path.rstrip("/")  # e.g. /tobai.botond
    base_path = urlparse(site["url"]).path.rstrip("/") + "/"
    first = imgs[0]["m"]

    photo = (f'<img id="soon-img" alt="Work by {e(name)}" sizes="(max-width: 760px) 90vw, 56vh">\n'
             f'    <noscript><img src="{first["src"]}" width="{first["w"]}" height="{first["h"]}" alt="Work by {e(name)}"></noscript>')
    if has_insta:
        link = f'href="{e(insta)}" target="_blank" rel="noopener"'
        photo = (f'<a class="soon-photo" {link} aria-label="{e(name)} on Instagram">\n    {photo}\n    </a>\n'
                 f'    <a class="soon-insta" {link}>{INSTAGRAM_ICON}<span>{e(handle)}</span></a>')

    def page(extra_head=""):
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(name)} — under construction</title>
  <meta name="robots" content="noindex">
  <meta name="description" content="{e(name)}: website under construction.">{extra_head}
  <link rel="icon" href="favicon.svg" type="image/svg+xml">
  <link rel="icon" href="favicon-32.png" sizes="32x32" type="image/png">
  <link rel="apple-touch-icon" href="apple-touch-icon.png">
  <link rel="preload" href="fonts/hanken-grotesk-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="css/style.css">
  <style>
    .soon-wrap {{ min-height: 100vh; margin: 0; display: flex; align-items: center; justify-content: center; padding: var(--pad); }}
    /* Box width = displayed image width (set from the image ratio by the script below),
       so the text line above never sticks out past the image */
    .soon-box {{ width: min(56vh, 90vw); }}
    .soon-text {{ margin: 0 0 0.6rem; }}
    .soon-img {{ margin: 0; }}
    .soon-img img {{ width: 100%; height: auto; background: var(--placeholder); }}
    .soon-photo {{ display: block; }}
    .soon-photo:hover img {{ opacity: 0.9; }}
    .soon-insta {{ display: inline-flex; align-items: center; gap: 0.4em; margin-top: 0.6rem; }}
    .soon-insta:hover {{ color: var(--ink-3); }}
  </style>
</head>
<body>
<main class="soon-wrap">
  <div class="soon-box">
    <p class="soon-text">{text}</p>
    <figure class="soon-img">
    {photo}
    </figure>
  </div>
</main>
<script>
  // A different image on every visit
  (function () {{
    var all = {data};
    var x = all[Math.floor(Math.random() * all.length)];
    var img = document.getElementById("soon-img");
    // At most 70% of the screen height and 90% of its width
    document.querySelector(".soon-box").style.width = "min(" + (70 * x.w / x.h).toFixed(2) + "vh, 90vw)";
    img.width = x.w;
    img.height = x.h;
    img.srcset = x.srcset;
    img.src = x.src;
  }})();
</script>
</body>
</html>
"""

    out("index.html", root=True).write_text(page(), encoding="utf-8")
    # 404: same page; <base> keeps asset paths working at any URL depth
    out("404.html", root=True).write_text(page(f'\n  <base href="{base_path}">'), encoding="utf-8")
    print(f"  temporary page: {len(imgs)} images")


def cleanup(c, langs, default):
    """Remove generated files that were not produced by this build."""
    asset_dirs = ("img", "media", PREVIEW + "img", PREVIEW + "media")
    for d in asset_dirs:
        for f in (ROOT / d).rglob("*") if (ROOT / d).exists() else []:
            if f.is_file() and f.resolve() not in produced:
                f.unlink()
    # Page folders from the previous build that no longer exist (e.g. renamed slugs)
    old = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []
    now = sorted({str(p.relative_to(ROOT)).replace("\\", "/") for p in produced if p.suffix == ".html"})
    for rel in set(old) - set(now):
        f = ROOT / rel
        if f.exists():
            f.unlink()
            # Remove now-empty page folders (e.g. hu/film-01/, then hu/)
            d = f.parent
            while d != ROOT:
                try:
                    d.rmdir()
                except OSError:
                    break
                d = d.parent
    MANIFEST.write_text(json.dumps(now, indent=1))
    for name in ("sitemap.xml", "robots.txt", "404.html", "CNAME"):
        f = ROOT / name
        if f.exists() and f.resolve() not in produced:
            f.unlink()
    if not PREFIX and (ROOT / PREVIEW).exists():
        shutil.rmtree(ROOT / PREVIEW)
    for d in sorted((ROOT / x for x in asset_dirs), reverse=True):
        for sub in sorted(d.rglob("*"), reverse=True) if d.exists() else []:
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()
        if d.exists() and not any(d.iterdir()):
            d.rmdir()


if __name__ == "__main__":
    main()

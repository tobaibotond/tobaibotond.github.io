# Portfólió weboldal

Statikus oldal: nincs szerver, nincs adatbázis. GitHub Pagesre vagy bármilyen tárhelyre feltölthető úgy, ahogy van.

## Hogyan működik?

A tartalom egyetlen fájlban van: **`_content/content.json`**. Ebből a `_tools/build.py` legyártja az összes oldalt és képet. **Szerkesztés után mindig futtasd le:**

```
python _tools/build.py
```

(Python 3.10+ és Pillow kell: `pip install pillow`. Videó-borítóképhez ffmpeg.)

Megnézni: dupla katt az `index.html`-re, vagy pontosabb előnézethez:

```
python -m http.server 8000
```

majd böngészőben: http://localhost:8000

## Mappák

| Mappa / fájl | Mi van benne | Kézzel szerkeszted? |
|---|---|---|
| `_content/content.json` | minden szöveg, projekt, beállítás | **igen** |
| `_content/home/strips/`, `_content/home/loops/` | a kezdőlap filmszalagjai és mozgó borítói | **igen**, ide teszed a fájlokat |
| `css/style.css`, `js/main.js` | kinézet, működés | ha a dizájnon változtatnál |
| `_tools/` | build script, helykitöltő-generátor | nem |
| `index.html`, `hu/`, `film-01/`… , `img/`, `media/`, `404.html`, `sitemap.xml` | **generált**, minden buildnél felülíródik | **nem** |

Az `_` kezdetű mappákat a GitHub Pages nem teszi közzé.

## Gyakori teendők

### Új projekt
Másolj le egy projektet a `content.json` `projects` listájában, és írd át:

- `slug`: ez lesz a címe (`domain.hu/slug/`), csak kisbetű, szám, kötőjel
- `title`, `year`, `category` (`films` / `installation` / `projects`)
- `source`: a képek mappája (abszolút útvonal vagy a `_content`-hez viszonyított). A képek **fájlnév szerint** rendeződnek, az első lesz a borító.

### Videó
`"video"` mezőbe a Vimeo vagy YouTube link (pl. `https://vimeo.com/123456`), vagy egy saját mp4 útvonala a `_content`-en belül (pl. `"videos/film-01.mp4"`). Ha nincs videó: `"video": null`, ilyenkor az első kép áll a helyén.
A videó csak kattintásra töltődik be (gyorsabb oldal, nincs süti a látogatónál). A borítókép alapból a projekt első képe, más képhez: `"video_poster": "posters/film-01.jpg"`.

### Szövegek két nyelven
Minden szöveg lehet sima szöveg (mindkét nyelven ugyanaz), vagy `{"hu": "...", "en": "..."}`. Az angol a fő nyelv (`/`), a magyar a `/hu/` alatt van. Ezt a `site.languages` sorrendje dönti el (az első a fő nyelv). A név is nyelvenként adható meg: `"name": {"en": "Botond Tobai", "hu": "Tobai Botond"}`.

### Kezdőlap
- **Bal oldal: projektborítók.** Alapból a projekt első képe. Mozgó borítóhoz add meg a projektnél: `"cover_loop": "home/loops/film-01.mp4"` (`null` = állókép). A videó némítva, ismétlődve megy, csak amikor látszik. Ajánlott: 4:3 arány, 480–720 px széles, 3–6 mp, H.264 mp4 hang nélkül, kb. 0,5 MB alatt.
- **Jobb oldal: filmszalagok.** A `_content/home/strips/` mappa **összes képe**, fájlnév szerinti sorrendben (pl. `01-…jpg`, `02-…jpg`). Nem linkek: kattintásra nagyítóban nyílnak meg, lapozhatók. Bármilyen arányú kép jó; a nagyon magasakat a nagyító görgethetően, olvasható szélességben mutatja. Javasolt min. 600 px szélesség.

**A `PLACEHOLDER-` kezdetű fájlok csak minták** (a `_tools/make_placeholders.py` generálta őket a projektképekből). Cseréld le őket: töröld a mintákat a `strips/` mappából és tedd be a sajátjaidat; a mozgó borítóknál írd át a `cover_loop` útvonalat. Utána `python _tools/build.py`.

### Ideiglenes oldal („under construction”)
A `content.json` → `maintenance.enabled`:
- `true`: a domainen csak egy ideiglenes oldal látszik (név, „under construction” szöveg és minden betöltéskor egy véletlen kép a projektekből). A teljes oldal ilyenkor a `_preview/` mappába készül: helyben a `_preview/index.html`-lel nézhető meg, de **nem kerül fel** a GitHubra.
- `false`: a teljes oldal megy élesbe, a `_preview/` mappa törlődik.

A szöveg a `maintenance.text` alatt írható át, a képek száma a `maintenance.count`-tal állítható. Az e-mail és az Instagram link csak akkor jelenik meg, ha a `site.email` / `site.instagram` valódi címre van átírva. Átállítás után: `python _tools/build.py`, majd feltöltés.

### Megosztási előnézet, domain
`site.url`: a végleges cím (pl. `https://www.domained.hu`). Ebből készülnek a Facebook/Instagram/Messenger előnézeti linkek, a `sitemap.xml` és a 404-es oldal hivatkozásai. **Élesítés előtt állítsd be!**

### Látogatottság-mérés (opcionális, sütimentes)
Regisztrálj a [GoatCounter](https://www.goatcounter.com)-en, és a `site.goatcounter` mezőbe írd a kódodat (pl. `"nevem"`). Üresen hagyva nincs mérés.

### Ikon (favicon)
`favicon.svg`, `favicon-32.png`, `apple-touch-icon.png` a gyökérben. Ha lecseréled őket, a build nem írja felül.

## Betűtípus
Hanken Grotesk (SIL Open Font License, `fonts/OFL.txt`), a saját tárhelyről töltődik, nem a Google-től.

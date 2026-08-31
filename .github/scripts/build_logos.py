#!/usr/bin/env python3
"""Fetch each issuer's own mark, once, into docs/logos/.

The issuer index reads as a list of names without them. With them it reads as a
row of institutions, which is the point: these are other people's credentials,
and their marks are what says so.

Every mark here is named explicitly, with the address it came from, because
guessing was not good enough. Reading a site's favicon and hoping worked for
about half of them and quietly failed for the rest: IBM's site icon is a
generic product tile rather than the eight-bar logo, IIT Bombay's is a sixteen
pixel square, and the LTCE one is an unreadable smudge. Each entry below was
looked at before it was accepted.

Four kinds of source, in order of preference:

  vector   The brand's own single-path mark, drawn in white. Simple-icons
           publishes most of these brands. Microsoft, IBM, LinkedIn and OpenAI
           were withdrawn from the current release after trademark requests, so
           those come from version 9.21.0, the last one that carried them.
  vector   The institution's own SVG, where it publishes one. COEP and
           Cambridge both serve a white version for dark backgrounds, which is
           exactly what a badge needs. Cambridge serves it as a lock-up, so the
           viewBox here trims it to the crest.
  raster   The institution's own PNG, where that is all it serves.
  vector   A plain symbol from Bootstrap Icons, for the two sections that are
           not issuers and so have no mark of their own.

A mark is only ever the compact one. A horizontal lock-up shrunk into a
fourteen pixel square is a smudge, and the badge already prints the name beside
it, so a wordmark would say it twice.

    python .github/scripts/build_logos.py            # fetch what is missing
    python .github/scripts/build_logos.py --all      # fetch everything again

Needs Pillow.
"""

import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "docs" / "logos"
SOURCES = OUT / "sources.json"

SIZE = 256
AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

SI = "https://cdn.simpleicons.org/"
SI9 = "https://cdn.jsdelivr.net/npm/simple-icons@9.21.0/icons/"
BI = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/icons/"

# The mark for each issuer, by the platform name in credentials.json.
#
#   url       where it comes from
#   kind      svg to inline, png to embed
#   viewBox   trims an SVG lock-up down to its mark
#   crop      "left-square" takes the mark off the front of a lock-up
#   ground    a background colour to clear, for an app icon drawn on a tile
#   white     redraws a raster as a white silhouette, for a mark that is one
#             solid colour and would otherwise be dark on a dark badge
#   draw      the mark is redrawn here rather than used as served; see DRAWN
MARKS = {
    "Ankur Warikoo": {
        "url": "https://ankurwarikoo.com/wp-content/uploads/2020/06/"
               "cropped-Copy-of-aw-1.png",
        "kind": "png"},
    "Anthropic courses": {"url": SI + "anthropic/white", "kind": "svg"},
    "Apple": {"url": SI + "apple/white", "kind": "svg"},
    "COE Pune": {
        "url": "https://www.coeptech.ac.in/wp-content/uploads/2023/10/brand-white.svg",
        "kind": "svg"},
    "Colgate Oral Health Network": {
        "url": "https://cdn.dental-tribune.com/cohn/wp-content/themes/cohn/"
               "images/favicon/android-icon-192x192.png",
        "kind": "png"},
    "Coursera": {"url": SI + "coursera/white", "kind": "svg"},
    "Eduonix": {"url": "https://cdn.eduonix.com/assets/images/logo_wht.png",
                "kind": "png", "crop": "left-square"},
    "Google": {"url": SI + "google/white", "kind": "svg"},
    "Harvard Medical School": {
        "url": "https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON"
               "&fallback_opts=TYPE,SIZE,URL&url=http://hms.harvard.edu&size=128",
        "kind": "png"},
    "IBM": {"url": SI9 + "ibm.svg", "kind": "svg"},
    "IIT Bombay": {
        "url": "https://www.iitb.ac.in/themes/custom/iitb_bootstrap/logo.png",
        "kind": "png"},
    "Intel": {"url": SI + "intel/white", "kind": "svg"},
    "Julia Academy": {"url": SI + "julia", "kind": "svg", "draw": "julia"},
    "Kaggle": {"url": "https://www.kaggle.com/static/images/favicon.ico",
               "kind": "png", "ground": "#ffffff", "white": True},
    "LTCE Webinar": {"url": "https://ltce.in/images/ltce-logo-tr.png",
                     "kind": "png"},
    "Linkedin Learning": {"url": SI9 + "linkedin.svg", "kind": "svg"},
    "MathWorks": {"url": "https://in.mathworks.com/favicon.ico", "kind": "png"},
    "Microsoft": {"url": SI9 + "microsoft.svg", "kind": "svg"},
    "Nvidia Deep Learning Institute": {"url": SI + "nvidia/white", "kind": "svg"},
    "OpenAI Academy": {"url": SI9 + "openai.svg", "kind": "svg"},
    "Quizzes": {"url": BI + "question-circle-fill.svg", "kind": "svg"},
    "Simplilearn": {
        "url": "https://www.simplilearn.com/static/frontend/images/favicon/"
               "apple-touch-icon-152x152_v2.png",
        "kind": "png", "ground": "#ffffff", "white": True},
    "Sports": {"url": BI + "trophy-fill.svg", "kind": "svg"},
    "Stanford University": {
        "url": "https://www.stanford.edu/icon1.png", "kind": "png"},
    "Stanford University School of Medicine": {
        "url": "https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON"
               "&fallback_opts=TYPE,SIZE,URL&url=http://medicine.stanford.edu"
               "&size=128",
        "kind": "png"},
    "Terna Engineering College": {
        "url": "https://ternaengg.ac.in/wp-content/uploads/site-icon-300x300.png",
        "kind": "png"},
    "Udemy": {"url": SI + "udemy/white", "kind": "svg"},
    "University of Cambridge": {
        "url": "https://www.cam.ac.uk/themes/custom/fresh/images/interface/"
               "university_logo_white-01.svg",
        "kind": "svg", "viewBox": "0 0 38 44"},
    "VIA Institute on Character": {
        "url": "https://static.viacharacter.org/web/via_brandmark_white.png",
        "kind": "png"},
}

# Julia's three dots are its logo only in its own colours. Flattened to one
# they are three circles that say nothing, which is what was wrong with them.
# Simple-icons draws all three as a single path, so they cannot be coloured
# separately by editing it; the circles are redrawn here at the centres and
# radius that path describes, in the three shades JuliaLang publishes.
DRAWN = {
    "julia": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
              'role="img"><title>Julia</title>'
              '<circle cx="5.569" cy="17.569" r="5.569" fill="#CB3C33"/>'
              '<circle cx="12" cy="6.431" r="5.569" fill="#9558B2"/>'
              '<circle cx="18.431" cy="17.569" r="5.569" fill="#389826"/></svg>'),
}

# Two of these are sections rather than issuers: the quiz records come from
# many small organisers and the sports awards from schools and clubs, so
# neither has a logo of its own. They carry a plain symbol from Bootstrap
# Icons, which is MIT licensed and says what the section is without pretending
# to be anyone's mark.
NO_MARK = set()


def fetch(url, timeout=30):
    host = urllib.parse.urlparse(url).netloc
    request = urllib.request.Request(url, headers={
        "User-Agent": AGENT, "Accept": "*/*", "Referer": f"https://{host}/"})
    with urllib.request.urlopen(request, timeout=timeout) as r:
        return r.read()


def as_svg(data, spec):
    text = data.decode("utf-8", "replace")
    if "<svg" not in text:
        return None
    if spec.get("viewBox"):
        text = re.sub(r'viewBox="[^"]*"', f'viewBox="{spec["viewBox"]}"',
                      text, count=1)
    if spec.get("draw"):
        return DRAWN[spec["draw"]]
    head = text.split(">", 1)[0]
    if "currentColor" in head:
        # Bootstrap draws in currentColor, which resolves to black inside the
        # badge because the mark sits outside the group that sets the text
        # colour. It is pinned to white here instead.
        text = text.replace("currentColor", "#ffffff", 1)
    elif 'fill="' not in head:
        text = text.replace("<svg", '<svg fill="#ffffff"', 1)
    return text


def open_widest(data):
    """The largest frame in the file: an .ico holds several sizes."""
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    if getattr(im, "n_frames", 1) > 1:
        best, area = im.copy(), im.size[0] * im.size[1]
        for frame in range(im.n_frames):
            im.seek(frame)
            if im.size[0] * im.size[1] > area:
                best, area = im.copy(), im.size[0] * im.size[1]
        im = best
    return im.convert("RGBA")


def clear_colour(im, colour):
    """Clear one named background colour, wherever it appears.

    An app icon is a picture of a tile: the mark sits on a white square with
    rounded corners, so the corners are transparent and the ground beneath the
    mark is not. Nothing detects that on its own, so the colour is named.
    """
    from PIL import Image
    want = tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    px, ox = im.load(), out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            near = all(abs(v - want[i]) <= 30 for i, v in enumerate((r, g, b)))
            ox[x, y] = (0, 0, 0, 0) if near else (r, g, b, a)
    return out


def drop_flat_ground(im):
    """Clear a solid background, so the mark is not a tile on the badge."""
    from PIL import Image
    corners = [im.getpixel(p) for p in
               ((0, 0), (im.width - 1, 0), (0, im.height - 1),
                (im.width - 1, im.height - 1))]
    if not all(c[3] > 250 for c in corners):
        return im
    ground = corners[0]
    if any(abs(c[i] - ground[i]) > 12 for c in corners for i in range(3)):
        return im
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    px, ox = im.load(), out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            near = all(abs(v - ground[i]) <= 24 for i, v in enumerate((r, g, b)))
            ox[x, y] = (0, 0, 0, 0) if near else (r, g, b, a)
    return out


def trim(im):
    box = im.getbbox()
    return im.crop(box) if box else im


def left_square(im):
    """The mark off the front of a lock-up: as wide as the artwork is tall."""
    im = trim(im)
    return trim(im.crop((0, 0, min(im.height, im.width), im.height)))


def whiten(im):
    from PIL import Image
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    px, ox = im.load(), out.load()
    for y in range(im.height):
        for x in range(im.width):
            ox[x, y] = (255, 255, 255, px[x, y][3])
    return out


def as_png(data, spec, path):
    """Normalise a raster: one size, trimmed to the mark, transparent ground."""
    from PIL import Image
    im = drop_flat_ground(open_widest(data))
    if spec.get("ground"):
        im = clear_colour(im, spec["ground"])
    if spec.get("crop") == "left-square":
        im = left_square(im)
    im = trim(im)
    if spec.get("white"):
        im = whiten(im)
    ratio = min(SIZE / im.width, SIZE / im.height)
    im = im.resize((max(1, round(im.width * ratio)),
                    max(1, round(im.height * ratio))), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2), im)
    canvas.save(path, "PNG", optimize=True)
    return im.size


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("  Pillow is not installed: pip install pillow")
        return 1

    again = "--all" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    sources = json.loads(SOURCES.read_text(encoding="utf-8")) if SOURCES.exists() else {}

    got = kept = failed = 0
    for name, spec in MARKS.items():
        key = slug(name)
        target = OUT / f"{key}.{spec['kind']}"
        if target.exists() and not again:
            kept += 1
            continue
        try:
            data = fetch(spec["url"])
        except Exception as error:  # noqa: BLE001
            print(f"  {name}: {str(error)[:80]}")
            failed += 1
            continue
        if spec["kind"] == "svg":
            text = as_svg(data, spec)
            if not text:
                print(f"  {name}: the address did not answer with an SVG")
                failed += 1
                continue
            target.write_text(text, encoding="utf-8")
        else:
            try:
                as_png(data, spec, target)
            except Exception as error:  # noqa: BLE001
                print(f"  {name}: {str(error)[:80]}")
                failed += 1
                continue
        # Only one file per issuer: a leftover from an earlier run in the other
        # format would still be found by the badge builder and quietly used.
        other = OUT / f"{key}.{'png' if spec['kind'] == 'svg' else 'svg'}"
        if other.exists():
            other.unlink()
        sources[key] = {"issuer": name, "source": spec["url"],
                        "kind": spec["kind"]}
        got += 1

    for stale in list(OUT.glob("*.png")) + list(OUT.glob("*.svg")):
        if stale.stem not in {slug(n) for n in MARKS}:
            stale.unlink()
            print(f"  removed a mark for an issuer no longer listed: {stale.name}")

    SOURCES.write_text(json.dumps(sources, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    vectors = sum(1 for s in MARKS.values() if s["kind"] == "svg")
    print(f"  {got} fetched, {kept} already held, {failed} that did not answer")
    print(f"  {len(MARKS)} issuers carry a mark, {vectors} of them vector; "
          f"{len(NO_MARK)} carry none by choice")
    return 0


if __name__ == "__main__":
    sys.exit(main())

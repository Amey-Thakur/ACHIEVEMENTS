#!/usr/bin/env python3
"""Render one badge per issuer: its own mark, on its own brand colour.

The badges are SVG. A raster has to pick a resolution and is soft at every
other one, and these are read at twenty pixels on screens with two or three
device pixels to each. An SVG has no resolution to pick.

The mark inside is vector too, wherever a vector exists. Fourteen of them are:
the brands simple-icons carries, and COEP and Cambridge, which publish a white
SVG of their own crest. The rest are embedded rasters, because a raster is all
those issuers serve. Where such a mark is close enough in colour to its badge
to be lost against it, a white chip is drawn behind it.

build_logos.py decides which mark each issuer gets and records where it came
from; this only draws them.

    python .github/scripts/build_issuer_badges.py

Writes docs/badges/*.svg. Needs Pillow to measure the text, the logos from
build_logos.py, and docs/credentials.json for the counts.
"""

import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LOGOS = ROOT / "docs" / "logos"
INDEX = ROOT / "docs" / "credentials.json"
OUT = ROOT / "docs" / "badges"
SQUARES = OUT / "square"

# Proportions rather than pixels: the badge is drawn once and rendered at
# whatever size the page asks for.
HEIGHT = 20
RADIUS = 3
PAD_X = 8
GAP = 6
LOGO = 14
FONT_SIZE = 11

# Each badge is as wide as what it says, and no wider. Padding them all out to
# one width lines the colours up down the column, but it leaves a short name
# sitting in a long empty field of colour, which reads worse than the ragged
# edge it fixes. They are centred in their cells instead.

# The count segment, dark enough for white text over any brand colour.
COUNT_BG = "#30363d"

# The square version, one per issuer, that goes in front of its section
# heading. Twenty pixels is the height of the heading text beside it.
SQUARE = 20
MARK = 13

# A stack the renderer will actually have. The text also carries a textLength,
# so it fits its segment exactly whichever of these wins.
FONT_STACK = "Verdana,DejaVu Sans,Geneva,sans-serif"

# The issuer's own colour, from its brand guidance or its site. A badge in the
# wrong colour is worse than a plain one: it looks official and is not.
BRAND = {
    "Ankur Warikoo": "#6E4AFF",
    "Anthropic": "#D97757",
    "Apple": "#000000",
    "COE Pune": "#0B3C5D",
    "Colgate": "#C8102E",
    "Coursera": "#0056D2",
    "Eduonix": "#F26522",
    "Google": "#4285F4",
    "Harvard Medical School": "#A51C30",
    "IBM": "#0F62FE",
    "IIT Bombay": "#003366",
    "Intel": "#0071C5",
    # Julia blue, not Julia purple: the mark is three dots, one of which
    # is that purple and vanished into the badge behind it.
    "Julia Academy": "#4063D8",
    "Kaggle": "#20BEFF",
    "LTCE Webinar": "#1F4E79",
    "LinkedIn Learning": "#0A66C2",
    "MathWorks": "#0076A8",
    "Microsoft": "#0067B8",
    "NVIDIA DLI": "#76B900",
    "OpenAI Academy": "#412991",
    "Quizzes": "#57606A",
    "Simplilearn": "#F58220",
    "Sports": "#1A7F37",
    "Stanford Medicine": "#8C1515",
    "Stanford University": "#8C1515",
    "Terna Engineering College": "#1F4E79",
    "Udemy": "#A435F0",
    "University of Cambridge": "#0072CF",
    "VIA Institute on Character": "#5B2C6F",
}

# The name on the badge, for the platforms whose folder is named differently.
PLATFORM_NAME = {
    "Anthropic courses": "Anthropic",
    "Colgate Oral Health Network": "Colgate",
    "Linkedin Learning": "LinkedIn Learning",
    "Nvidia Deep Learning Institute": "NVIDIA DLI",
    "Stanford University School of Medicine": "Stanford Medicine",
}

# Where the name on the badge differs from the folder the logo was fetched
# under. Without these, Anthropic and Stanford Medicine came out with no mark.
ALIASES = {
    "Anthropic": "Anthropic courses",
    "Colgate": "Colgate Oral Health Network",
    "LinkedIn Learning": "Linkedin Learning",
    "NVIDIA DLI": "Nvidia Deep Learning Institute",
    "Stanford Medicine": "Stanford University School of Medicine",
}

MEASURE_FONTS = [
    r"C:\Windows\Fonts\verdana.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def measure(text, size):
    """How wide this text will be, so its segment can be cut to fit."""
    from PIL import Image, ImageDraw, ImageFont
    for path in MEASURE_FONTS:
        if Path(path).exists():
            face = ImageFont.truetype(path, size * 10)
            box = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox(
                (0, 0), text, font=face)
            return box[2] / 10
    return len(text) * size * 0.62


def mark_for(display, index):
    """The issuer's mark: the vector if there is one, the icon otherwise."""
    wanted = ALIASES.get(display, display)
    key = slug(wanted)
    for candidate, meta in index.items():
        if meta["issuer"] == wanted or slug(meta["issuer"]) == slug(wanted):
            key = candidate
            break
    vector, raster = LOGOS / f"{key}.svg", LOGOS / f"{key}.png"
    if vector.exists():
        return "vector", vector
    if raster.exists():
        return "raster", raster
    return None, None


def ink(path):
    """The average colour of a raster mark, ignoring what is transparent."""
    from PIL import Image
    with Image.open(path) as im:
        pixels = im.convert("RGBA").tobytes()
    total, seen = [0, 0, 0], 0
    for i in range(0, len(pixels), 4):
        a = pixels[i + 3]
        if a > 60:
            for c in range(3):
                total[c] += pixels[i + c] * a
            seen += a
    return tuple(c // seen for c in total) if seen else (255, 255, 255)


def needs_chip(kind, path, colour):
    """Whether the mark would disappear into the badge behind it.

    Colgate's mark is red and its badge is red; Harvard's crimson shield sits
    on Harvard crimson. Both read as a smudge without something behind them.
    A vector is drawn in white here and never needs one.
    """
    if kind != "raster":
        return False
    want = tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
    got = ink(path)
    distance = sum((a - b) ** 2 for a, b in zip(want, got)) ** 0.5
    return distance < 110


def logo_markup(kind, path, x, y, size):
    """The mark, placed.

    A vector is nested as its own svg so its viewBox does the scaling, which
    is what lets a 24 by 24 icon and a 512 by 512 one sit at the same size
    without either being measured here.
    """
    if kind == "vector":
        source = path.read_text(encoding="utf-8")
        box = re.search(r'viewBox="([^"]+)"', source)
        # The colour is set on the source's own root element, which is the tag
        # being replaced here. Losing it left every path filled with the
        # default black: invisible on Apple's black badge, and wrong on the
        # other eight. It is carried across explicitly.
        colour = re.search(r'<svg[^>]*\bfill="([^"]+)"', source)
        inner = re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", source, flags=re.S)
        inner = re.sub(r"<title>.*?</title>", "", inner, flags=re.S)
        view = box.group(1) if box else "0 0 24 24"
        return (f'<svg x="{x}" y="{y}" width="{size}" height="{size}" '
                f'viewBox="{view}" fill="{colour.group(1) if colour else "#ffffff"}">'
                f'{inner}</svg>')
    data = base64.b64encode(path.read_bytes()).decode()
    return (f'<image x="{x}" y="{y}" width="{size}" height="{size}" '
            f'href="data:image/png;base64,{data}"/>')


def build(display, colour, tally, kind, path):
    """One badge, cut to what it says."""
    name_w = measure(display, FONT_SIZE)
    tally_w = measure(tally, FONT_SIZE)
    left = round(PAD_X + (LOGO + GAP if path else 0) + name_w + PAD_X, 1)
    count_w = round(tally_w + PAD_X * 2, 1)
    width = round(left + count_w, 1)
    baseline = round(HEIGHT / 2 + FONT_SIZE * 0.35, 1)

    logo = logo_markup(kind, path, PAD_X, (HEIGHT - LOGO) / 2, LOGO) if path else ""
    if path and needs_chip(kind, path, colour):
        pad, top = 1.5, (HEIGHT - LOGO) / 2 - 1.5
        logo = (f'<rect x="{PAD_X - pad}" y="{top}" width="{LOGO + pad * 2}" '
                f'height="{LOGO + pad * 2}" rx="3" fill="#ffffff"/>{logo}')
    name_x = PAD_X + (LOGO + GAP if path else 0)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" \
height="{HEIGHT}" viewBox="0 0 {width} {HEIGHT}" role="img" \
aria-label="{escape(display)}: {escape(tally)}">
<title>{escape(display)}: {escape(tally)}</title>
<linearGradient id="g" x2="0" y2="100%">
<stop offset="0" stop-color="#fff" stop-opacity=".12"/>
<stop offset="1" stop-opacity=".12"/>
</linearGradient>
<clipPath id="c"><rect width="{width}" height="{HEIGHT}" rx="{RADIUS}"/></clipPath>
<g clip-path="url(#c)">
<rect width="{left}" height="{HEIGHT}" fill="{colour}"/>
<rect x="{left}" width="{count_w}" height="{HEIGHT}" fill="{COUNT_BG}"/>
<rect width="{width}" height="{HEIGHT}" fill="url(#g)"/>
</g>
{logo}
<g fill="#ffffff" font-family="{FONT_STACK}" font-size="{FONT_SIZE}" font-weight="bold">
<text x="{name_x}" y="{baseline}" textLength="{round(name_w, 1)}" \
lengthAdjust="spacingAndGlyphs">{escape(display)}</text>
<text x="{round(left + count_w / 2, 1)}" y="{baseline}" text-anchor="middle" \
textLength="{round(tally_w, 1)}" lengthAdjust="spacingAndGlyphs">{escape(tally)}</text>
</g>
</svg>
'''


def square(display, colour, kind, path):
    """The same mark again, as a small square, for the section headings.

    A bare logo cannot go in a heading: half of them are drawn in white and
    would vanish on a light page, the other half in dark ink and would vanish
    on a dark one. On its own brand colour a mark reads either way, and it ties
    the heading to the badge for the same issuer in the index above.
    """
    logo = logo_markup(kind, path, (SQUARE - MARK) / 2, (SQUARE - MARK) / 2,
                       MARK) if path else ""
    if path and needs_chip(kind, path, colour):
        logo = (f'<rect x="1" y="1" width="{SQUARE - 2}" height="{SQUARE - 2}" '
                f'rx="{RADIUS - 1}" fill="#ffffff"/>{logo}')
    initial = ""
    if not path:
        initial = (f'<text x="{SQUARE / 2}" y="{SQUARE * 0.72}" '
                   f'text-anchor="middle" font-family="{FONT_STACK}" '
                   f'font-size="{SQUARE * 0.62}" font-weight="bold" '
                   f'fill="#ffffff">{escape(display[0])}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{SQUARE}" \
height="{SQUARE}" viewBox="0 0 {SQUARE} {SQUARE}" role="img" \
aria-label="{escape(display)}">
<title>{escape(display)}</title>
<linearGradient id="g" x2="0" y2="100%">
<stop offset="0" stop-color="#fff" stop-opacity=".12"/>
<stop offset="1" stop-opacity=".12"/>
</linearGradient>
<rect width="{SQUARE}" height="{SQUARE}" rx="{RADIUS}" fill="{colour}"/>
<rect width="{SQUARE}" height="{SQUARE}" rx="{RADIUS}" fill="url(#g)"/>
{logo}{initial}
</svg>
'''


def main():
    try:
        from PIL import ImageFont  # noqa: F401
    except ImportError:
        print("  Pillow is not installed: pip install pillow")
        return 1

    sources = LOGOS / "sources.json"
    index = json.loads(sources.read_text(encoding="utf-8")) if sources.exists() else {}
    data = json.loads(INDEX.read_text(encoding="utf-8"))

    counts = {}
    for cred in data["credentials"]:
        name = PLATFORM_NAME.get(cred["platform"], cred["platform"])
        counts[name] = counts.get(name, 0) + 1

    OUT.mkdir(parents=True, exist_ok=True)
    SQUARES.mkdir(parents=True, exist_ok=True)
    for stale in list(OUT.glob("*.png")) + list(SQUARES.glob("*.png")):
        stale.unlink()

    marks = {d: mark_for(d, index) for d in BRAND}
    vector = raster = plain = 0
    for display, colour in sorted(BRAND.items()):
        kind, path = marks[display]
        # One number, always the same number: how many credentials this
        # issuer awarded. Showing the verifiable count beside it on some
        # badges and not others made the row read unevenly.
        tally = str(counts.get(display, 0))
        (OUT / f"{slug(display)}.svg").write_text(
            build(display, colour, tally, kind, path), encoding="utf-8")
        (SQUARES / f"{slug(display)}.svg").write_text(
            square(display, colour, kind, path), encoding="utf-8")
        vector += kind == "vector"
        raster += kind == "raster"
        plain += kind is None

    print(f"  {vector + raster + plain} badges written to "
          f"{OUT.relative_to(ROOT).as_posix()}, every one an SVG, "
          f"each with a square twin for its section heading")
    print(f"  {vector} carry a vector mark, {raster} an embedded icon, "
          f"{plain} are colour only")
    return 0


if __name__ == "__main__":
    sys.exit(main())

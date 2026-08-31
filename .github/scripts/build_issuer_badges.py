#!/usr/bin/env python3
"""Render one badge per issuer: its own mark, on its own brand colour.

The badges are SVG. A raster has to pick a resolution and is soft at every
other one, and these are read at twenty pixels on screens with two or three
device pixels to each. An SVG has no resolution to pick.

The mark inside is vector too, wherever a vector exists. Simple-icons publishes
nine of these issuers as a single path and that path is inlined. It does not
publish Microsoft, IBM, LinkedIn, MathWorks or OpenAI, all removed after
trademark requests, and it has never carried the universities; for those the
issuer's own icon is embedded, which is a raster because that is all their
sites serve.

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

# Proportions rather than pixels: the badge is drawn once and rendered at
# whatever size the page asks for.
HEIGHT = 20
RADIUS = 3
PAD_X = 8
GAP = 6
LOGO = 14
FONT_SIZE = 11

# Every badge is the same width, and the count segment starts at the same
# place in all of them. Sized to the longest issuer name and the largest
# count, they line up down the column and across the row; sized to their own
# contents they cannot, however the cells around them are aligned.
COUNT_W = 38

# The count segment, dark enough for white text over any brand colour.
COUNT_BG = "#30363d"

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
    "Julia Academy": "#9558B2",
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


def build(display, colour, tally, kind, path, left):
    """One badge, at the width every badge shares.

    `left` is where the count segment begins and is the same for all of them,
    so the colours break on one line down the whole grid. Sized to its own
    contents, a badge cannot line up with its neighbours however the cells
    around it are aligned, which is what made the index look ragged.
    """
    name_w = measure(display, FONT_SIZE)
    tally_w = measure(tally, FONT_SIZE)
    width = round(left + COUNT_W, 1)
    baseline = round(HEIGHT / 2 + FONT_SIZE * 0.35, 1)

    logo = logo_markup(kind, path, PAD_X, (HEIGHT - LOGO) / 2, LOGO) if path else ""
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
<rect x="{left}" width="{COUNT_W}" height="{HEIGHT}" fill="{COUNT_BG}"/>
<rect width="{width}" height="{HEIGHT}" fill="url(#g)"/>
</g>
{logo}
<g fill="#ffffff" font-family="{FONT_STACK}" font-size="{FONT_SIZE}" font-weight="bold">
<text x="{name_x}" y="{baseline}" textLength="{round(name_w, 1)}" \
lengthAdjust="spacingAndGlyphs">{escape(display)}</text>
<text x="{round(left + COUNT_W / 2, 1)}" y="{baseline}" text-anchor="middle" \
textLength="{round(tally_w, 1)}" lengthAdjust="spacingAndGlyphs">{escape(tally)}</text>
</g>
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
    for stale in OUT.glob("*.png"):
        stale.unlink()

    # The shared split point: the longest name, with room for a mark, so no
    # badge has to be wider than any other.
    marks = {d: mark_for(d, index) for d in BRAND}
    left = round(max(PAD_X + (LOGO + GAP if marks[d][1] else 0)
                     + measure(d, FONT_SIZE) + PAD_X for d in BRAND), 1)

    vector = raster = plain = 0
    for display, colour in sorted(BRAND.items()):
        kind, path = marks[display]
        # One number, always the same number: how many credentials this
        # issuer awarded. Showing the verifiable count beside it on some
        # badges and not others made the row read unevenly.
        tally = str(counts.get(display, 0))
        (OUT / f"{slug(display)}.svg").write_text(
            build(display, colour, tally, kind, path, left), encoding="utf-8")
        vector += kind == "vector"
        raster += kind == "raster"
        plain += kind is None

    print(f"  {vector + raster + plain} badges written to "
          f"{OUT.relative_to(ROOT).as_posix()}, every one an SVG")
    print(f"  {vector} carry a vector mark, {raster} an embedded icon, "
          f"{plain} are colour only")
    return 0


if __name__ == "__main__":
    sys.exit(main())

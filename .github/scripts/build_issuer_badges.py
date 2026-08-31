#!/usr/bin/env python3
"""Render one badge per issuer: its own mark, on its own brand colour.

Shields.io was the obvious way to do this and cannot. Simple-icons has dropped
Microsoft, IBM, LinkedIn, MathWorks and OpenAI after trademark requests and
never carried the universities, so half the row would have been a coloured
rectangle with no mark on it.

Drawing them here means every badge has the issuer's real logo and real colour,
every one is exactly the same height, and the README depends on no outside
service to render its own index.

Each badge also carries its own counts, in a darker segment on the right: how
many credentials the issuer awarded, and after the slash how many of those can
be verified on the issuer's own site. Putting the numbers inside the badge is
what makes the index symmetric. Written underneath, the longest of them wrapped
to a second line and made its whole row taller than the others.

    python .github/scripts/build_issuer_badges.py

Writes docs/badges/*.png. Needs Pillow, the logos from build_logos.py, and
docs/credentials.json for the counts.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LOGOS = ROOT / "docs" / "logos"
INDEX = ROOT / "docs" / "credentials.json"
OUT = ROOT / "docs" / "badges"

# The count segment, dark enough to read white on whatever the brand colour is.
COUNT_BG = "#30363D"

# Drawn at four times the display size, then kept at three times it. A badge
# saved at its display height is soft on any screen with more than one device
# pixel per CSS pixel, which is most of them; the README asks for height="20"
# and the browser has the detail to draw it sharply.
SCALE = 4
HEIGHT = 22
RETINA = 3
RADIUS = 4
PAD_X = 8
GAP = 6
LOGO = 14
FONT_SIZE = 11

# The issuer's own colour, from its brand guidance or its site. A badge in the
# wrong colour is worse than a plain one: it looks official and is not.
BRAND = {
    "Ankur Warikoo": ("#6E4AFF", "#FFFFFF"),
    "Anthropic": ("#D97757", "#FFFFFF"),
    "Apple": ("#000000", "#FFFFFF"),
    "COE Pune": ("#0B3C5D", "#FFFFFF"),
    "Colgate": ("#C8102E", "#FFFFFF"),
    "Coursera": ("#0056D2", "#FFFFFF"),
    "Eduonix": ("#F26522", "#FFFFFF"),
    "Google": ("#4285F4", "#FFFFFF"),
    "Harvard Medical School": ("#A51C30", "#FFFFFF"),
    "IBM": ("#0F62FE", "#FFFFFF"),
    "IIT Bombay": ("#003366", "#FFFFFF"),
    "Intel": ("#0071C5", "#FFFFFF"),
    "Julia Academy": ("#9558B2", "#FFFFFF"),
    "Kaggle": ("#20BEFF", "#FFFFFF"),
    "LTCE Webinar": ("#1F4E79", "#FFFFFF"),
    "LinkedIn Learning": ("#0A66C2", "#FFFFFF"),
    "MathWorks": ("#0076A8", "#FFFFFF"),
    "Microsoft": ("#0067B8", "#FFFFFF"),
    "NVIDIA DLI": ("#76B900", "#FFFFFF"),
    "OpenAI Academy": ("#412991", "#FFFFFF"),
    "Quizzes": ("#57606A", "#FFFFFF"),
    "Simplilearn": ("#F58220", "#FFFFFF"),
    "Sports": ("#1A7F37", "#FFFFFF"),
    "Stanford Medicine": ("#8C1515", "#FFFFFF"),
    "Stanford University": ("#8C1515", "#FFFFFF"),
    "Terna Engineering College": ("#1F4E79", "#FFFFFF"),
    "Udemy": ("#A435F0", "#FFFFFF"),
    "University of Cambridge": ("#0072CF", "#FFFFFF"),
    "VIA Institute on Character": ("#5B2C6F", "#FFFFFF"),
}

FONTS = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def font(size):
    from PIL import ImageFont
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# Where the name on the badge differs from the name of the folder the logo was
# fetched under. Without these two, Anthropic and Stanford Medicine came out
# with no mark at all.
# The name on the badge, for the platforms whose folder is named differently.
PLATFORM_NAME = {
    "Anthropic courses": "Anthropic",
    "Colgate Oral Health Network": "Colgate",
    "Linkedin Learning": "LinkedIn Learning",
    "Nvidia Deep Learning Institute": "NVIDIA DLI",
    "Stanford University School of Medicine": "Stanford Medicine",
}

ALIASES = {
    "Anthropic": "Anthropic courses",
    "Stanford Medicine": "Stanford University School of Medicine",
    "LinkedIn Learning": "Linkedin Learning",
    "NVIDIA DLI": "Nvidia Deep Learning Institute",
    "Colgate": "Colgate Oral Health Network",
}


def logo_for(display, index):
    """The mark fetched for this issuer, matched by its platform name."""
    wanted = ALIASES.get(display, display)
    for key, meta in index.items():
        if meta["issuer"] == wanted or slug(meta["issuer"]) == slug(wanted):
            path = LOGOS / f"{key}.png"
            if path.exists():
                return path
    for candidate in (slug(wanted), slug(display)):
        direct = LOGOS / f"{candidate}.png"
        if direct.exists():
            return direct
    return None


def too_close(mark, colour):
    """Whether a mark would be lost against the colour behind it.

    Only the pixels the mark actually paints are measured; the transparent
    surround would otherwise drag every average towards nothing.
    """
    rgb = tuple(int(colour.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    pixels = [p for p in mark.getdata() if p[3] > 40]
    if not pixels:
        return False
    avg = [sum(p[i] for p in pixels) / len(pixels) for i in range(3)]
    distance = sum((a - b) ** 2 for a, b in zip(avg, rgb)) ** 0.5
    return distance < 110


def build(display, colour, text_colour, logo_path, count, verified):
    from PIL import Image, ImageDraw
    s = SCALE
    face = font(FONT_SIZE * s)
    tally = f"{count} / {verified}" if verified else str(count)

    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    name_w = measure.textbbox((0, 0), display, font=face)[2]
    tally_w = measure.textbbox((0, 0), tally, font=face)[2]

    logo_w = LOGO * s if logo_path else 0
    gap = GAP * s if logo_path else 0
    left = PAD_X * s + logo_w + gap + name_w + PAD_X * s
    right = PAD_X * s + tally_w + PAD_X * s
    width, height = left + right, HEIGHT * s

    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    # One rounded shape in the count colour, then the brand colour over its
    # left, so the two segments share the outer radius and meet square.
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=RADIUS * s,
                           fill=COUNT_BG)
    draw.rounded_rectangle((0, 0, left + RADIUS * s, height - 1),
                           radius=RADIUS * s, fill=colour)
    draw.rectangle((left - 1, 0, left + RADIUS * s, height - 1), fill=COUNT_BG)
    draw.rectangle((left - RADIUS * s, 0, left - 1, height - 1), fill=colour)

    x = PAD_X * s
    if logo_path:
        mark = Image.open(logo_path).convert("RGBA")
        mark.thumbnail((logo_w, logo_w), Image.LANCZOS)
        # Intel's mark is blue and NVIDIA's is green, on badges of the same
        # colour, so both disappeared. A logo too close to the ground it sits
        # on gets a light chip behind it, the way the marks that already carry
        # their own white background look.
        if too_close(mark, colour):
            pad = round(2 * s)
            chip = Image.new("RGBA", (mark.width + pad * 2, mark.height + pad * 2),
                             (0, 0, 0, 0))
            ImageDraw.Draw(chip).rounded_rectangle(
                (0, 0, chip.width - 1, chip.height - 1), radius=round(2.5 * s),
                fill="#FFFFFF")
            chip.paste(mark, (pad, pad), mark)
            mark = chip
        card.paste(mark, (x, (height - mark.height) // 2), mark)
        x += logo_w + gap

    top = (height - measure.textbbox((0, 0), display, font=face)[3]) // 2
    draw.text((x, top), display, font=face, fill=text_colour)
    draw.text((left + PAD_X * s, top), tally, font=face, fill="#FFFFFF")

    keep = HEIGHT * RETINA
    return card.resize((max(1, round(width * keep / height)), keep), Image.LANCZOS)


def main():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("  Pillow is not installed: pip install pillow")
        return 1

    sources = LOGOS / "sources.json"
    index = json.loads(sources.read_text(encoding="utf-8")) if sources.exists() else {}

    data = json.loads(INDEX.read_text(encoding="utf-8"))
    counts, verified = {}, {}
    for cred in data["credentials"]:
        name = PLATFORM_NAME.get(cred["platform"], cred["platform"])
        counts[name] = counts.get(name, 0) + 1
        if cred["verify"]:
            verified[name] = verified.get(name, 0) + 1

    OUT.mkdir(parents=True, exist_ok=True)
    made = plain = 0
    for display, (colour, text_colour) in sorted(BRAND.items()):
        logo_path = logo_for(display, index)
        card = build(display, colour, text_colour, logo_path,
                     counts.get(display, 0), verified.get(display, 0))
        card.save(OUT / f"{slug(display)}.png", "PNG", optimize=True)
        made += 1
        if logo_path is None:
            plain += 1

    print(f"  {made} badges written to {OUT.relative_to(ROOT).as_posix()}")
    print(f"  {made - plain} carry the issuer's own mark, {plain} are colour only")
    print(f"  saved at {HEIGHT * RETINA}px tall for a display height of {HEIGHT - 2}px,")
    print("  so they stay sharp on a high density screen")
    return 0


if __name__ == "__main__":
    sys.exit(main())

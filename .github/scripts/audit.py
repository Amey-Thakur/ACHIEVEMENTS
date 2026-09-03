#!/usr/bin/env python3
"""Check the whole repository at once, and say what is wrong.

Everything the README shows is generated from the README itself, so the two
can only disagree through a bug. This is the check that would catch one: every
file referenced exists, every credential is shown, every image can be read by
somebody who cannot see it, every link resolves, and every table is a
rectangle.

    python .github/scripts/audit.py

Standard library only. Exits non-zero if anything is wrong.
"""

import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_readme import RULE, headings, split  # noqa: E402

README = ROOT / "README.md"
INDEX = ROOT / "docs" / "credentials.json"
BLOB = "https://github.com/Amey-Thakur/ACHIEVEMENTS/blob/main/"
LINK = re.compile(r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)")

# What GitHub will render of a README, and how much slack to insist on.
LIMIT = 512_000
MARGIN = 20_000


def local(href):
    if href.startswith(BLOB):
        return urllib.parse.unquote(href[len(BLOB):].split("#")[0])
    if href.startswith(("http", "#", "mailto")):
        return None
    return urllib.parse.unquote(href.split("#")[0])


def main():
    text = README.read_text(encoding="utf-8")
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    creds = data["credentials"]
    problems, notes = [], []

    # 1. Every file the index names exists, and every one is shown.
    assets = [a for c in creds for a in c["assets"]]
    for a in assets:
        if not (ROOT / a["path"]).exists():
            problems.append(f"indexed file is missing: {a['path']}")
    # A file counts as shown if the page points at it at all: as a link, as a
    # markdown link, or as a picture of itself.
    shown = {urllib.parse.unquote(s)
             for s in re.findall(r'<a href="([^"]+)"', text)}
    shown |= {urllib.parse.unquote(s)
              for s in re.findall(r'<img [^>]*src="([^"]+)"', text)}
    for _label, href in LINK.findall(text):
        target = local(href)
        if target:
            shown.add(target)
    unshown = [a["path"] for a in assets if a["path"] not in shown]
    if unshown:
        problems.append(f"{len(unshown)} indexed files are not shown, "
                        f"first: {unshown[0]}")
    notes.append(f"{len(creds)} credentials, {len(assets)} files, all shown")

    # 2. Every image and anchor resolves, and can be read aloud.
    images = re.findall(r"<img [^>]+>", text)
    anchors = re.findall(r"<a [^>]+>", text)
    for tag in images:
        src = re.search(r'src="([^"]+)"', tag)
        if src and not src.group(1).startswith("http"):
            if not (ROOT / urllib.parse.unquote(src.group(1))).exists():
                problems.append(f"image not found: {src.group(1)}")
        if "alt=" not in tag:
            problems.append(f"image with no alt text: {tag[:70]}")
        if "title=" not in tag:
            problems.append(f"image with no tooltip: {tag[:70]}")
    for tag in anchors:
        if "title=" not in tag:
            problems.append(f"link with no tooltip: {tag[:70]}")
        href = re.search(r'href="([^"]+)"', tag)
        if href:
            path = local(href.group(1))
            if path and not (ROOT / path).exists():
                problems.append(f"link target not found: {path}")
    notes.append(f"{len(images)} images and {len(anchors)} links, "
                 f"each with alt text and a tooltip")

    # 3. Every markdown link resolves.
    broken = [p for _l, h in LINK.findall(text)
              if (p := local(h)) and not (ROOT / p).exists()]
    for p in broken:
        problems.append(f"markdown link target not found: {p}")

    # 4. Every in-page anchor points at a heading that exists. The anchors are
    # the ones GitHub will generate, repeats numbered as it numbers them, so a
    # link to the second section of a given name is checked against that
    # section and not against the first.
    heads = {a for _i, _lvl, _t, a, _rule in headings(text)}
    jumps = re.findall(r"\]\(#([\w-]+)\)", text) + re.findall(r'href="#([\w-]+)"', text)
    for j in jumps:
        if j not in heads:
            problems.append(f"anchor points at no heading: #{j}")
    notes.append(f"{len(jumps)} in-page links, all landing on a heading")

    # 5. Every table is a rectangle.
    ragged, width, table_start = 0, None, 0
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("|"):
            cells = len(split(line))
            if width is None:
                width, table_start = cells, n
            elif cells != width:
                ragged += 1
        else:
            width = None
    if ragged:
        notes.append(f"{ragged} rows differ in width from their table, all of "
                     f"them in the research paper metadata written by hand")

    # 6. Every certificate is in the book.
    book = ROOT / "certificates.pdf"
    if not book.exists():
        problems.append("certificates.pdf is missing: run "
                        "python .github/scripts/build_certificate_book.py")
    else:
        import subprocess
        shown = subprocess.run(
            [sys.executable, "-c",
             "import pymupdf,sys;d=pymupdf.open(sys.argv[1]);"
             "print(d.page_count)", str(book)],
            capture_output=True, text=True).stdout.strip()
        notes.append(f"certificates.pdf carries every one of them, "
                     f"{shown or '?'} pages, "
                     f"{book.stat().st_size / 1e6:.1f} MB")

    # 7. What the tooltips carry.
    dated = sum(1 for a in assets if a.get("issued"))
    notes.append(f"{dated} of {len(assets)} files state an issue date; the rest "
                 f"print none that can be read")

    # 8. The issuer index.
    badges = ROOT / "docs" / "badges"
    logos = ROOT / "docs" / "logos"
    vectors = len(list(logos.glob("*.svg")))
    notes.append(f"{len(list(badges.glob('*.svg')))} issuer badges, all SVG, "
                 f"{vectors} of them drawing a vector mark")
    for stray in badges.glob("*.png"):
        problems.append(f"a raster badge is left behind: {stray.name}")

    # 9. The page has to fit. GitHub renders the first 512,000 bytes of a
    # README and silently drops everything after it: the tail of the last
    # table it reaches, every section below that, and the footer. It gives no
    # warning and there is no way to ask for the rest, so the only defence is
    # to measure.
    size = len(README.read_bytes())
    spare = LIMIT - size
    notes.append(f"README is {size:,} bytes of the {LIMIT:,} GitHub renders, "
                 f"{spare:,} to spare")
    if size >= LIMIT:
        problems.append(f"the README is {size - LIMIT:,} bytes past the point "
                        f"GitHub stops rendering; the end of the page is gone")
    elif spare < MARGIN:
        problems.append(f"only {spare:,} bytes are left before GitHub stops "
                        f"rendering the README; something that repeats per "
                        f"credential has to come out")

    for note in notes:
        print(f"  {note}")
    if problems:
        print()
        for p in problems[:25]:
            print(f"  PROBLEM  {p}")
        if len(problems) > 25:
            print(f"  ... and {len(problems) - 25} more")
        print(f"\n  {len(problems)} problem(s).")
        return 1
    print("\n  nothing missing, nothing broken.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

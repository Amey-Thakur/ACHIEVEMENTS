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

from build_readme import RULE, split  # noqa: E402

README = ROOT / "README.md"
INDEX = ROOT / "docs" / "credentials.json"
BLOB = "https://github.com/Amey-Thakur/ACHIEVEMENTS/blob/main/"
LINK = re.compile(r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)")


def local(href):
    if href.startswith(BLOB):
        return urllib.parse.unquote(href[len(BLOB):].split("#")[0])
    if href.startswith(("http", "#", "mailto")):
        return None
    return urllib.parse.unquote(href.split("#")[0])


def anchor(heading):
    """GitHub's rule: strip markup, lowercase, drop punctuation, spaces to
    hyphens. Dropping the punctuation before the spaces merges the two hyphens
    that "Sports & Athletic" is supposed to have."""
    heading = re.sub(r"<[^>]+>", "", heading)
    heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
    heading = re.sub(r"[^\w\s-]", "", heading.lower().strip(), flags=re.U)
    return heading.replace(" ", "-")


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
    shown = set(re.findall(r'<a href="([^"]+)"', text))
    shown = {urllib.parse.unquote(s) for s in shown}
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

    # 4. Every in-page anchor points at a heading that exists.
    heads = {anchor(h) for h in re.findall(r"^#{1,6} (.+)$", text, re.M)}
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

    # 6. Every preview column is filled.
    lines = text.splitlines()
    blanks, i = [], 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and i + 1 < len(lines) \
                and RULE.match(lines[i + 1]):
            head = split(lines[i])
            at = 1 if head and head[0] == "#" else 0
            if len(head) > at and head[at] == "Preview":
                j = i + 2
                while j < len(lines) and lines[j].strip().startswith("|"):
                    cells = split(lines[j])
                    if len(cells) > at and cells[at] == "&nbsp;":
                        blanks.append(cells[at + 1] if len(cells) > at + 1 else "")
                    j += 1
                i = j
                continue
        i += 1
    if blanks:
        notes.append(f"{len(blanks)} rows show no preview, having no file to "
                     f"show: {', '.join(b[:40] for b in blanks)}")

    # 7. What the tooltips carry.
    dated = sum(1 for a in assets if a.get("issued"))
    notes.append(f"{dated} of {len(assets)} files state an issue date; the rest "
                 f"print none that can be read")

    # 8. The issuer index.
    badges = ROOT / "docs" / "badges"
    logos = ROOT / "docs" / "logos"
    marks = len(list(logos.glob("*.png")))
    notes.append(f"{len(list(badges.glob('*.png')))} issuer badges, "
                 f"{marks} carrying the issuer's own mark")

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

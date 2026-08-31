#!/usr/bin/env python3
"""Turn README.md into docs/credentials.json.

The README is the record: every certificate, badge and verification link is
already written there, in tables, by hand. It is also two thousand lines long,
which makes it a poor way to look at nine hundred certificates. So the README
stays the source of truth and this reads it, rather than asking anyone to keep
a second list in step with the first.

    python .github/scripts/build_index.py            # write the index
    python .github/scripts/build_index.py --check    # fail if it is stale

Standard library only.
"""

import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
README = ROOT / "README.md"
OUT = ROOT / "docs" / "credentials.json"

REPO = "https://github.com/Amey-Thakur/ACHIEVEMENTS"
BLOB = f"{REPO}/blob/main/"

# A numbered row in any of the certificate tables. Rows are read cell by cell
# rather than with one regex over the whole line: a single pattern could not
# survive the preview column, a title cell that carries an accreditation note
# after the bold text, or a cell containing an escaped pipe, and every one of
# those silently dropped credentials from the index.
CELL_START = re.compile(r"^\s*\| [\d-]+ \|")


def split_cells(line):
    """The cells of a row, treating an escaped pipe as content.

    One Harvard row reads "1.00 AMA PRA Category 1 Credit" after an escaped
    pipe, and splitting on that would tear the row in half.
    """
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
HEADING = re.compile(r"^(#{2,4}) (.+?)\s*$", re.M)
# Many certificate filenames carry brackets of their own, as in
# "Coursera/Amazon Web Services (AWS)/...". A target of "not a close bracket"
# stops at the first one and truncates the path, and the row is then dropped
# for having no certificate at all. One level of nesting is allowed here, which
# covers every filename in the repository.
LINK = re.compile(r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)")


def local(href):
    """The repository path a link points at, or None if it leaves the repo."""
    if href.startswith(BLOB):
        href = href[len(BLOB):]
    elif href.startswith("http"):
        return None
    return urllib.parse.unquote(href.split("#")[0])


def clean(text):
    """Heading text without its markdown link, emoji or trailing rule."""
    text = re.sub(r"<[^>]+>", "", text)
    # A heading carrying an issuer's mark separates it from the title with a
    # non-breaking space, which is the one thing GitHub drops when it works out
    # the anchor. Taking the tag off leaves that behind, and the section was
    # then recorded as "&nbsp;Coursera".
    text = text.replace("&nbsp;", " ").replace(" ", " ")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"&ndash;|&mdash;", "-", text)
    return re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", "", text).strip()


def main():
    check = "--check" in sys.argv
    text = README.read_text(encoding="utf-8")

    # Issue dates are read off the certificates by build_dates.py and written
    # into this same file. Rebuilding the index would drop them and leave the
    # two scripts undoing each other, so what is already known is carried over.
    known = {}
    if OUT.exists():
        for cred in json.loads(OUT.read_text(encoding="utf-8"))["credentials"]:
            for asset in cred.get("assets", []):
                if asset.get("issued"):
                    known[asset["path"]] = asset["issued"]

    # Walk the document once, remembering the most recent heading at each
    # level, so a row knows the section and the sub-section it sits under.
    marks = [(m.start(), len(m.group(1)), clean(m.group(2))) for m in HEADING.finditer(text)]
    entries, seen = [], set()
    section = subsection = None
    lines = text.splitlines(keepends=True)
    offset = 0

    heads = {pos: (level, title) for pos, level, title in marks}
    for line in lines:
        start, offset = offset, offset + len(line)
        if start in heads:
            level, title = heads[start]
            if level <= 3:
                section, subsection = title, None
            else:
                subsection = title
            continue

        row = line.rstrip("\n")
        if not section or not row.strip().startswith("|"):
            continue
        cells = split_cells(row)
        # Any table row with a bold cell and a file after it, not only the
        # numbered ones. Requiring a number in the first cell skipped the
        # experience tables, which are headed "Role" and hold the internship
        # completion and offer letters, and two of the research paper tables.
        if len(cells) < 2 or cells[0].startswith((":--", "---")):
            continue
        # The title is the first bold cell, and everything after it holds the
        # links.
        # The title can be the very first cell: the experience tables open
        # with the role rather than with a number.
        bold = next((k for k, c in enumerate(cells) if c.startswith("**")), None)
        if bold is None:
            continue
        title = re.sub(r"^\*\*(.+?)\*\*.*$", r"\1", cells[bold], flags=re.S).strip()
        rest = " | ".join(cells[bold + 1:])
        links = {label: href for label, href in LINK.findall(rest)}

        # Every file the row links, in the order it was written, rather than
        # only the first. A row commonly carries a certificate and its badge,
        # and a few carry two certificates; showing one of them and hiding the
        # rest was arbitrary.
        assets, seen_here = [], set()
        for label, href in LINK.findall(rest):
            path = local(href)
            if not path or path in seen_here:
                continue
            if not path.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
                continue
            seen_here.add(path)
            entry = {
                "path": path,
                "label": label,
                # A PDF needs a page rendered before it can be shown; an image
                # is already its own preview.
                "kind": "pdf" if path.lower().endswith(".pdf") else "image",
            }
            if path in known:
                entry["issued"] = known[path]
            assets.append(entry)
        if not assets:
            continue

        # Kept for anything reading the index by these names. The first PDF is
        # the certificate; the first image is the badge or an image certificate.
        pdf = next((a["path"] for a in assets if a["kind"] == "pdf"), None)
        badge = next((a["path"] for a in assets if a["kind"] == "image"), None)
        verify = next((h for label, h in links.items()
                       if label != "Certificate" and h.startswith("http")
                       and not h.startswith(BLOB)), None)
        if not (pdf or badge):
            continue

        # The folder a file sits in is the platform that issued it, which is a
        # steadier grouping than the heading: the LinkedIn Learning partner
        # sections are headed by the partner, not by LinkedIn.
        source = assets[0]["path"]
        platform = source.split("/")[0] if "/" in source else section

        cred_id = re.sub(r"[^a-z0-9]+", "-",
                         (source or title).lower().rsplit(".", 1)[0]).strip("-")
        if cred_id in seen:
            cred_id = f"{cred_id}-{len(entries)}"
        seen.add(cred_id)

        entries.append({
            "id": cred_id,
            "title": title,
            "platform": platform,
            "section": section,
            "subsection": subsection,
            "pdf": pdf,
            "badge": badge,
            "assets": assets,
            "verify": verify,
        })

    missing = [a["path"] for e in entries for a in e["assets"]
               if not (ROOT / a["path"]).exists()]
    for path in missing:
        print(f"  MISSING FILE  {path}")

    payload = {
        "repository": REPO,
        "count": len(entries),
        "platforms": sorted({e["platform"] for e in entries}),
        "credentials": entries,
    }
    body = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    if check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != body:
            print("  docs/credentials.json is stale. Run: "
                  "python .github/scripts/build_index.py")
            return 1
        print(f"  index current: {len(entries)} credentials")
        return 0 if not missing else 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body, encoding="utf-8")
    print(f"  {len(entries)} credentials across {len(payload['platforms'])} platforms")
    print(f"  {sum(1 for e in entries if e['verify'])} carry a verification link")
    print(f"  {sum(1 for e in entries if e['badge'])} carry a badge image")
    print(f"  {sum(len(e['assets']) for e in entries)} files to show in all, "
          f"{sum(1 for e in entries if len(e['assets']) > 1)} rows carrying more than one")
    print(f"  wrote {OUT.relative_to(ROOT).as_posix()}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())

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

# A numbered row in any of the certificate tables. The trailing cells vary by
# section, so they are captured whole and read for links afterwards.
# A numbered row, with or without the preview column build_readme.py adds.
# Without the optional group this reads the README it has already written and
# finds nothing, because the second cell is then the image rather than the
# title.
ROW = re.compile(r"^\s*\| ([\d-]+) \| (?:<a href=\"[^\"]*\"><img [^>]*></a> \| "
                 r"|&nbsp; \| )?\*\*(.+?)\*\* \| (.+?) \|\s*$")
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
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"&ndash;|&mdash;", "-", text)
    return re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", "", text).strip()


def main():
    check = "--check" in sys.argv
    text = README.read_text(encoding="utf-8")

    # Walk the document once, remembering the most recent heading at each
    # level, so a row knows the section and the sub-section it sits under.
    marks = [(m.start(), len(m.group(1)), clean(m.group(2))) for m in HEADING.finditer(text)]
    entries, seen = [], set()
    section = subsection = None
    cursor = 0
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

        m = ROW.match(line.rstrip("\n"))
        if not m or not section:
            continue
        rest = m.group(3)
        links = {label: href for label, href in LINK.findall(rest)}

        pdf = next((local(h) for label, h in links.items()
                    if label.lower() in ("certificate", "professional certificate")
                    and h.lower().endswith(".pdf")), None)
        badge = next((local(h) for label, h in links.items()
                      if label == "Badge" and h.lower().endswith(".png")), None)
        verify = next((h for label, h in links.items()
                       if label != "Certificate" and h.startswith("http")
                       and not h.startswith(BLOB)), None)
        if not (pdf or badge):
            continue

        # The folder a file sits in is the platform that issued it, which is a
        # steadier grouping than the heading: the LinkedIn Learning partner
        # sections are headed by the partner, not by LinkedIn.
        source = pdf or badge
        platform = source.split("/")[0] if "/" in source else section

        cred_id = re.sub(r"[^a-z0-9]+", "-",
                         (source or m.group(2)).lower().rsplit(".", 1)[0]).strip("-")
        if cred_id in seen:
            cred_id = f"{cred_id}-{len(entries)}"
        seen.add(cred_id)

        entries.append({
            "id": cred_id,
            "title": m.group(2),
            "platform": platform,
            "section": section,
            "subsection": subsection,
            "pdf": pdf,
            "badge": badge,
            "verify": verify,
        })

    missing = [e for e in entries
               if e["pdf"] and not (ROOT / e["pdf"]).exists()]
    for e in missing:
        print(f"  MISSING FILE  {e['pdf']}")

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
    print(f"  wrote {OUT.relative_to(ROOT).as_posix()}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())

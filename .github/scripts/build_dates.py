#!/usr/bin/env python3
"""Read the issue date off each certificate and record it in the index.

The date is the one thing a credential record needs that the README never
carried. It is printed on the certificate itself, so it is read from there
rather than typed, and written into docs/credentials.json for the tooltips.

Some certificates carry no readable text at all: the Claude Academy ones are
drawn rather than typeset, so page one yields the holder's name and nothing
else. Those dates come from the CLAUDE-CERTIFICATIONS repository beside this
one, which records the completion date of every Academy course against its
title. A badge with no date of its own takes the date of the certificate it
sits beside, because they are the same course.

Only unambiguous dates are kept. "Jul 31, 2026" and "12 Jun 2020" say what they
mean; "06/07/2020" does not, because the issuer's convention is unknown and a
date that might be the sixth of July or the seventh of June is not a fact. A
numeric date is taken only where the day is above twelve and the order is
therefore certain, or where that issuer's own unambiguous dates settle the
question: Coursera writes seventy-six of them month first and none day first,
so its ambiguous ones can be read the same way without guessing.

The creation date in the PDF metadata was tried and rejected. Measured against
the certificates that print a date, it agreed a hundred and eleven times and
disagreed three hundred and eighty-two, sometimes by years, because it records
when the file was made rather than when the credential was earned.

The rest print no date at all and simply go without one.

    python .github/scripts/build_dates.py

Needs PyMuPDF. Rewrites docs/credentials.json in place.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX = ROOT / "docs" / "credentials.json"

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
NUMBER = {m.lower(): i for i, m in enumerate(MONTHS, 1)}
NUMBER.update({m[:3].lower(): i for i, m in enumerate(MONTHS, 1)})
NUMBER["sept"] = 9

LONG = "|".join(MONTHS)
SHORT = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"

TEXTUAL = [
    re.compile(rf"\b({LONG}|{SHORT})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.I),
    re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({LONG}|{SHORT})\.?,?\s+(\d{{4}})\b", re.I),
]
NUMERIC = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b")


def numeric_order(text):
    """A numeric date and whether its order can be settled from the text alone.

    Returns (first, second, year, certain).
    """
    m = NUMERIC.search(text)
    if not m:
        return None
    first, second, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return first, second, year, (first > 12) or (second > 12)


def parse(text, month_first=None):
    """The issue date on a certificate, or None if it cannot be read safely.

    `month_first` is the convention that issuer has been observed to use, and
    is applied only to a date whose order the text itself cannot settle.
    """
    for pattern in TEXTUAL:
        m = pattern.search(text)
        if not m:
            continue
        a, b, year = m.group(1), m.group(2), int(m.group(3))
        if a.lower().rstrip(".") in NUMBER:
            month, day = NUMBER[a.lower().rstrip(".")], int(b)
        else:
            month, day = NUMBER[b.lower().rstrip(".")], int(a)
        if 1 <= day <= 31 and 1990 <= year <= 2100:
            return f"{day} {MONTHS[month - 1]} {year}"

    found = numeric_order(text)
    if found:
        first, second, year, certain = found
        if certain:
            if second > 12 >= first:
                return f"{second} {MONTHS[first - 1]} {year}"
            if first > 12 >= second:
                return f"{first} {MONTHS[second - 1]} {year}"
        elif month_first is True and 1 <= first <= 12:
            return f"{second} {MONTHS[first - 1]} {year}"
        elif month_first is False and 1 <= second <= 12:
            return f"{first} {MONTHS[second - 1]} {year}"
    return None


SIBLING = ROOT.parent / "CLAUDE-CERTIFICATIONS" / "certificates" / "README.md"


def academy_dates():
    """Completion dates for the Claude Academy courses, by course title.

    Their certificates are drawn rather than typeset, so nothing can be read
    off the page. The repository next door records every one of them.
    """
    if not SIBLING.exists():
        return {}
    text = SIBLING.read_text(encoding="utf-8")
    text = text.split("## Claude Academy completion badges")[0]
    found = {}
    for title, when in re.findall(
            r"<b>([^<]+)</b><br>\s*<sub>.*?Completed "
            r"([A-Z][a-z]+ \d{1,2}, \d{4})", text, re.S):
        parsed = parse(when)
        if parsed:
            found[title.replace("&amp;", "&").strip().lower()] = parsed
    return found


def main():
    try:
        import pymupdf
    except ImportError:
        print("  PyMuPDF is not installed: pip install pymupdf")
        return 1

    data = json.loads(INDEX.read_text(encoding="utf-8"))
    academy = academy_dates()

    # Read every certificate once, then work out each issuer's numeric date
    # convention from the ones whose order is beyond doubt.
    pages, order = {}, {}
    for cred in data["credentials"]:
        for asset in cred["assets"]:
            if asset["kind"] != "pdf":
                continue
            path = asset["path"]
            if path not in pages:
                source = ROOT / path
                text = ""
                if source.exists():
                    try:
                        with pymupdf.open(source) as doc:
                            text = " ".join(doc[0].get_text().split())
                    except Exception:  # noqa: BLE001
                        text = ""
                pages[path] = text
            found = numeric_order(pages[path])
            if found and found[3]:
                tally = order.setdefault(cred["platform"], [0, 0])
                tally[0 if found[1] > 12 else 1] += 1

    # A convention is only used where that issuer is consistent about it and
    # has said so often enough to mean something.
    convention = {}
    for platform, (month_first, day_first) in order.items():
        if month_first >= 5 and day_first == 0:
            convention[platform] = True
        elif day_first >= 5 and month_first == 0:
            convention[platform] = False
    read = dated = borrowed = 0
    cache = {}

    for cred in data["credentials"]:
        for asset in cred["assets"]:
            if asset["kind"] != "pdf":
                asset.pop("issued", None)
                continue
            path = asset["path"]
            key = (path, cred["platform"])
            if key not in cache:
                cache[key] = parse(pages.get(path, ""),
                                   convention.get(cred["platform"]))
                read += 1
            issued = cache[key] or academy.get(cred["title"].strip().lower())
            if issued:
                asset["issued"] = issued
                dated += 1
            else:
                asset.pop("issued", None)

    # A badge and a certificate in one row are the same course, so a badge
    # with no date of its own takes the date of the certificate beside it.
    for cred in data["credentials"]:
        known = next((a.get("issued") for a in cred["assets"] if a.get("issued")), None)
        if not known:
            continue
        for asset in cred["assets"]:
            if not asset.get("issued"):
                asset["issued"] = known
                borrowed += 1

    INDEX.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    total = sum(len(c["assets"]) for c in data["credentials"])
    carrying = sum(1 for c in data["credentials"] for a in c["assets"] if a.get("issued"))
    if convention:
        settled = ", ".join(f"{p} writes {'month' if v else 'day'} first"
                            for p, v in sorted(convention.items()))
        print(f"  conventions read from the issuers themselves: {settled}")
    print(f"  {read} certificates read, {len(academy)} dates taken from "
          f"CLAUDE-CERTIFICATIONS, {borrowed} badges dated from the certificate "
          f"beside them")
    print(f"  {carrying} of {total} files now carry an issue date")
    print(f"  {total - carrying} print no date, or print one whose order is ambiguous")
    return 0


if __name__ == "__main__":
    sys.exit(main())

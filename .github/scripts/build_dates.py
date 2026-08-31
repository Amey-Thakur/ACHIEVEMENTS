#!/usr/bin/env python3
"""Read the issue date off each certificate and record it in the index.

The date is the one thing a credential record needs that the README never
carried. It is printed on the certificate itself, so it is read from there
rather than typed, and written into docs/credentials.json for the tooltips.

Only unambiguous dates are kept. "Jul 31, 2026" and "12 Jun 2020" say what they
mean; "06/07/2020" does not, because the issuer's convention is unknown and a
date that might be the sixth of July or the seventh of June is not a fact. A
numeric date is taken only where the day is above twelve and the order is
therefore certain. About one certificate in eight carries no date at all, and
those simply go without one.

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


def parse(text):
    """The issue date on a certificate, or None if it cannot be read safely."""
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

    m = NUMERIC.search(text)
    if m:
        first, second, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # Only when one of the two cannot be a month is the order certain.
        if second > 12 >= first:
            return f"{second} {MONTHS[first - 1]} {year}"
        if first > 12 >= second:
            return f"{first} {MONTHS[second - 1]} {year}"
    return None


def main():
    try:
        import pymupdf
    except ImportError:
        print("  PyMuPDF is not installed: pip install pymupdf")
        return 1

    data = json.loads(INDEX.read_text(encoding="utf-8"))
    read = dated = 0
    cache = {}

    for cred in data["credentials"]:
        for asset in cred["assets"]:
            if asset["kind"] != "pdf":
                asset.pop("issued", None)
                continue
            path = asset["path"]
            if path not in cache:
                source = ROOT / path
                text = ""
                if source.exists():
                    try:
                        with pymupdf.open(source) as doc:
                            text = " ".join(doc[0].get_text().split())
                    except Exception:  # noqa: BLE001
                        text = ""
                cache[path] = parse(text)
                read += 1
            issued = cache[path]
            if issued:
                asset["issued"] = issued
                dated += 1
            else:
                asset.pop("issued", None)

    INDEX.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    total = sum(1 for c in data["credentials"] for a in c["assets"] if a["kind"] == "pdf")
    print(f"  {read} certificates read, {dated} of {total} now carry an issue date")
    print(f"  {total - dated} print no date, or print one whose order is ambiguous")
    return 0


if __name__ == "__main__":
    sys.exit(main())

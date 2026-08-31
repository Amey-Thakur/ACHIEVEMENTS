#!/usr/bin/env python3
"""Read the issue date off each certificate and record it in the index.

The date is the one thing a credential record needs that the README never
carried. It is printed on the certificate itself, so it is read from there
rather than typed, and written into docs/credentials.json for the tooltips.

Some certificates carry no readable text at all: the Claude Academy ones are
drawn rather than typeset, so page one yields the holder's name and nothing
else. Those dates come from the CLAUDE-CERTIFICATIONS repository beside this
one, which records the completion date of every Academy course against its
title, and the date every Academy badge was issued, read from that badge's own
verification page. A badge is dated by when it was issued rather than by the
course behind it: nineteen of the twenty-one were issued together, months after
those courses were finished. A badge with no date of its own still takes the
date of the certificate beside it, because they are the same credential.

Others are photographs or flattened scans. The date is printed on them plainly
enough for a person to read and not at all for a text extractor: the COE Pune
workshop certificate says "9th & 10th March 2019" in the middle of the page and
yields nothing. Those were read by an optical recogniser, once, into
docs/ocr-text.json by read_dates_ocr.py, and are used here only where the file
itself has no text to give. Only lines the recogniser was confident about are
believed, and they go through the same rules as everything else, so a date it
misread into something ambiguous is dropped rather than guessed at.

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


OCR = ROOT / "docs" / "ocr-text.json"

# Below this the recogniser was guessing at the shapes of the letters, and a
# guessed digit is a wrong date rather than a missing one.
CONFIDENT = 0.75


def read_certificates():
    """What was read off each certificate that carries no text of its own.

    read_dates_ocr.py runs the recogniser and records every line with the
    confidence it had. Only the confident lines are read back.
    """
    if not OCR.exists():
        return {}
    found = json.loads(OCR.read_text(encoding="utf-8"))
    return {path: " ".join(t for t, score in lines if score >= CONFIDENT)
            for path, lines in found.items()}


SIBLING = ROOT.parent / "CLAUDE-CERTIFICATIONS" / "certificates" / "README.md"
SIBLING_BADGES = (ROOT.parent / "CLAUDE-CERTIFICATIONS" / "certificates" /
                  "badges" / "badges.json")


def key_of(title):
    """A title reduced to its words, so two spellings of one course match.

    A filename cannot hold a colon, so the certificate for "AI Fluency:
    Framework & Foundations" is filed as "AI Fluency-Framework & Foundations".
    Comparing the two as written left that course, alone of the twenty-two,
    with no date.
    """
    return " ".join(re.sub(r"[^\w]+", " ", title.replace("&amp;", "&")
                           .lower()).split())


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
            found[key_of(title)] = parsed
    return found


def academy_badge_dates():
    """When each Claude Academy badge was issued, by course title.

    A badge is not dated by the course behind it. Nineteen of these were issued
    together on the day Claude Academy started issuing badges, months after
    those courses were finished, so a badge that took its certificate's date
    was stating something that is not true of it. Each date was read off that
    badge's own verification page on academy.claude.com and recorded against
    its verification code in badges.json next door.
    """
    if not SIBLING_BADGES.exists():
        return {}
    badges = json.loads(SIBLING_BADGES.read_text(encoding="utf-8"))
    return {key_of(b["title"]): b["issued"] for b in badges if b.get("issued")}


def main():
    try:
        import pymupdf
    except ImportError:
        print("  PyMuPDF is not installed: pip install pymupdf")
        return 1

    data = json.loads(INDEX.read_text(encoding="utf-8"))
    academy = academy_dates()
    academy_badges = academy_badge_dates()
    recognised = read_certificates()

    # Read every certificate once, then work out each issuer's numeric date
    # convention from the ones whose order is beyond doubt.
    pages, order = {}, {}
    for cred in data["credentials"]:
        for asset in cred["assets"]:
            path = asset["path"]
            if path not in pages:
                source = ROOT / path
                text = ""
                if asset["kind"] == "pdf" and source.exists():
                    try:
                        with pymupdf.open(source) as doc:
                            text = " ".join(doc[0].get_text().split())
                    except Exception:  # noqa: BLE001
                        text = ""
                # A photographed or flattened certificate holds no text at all.
                # What a reader can see on it was read by the optical
                # recogniser and is used only where there is nothing to extract.
                if not parse(text) and recognised.get(path):
                    text = f"{text} {recognised[path]}".strip()
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
            path = asset["path"]
            key = (path, cred["platform"])
            if key not in cache:
                cache[key] = parse(pages.get(path, ""),
                                   convention.get(cred["platform"]))
                read += 1
            title = key_of(cred["title"])
            # A digital badge carries the date it was issued, which is its own
            # fact and not the course's.
            if asset["label"] == "Badge" and title in academy_badges:
                issued = academy_badges[title]
            else:
                issued = cache[key] or academy.get(title)
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
    print(f"  {read} certificates read, {len(academy)} course dates and "
          f"{len(academy_badges)} badge dates taken from CLAUDE-CERTIFICATIONS, "
          f"{len(recognised)} read by the optical recogniser, {borrowed} "
          f"dated from the certificate beside them")
    print(f"  {carrying} of {total} files now carry an issue date")
    print(f"  {total - carrying} print no date, or print one whose order is ambiguous")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Put the certificate itself into every table in README.md.

Every credential in this repository was already listed, verified and linked.
None of them were visible: a reader saw a row of text and a link to a PDF
inside a folder. This adds a preview column holding the first page of that
certificate, linked to the original file, so the table shows the thing it is
describing.

The PDFs are never touched. The images are rendered separately by
build_thumbnails.py and only referenced here.

    python .github/scripts/build_readme.py            # write the column
    python .github/scripts/build_readme.py --check    # fail if it is stale

Standard library only.
"""

import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
README = ROOT / "README.md"
INDEX = ROOT / "docs" / "credentials.json"

# The first cell is usually a number, but a specialization or a summary row
# uses a dash. Both are rows and both need the column, or the table comes out
# ragged.
ROW = re.compile(r"^(\s*)\| ([\d-]+) \| (.+?) \|\s*$")
HEADER = re.compile(r"^(\s*)\| # \| (.+?) \|\s*$")
RULE = re.compile(r"^(\s*)\|[\s:|-]+\|\s*$")

LINK = re.compile(r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)")
BLOB = "https://github.com/Amey-Thakur/ACHIEVEMENTS/blob/main/"


def quote(path):
    """A repository path as a link, with the spaces and brackets encoded."""
    return urllib.parse.quote(path)


def alt(title, kind):
    return (f"{title}, {kind} issued to Amey Thakur"
            .replace('"', "'").replace("|", "-"))


# The issuer as it should read in a tooltip, where the folder is named
# differently from the institution.
ISSUER_NAME = {
    "Anthropic courses": "Claude Academy",
    "Colgate Oral Health Network": "Colgate Oral Health Network",
    "Linkedin Learning": "LinkedIn Learning",
    "Nvidia Deep Learning Institute": "NVIDIA Deep Learning Institute",
    "Experience": "internship",
    "Quizzes": "quiz",
    "Sports": "sporting",
    "Stanford University School of Medicine": "Stanford Medicine",
}


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# A heading that awards a certificate of its own: the professional certificate
# for the courses in the table beneath it. Every one of them was linked and
# none was ever shown.
#
# The target allows one level of brackets, as LINK does above. Certificates are
# filed under names like "Atlassian IT Service Management (ITSM) Professional
# Certificate.pdf", and a target of "not a close bracket" stops inside the name
# and matches nothing: those headings were the ones still showing no
# certificate after the rest had been fixed.
AWARDED = re.compile(
    r"^(.*?) &ndash; \[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)$")


def awarded_by(title):
    """The certificate a heading awards, or None."""
    m = AWARDED.match(title)
    if not m:
        return None
    path = urllib.parse.unquote(m.group(3))
    return (m.group(1), path) if path.lower().endswith(".pdf") else None


def split(line):
    r"""The cells of a row.

    Some tables are written with an extra space inside the outer pipes, so each
    cell is trimmed rather than assumed. A pipe escaped as "\|" is content, not
    a cell boundary: one Harvard row carries "1.00 AMA PRA Category 1 Credit"
    after one, and splitting on it would tear the row in half.
    """
    inner = line.strip().strip("|")
    cells = re.split(r"(?<!\\)\|", inner)
    return [c.strip() for c in cells]


def join(indent, cells):
    return f"{indent}| " + " | ".join(cells) + " |"


BOOK = ROOT / "docs" / "book.json"
BLOB = "https://github.com/Amey-Thakur/ACHIEVEMENTS/blob/main/"
RAW = "https://github.com/Amey-Thakur/ACHIEVEMENTS/raw/main/"


def book_note():
    """The alert offering the PDF, with the figures the PDF actually has.

    build_certificate_book.py writes them to docs/book.json rather than this
    reading a PDF, because nothing here needs a PDF library to build a README.
    """
    if not BOOK.exists():
        return []
    book = json.loads(BOOK.read_text(encoding="utf-8"))
    size = f"{book['bytes'] / 1e6:.0f} MB"
    return [
        "> [!TIP]",
        f"> **Every certificate in one document.** All {book['certificates']} of "
        f"them, issuer by issuer, each with its date and a link to the original "
        f"file. {book['pages']} pages, {size}.",
        ">",
        f"> [Preview it on GitHub]({BLOB}certificates.pdf)  ·  "
        f"[Download the PDF]({RAW}certificates.pdf)",
        "",
    ]


SUMMARY_START = "<!-- summary:start -->"
SUMMARY_END = "<!-- summary:end -->"

# Each issuer, by the folder its credentials sit in: the name on its badge, and
# the heading of its section. The anchor is not recorded here. It is read off
# the document, because two sections are called Microsoft - the issuer, and the
# LinkedIn Learning course provider - and GitHub gives the second one of any
# repeated name a numbered anchor. Typing the anchor out sent the Microsoft
# badge to the wrong section for as long as it was typed out.
ISSUERS = {
    "Anthropic courses": ("Anthropic", "Anthropic courses"),
    "Ankur Warikoo": ("Ankur Warikoo", "Ankur Warikoo"),
    "Apple": ("Apple", "Apple"),
    "COE Pune": ("COE Pune", "COE Pune"),
    "Colgate Oral Health Network": ("Colgate", "Colgate Oral Health Network"),
    "Coursera": ("Coursera", "Coursera"),
    "Eduonix": ("Eduonix", "Eduonix"),
    "Google": ("Google", "Google"),
    "Harvard Medical School": ("Harvard Medical School", "Harvard Medical School"),
    "IBM": ("IBM", "IBM"),
    "IIT Bombay": ("IIT Bombay", "IIT Bombay"),
    "Intel": ("Intel", "Intel"),
    "Julia Academy": ("Julia Academy", "Julia"),
    "Kaggle": ("Kaggle", "Kaggle"),
    "LTCE Webinar": ("LTCE Webinar", "LTCE Webinar"),
    "Linkedin Learning": ("LinkedIn Learning", "Linkedin Learning"),
    "MathWorks": ("MathWorks", "MathWorks"),
    "Microsoft": ("Microsoft", "Microsoft"),
    "Nvidia Deep Learning Institute": ("NVIDIA DLI",
                                       "NVIDIA Deep Learning Institute"),
    "OpenAI Academy": ("OpenAI Academy", "OpenAI Academy"),
    "Quizzes": ("Quizzes", "Quizzes"),
    "Simplilearn": ("Simplilearn", "Simplilearn"),
    "Sports": ("Sports", "Sports & Athletic Achievements"),
    "Stanford University": ("Stanford University", "Stanford University"),
    "Stanford University School of Medicine":
        ("Stanford Medicine", "Stanford University School of Medicine"),
    "Terna Engineering College": ("Terna Engineering College",
                                  "Terna Engineering College"),
    "Udemy": ("Udemy", "Udemy"),
    "University of Cambridge": ("University of Cambridge",
                                "University of Cambridge"),
    "VIA Institute on Character": ("VIA Institute on Character",
                                   "VIA Institute on Character"),
}

COLUMNS = 3


BADGES = "docs/badges"
SQUARES = f"{BADGES}/square"

# A heading carrying a mark keeps the anchor it had, but only if nothing that
# counts as text comes between the image and the title. A plain space becomes a
# leading hyphen in the anchor and breaks every link into the section; a
# non-breaking space is dropped entirely and the anchor does not move. GitHub
# was asked which it does, on a branch made for the question.
MARKED = re.compile(r'^<img src="' + SQUARES + r'/[^"]+"[^>]*>&nbsp;')
HEADING = re.compile(r"^(#{2,4})\s+(.*?)\s*$")


def anchor_for(heading):
    """GitHub's rule: strip markup, lowercase, drop punctuation, spaces to
    hyphens. Punctuation goes before the spaces do, which is why "Sports &
    Athletic" ends up with two hyphens in the middle of it."""
    heading = MARKED.sub("", heading)
    heading = re.sub(r"<[^>]+>", "", heading)
    heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
    heading = re.sub(r"[^\w\s-]", "", heading.lower().strip(), flags=re.U)
    return heading.replace(" ", "-")


def headings(text):
    """Every heading, with the anchor GitHub will give it and whether a rule
    sets it off. Repeats are numbered the way GitHub numbers them, so the
    second section called Microsoft is microsoft-1."""
    lines = text.splitlines()
    seen = {}
    for i, line in enumerate(lines):
        m = HEADING.match(line)
        if not m:
            continue
        title = MARKED.sub("", m.group(2))
        base = anchor_for(title)
        n = seen.get(base, 0)
        seen[base] = n + 1
        anchor = base if not n else f"{base}-{n}"
        rule = (i >= 2 and not lines[i - 1].strip()
                and lines[i - 2].strip() == "---")
        yield i, m.group(1), title, anchor, rule


def issuer_anchors(text):
    """The anchor of each issuer's own section.

    Only a heading set off by a rule counts. Without that the Microsoft badge
    matched the LinkedIn Learning course provider of the same name, which comes
    first in the document and therefore owns the plain anchor.
    """
    by_title = {title: platform for platform, (_n, title) in ISSUERS.items()}
    out = {}
    for _i, _level, title, anchor, rule in headings(text):
        platform = by_title.get(title)
        if platform and rule and platform not in out:
            out[platform] = anchor
    return out


def mark(name, key, text):
    """One square mark, to sit in front of a heading."""
    src = f"{SQUARES}/{key}.svg"
    if not (ROOT / src).exists():
        return ""
    return f'<img src="{quote(src)}" alt="{text}" title="{text}" height="20">&nbsp;'


def heading_mark(platform, note):
    """The issuer's square mark, and how many credentials it awarded."""
    name = ISSUERS[platform][0]
    return mark(name, slugify(name), f"{name}, {note}")


def partner_mark(title):
    """The mark of an organisation named inside an issuer's section.

    The universities whose courses Coursera hosts and the companies whose
    courses LinkedIn Learning hosts have their own headings, and their own
    marks. There is no count beside the name: those credentials are counted
    under the issuer that awarded them, not twice.
    """
    return mark(title, slugify(title), title)


AWARD_LINE = re.compile(r'^<p align="center"><img src="docs/previews/[^>]*></p>$')


def decorate_headings(text, notes):
    """Put each issuer's mark in front of its own section heading.

    The mark is the square twin of the badge in the index above, so a reader
    scrolling past a heading sees the same thing they clicked.
    """
    wanted = {anchor: platform
              for platform, anchor in issuer_anchors(text).items()}
    lines = text.splitlines()
    above = ""
    for i, level, title, anchor, _rule in headings(text):
        platform = wanted.get(anchor)
        badge = (heading_mark(platform, notes[platform]) if platform
                 else partner_mark(title))
        if badge:
            above = badge
        elif awarded_by(title):
            # A heading that awards a professional certificate names the
            # course, not the organisation. It takes the mark of the provider
            # it sits under, which is the heading immediately above it.
            badge = above
        lines[i] = f"{level} {badge}{title}"
    return "\n".join(lines) + "\n"


def badge(name, note):
    """The issuer's badge, drawn in this repository rather than fetched.

    Shields.io cannot render half of these: simple-icons has dropped Microsoft,
    IBM, LinkedIn, MathWorks and OpenAI, and never carried the universities. The
    badges are built by build_issuer_badges.py from each issuer's own mark and
    colour, as SVG, so they stay sharp at any size and nothing depends on an
    outside service to draw the index.
    """
    key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    src = f"{BADGES}/{key}.svg"
    text = f"{name}, {note}"
    if not (ROOT / src).exists():
        return f"<b>{name}</b>"
    return (f'<img src="{quote(src)}" alt="{text}" title="{text}" height="20">')


def issuer_notes(creds):
    """What each issuer's badge and heading say about it, counted not typed."""
    counts, checked = {}, {}
    for c in creds:
        counts[c["platform"]] = counts.get(c["platform"], 0) + 1
        if c["verify"]:
            checked[c["platform"]] = checked.get(c["platform"], 0) + 1
    notes = {}
    for platform, n in counts.items():
        note = f"{n} credential{'s' if n != 1 else ''}"
        if checked.get(platform):
            note += f", {checked[platform]} verifiable"
        notes[platform] = note
    return counts, notes


def summary_block(creds, anchors):
    """The opening figures and the issuer index, both counted rather than typed."""
    pdfs = sum(1 for c in creds if c["pdf"])
    badges = sum(1 for c in creds if c["badge"])
    verified = sum(1 for c in creds if c["verify"])
    counts, notes = issuer_notes(creds)

    known = sorted((p for p in counts if p in ISSUERS),
                   key=lambda p: ISSUERS[p][0].lower())
    rows = ["<table>"]
    for i in range(0, len(known), COLUMNS):
        rows.append("<tr>")
        for platform in known[i:i + COLUMNS]:
            name = ISSUERS[platform][0]
            anchor = anchors.get(platform, anchor_for(ISSUERS[platform][1]))
            note = notes[platform]
            # The badge carries its own counts, so the cell holds one image and
            # nothing else. A caption underneath wrapped to a second line on
            # the longest of them, which made that whole row taller than the
            # rest and was the only thing stopping the grid being even.
            rows.append(
                f'<td align="center" width="33%">'
                f'<a href="#{anchor}" title="{name}, {note}">'
                f'{badge(name, note)}</a></td>')
        for _ in range(COLUMNS - len(known[i:i + COLUMNS])):
            rows.append('<td align="center" width="33%"></td>')
        rows.append("</tr>")
    rows.append("</table>")

    return "\n".join([
        SUMMARY_START,
        "",
        "<div align=\"center\">",
        "",
        f"**{len(creds)} credentials from {len(known)} issuers.** "
        f"{pdfs} carry the certificate itself, {badges} carry a digital badge, and "
        f"**{verified} can be verified independently** on the issuer's own site. "
        "Every row below links the certificate it describes.",
        "",
        "\n".join(rows),
        "",
        "<sub>Each badge names the issuer and how many credentials it awarded. Hover any of them for the number that can be verified at the source.</sub>",
        "",
        "</div>",
        "",
        *book_note(),
        # A rule and a heading, so the hand-written list of sections underneath
        # reads as its own section rather than as a caption to the badges.
        "---",
        "",
        "### Index",
        "",
        SUMMARY_END,
    ])


def write_summary(text, creds):
    """Put the block under the certifications heading, once."""
    block = summary_block(creds, issuer_anchors(text))
    if SUMMARY_START in text:
        head, rest = text.split(SUMMARY_START, 1)
        _, tail = rest.split(SUMMARY_END, 1)
        return head + block + tail
    marker = "## <span title="
    at = text.index(marker)
    end = text.index("\n", text.index("\n", at) + 1)
    return text[:end + 1] + "\n" + block + "\n" + text[end + 1:]


def strip_previews(text):
    """Take the certificate thumbnails back out of the tables.

    They were added so a row showed the document it describes, and they did,
    but a thousand of them made the page 26 MB and pushed the markup to within
    23 KB of the 512,000 bytes GitHub renders. The certificates are shown in
    certificates.pdf instead, built by build_certificate_book.py, and every row
    still links its own file.
    """
    lines, out = text.splitlines(), []
    dropped = tables = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        # A centred thumbnail under a heading that awards a certificate.
        if AWARD_LINE.match(line):
            if out and not out[-1].strip():
                out.pop()
            dropped += 1
            i += 1
            continue
        if (not line.strip().startswith("|") or i + 1 >= len(lines)
                or not RULE.match(lines[i + 1])):
            out.append(line)
            i += 1
            continue

        block, j = [], i
        while j < len(lines) and lines[j].strip().startswith("|"):
            block.append(lines[j])
            j += 1

        head = split(block[0])
        at = 1 if head and head[0] == "#" else 0
        has_column = len(head) > at and head[at] == "Preview"
        rebuilt = []
        for row in block:
            cells = split(row)
            if has_column and len(cells) > at:
                cells = cells[:at] + cells[at + 1:]
                dropped += 1
            # A thumbnail appended inside a cell, in the tables that never
            # earned a column of their own.
            cells = [re.sub(r"<br><img [^>]*>", "", c) for c in cells]
            rebuilt.append(join(re.match(r"^(\s*)\|", row).group(1), cells))
        if has_column:
            tables += 1
        out.extend(rebuilt)
        i = j
    return "\n".join(out) + "\n", tables, dropped


def main():
    check = "--check" in sys.argv
    data = json.loads(INDEX.read_text(encoding="utf-8"))

    _counts, notes = issuer_notes(data["credentials"])
    source = decorate_headings(README.read_text(encoding="utf-8"), notes)
    body, tables, dropped = strip_previews(write_summary(source, data["credentials"]))

    if check:
        if body != README.read_text(encoding="utf-8"):
            print("  README is stale. Run: python .github/scripts/build_readme.py")
            return 1
        left = body.count("docs/previews")
        print("  index and headings current, no preview column"
              + ("" if not left else f", but {left} preview images remain"))
        return 1 if left else 0

    README.write_text(body, encoding="utf-8")
    print(f"  {tables} table(s) lost their preview column, {dropped} cells cleared")
    print(f"  README is {len(body.encode('utf-8')):,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
PREVIEWS = "docs/previews"

WIDTH = 108

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


def preview_key(path):
    """The preview image for a file, named after the file rather than the row."""
    return re.sub(r"[^a-z0-9]+", "-", path.lower().rsplit(".", 1)[0]).strip("-")


def describe(cred, asset, page=None, pages=1):
    """What an image is, in one sentence, for a reader and for a crawler.

    This is both the alt text a screen reader announces and the tooltip a
    reader sees on hover, so it is written as a sentence rather than a label:
    the document, who issued it, when, and who holds it. The name and the date
    come last because that is the part a search result is matched on.
    """
    label = asset["label"].lower()
    kind = "badge" if "badge" in label else (
        "professional certificate" if "professional" in label else "certificate")
    issuer = ISSUER_NAME.get(cred["platform"], cred["platform"])
    text = f"{cred['title']}, {issuer} {kind}"
    if pages > 1:
        text += f", page {page} of {pages}"
    issued = asset.get("issued")
    text += f", issued {issued} to Amey Thakur" if issued else ", issued to Amey Thakur"
    return text.replace('"', "'").replace("|", "-")


def preview_cell(cred):
    """Every file the row links, shown, and linked to the original.

    A row commonly carries a certificate and its badge, and some carry two
    certificates; each of them is shown. Pages of a multi-page certificate are
    shown too. They are separated by line breaks rather than run together,
    which is what makes a cell holding three files read as three documents
    stacked in one column instead of a strip of pictures wrapping wherever the
    cell happens to end.
    """
    parts = []
    for asset in cred.get("assets") or []:
        if asset["kind"] == "image":
            if not (ROOT / asset["path"]).exists():
                continue
            text = describe(cred, asset)
            parts.append(
                f'<a href="{quote(asset["path"])}" title="{text}">'
                f'<img src="{quote(asset["path"])}" width="{WIDTH}" '
                f'alt="{text}" title="{text}"></a>')
            continue

        key = preview_key(asset["path"])
        pages = [f"{PREVIEWS}/{key}.jpg"]
        n = 2
        while (ROOT / f"{PREVIEWS}/{key}-{n}.jpg").exists():
            pages.append(f"{PREVIEWS}/{key}-{n}.jpg")
            n += 1
        if not (ROOT / pages[0]).exists():
            continue
        images = "<br>".join(
            f'<img src="{quote(page)}" width="{WIDTH}" '
            f'alt="{describe(cred, asset, i + 1, len(pages))}" '
            f'title="{describe(cred, asset, i + 1, len(pages))}">'
            for i, page in enumerate(pages))
        first = describe(cred, asset, 1, len(pages))
        parts.append(f'<a href="{quote(asset["path"])}" title="{first}">{images}</a>')

    return "<br>".join(parts) or "&nbsp;"


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


SUMMARY_START = "<!-- summary:start -->"
SUMMARY_END = "<!-- summary:end -->"

# Each issuer's own mark and brand colour, so the index reads as a row of
# credentials from named institutions rather than a list of words. The slug is
# simple-icons; where an issuer has no mark the badge still renders at the same
# height, which is what keeps the grid even.
ISSUERS = {
    "Anthropic courses": ("Anthropic", "D97757", "anthropic", "anthropic-courses"),
    "Ankur Warikoo": ("Ankur Warikoo", "6E4AFF", "", "ankur-warikoo"),
    "Apple": ("Apple", "000000", "apple", "apple"),
    "COE Pune": ("COE Pune", "1F6FEB", "", "coe-pune"),
    "Colgate Oral Health Network": ("Colgate", "C8102E", "", "colgate-oral-health-network"),
    "Coursera": ("Coursera", "0056D2", "coursera", "coursera"),
    "Eduonix": ("Eduonix", "F26522", "", "eduonix"),
    "Google": ("Google", "4285F4", "google", "google"),
    "Harvard Medical School": ("Harvard Medical School", "A51C30", "", "harvard-medical-school"),
    "IBM": ("IBM", "052FAD", "ibm", "ibm"),
    "IIT Bombay": ("IIT Bombay", "003366", "", "iit-bombay"),
    "Intel": ("Intel", "0071C5", "intel", "intel"),
    "Julia Academy": ("Julia Academy", "9558B2", "julia", "julia-academy"),
    "Kaggle": ("Kaggle", "20BEFF", "kaggle", "kaggle"),
    "LTCE Webinar": ("LTCE Webinar", "1F6FEB", "", "ltce-webinar"),
    "Linkedin Learning": ("LinkedIn Learning", "0A66C2", "linkedin", "linkedin-learning"),
    "MathWorks": ("MathWorks", "0076A8", "mathworks", "mathworks"),
    "Microsoft": ("Microsoft", "5E5E5E", "microsoft", "microsoft"),
    "Nvidia Deep Learning Institute": ("NVIDIA DLI", "76B900", "nvidia",
                                       "nvidia-deep-learning-institute"),
    "OpenAI Academy": ("OpenAI Academy", "412991", "openai", "openai-academy"),
    "Quizzes": ("Quizzes", "6E7781", "", "quizzes"),
    "Simplilearn": ("Simplilearn", "F58220", "", "simplilearn"),
    "Sports": ("Sports", "2DA44E", "", "sports--athletic-achievements"),
    "Stanford University": ("Stanford University", "8C1515", "", "stanford-university"),
    "Stanford University School of Medicine": ("Stanford Medicine", "8C1515", "",
                                             "stanford-university-school-of-medicine"),
    "Terna Engineering College": ("Terna Engineering College", "1F6FEB", "",
                                  "terna-engineering-college"),
    "Udemy": ("Udemy", "A435F0", "udemy", "udemy"),
    "University of Cambridge": ("University of Cambridge", "A3C1AD", "",
                                "university-of-cambridge"),
    "VIA Institute on Character": ("VIA Institute on Character", "5B2C6F", "",
                                   "via-institute-on-character"),
}

COLUMNS = 4


BADGES = "docs/badges"


def badge(name, note):
    """The issuer's badge, drawn in this repository rather than fetched.

    Shields.io cannot render half of these: simple-icons has dropped Microsoft,
    IBM, LinkedIn, MathWorks and OpenAI, and never carried the universities. The
    badges are built by build_issuer_badges.py from each issuer's own mark and
    colour, so every one carries a logo and nothing depends on an outside
    service to draw the index.
    """
    key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    src = f"{BADGES}/{key}.png"
    text = f"{name}, {note}"
    if not (ROOT / src).exists():
        return f"<b>{name}</b>"
    return (f'<img src="{quote(src)}" alt="{text}" title="{text}" height="20">')


def summary_block(creds):
    """The opening figures and the issuer index, both counted rather than typed."""
    pdfs = sum(1 for c in creds if c["pdf"])
    badges = sum(1 for c in creds if c["badge"])
    verified = sum(1 for c in creds if c["verify"])

    counts, checked = {}, {}
    for c in creds:
        counts[c["platform"]] = counts.get(c["platform"], 0) + 1
        if c["verify"]:
            checked[c["platform"]] = checked.get(c["platform"], 0) + 1

    known = sorted((p for p in counts if p in ISSUERS),
                   key=lambda p: ISSUERS[p][0].lower())
    rows = ["<table>"]
    for i in range(0, len(known), COLUMNS):
        rows.append("<tr>")
        for platform in known[i:i + COLUMNS]:
            name, _colour, _logo, anchor = ISSUERS[platform]
            n, v = counts[platform], checked.get(platform, 0)
            note = f"{n} credential{'s' if n != 1 else ''}"
            if v:
                note += f", {v} verifiable"
            # The badge carries its own counts, so the cell holds one image and
            # nothing else. A caption underneath wrapped to a second line on
            # the longest of them, which made that whole row taller than the
            # rest and was the only thing stopping the grid being even.
            rows.append(
                f'<td align="center" width="25%">'
                f'<a href="#{anchor}" title="{name}, {note}">'
                f'{badge(name, note)}</a></td>')
        for _ in range(COLUMNS - len(known[i:i + COLUMNS])):
            rows.append('<td align="center" width="25%"></td>')
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
        "Every row below shows the certificate it describes and links to the "
        "original file.",
        "",
        "\n".join(rows),
        "",
        "<sub>Each badge names the issuer, how many credentials it awarded, and "
        "after the slash how many of those can be verified on its own site.</sub>",
        "",
        "</div>",
        "",
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
    block = summary_block(creds)
    if SUMMARY_START in text:
        head, rest = text.split(SUMMARY_START, 1)
        _, tail = rest.split(SUMMARY_END, 1)
        return head + block + tail
    marker = "## <span title="
    at = text.index(marker)
    end = text.index("\n", text.index("\n", at) + 1)
    return text[:end + 1] + "\n" + block + "\n" + text[end + 1:]


def main():
    check = "--check" in sys.argv
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    # Rows are matched by the certificate they link, which is unique and does
    # not move when a table is re-ordered or a title is edited.
    by_target = {}
    for cred in data["credentials"]:
        for key in (cred["pdf"], cred["badge"]):
            if key:
                by_target[key] = cred

    lines = write_summary(README.read_text(encoding="utf-8"),
                          data["credentials"]).splitlines()
    out, i, changed = [], 0, 0

    while i < len(lines):
        # Any table, not only the numbered ones. The experience tables are
        # headed "Role" and hold the internship letters, and two research paper
        # tables are headed "Feature"; all of them link certificates and none
        # of them showed one.
        if (not lines[i].strip().startswith("|") or i + 1 >= len(lines)
                or not RULE.match(lines[i + 1])):
            out.append(lines[i])
            i += 1
            continue
        header = re.match(r"^(\s*)\|", lines[i])

        # Collect the whole table, then decide whether it holds credentials.
        block, j = [], i
        while j < len(lines) and lines[j].strip().startswith("|"):
            block.append(lines[j])
            j += 1

        # Whether this table already carries the column is decided once, from
        # the header, and applied to every row including the alignment rule.
        # The rule row reads ":---: | :---:" either way and cannot tell you
        # itself, so asking it was what made a second run add a second column.
        head_cells = split(block[0])
        # The column goes after the number where there is one, and first
        # otherwise, so it always sits at the left of the row it belongs to.
        at = 1 if head_cells and head_cells[0] == "#" else 0
        had = len(head_cells) > at and head_cells[at] == "Preview"

        def without(cells):
            if not had or len(cells) <= at:
                return cells
            return cells[:at] + cells[at + 1:]

        creds = []
        for line in block[2:]:
            cred = None
            if line.strip().startswith("|"):
                rest = " | ".join(without(split(line)))
                for _label, href in LINK.findall(rest):
                    target = href[len(BLOB):] if href.startswith(BLOB) else href
                    target = urllib.parse.unquote(target)
                    if target in by_target:
                        cred = by_target[target]
                        break
            creds.append(cred)

        # A table earns the column when the documents are the point of it.
        # Two of the research paper tables list a journal, a preprint link, the
        # authors and one PDF; giving those a preview column means six empty
        # cells to show one thing, which reads as five things missing.
        rows_with_assets = sum(1 for c in creds if c)
        if not rows_with_assets or rows_with_assets * 2 < len(creds):
            # If an earlier run gave this table a column, take it back off
            # rather than leaving it there with nothing in it.
            out.extend([join(re.match(r"^(\s*)\|", line).group(1), without(split(line)))
                        if had and line.strip().startswith("|") else line
                        for line in block])
            i = j
            continue

        indent = header.group(1)
        head_cells = without(head_cells)
        rule_cells = without(split(block[1]))
        new = [join(indent, head_cells[:at] + ["Preview"] + head_cells[at:]),
               join(indent, rule_cells[:at] + [":---:"] + rule_cells[at:])]
        for line, cred in zip(block[2:], creds):
            m = re.match(r"^(\s*)\|", line)
            if not m:
                new.append(line)
                continue
            cells = without(split(line))
            cell = preview_cell(cred) if cred else "&nbsp;"
            new.append(join(m.group(1), cells[:at] + [cell] + cells[at:]))

        if new != block:
            changed += 1
        out.extend(new)
        i = j

    body = "\n".join(out) + "\n"
    if check:
        if body != README.read_text(encoding="utf-8"):
            print("  README preview columns are stale. Run: "
                  "python .github/scripts/build_readme.py")
            return 1
        print("  every certificate table shows its preview")
        return 0

    README.write_text(body, encoding="utf-8")
    shown = sum(1 for line in out if "docs/previews" in line or
                (".png" in line and "<img" in line))
    print(f"  {changed} table(s) rewritten, {shown} previews shown")
    return 0


if __name__ == "__main__":
    sys.exit(main())

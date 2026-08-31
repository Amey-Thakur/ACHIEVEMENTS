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


def preview_cell(cred):
    """The image for one credential, linked to the file it came from.

    A certificate that runs to several pages shows all of them, stacked in the
    one cell. Stacking rather than placing them side by side is what keeps the
    column a single width down the whole table.
    """
    if cred["pdf"]:
        pages = [f"{PREVIEWS}/{cred['id']}.jpg"]
        n = 2
        while (ROOT / f"{PREVIEWS}/{cred['id']}-{n}.jpg").exists():
            pages.append(f"{PREVIEWS}/{cred['id']}-{n}.jpg")
            n += 1
        if not (ROOT / pages[0]).exists():
            return "&nbsp;"
        images = "".join(
            f'<img src="{quote(page)}" width="{WIDTH}" '
            f'alt="{alt(cred["title"], "certificate" if i == 0 else f"certificate page {i + 1}")}">'
            for i, page in enumerate(pages))
        return f'<a href="{quote(cred["pdf"])}">{images}</a>'
    if cred["badge"]:
        return (f'<a href="{quote(cred["badge"])}">'
                f'<img src="{quote(cred["badge"])}" width="{WIDTH}" '
                f'alt="{alt(cred["title"], "badge")}"></a>')
    return "&nbsp;"


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

COLUMNS = 3


def badge(name, colour, logo):
    label = urllib.parse.quote(name.replace("-", "--"))
    src = f"https://img.shields.io/badge/{label}-{colour}?style=flat"
    if logo:
        src += f"&logo={logo}&logoColor=white"
    return f'<img src="{src}" alt="{name}" height="20">'


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
            name, colour, logo, anchor = ISSUERS[platform]
            n, v = counts[platform], checked.get(platform, 0)
            note = f"{n} credential{'s' if n != 1 else ''}"
            if v:
                note += f", {v} verifiable"
            rows.append(
                f'<td align="center" width="33%"><a href="#{anchor}">'
                f'{badge(name, colour, logo)}</a><br>'
                f'<sub>{note}</sub></td>')
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
        "Every row below shows the certificate it describes and links to the "
        "original file.",
        "",
        "\n".join(rows),
        "",
        "</div>",
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
        header = HEADER.match(lines[i])
        if not header or i + 1 >= len(lines) or not RULE.match(lines[i + 1]):
            out.append(lines[i])
            i += 1
            continue

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
        had = len(head_cells) > 1 and head_cells[1] == "Preview"

        def without(cells):
            return [cells[0]] + cells[2:] if had and len(cells) > 1 else cells

        creds = []
        for line in block[2:]:
            m = ROW.match(line)
            cred = None
            if m:
                rest = " | ".join(without(split(line))[1:])
                for _label, href in LINK.findall(rest):
                    target = href[len(BLOB):] if href.startswith(BLOB) else href
                    target = urllib.parse.unquote(target)
                    if target in by_target:
                        cred = by_target[target]
                        break
            creds.append(cred)

        if not any(creds):
            out.extend(block)
            i = j
            continue

        indent = header.group(1)
        head_cells = without(head_cells)
        rule_cells = without(split(block[1]))
        new = [join(indent, [head_cells[0], "Preview"] + head_cells[1:]),
               join(indent, [rule_cells[0], ":---:"] + rule_cells[1:])]
        for line, cred in zip(block[2:], creds):
            m = ROW.match(line)
            if not m:
                new.append(line)
                continue
            cells = without(split(line))
            cell = preview_cell(cred) if cred else "&nbsp;"
            new.append(join(m.group(1), [cells[0], cell] + cells[1:]))

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

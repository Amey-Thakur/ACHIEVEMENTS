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


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def short_key(path):
    return slugify(path.rsplit("/", 1)[-1].rsplit(".", 1)[0])


def long_key(path):
    return slugify(path.rsplit(".", 1)[0])


def preview_keys(creds):
    """One preview name per file: short, and never ambiguous.

    The name is the certificate's own filename rather than its whole path.
    GitHub renders the first 512,000 bytes of a README and drops the rest of
    the page on the floor, so a byte in a cell that repeats 859 times is worth
    having: the folder is already the section the row sits in, and leaving it
    out is twenty characters back each time.

    Twenty-three filenames appear in more than one folder - two courses called
    "What is Generative AI", from different issuers. Those keep the full path
    in their name, because a shared preview would show the wrong certificate.
    """
    together = {}
    for cred in creds:
        for asset in cred["assets"]:
            together.setdefault(short_key(asset["path"]), set()).add(asset["path"])
    keys = {}
    for name, paths in together.items():
        for path in paths:
            keys[path] = name if len(paths) == 1 else long_key(path)
    return keys


def label_of(cred, asset):
    """What the thumbnail is, in a few words: the alt a screen reader reads."""
    kind = "badge" if "badge" in asset["label"].lower() else "certificate"
    return f"{cred['title']} {kind}".replace('"', "'").replace("|", "-")


def describe(cred, asset):
    """What the thumbnail is, in full: the tooltip, and what a crawler indexes.

    Four facts, in the order a search result is matched on: the document, who
    issued it, when, and who holds it. It is deliberately terse. This string is
    written 859 times into a file GitHub stops reading at 512,000 bytes, and
    the sentence it replaced - "issued 1 August 2026 to Amey Thakur" rather
    than "1 August 2026, Amey Thakur" - cost eighteen kilobytes of the page.
    """
    label = asset["label"].lower()
    kind = "badge" if "badge" in label else (
        "professional certificate" if "professional" in label else "certificate")
    issuer = ISSUER_NAME.get(cred["platform"], cred["platform"])
    issued = asset.get("issued")
    text = f"{cred['title']}, {issuer} {kind}"
    text += f", {issued}, Amey Thakur" if issued else ", Amey Thakur"
    return text.replace('"', "'").replace("|", "-")


def preview_cell(cred, keys):
    """Every file the row holds, shown.

    A row commonly carries a certificate and its badge, and some carry two
    certificates; each of them is shown, separated by a line break, so a cell
    holding three files reads as three documents stacked rather than a strip of
    pictures wrapping wherever the cell happens to end.

    The thumbnail is not itself a link. It was, and the address of the
    certificate is ninety bytes that the row already carries in its
    Certification column; repeated across every row it was seventy kilobytes of
    a page GitHub had already stopped rendering.
    """
    parts = []
    for asset in cred.get("assets") or []:
        if asset["kind"] == "image":
            if not (ROOT / asset["path"]).exists():
                continue
            parts.append(f'<img src="{quote(asset["path"])}" width="{WIDTH}" '
                         f'alt="{label_of(cred, asset)}" '
                         f'title="{describe(cred, asset)}">')
            continue

        page = f"{PREVIEWS}/{keys[asset['path']]}.jpg"
        if not (ROOT / page).exists():
            continue
        parts.append(f'<img src="{quote(page)}" width="{WIDTH}" '
                     f'alt="{label_of(cred, asset)}" '
                     f'title="{describe(cred, asset)}">')

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


def heading_mark(platform, note):
    """The issuer's square mark, to sit in front of its section heading."""
    name = ISSUERS[platform][0]
    key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    src = f"{SQUARES}/{key}.svg"
    if not (ROOT / src).exists():
        return ""
    text = f"{name}, {note}"
    return f'<img src="{quote(src)}" alt="{text}" title="{text}" height="20">&nbsp;'


def decorate_headings(text, notes):
    """Put each issuer's mark in front of its own section heading.

    The mark is the square twin of the badge in the index above, so a reader
    scrolling past a heading sees the same thing they clicked.
    """
    wanted = {anchor: platform
              for platform, anchor in issuer_anchors(text).items()}
    lines = text.splitlines()
    for i, level, title, anchor, _rule in headings(text):
        platform = wanted.get(anchor)
        mark = heading_mark(platform, notes[platform]) if platform else ""
        lines[i] = f"{level} {mark}{title}"
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
        "Every row below shows the certificate it describes and links to the "
        "original file.",
        "",
        "\n".join(rows),
        "",
        "<sub>Each badge names the issuer and how many credentials it awarded. Hover any of them for the number that can be verified at the source.</sub>",
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
    block = summary_block(creds, issuer_anchors(text))
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

    keys = preview_keys(data["credentials"])
    _counts, notes = issuer_notes(data["credentials"])
    source = decorate_headings(README.read_text(encoding="utf-8"), notes)
    lines = write_summary(source, data["credentials"]).splitlines()
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
            # A table that is mostly not about documents does not get a column
            # of its own: the research paper tables list a journal, a preprint
            # link and the authors, and one publication certificate. The
            # certificate is still shown, inline in the cell that links it, so
            # nothing goes unseen and five empty cells are not introduced to
            # show one thing.
            rebuilt = []
            for line, cred in zip(block, [None, None] + list(creds)):
                if had and line.strip().startswith("|"):
                    line = join(re.match(r"^(\s*)\|", line).group(1),
                                without(split(line)))
                if cred:
                    cells = split(line)
                    for k, cell in enumerate(cells):
                        # Take off anything an earlier run appended before
                        # appending again, or the preview doubles every build.
                        bare = re.sub(r"<br><img .*$", "", cell)
                        if "](" in bare and any(a["path"].split("/")[-1] in
                                                urllib.parse.unquote(bare)
                                                for a in cred["assets"]):
                            cells[k] = f"{bare}<br>{preview_cell(cred, keys)}"
                            line = join(re.match(r"^(\s*)\|", line).group(1), cells)
                            break
                rebuilt.append(line)
            out.extend(rebuilt)
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
            cell = preview_cell(cred, keys) if cred else "&nbsp;"
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

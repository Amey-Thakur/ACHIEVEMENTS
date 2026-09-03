#!/usr/bin/env python3
"""Put every certificate into one PDF, so they can be seen rather than opened.

The README used to carry a thumbnail of every certificate. It showed the
collection well and it cost too much: over a thousand images, twenty-six
megabytes on every page load, and a page within a few kilobytes of the 512,000
bytes GitHub will render before it stops and drops the rest, footer included.

So the showcase moved here. This renders page one of every certificate, lays
them out issuer by issuer with the title, the date and the awarding
institution under each, and writes one document with a cover, a contents page
and a bookmark per issuer. The README keeps the record; this carries the
pictures.

    python .github/scripts/build_certificate_book.py
    python .github/scripts/build_certificate_book.py --all   # re-render every page

Writes certificates.pdf. Needs PyMuPDF and Chrome.

The certificates themselves are never touched. They are opened read-only, and
the rendered pages are cached outside the repository.
"""

import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX = ROOT / "docs" / "credentials.json"
OUT = ROOT / "certificates.pdf"
CACHE = Path(tempfile.gettempdir()) / "achievements-certificate-book"

AUTHOR = "Amey Thakur"
REPO = "github.com/Amey-Thakur/ACHIEVEMENTS"
ORCID = "0000-0001-5644-1575"
BLOB = f"https://{REPO}/blob/main/"

# Rendered wide enough to read the holder's name on a printed page, which is
# what a certificate is for. Four to a row on A4 portrait leaves each about
# 42mm across, and five rows fill the page without crowding it.
WIDTH = 420
QUALITY = 78
PER_ROW = 4

CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]

# The issuer as it should read under a certificate, where the folder is named
# differently from the institution that awarded it.
ISSUER_NAME = {
    "Anthropic courses": "Claude Academy",
    "Linkedin Learning": "LinkedIn Learning",
    "Nvidia Deep Learning Institute": "NVIDIA Deep Learning Institute",
    "Experience": "Internships",
    "Quizzes": "Quizzes and competitions",
    "Sports": "Sport",
    "Stanford University School of Medicine": "Stanford Medicine",
    "COE Pune": "College of Engineering, Pune",
    "IIT Bombay": "Indian Institute of Technology Bombay",
    "LTCE Webinar": "Lokmanya Tilak College of Engineering",
}

CSS = """
@page { size: A4 portrait; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; background: #ffffff; color: #1f2328;
       font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
/* The footer sits 10mm from the foot and stands about 8mm tall, so the content
   box stops 22mm short of the page rather than running underneath it. */
.page { position: relative; width: 210mm; height: 297mm; padding: 16mm 15mm 22mm;
        page-break-after: always; overflow: hidden; display: flex;
        flex-direction: column; }
.page:last-child { page-break-after: auto; }
.rule { position: absolute; inset: 0 0 auto 0; height: 2.5mm; background: #0969da; }
.foot { position: absolute; left: 15mm; right: 15mm; bottom: 10mm;
        display: flex; align-items: baseline; gap: 2mm;
        border-top: 1px solid #d1d9e0; padding-top: 2.5mm;
        font-size: 7.5pt; color: #59636e; }
.foot .who { font-weight: 600; color: #1f2328; }
.foot .sep { color: #b7bec6; }
.foot .what { margin-left: auto; }
.foot .no { margin-left: 5mm; font-weight: 600; color: #1f2328;
            min-width: 6mm; text-align: right; }
/* A section on a page it shares with another needs the gap to read as a
   break, not as a wider row. */
.block + .block { margin-top: 7mm; }
.block .kicker { margin-bottom: 1.5mm; }
.block h2 { margin-bottom: 4mm; }
h1 { font-size: 26pt; margin: 0 0 2mm; font-weight: 600; letter-spacing: -0.3pt; }
h2 { font-size: 13pt; margin: 0 0 5mm; font-weight: 600; }
.kicker { font-size: 8pt; letter-spacing: 1.4pt; text-transform: uppercase;
          color: #59636e; font-weight: 700; margin: 0 0 2mm; }
.small { font-size: 8.5pt; color: #59636e; }
/* The cover borrows the social preview: navy ground, a gold rule with a
   diamond at each corner, everything centred, the title in a serif. Nothing on
   it is a number, because a cover that counts is out of date the next time a
   certificate arrives. */
.cover-page { background: #0d2340; color: #e8ecf1; padding: 0;
              display: flex; align-items: center; justify-content: center; }
.cover-page .rule { display: none; }
.frame { position: absolute; inset: 12mm; border: 0.4mm solid #b08d3f; }
.frame span { position: absolute; width: 3mm; height: 3mm;
              background: #b08d3f; transform: rotate(45deg); }
.frame .tl { top: -1.5mm; left: -1.5mm; }
.frame .tr { top: -1.5mm; right: -1.5mm; }
.frame .bl { bottom: -1.5mm; left: -1.5mm; }
.frame .br { bottom: -1.5mm; right: -1.5mm; }
.middle { text-align: center; padding: 0 28mm; }
.middle .kicker { color: #c9a227; letter-spacing: 4pt; margin-bottom: 8mm;
                  font-size: 8.5pt; }
.middle h1 { font-family: Georgia, "Times New Roman", serif; color: #ffffff;
             font-size: 27pt; font-weight: 400; letter-spacing: 2.5pt;
             line-height: 1.32; margin: 0 0 9mm; text-transform: uppercase; }
.diamond { display: flex; align-items: center; justify-content: center;
           gap: 4mm; margin: 0 0 9mm; }
.diamond i { display: block; width: 22mm; height: 0.25mm; background: #6a7f9c; }
.diamond b { display: block; width: 2mm; height: 2mm; background: #b08d3f;
             transform: rotate(45deg); }
.middle .line { font-size: 11pt; color: #c3cdda; line-height: 1.62;
                margin: 0 0 14mm; }
.middle .sig { font-size: 8pt; letter-spacing: 2.6pt; color: #8b9bb0;
               text-transform: uppercase; }
.middle .said { font-family: Georgia, "Times New Roman", serif;
                font-size: 13pt; font-style: italic; color: #e8ecf1;
                line-height: 1.6; margin: 0 0 10mm; }
.middle .namaskar { font-family: Georgia, "Times New Roman", serif;
                    font-size: 10pt; font-style: italic; color: #b08d3f;
                    margin: 6mm 0 0; }
.index { display: flex; gap: 10mm; }
.index table { flex: 1; border-collapse: collapse; font-size: 8.6pt; }
.index th { text-align: left; font-size: 7pt; letter-spacing: 0.8pt;
            text-transform: uppercase; color: #8a93a0; font-weight: 700;
            padding: 0 0 1.5mm; border-bottom: 0.4mm solid #d1d9e0; }
.index td { padding: 1.5mm 0; border-bottom: 0.2mm solid #eef1f4;
            vertical-align: top; }
.index .n { text-align: right; width: 12mm; color: #59636e; }
.lead { font-size: 9.5pt; color: #59636e; margin: 0 0 5mm; }
.grid { display: grid; grid-template-columns: repeat(%(per_row)d, 1fr);
        gap: 6mm 6mm; align-content: start; }
.card { display: flex; flex-direction: column; gap: 1.6mm; }
/* Every certificate gets the same box and sits in the middle of it. They are
   not the same shape: a landscape certificate beside a portrait one leaves the
   captions on two different lines, and a page of that reads as a mistake. */
.card .shot { height: 30mm; }
/* The link is the flex item, not the picture. With the anchor left to size
   itself the image had no definite height to measure a percentage against, so
   max-height did nothing and every portrait certificate overflowed its box
   into the captions below it. */
.card .shot a { display: flex; height: 100%%; width: 100%%;
                align-items: center; justify-content: center;
                text-decoration: none; }
.card img { max-width: 100%%; max-height: 100%%; width: auto; height: auto;
            border: 1px solid #d1d9e0; border-radius: 1mm; display: block; }
.card .t { font-size: 7.2pt; font-weight: 600; line-height: 1.3;
           color: #1f2328; }
.card .m { font-size: 6.6pt; color: #59636e; line-height: 1.28; }
.contents { columns: 2; column-gap: 10mm; font-size: 9pt; }
.contents div { break-inside: avoid; margin-bottom: 1.8mm; }
.contents .n { color: #59636e; }
"""


def find_chrome():
    for path in CHROME:
        if Path(path).exists():
            return path
    found = shutil.which("chrome") or shutil.which("google-chrome")
    if not found:
        raise SystemExit("  Chrome is needed to render the PDF and was not found")
    return found


def quote(path):
    return urllib.parse.quote(path)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def render(path, target):
    """Page one of a certificate, as a JPEG, without touching the original."""
    import pymupdf

    source = ROOT / path
    if path.lower().endswith((".png", ".jpg", ".jpeg")):
        from PIL import Image
        with Image.open(source) as im:
            im = im.convert("RGB")
            ratio = WIDTH / im.width
            im = im.resize((WIDTH, max(1, round(im.height * ratio))),
                           Image.LANCZOS)
            im.save(target, "JPEG", quality=QUALITY, optimize=True)
        return True
    with pymupdf.open(source) as doc:
        page = doc[0]
        zoom = WIDTH / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        pix.pil_save(target, format="JPEG", quality=QUALITY, optimize=True)
    return True


def uri(path):
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()


def escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def page(inner, label, number):
    """One page, with the same rule above and the same credit below.

    The holder's name and the repository are on every page, not only the
    cover, because a page of this is as likely to be sent on by itself as the
    whole document is.
    """
    return (f'<section class="page"><div class="rule"></div>{inner}'
            f'<div class="foot"><span class="who">{escape(AUTHOR)}</span>'
            f'<span class="sep">&middot;</span><span>{escape(REPO)}</span>'
            f'<span class="what">{escape(label)}</span>'
            f'<span class="no">{number}</span></div></section>')


def cover(number):
    """Title, one sentence, and a name. No counts.

    A cover that states how many certificates there are is wrong the next time
    one is issued, and this document is rebuilt often enough for that to
    happen. The figures live on the contents page, where they are read as a
    listing rather than as a claim.
    """
    return (f'<section class="page cover-page">'
            f'<div class="frame"><span class="tl"></span><span class="tr"></span>'
            f'<span class="bl"></span><span class="br"></span></div>'
            f'<div class="middle">'
            f'<p class="kicker">Archive</p>'
            f'<h1>Certifications<br>and Achievements</h1>'
            f'<div class="diamond"><i></i><b></b><i></i></div>'
            f'<p class="line">Every credential kept as the document that was '
            f'issued, filed under the body that awarded it, and checkable at '
            f'the source rather than taken on trust.</p>'
            f'<p class="sig">{escape(AUTHOR)} &nbsp;&middot;&nbsp; '
            f'ORCID {ORCID}</p>'
            f'</div></section>')


def closing():
    """The last page, in his own words rather than a manufactured sign-off.

    The same line the repository ends on, so the document closes the way the
    page it came from does. It bookends the cover: same ground, same frame.
    """
    return ('<section class="page cover-page">'
            '<div class="frame"><span class="tl"></span><span class="tr"></span>'
            '<span class="bl"></span><span class="br"></span></div>'
            '<div class="middle">'
            '<div class="diamond"><i></i><b></b><i></i></div>'
            '<p class="said">Every idea I open-source is a spark handed to '
            'someone I may never meet. That is the whole point.</p>'
            f'<p class="sig">{escape(AUTHOR)}</p>'
            '<p class="namaskar">Namaskar</p>'
            '</div></section>')


def contents(sections, starts, number):
    """The issuers, as a table. Two columns of prose made the eye hunt."""
    half = -(-len(sections) // 2)
    columns = [sections[:half], sections[half:]]
    tables = ""
    for part in columns:
        rows = "".join(
            f'<tr><td>{escape(name)}</td><td class="n">{len(cards)}</td>'
            f'<td class="n">{starts.get(name, "")}</td></tr>'
            for name, cards in part)
        tables += (f'<table><thead><tr><th>Issuer</th><th class="n">Held</th>'
                   f'<th class="n">Page</th></tr></thead>'
                   f'<tbody>{rows}</tbody></table>')
    total = sum(len(c) for _n, c in sections)
    return page(f'<p class="kicker">Contents</p><h1>By issuer</h1>'
                f'<p class="lead">{total} certificates from {len(sections)} '
                f'issuers, in the order they appear.</p>'
                f'<div class="index">{tables}</div>', "Contents", number)


def main():
    try:
        import pymupdf
    except ImportError:
        print("  PyMuPDF is required: pip install pymupdf")
        return 1

    again = "--all" in sys.argv
    CACHE.mkdir(parents=True, exist_ok=True)
    data = json.loads(INDEX.read_text(encoding="utf-8"))

    by_issuer = {}
    for cred in data["credentials"]:
        for asset in cred["assets"]:
            by_issuer.setdefault(cred["platform"], []).append((cred, asset))

    made = failed = 0
    sections = []
    for platform in sorted(by_issuer, key=lambda p: ISSUER_NAME.get(p, p).lower()):
        cards = []
        for cred, asset in by_issuer[platform]:
            target = CACHE / f"{slug(asset['path'])}.jpg"
            if not target.exists() or again:
                try:
                    render(asset["path"], target)
                    made += 1
                except Exception as error:  # noqa: BLE001
                    print(f"  could not render {asset['path']}: {str(error)[:60]}")
                    failed += 1
                    continue
            note = asset.get("issued") or "date not printed"
            if asset["label"] and asset["label"] != "Certificate":
                note = f"{asset['label']} &middot; {note}"
            cards.append((cred["title"], note, target, asset["path"]))
        if cards:
            sections.append((ISSUER_NAME.get(platform, platform), cards))

    total_files = sum(len(c) for _n, c in sections)

    # Sections flow onto pages rather than each taking one of its own. Apple
    # has three certificates and Yale one; a page each left most of the paper
    # empty and made the document look padded rather than full.
    # Measured, not guessed: the content box is 259mm tall, a row of cards is
    # about 46mm of it, a section's opening heading about 15mm and a continued
    # one about 8mm. check_book_layout.py measures the result and fails if this
    # is optimistic.
    rows_per_page = 5.2
    first_heading = 0.33
    more_heading = 0.18

    pages_of, current, left = [], [], float(rows_per_page)
    starts = {}
    for name, cards in sections:
        first = True
        at = 0
        while at < len(cards) or first:
            cost = first_heading if first else more_heading
            if left - cost < 1:
                pages_of.append(current)
                current, left = [], float(rows_per_page)
            room = int(left - cost)
            take = cards[at:at + room * PER_ROW]
            if first:
                starts[name] = len(pages_of) + 3
            current.append((name, take, first, len(cards)))
            left -= cost + -(-len(take) // PER_ROW)
            at += len(take)
            first = False
            if at >= len(cards):
                break
    if current:
        pages_of.append(current)

    body_pages = []
    for number, blocks in enumerate(pages_of, 3):
        inner = ""
        for name, chunk, first, total in blocks:
            tiles = "".join(
                f'<div class="card"><div class="shot">'
                f'<a href="{BLOB}{quote(source)}">'
                f'<img src="{uri(path)}" alt=""></a></div>'
                f'<div class="t">{escape(title)}</div>'
                f'<div class="m">{note}</div></div>'
                for title, note, path, source in chunk)
            inner += (f'<div class="block"><p class="kicker">{escape(name)}'
                      f'{"" if first else ", continued"}</p>'
                      + (f'<h2>{total} certificate{"s" if total != 1 else ""}</h2>'
                         if first else "")
                      + f'<div class="grid">{tiles}</div></div>')
        label = blocks[0][0] if len(blocks) == 1 else "Certificates"
        body_pages.append(page(inner, label, number))

    pages = [cover(1),
             contents(sections, starts, 2)]
    pages.extend(body_pages)
    pages.append(closing())

    html = (f"<!doctype html><meta charset='utf-8'><style>{CSS % {'per_row': PER_ROW}}"
            f"</style>{''.join(pages)}")
    work = CACHE / "book.html"
    work.write_text(html, encoding="utf-8")

    subprocess.run([find_chrome(), "--headless", "--disable-gpu",
                    "--no-pdf-header-footer", "--print-to-pdf-no-header",
                    f"--print-to-pdf={OUT}", work.as_uri()],
                   check=True, capture_output=True, timeout=1800)

    # Chrome writes no outline, so the bookmarks are added afterwards. Without
    # them a two hundred page document can only be paged through.
    with pymupdf.open(OUT) as doc:
        toc = [[1, "Cover", 1], [1, "Contents", 2]]
        toc += [[1, name, starts[name]] for name, _cards in sections
                if name in starts]
        doc.set_toc(toc)
        doc.saveIncr()
        count = doc.page_count

    size = OUT.stat().st_size
    # The README states the size and the page count, and build_readme.py is
    # standard library only, so the two facts are left here for it to read
    # rather than opening a PDF to find them.
    (ROOT / "docs" / "book.json").write_text(
        json.dumps({"pages": count, "bytes": size, "certificates": total_files,
                    "issuers": len(sections)}, indent=2) + "\n",
        encoding="utf-8")

    print(f"  {made} pages rendered, {failed} that could not be read")
    print(f"  {total_files} certificates from {len(sections)} issuers")
    print(f"  {OUT.name}: {count} pages, {size / 1e6:.1f} MB")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

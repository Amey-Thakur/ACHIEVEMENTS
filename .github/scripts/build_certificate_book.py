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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX = ROOT / "docs" / "credentials.json"
OUT = ROOT / "certificates.pdf"
CACHE = Path(tempfile.gettempdir()) / "achievements-certificate-book"

AUTHOR = "Amey Thakur"
REPO = "github.com/Amey-Thakur/ACHIEVEMENTS"

# Rendered wide enough to read the holder's name on a printed page, which is
# what a certificate is for. Five to a row on A4 landscape leaves each about
# 54mm across, and three rows fill the page without crowding it.
WIDTH = 420
QUALITY = 78
PER_ROW = 5

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
@page { size: A4 landscape; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; background: #ffffff; color: #1f2328;
       font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { position: relative; width: 297mm; height: 210mm; padding: 14mm 15mm 16mm;
        page-break-after: always; overflow: hidden; display: flex;
        flex-direction: column; }
.page:last-child { page-break-after: auto; }
.rule { position: absolute; inset: 0 0 auto 0; height: 3mm; background: #0969da; }
.foot { position: absolute; left: 15mm; right: 15mm; bottom: 7mm;
        display: flex; border-top: 1px solid #d1d9e0; padding-top: 2.5mm;
        font-size: 8pt; color: #59636e; }
.foot .no { margin-left: auto; font-weight: 600; color: #1f2328; }
h1 { font-size: 34pt; margin: 0 0 4mm; font-weight: 600; letter-spacing: -0.4pt; }
h2 { font-size: 15pt; margin: 0 0 1mm; font-weight: 600; }
.kicker { font-size: 9pt; letter-spacing: 1.2pt; text-transform: uppercase;
          color: #59636e; font-weight: 700; margin: 0 0 3mm; }
.lead { font-size: 12pt; color: #424a53; margin: 0 0 3mm; max-width: 210mm;
        line-height: 1.55; }
.small { font-size: 8.5pt; color: #59636e; }
/* The cover holds its title block in the middle and its credit at the foot,
   so the page carries one measured gap rather than two. */
.cover { justify-content: center; }
.stats { display: flex; gap: 14mm; margin: 6mm 0 0; padding-top: 5mm;
         border-top: 1px solid #d1d9e0; }
.stats .v { font-size: 19pt; font-weight: 600; }
.stats .k { font-size: 8.5pt; color: #59636e; }
.by { position: absolute; left: 15mm; bottom: 16mm; font-size: 10pt; }
.by b { font-size: 12pt; }
.grid { display: grid; grid-template-columns: repeat(%(per_row)d, 1fr);
        gap: 7mm 6mm; align-content: start; }
.card { display: flex; flex-direction: column; gap: 1.6mm; }
/* Every certificate gets the same box and sits in the middle of it. They are
   not the same shape: a landscape certificate beside a portrait one leaves the
   captions on two different lines, and a page of that reads as a mistake. */
.card .shot { height: 38mm; display: flex; align-items: center;
              justify-content: center; }
.card img { max-width: 100%%; max-height: 100%%; width: auto; height: auto;
            border: 1px solid #d1d9e0; border-radius: 1mm; display: block; }
.card .t { font-size: 7.6pt; font-weight: 600; line-height: 1.32;
           color: #1f2328; }
.card .m { font-size: 6.9pt; color: #59636e; line-height: 1.3; }
.contents { columns: 3; column-gap: 10mm; font-size: 9.5pt; }
.contents div { break-inside: avoid; margin-bottom: 1.6mm; }
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
    return (f'<section class="page"><div class="rule"></div>{inner}'
            f'<div class="foot"><span>{escape(label)}</span>'
            f'<span class="no">{number}</span></div></section>')


def cover(counts, number):
    issuers, files, dated = counts
    stats = "".join(
        f'<div><div class="v">{v}</div><div class="k">{k}</div></div>'
        for v, k in ((f"{files}", "certificates"), (f"{issuers}", "issuers"),
                     (f"{dated}", "carrying a date")))
    return (f'<section class="page cover"><div class="rule"></div>'
            f'<p class="kicker">Certificates and achievements</p>'
            f'<h1>Every certificate, in one place</h1>'
            f'<p class="lead">The complete record behind '
            f'{escape(REPO)}: every certificate, professional certificate and '
            f'completion badge awarded to {escape(AUTHOR)}, shown as it was '
            f'issued. Each one is filed in the repository under the issuer '
            f'that awarded it, with its verification link where the issuer '
            f'provides one.</p>'
            f'<div class="stats">{stats}</div>'
            f'<div class="by">Compiled by <b>{escape(AUTHOR)}</b><br>'
            f'<span class="small">{escape(REPO)}</span></div>'
            f'<div class="foot"><span>Certificates and achievements</span>'
            f'<span class="no">{number}</span></div></section>')


def contents(sections, first_page, number):
    rows, at = [], first_page
    for name, cards in sections:
        rows.append(f'<div>{escape(name)} <span class="n">'
                    f'&middot; {len(cards)} &middot; page {at}</span></div>')
        at += max(1, -(-len(cards) // (PER_ROW * 3)))
    return page(f'<p class="kicker">Contents</p><h1>By issuer</h1>'
                f'<div class="contents">{"".join(rows)}</div>',
                "Contents", number)


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
            cards.append((cred["title"], note, target))
        if cards:
            sections.append((ISSUER_NAME.get(platform, platform), cards))

    total_files = sum(len(c) for _n, c in sections)
    dated = sum(1 for _n, cards in sections for _t, note, _p in cards
                if "not printed" not in note)

    pages = [cover((len(sections), total_files, dated), 1)]
    body_pages, number = [], 3
    for name, cards in sections:
        per_page = PER_ROW * 3
        for start in range(0, len(cards), per_page):
            chunk = cards[start:start + per_page]
            tiles = "".join(
                f'<div class="card"><div class="shot">'
                f'<img src="{uri(path)}" alt=""></div>'
                f'<div class="t">{escape(title)}</div>'
                f'<div class="m">{note}</div></div>'
                for title, note, path in chunk)
            heading = (f'<p class="kicker">{escape(name)}</p>'
                       f'<h2>{len(cards)} certificate'
                       f'{"s" if len(cards) != 1 else ""}</h2>'
                       if start == 0 else
                       f'<p class="kicker">{escape(name)}, continued</p>')
            body_pages.append(page(f'{heading}<div class="grid">{tiles}</div>',
                                   name, number))
            number += 1
    pages.append(contents(sections, 3, 2))
    pages.extend(body_pages)

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
        toc, at = [["Cover", 1], ["Contents", 2]], 3
        for name, cards in sections:
            toc.append([name, at])
            at += max(1, -(-len(cards) // (PER_ROW * 3)))
        doc.set_toc([[1, title, page_no] for title, page_no in toc])
        doc.saveIncr()
        count = doc.page_count

    size = OUT.stat().st_size
    print(f"  {made} pages rendered, {failed} that could not be read")
    print(f"  {total_files} certificates from {len(sections)} issuers")
    print(f"  {OUT.name}: {count} pages, {size / 1e6:.1f} MB")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

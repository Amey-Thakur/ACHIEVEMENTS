#!/usr/bin/env python3
"""Render the first page of every certificate to a thumbnail for the gallery.

A certificate that only exists as a PDF inside a folder is not shown to
anybody. The gallery shows the certificate itself, which means an image, and
these are it.

The images are committed alongside the PDFs they come from, because the README
shows them and a README cannot render a file that only exists after a build.
The PDFs themselves are never written to, moved or renamed: this reads page one
and writes a new file next to the index.

    python .github/scripts/build_thumbnails.py           # missing ones only
    python .github/scripts/build_thumbnails.py --all     # rebuild everything

Needs PyMuPDF.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX = ROOT / "docs" / "credentials.json"
OUT = ROOT / "docs" / "previews"

# Wide enough to read the holder's name and the issuer on a retina screen at
# card size, small enough that six hundred of them stay under ten megabytes.
WIDTH = 480
QUALITY = 74

# Four pages is enough to show what a certificate contains; the longest here
# is a ten page quiz record whose remaining pages are the same form repeated.
MAX_PAGES = 4


def main():
    rebuild = "--all" in sys.argv
    try:
        import pymupdf
    except ImportError:
        print("  PyMuPDF is not installed: pip install pymupdf")
        return 1

    data = json.loads(INDEX.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    made = skipped = failed = 0
    for cred in data["credentials"]:
        if not cred["pdf"]:
            continue
        target = OUT / f"{cred['id']}.jpg"
        source = ROOT / cred["pdf"]
        if not source.exists():
            print(f"  MISSING  {cred['pdf']}")
            failed += 1
            continue
        try:
            with pymupdf.open(source) as doc:
                # Ten certificates run to more than one page, and a preview of
                # only the first hides half of what they say. Every page is
                # rendered; the README stacks them in one column so the table
                # keeps a single width.
                for number in range(min(doc.page_count, MAX_PAGES)):
                    out = target if number == 0 else \
                        OUT / f"{cred['id']}-{number + 1}.jpg"
                    if out.exists() and not rebuild:
                        continue
                    page = doc[number]
                    zoom = WIDTH / page.rect.width
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                    pix.pil_save(out, format="JPEG", quality=QUALITY, optimize=True)
            made += 1
        except Exception as exc:  # noqa: BLE001  (one bad PDF must not stop the rest)
            print(f"  FAILED   {cred['pdf']}: {exc}")
            failed += 1

    total = sum((OUT / f"{c['id']}.jpg").stat().st_size
                for c in data["credentials"]
                if c["pdf"] and (OUT / f"{c['id']}.jpg").exists())
    print(f"  {made} rendered, {skipped} already present, {failed} failed")
    print(f"  {total // 1024 // 1024} MB in {OUT.relative_to(ROOT).as_posix()}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

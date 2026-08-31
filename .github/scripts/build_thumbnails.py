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
import re
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


def preview_key(path):
    """A preview is named after the file it came from, not after the row.

    Keying on the row meant a row linking two certificates could only ever show
    one of them.
    """
    return re.sub(r"[^a-z0-9]+", "-", path.lower().rsplit(".", 1)[0]).strip("-")


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
    wanted = set()
    for cred in data["credentials"]:
        for asset in cred["assets"]:
            if asset["kind"] != "pdf":
                continue
            source = ROOT / asset["path"]
            key = preview_key(asset["path"])
            wanted.add(key)
            target = OUT / f"{key}.jpg"
            if not source.exists():
                print(f"  MISSING  {asset['path']}")
                failed += 1
                continue
            if target.exists() and not rebuild:
                skipped += 1
                continue
            try:
                with pymupdf.open(source) as doc:
                    # Ten certificates run to more than one page, and a preview
                    # of only the first hides half of what they say. Every page
                    # is rendered; the README stacks them in one column so the
                    # table keeps a single width.
                    for number in range(min(doc.page_count, MAX_PAGES)):
                        out = target if number == 0 else OUT / f"{key}-{number + 1}.jpg"
                        page = doc[number]
                        zoom = WIDTH / page.rect.width
                        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom),
                                              alpha=False)
                        pix.pil_save(out, format="JPEG", quality=QUALITY,
                                     optimize=True)
                made += 1
            except Exception as exc:  # noqa: BLE001  (one bad PDF must not stop the rest)
                print(f"  FAILED   {asset['path']}: {exc}")
                failed += 1

    # A preview whose certificate is gone is dead weight and would keep being
    # served by the README until somebody noticed.
    stale = 0
    for old_file in OUT.glob("*.jpg"):
        base = re.sub(r"-\d+$", "", old_file.stem)
        if base not in wanted and old_file.stem not in wanted:
            old_file.unlink()
            stale += 1
    if stale:
        print(f"  {stale} preview(s) removed for certificates no longer listed")

    total = sum(f.stat().st_size for f in OUT.glob("*.jpg"))
    print(f"  {made} rendered, {skipped} already present, {failed} failed")
    print(f"  {total // 1024 // 1024} MB in {OUT.relative_to(ROOT).as_posix()}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

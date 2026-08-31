#!/usr/bin/env python3
"""Read the certificates that carry no text, so their dates can be recovered.

Most certificates here are typeset and PyMuPDF can read the date straight off
the page. Some are photographs or flattened scans: the date is printed on them
plainly enough for a person to read, and not at all for a text extractor. The
COE Pune workshop certificate is one of those, and it says "9th & 10th March
2019" in the middle of the page.

This runs an optical character reader over exactly those files and records what
it saw in docs/ocr-text.json, with the recogniser's own confidence beside every
line. build_dates.py reads that cache like any other text source, so the date
pass keeps working on a machine with no OCR engine installed and the cache stays
reviewable: a wrong date can be traced to the line it came from.

    python .github/scripts/read_dates_ocr.py           # only files not yet read
    python .github/scripts/read_dates_ocr.py --all     # read everything again

Needs rapidocr-onnxruntime and PyMuPDF. Nothing is written to the certificates
themselves; they are opened read-only and never touched.
"""

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX = ROOT / "docs" / "credentials.json"
CACHE = ROOT / "docs" / "ocr-text.json"

# Two pages is enough. A date printed later than that is on a transcript rather
# than a certificate, and reading every page of everything costs minutes.
MAX_PAGES = 2

# Below this the recogniser is guessing at the shapes, and a guessed digit is a
# wrong date rather than a missing one.
KEEP = 0.5

DPI = 200
IMAGES = {"png", "jpg", "jpeg"}


def pages(path):
    """The pictures to read for one asset: rendered PDF pages, or the image."""
    import pymupdf
    from PIL import Image

    if path.suffix.lower().lstrip(".") in IMAGES:
        with Image.open(path) as im:
            yield im.convert("RGB")
        return
    with pymupdf.open(path) as doc:
        for number in range(min(MAX_PAGES, doc.page_count)):
            pix = doc[number].get_pixmap(dpi=DPI)
            with Image.open(io.BytesIO(pix.tobytes("png"))) as im:
                yield im.convert("RGB")


def main():
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        print("  the OCR engine is not installed: "
              "pip install rapidocr-onnxruntime")
        return 1

    again = "--all" in sys.argv
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    wanted = []
    for cred in data["credentials"]:
        for asset in cred["assets"]:
            if asset.get("issued"):
                continue
            path = asset["path"]
            if path in wanted or (path in cache and not again):
                continue
            wanted.append(path)

    if not wanted:
        print("  every undated certificate has already been read")
        return 0

    engine = RapidOCR()
    read = empty = failed = 0
    for n, path in enumerate(wanted, 1):
        source = ROOT / path
        lines = []
        try:
            for picture in pages(source):
                found, _elapsed = engine(np.array(picture))
                for _box, text, score in found or []:
                    if float(score) >= KEEP:
                        lines.append([text, round(float(score), 3)])
        except Exception as error:  # noqa: BLE001
            failed += 1
            print(f"  [{n}/{len(wanted)}] could not read {path}: {error}")
            continue
        cache[path] = lines
        read += 1
        empty += not lines
        if n % 10 == 0 or n == len(wanted):
            CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False) + "\n",
                             encoding="utf-8")
            print(f"  [{n}/{len(wanted)}] read", flush=True)

    CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    print(f"  {read} certificates read, {empty} of them carrying no legible "
          f"text at all, {failed} that could not be opened")
    print(f"  written to {CACHE.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

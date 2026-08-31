#!/usr/bin/env python3
"""Ask GitHub for every picture the README shows, and report any it will not serve.

audit.py checks that each image exists on disk. That is not the same question:
a file can be present locally and absent from the branch, or present in the
branch under a name that differs by a character, and the reader sees a broken
image either way. This asks the server.

    python .github/scripts/check_images.py
    python .github/scripts/check_images.py --workers 4

Standard library only. Exits non-zero if anything is missing.
"""

import concurrent.futures as cf
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
README = ROOT / "README.md"
RAW = "https://raw.githubusercontent.com/Amey-Thakur/ACHIEVEMENTS/main/"

WORKERS = 6
TRIES = 3
AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")


def head(path):
    """Whether the branch serves this file, with a retry: a page asking for a
    thousand pictures at once will have a few refused for the asking, not for
    the file."""
    url = RAW + urllib.parse.quote(urllib.parse.unquote(path))
    for attempt in range(TRIES):
        request = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as r:
                return path, r.status, ""
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return path, 404, "not on the branch"
            reason = f"{error.code}"
        except Exception as error:  # noqa: BLE001
            reason = str(error)[:60]
        time.sleep(1.5 * (attempt + 1))
    return path, 0, reason


def main():
    workers = WORKERS
    if "--workers" in sys.argv:
        workers = int(sys.argv[sys.argv.index("--workers") + 1])

    text = README.read_text(encoding="utf-8")
    wanted = sorted({s for s in re.findall(r'<img [^>]*src="([^"]+)"', text)
                     if not s.startswith("http")})
    print(f"  {len(wanted)} pictures to ask about, {workers} at a time")

    bad = []
    done = 0
    with cf.ThreadPoolExecutor(workers) as pool:
        for path, status, why in pool.map(head, wanted):
            done += 1
            if status != 200:
                bad.append((path, status, why))
            if done % 200 == 0:
                print(f"  {done} asked, {len(bad)} missing", flush=True)

    if bad:
        for path, status, why in bad[:25]:
            print(f"  MISSING  {status}  {urllib.parse.unquote(path)}  {why}")
        if len(bad) > 25:
            print(f"  ... and {len(bad) - 25} more")
        print(f"\n  {len(bad)} of {len(wanted)} pictures are not being served.")
        return 1
    print(f"  every one of the {len(wanted)} is served.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

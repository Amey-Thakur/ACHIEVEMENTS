#!/usr/bin/env python3
"""Check that every verification link in the README still resolves.

A verification link is the only part of this repository a stranger can use to
confirm a certificate is real. A dead one is worse than none: it looks like
proof and is not. Issuers retire verification services without notice, so the
links are checked rather than assumed.

    python .github/scripts/check_verify_links.py           # check them all
    python .github/scripts/check_verify_links.py --slow    # one at a time

Standard library only. Exits non-zero if any link is gone.
"""

import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX = ROOT / "docs" / "credentials.json"

AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")
TIMEOUT = 25

# A verification page that answers at all is doing its job. Several issuers
# return 403 to anything without a browser fingerprint and 429 when a run
# checks many of their links at once; neither means the credential is gone.
TOLERATED = {403, 405, 429, 999}


def once(url):
    request = urllib.request.Request(url, method="GET", headers={
        "User-Agent": AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    })
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT, context=context) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__


def check(url):
    """One link, retried on a server error.

    Eighty-four of these point at one host, and checking them quickly makes it
    answer 502 to about one in eight. That is the checker being rude, not a
    credential being gone, and reporting it as a dead link would send somebody
    to fix something that was never broken.
    """
    for attempt in range(3):
        status, err = once(url)
        if status and (200 <= status < 400 or status in TOLERATED):
            return status, err
        if status is not None and status < 500:
            return status, err
        time.sleep(1.5 * (attempt + 1))
    return status, err


def main():
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    links = {}
    for cred in data["credentials"]:
        if cred["verify"]:
            links.setdefault(cred["verify"], []).append(cred["title"])

    print(f"  {len(links)} distinct verification links to check")
    # Four at a time, so no single issuer sees a burst.
    workers = 1 if "--slow" in sys.argv else 4
    urls = list(links)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(check, urls))

    dead, tolerated = [], 0
    for url, (status, err) in zip(urls, results):
        if status and 200 <= status < 400:
            continue
        if status in TOLERATED:
            tolerated += 1
            continue
        dead.append((url, status or err, links[url][0]))

    print(f"  {len(urls) - len(dead) - tolerated} answered, "
          f"{tolerated} refused an automated request, {len(dead)} did not answer")
    for url, why, title in sorted(dead, key=lambda d: str(d[1])):
        print(f"    {str(why):>18}  {title[:44]:44}  {url}")
    return 1 if dead else 0


if __name__ == "__main__":
    sys.exit(main())

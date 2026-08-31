#!/usr/bin/env python3
"""Fetch each issuer's own mark, once, into docs/logos/.

The issuer index reads as a list of names without them. With them it reads as a
row of institutions, which is the point: these are other people's credentials,
and their marks are what says so.

Shields.io was tried first and cannot do it. Simple-icons has dropped Microsoft,
IBM, LinkedIn, MathWorks and OpenAI after trademark requests, and it never had
the universities, so half the row would have carried no mark at all.

Where simple-icons carries the brand, its vector mark is used, drawn in white:
it is the mark the brand publishes for exactly this purpose, and it reads
cleanly at twenty pixels in a way a favicon cropped for a browser tab does not.
Nine of these issuers have one. For the rest, the mark is the icon the issuer
serves from its own domain: the touch icon where there is one, because it is
the largest, and the favicon otherwise.

The source URL is recorded beside every file, so the provenance is checkable.

    python .github/scripts/build_logos.py            # fetch what is missing
    python .github/scripts/build_logos.py --all      # fetch everything again

Needs Pillow.
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "docs" / "logos"
SOURCES = OUT / "sources.json"

SIZE = 128
AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

# The platform name in credentials.json, and the domain that issued it.
DOMAINS = {
    "Ankur Warikoo": "warikoo.com",
    "Anthropic courses": "anthropic.com",
    "Apple": "apple.com",
    "COE Pune": "coep.org.in",
    "Colgate Oral Health Network": "colgateoralhealthnetwork.com",
    "Coursera": "coursera.org",
    "Eduonix": "eduonix.com",
    "Google": "google.com",
    "Harvard Medical School": "hms.harvard.edu",
    "IBM": "ibm.com",
    "IIT Bombay": "iitb.ac.in",
    "Intel": "intel.com",
    "Julia Academy": "julialang.org",
    "Kaggle": "kaggle.com",
    "LTCE Webinar": "ltce.in",
    "Linkedin Learning": "linkedin.com",
    "MathWorks": "mathworks.com",
    "Microsoft": "microsoft.com",
    "Nvidia Deep Learning Institute": "nvidia.com",
    "OpenAI Academy": "openai.com",
    "Simplilearn": "simplilearn.com",
    "Stanford University": "stanford.edu",
    "Stanford University School of Medicine": "medicine.stanford.edu",
    "Terna Engineering College": "ternaengg.ac.in",
    "Udemy": "udemy.com",
    "University of Cambridge": "cam.ac.uk",
    "VIA Institute on Character": "viacharacter.org",
}

# Two sections are not issuers and have no mark to fetch: the quiz records come
# from many small organisers, and the sports awards from schools and clubs.
NO_MARK = {"Quizzes", "Sports"}

# The brands simple-icons carries, by the name they are listed under here.
# Microsoft, IBM, LinkedIn, MathWorks and OpenAI were all removed from that set
# after trademark requests, so those fall back to the site icon.
VECTOR = {
    "Anthropic courses": "anthropic",
    "Apple": "apple",
    "Coursera": "coursera",
    "Google": "google",
    "Intel": "intel",
    "Julia Academy": "julia",
    "Kaggle": "kaggle",
    "Nvidia Deep Learning Institute": "nvidia",
    "Udemy": "udemy",
}


ICON = re.compile(
    r'<link[^>]+rel=["\'][^"\']*(?:apple-touch-icon|icon)[^"\']*["\'][^>]*>',
    re.I)
HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
SIZES = re.compile(r'sizes=["\'](\d+)x\d+["\']', re.I)


def fetch(url, timeout=20):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as r:
        return r.read(), r.geturl()


def candidates(domain):
    """Icon URLs for a domain, largest first, then the search-engine fallback."""
    found = []
    for scheme in ("https://www.", "https://"):
        try:
            html, final = fetch(scheme + domain, timeout=18)
        except Exception:  # noqa: BLE001
            continue
        page = html.decode("utf-8", "replace")
        for tag in ICON.findall(page):
            href = HREF.search(tag)
            if not href:
                continue
            size = SIZES.search(tag)
            found.append((int(size.group(1)) if size else 0,
                          urllib.parse.urljoin(final, href.group(1))))
        break
    found.sort(reverse=True)
    urls = [u for _s, u in found]
    urls.append(f"https://www.google.com/s2/favicons?domain={domain}&sz={SIZE}")
    return urls


def vector(slug, path):
    """Save a simple-icons mark as SVG, white.

    The badge inlines this path rather than a picture of it, so the mark is as
    sharp as the type beside it at any size.
    """
    try:
        data, final = fetch(f"https://cdn.simpleicons.org/{slug}/white")
    except Exception:  # noqa: BLE001
        return None
    text = data.decode("utf-8", "replace")
    if "<svg" not in text:
        return None
    path.with_suffix(".svg").write_text(text, encoding="utf-8")
    return final


def measure(data):
    """The pixel area of an icon, so the largest candidate can be chosen."""
    from PIL import Image
    import io
    try:
        with Image.open(io.BytesIO(data)) as im:
            widest = im.size
            for frame in range(getattr(im, "n_frames", 1)):
                im.seek(frame)
                if im.size[0] * im.size[1] > widest[0] * widest[1]:
                    widest = im.size
        return widest[0] * widest[1]
    except Exception:  # noqa: BLE001
        return 0


def square(data, path):
    """Normalise to one size on a transparent ground, so the grid stays even."""
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(data))
    if getattr(im, "n_frames", 1) > 1:          # an .ico holds several sizes
        best, area = im, im.size[0] * im.size[1]
        for frame in range(im.n_frames):
            im.seek(frame)
            if im.size[0] * im.size[1] > area:
                best, area = im.copy(), im.size[0] * im.size[1]
        im = best
    im = im.convert("RGBA")
    # Scale to fill, not just to fit. thumbnail() only ever shrinks, so a
    # sixteen pixel favicon stayed sixteen pixels in the middle of a hundred
    # and twenty eight pixel canvas and came out as a speck on the badge.
    original = im.size
    ratio = min(SIZE / im.width, SIZE / im.height)
    im = im.resize((max(1, round(im.width * ratio)),
                    max(1, round(im.height * ratio))), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2), im)
    canvas.save(path, "PNG", optimize=True)
    return original


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    again = "--all" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    sources = json.loads(SOURCES.read_text(encoding="utf-8")) if SOURCES.exists() else {}

    got = kept = failed = 0
    for name, domain in DOMAINS.items():
        target = OUT / f"{slug(name)}.png"
        if target.exists() and not again:
            kept += 1
            continue
        # The published vector mark first, where there is one. A raster is
        # still fetched beside it, so anything that cannot inline an SVG has
        # something to fall back to.
        if name in VECTOR:
            final = vector(VECTOR[name], target)
            if final:
                sources[slug(name)] = {"issuer": name, "domain": domain,
                                       "source": final}
                print(f"  {name:40} vector   {final[:62]}")
                got += 1
                continue
        target.with_suffix(".svg").unlink(missing_ok=True)

        # Try every candidate and keep the largest. Taking the first that
        # answers gave sixteen pixel marks for Cambridge and IIT Bombay, which
        # are specks beside a hundred and twenty eight pixel one.
        best = None
        for url in candidates(domain):
            try:
                data, final = fetch(url)
                area = measure(data)
            except Exception:  # noqa: BLE001
                continue
            if area and (best is None or area > best[0]):
                best = (area, data, final)
        if best is None:
            print(f"  {name:40} no icon found")
            failed += 1
            continue
        size = square(best[1], target)
        sources[slug(name)] = {"issuer": name, "domain": domain, "source": best[2]}
        print(f"  {name:40} {size[0]}x{size[1]:<4} {best[2][:62]}")
        got += 1

    SOURCES.write_text(json.dumps(sources, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"\n  {got} fetched, {kept} already present, {failed} without a mark")
    print(f"  {len(NO_MARK)} sections have no issuer to fetch one from: "
          f"{', '.join(sorted(NO_MARK))}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

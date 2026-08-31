#!/usr/bin/env python3
"""Fetch each issuer's own mark, once, into docs/logos/.

The issuer index reads as a list of names without them. With them it reads as a
row of institutions, which is the point: these are other people's credentials,
and their marks are what says so.

Every mark here is named explicitly, with the address it came from, because
guessing was not good enough. Reading a site's favicon and hoping worked for
about half of them and quietly failed for the rest: IBM's site icon is a
generic product tile rather than the eight-bar logo, IIT Bombay's is a sixteen
pixel square, and the LTCE one is an unreadable smudge. Each entry below was
looked at before it was accepted.

Four kinds of source, in order of preference:

  vector   The brand's own single-path mark, drawn in white. Simple-icons
           publishes most of these brands. Microsoft, IBM, LinkedIn and OpenAI
           were withdrawn from the current release after trademark requests, so
           those come from version 9.21.0, the last one that carried them.
  vector   The institution's own SVG, where it publishes one. COEP and
           Cambridge both serve a white version for dark backgrounds, which is
           exactly what a badge needs. Cambridge serves it as a lock-up, so the
           viewBox here trims it to the crest.
  raster   The institution's own PNG, where that is all it serves.
  vector   A plain symbol from Bootstrap Icons, for the two sections that are
           not issuers and so have no mark of their own.

A mark is only ever the compact one. A horizontal lock-up shrunk into a
fourteen pixel square is a smudge, and the badge already prints the name beside
it, so a wordmark would say it twice.

    python .github/scripts/build_logos.py            # fetch what is missing
    python .github/scripts/build_logos.py --all      # fetch everything again

Needs Pillow.
"""

import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "docs" / "logos"
SOURCES = OUT / "sources.json"

SIZE = 256
AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

SI = "https://cdn.simpleicons.org/"
SI9 = "https://cdn.jsdelivr.net/npm/simple-icons@9.21.0/icons/"
BI = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/icons/"

# The mark for each issuer, by the platform name in credentials.json.
#
#   url       where it comes from
#   kind      svg to inline, png to embed
#   viewBox   trims an SVG lock-up down to its mark
#   crop      "left-square" takes the mark off the front of a lock-up
#   ground    a background colour to clear, for an app icon drawn on a tile
#   white     redraws a raster as a white silhouette, for a mark that is one
#             solid colour and would otherwise be dark on a dark badge
#   draw      the mark is redrawn here rather than used as served; see DRAWN
MARKS = {
    "Ankur Warikoo": {
        "url": "https://ankurwarikoo.com/wp-content/uploads/2020/06/"
               "cropped-Copy-of-aw-1.png",
        "kind": "png"},
    "Anthropic courses": {"url": SI + "anthropic/white", "kind": "svg"},
    "Apple": {"url": SI + "apple/white", "kind": "svg"},
    "COE Pune": {
        "url": "https://www.coeptech.ac.in/wp-content/uploads/2023/10/brand-white.svg",
        "kind": "svg"},
    "Colgate Oral Health Network": {
        "url": "https://cdn.dental-tribune.com/cohn/wp-content/themes/cohn/"
               "images/favicon/android-icon-192x192.png",
        "kind": "png"},
    "Coursera": {"url": SI + "coursera/white", "kind": "svg"},
    "Eduonix": {"url": "https://cdn.eduonix.com/assets/images/logo_wht.png",
                "kind": "png", "crop": "left-square"},
    "Google": {"url": SI + "google/white", "kind": "svg"},
    "Harvard Medical School": {
        "url": "https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON"
               "&fallback_opts=TYPE,SIZE,URL&url=http://hms.harvard.edu&size=128",
        "kind": "png"},
    "IBM": {"url": SI9 + "ibm.svg", "kind": "svg"},
    "IIT Bombay": {
        "url": "https://www.iitb.ac.in/themes/custom/iitb_bootstrap/logo.png",
        "kind": "png"},
    "Intel": {"url": SI + "intel/white", "kind": "svg"},
    "Julia Academy": {"url": SI + "julia", "kind": "svg", "draw": "julia"},
    "Kaggle": {"url": "https://www.kaggle.com/static/images/favicon.ico",
               "kind": "png", "ground": "#ffffff", "white": True},
    "LTCE Webinar": {"url": "https://ltce.in/images/ltce-logo-tr.png",
                     "kind": "png"},
    "Linkedin Learning": {"url": SI9 + "linkedin.svg", "kind": "svg"},
    "MathWorks": {"url": "https://in.mathworks.com/favicon.ico", "kind": "png"},
    "Microsoft": {"url": SI9 + "microsoft.svg", "kind": "svg"},
    "Nvidia Deep Learning Institute": {"url": SI + "nvidia/white", "kind": "svg"},
    "OpenAI Academy": {"url": SI9 + "openai.svg", "kind": "svg"},
    "Quizzes": {"url": BI + "question-circle-fill.svg", "kind": "svg"},
    "Simplilearn": {
        "url": "https://www.simplilearn.com/static/frontend/images/favicon/"
               "apple-touch-icon-152x152_v2.png",
        "kind": "png", "ground": "#ffffff", "white": True},
    "Sports": {"url": BI + "trophy-fill.svg", "kind": "svg"},
    "Stanford University": {
        "url": "https://www.stanford.edu/icon1.png", "kind": "png"},
    "Stanford University School of Medicine": {
        "url": "https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON"
               "&fallback_opts=TYPE,SIZE,URL&url=http://medicine.stanford.edu"
               "&size=128",
        "kind": "png"},
    "Terna Engineering College": {
        "url": "https://ternaengg.ac.in/wp-content/uploads/site-icon-300x300.png",
        "kind": "png"},
    "Udemy": {"url": SI + "udemy/white", "kind": "svg"},
    "University of Cambridge": {
        "url": "https://www.cam.ac.uk/themes/custom/fresh/images/interface/"
               "university_logo_white-01.svg",
        "kind": "svg", "viewBox": "0 0 38 44"},
    "VIA Institute on Character": {
        "url": "https://static.viacharacter.org/web/via_brandmark_white.png",
        "kind": "png"},
}

# The organisations named inside an issuer's section: the universities whose
# courses Coursera hosts, the companies whose courses LinkedIn Learning hosts,
# and the training arms of issuers already listed above. Their headings carry a
# mark too, so a reader scrolling the Coursera section can see at a glance
# which institution taught what.
#
# Each entry names where the mark comes from and the colour it sits on:
#   ("si", slug)    simple-icons, current release
#   ("si9", slug)   simple-icons 9.21.0, for the brands withdrawn since
#   ("site", host)  the institution's own icon, discovered from its home page
#
# The colours are each brand's or institution's published one. A crest read off
# a favicon cannot be trusted to give it: half of these render on white.
PARTNERS = {
    # Coursera's partner institutions
    "Amazon Web Services (AWS)": (("si9", "amazonaws"), "#232F3E"),
    "Case Western Reserve University EST.1826": (("site", "case.edu"), "#0A304E"),
    "Coursera Project Network": (("si", "coursera"), "#0056D2"),
    "DeepLearning.AI": (("site", "deeplearning.ai"), "#0B5FA5"),
    "Duke University": (("site", "duke.edu"), "#00539B"),
    "Georgia Institute of Technology": (("site", "gatech.edu"), "#003057"),
    "Imperial College London": (("site", "imperial.ac.uk"), "#003E74"),
    "Indian School of Business (ISB)": (("site", "isb.edu"), "#8A1538"),
    "INSEAD - The Business School for the World, Fontainebleau, France":
        (("site", "insead.edu"), "#0033A0"),
    "Johns Hopkins University": (("site", "jhu.edu"), "#002D72"),
    "McMaster University": (("site", "brand.mcmaster.ca"), "#7A003C"),
    "Osmosis.org": (("site", "osmosis.org"), "#00A5B5"),
    "SUNY - The State University of New York": (("site", "suny.edu"), "#00539B"),
    "The Linux Foundation": (("si", "linuxfoundation"), "#003778"),
    "The University of Edinburgh": (("site", "ed.ac.uk"), "#00325F"),
    "University of Alberta": (("site", "ualberta.ca"), "#007C41"),
    "University of California Irvine": (("site", "uci.edu"), "#0064A4"),
    "University of California San Diego": (("site", "ucsd.edu"), "#182B49"),
    "University of California, Irvine Division of Continuing Education":
        (("site", "ce.uci.edu"), "#0064A4"),
    "University of Cape Town": (("site", "uct.ac.za"), "#003B5C"),
    "University of Colorado Boulder": (("site", "colorado.edu"), "#565A5C"),
    "University of Florida": (("site", "ufl.edu"), "#0021A5"),
    "University of London": (("site", "london.ac.uk"), "#00263A"),
    "University of Michigan": (("site", "umich.edu"), "#00274C"),
    "University of Minnesota": (("site", "umn.edu"), "#7A0019"),
    "University of North Carolina at Chapel Hill": (("site", "unc.edu"), "#13294B"),
    "University of Toronto": (("site", "utoronto.ca"), "#002A5C"),
    "University of Virginia": (("site", "virginia.edu"), "#232D4B"),
    "Yale University": (("si", "yale"), "#00356B"),
    # Google's own academies
    "Google Digital Unlocked": (("si", "google"), "#4285F4"),
    "Google Play Academy": (("si", "googleplay"), "#414141"),
    "Google Skillshop": (("si", "google"), "#4285F4"),
    # the training arms of issuers already listed
    "IBM Training": (("si9", "ibm"), "#0F62FE"),
    "IIT Bombay Training": (("site", "iitb.ac.in"), "#003366"),
    "Intel® AI Academy": (("si", "intel"), "#0071C5"),
    "Julia Academy": (("si", "julia"), "#4063D8"),
    "Kaggle Academy": (("site", "kaggle.com"), "#20BEFF"),
    "MATLAB Academy": (("site", "in.mathworks.com"), "#0076A8"),
    "Microsoft Training": (("si9", "microsoft"), "#0067B8"),
    "NVIDIA Training": (("si", "nvidia"), "#76B900"),
    # LinkedIn Learning's course providers
    "Adobe": (("si9", "adobe"), "#FF0000"),
    "Aha!": (("site", "aha.io"), "#0089FF"),
    "All Tech Is Human": (("site", "alltechishuman.org"), "#1F3A5F"),
    "American Marketing Association": (("site", "ama.org"), "#005EB8"),
    "Anaconda": (("si", "anaconda"), "#44A833"),
    "Astronomer": (("site", "astronomer.io"), "#2B6CB0"),
    "Atlassian": (("si", "atlassian"), "#0052CC"),
    "Canonical": (("si", "canonical"), "#E95420"),
    "ChurnZero": (("site", "churnzero.com"), "#00B2A9"),
    "Docker": (("si", "docker"), "#2496ED"),
    "GitHub": (("si", "github"), "#24292F"),
    "Grammarly": (("si", "grammarly"), "#027E6F"),
    "Intuit Mailchimp": (("si", "mailchimp"), "#241C15"),
    "KNIME": (("si", "knime"), "#3E4E58"),
    "LinkedIn": (("si9", "linkedin"), "#0A66C2"),
    "Moz": (("site", "moz.com"), "#00A4BD"),
    "Mozilla": (("si", "mozilla"), "#161616"),
    "PagerDuty": (("si", "pagerduty"), "#06AC38"),
    "SS&C Blue Prism": (("site", "blueprism.com"), "#0C2340"),
    "ServiceNow": (("site", "servicenow.com"), "#062D30"),
    "Snowflake": (("si", "snowflake"), "#29B5E8"),
    "TestMu AI": (("site", "lambdatest.com"), "#FF6112"),
    "Toastmasters International": (("site", "toastmasters.org"), "#772432"),
    "Wolfram Research": (("si", "wolfram"), "#DD1100"),
    "Zendesk": (("si", "zendesk"), "#03363D"),
}


# Julia's three dots are its logo only in its own colours. Flattened to one
# they are three circles that say nothing, which is what was wrong with them.
# Simple-icons draws all three as a single path, so they cannot be coloured
# separately by editing it; the circles are redrawn here at the centres and
# radius that path describes, in the three shades JuliaLang publishes.
DRAWN = {
    "julia": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
              'role="img"><title>Julia</title>'
              '<circle cx="5.569" cy="17.569" r="5.569" fill="#CB3C33"/>'
              '<circle cx="12" cy="6.431" r="5.569" fill="#9558B2"/>'
              '<circle cx="18.431" cy="17.569" r="5.569" fill="#389826"/></svg>'),
}

# Two of these are sections rather than issuers: the quiz records come from
# many small organisers and the sports awards from schools and clubs, so
# neither has a logo of its own. They carry a plain symbol from Bootstrap
# Icons, which is MIT licensed and says what the section is without pretending
# to be anyone's mark.
NO_MARK = set()


def fetch(url, timeout=30):
    host = urllib.parse.urlparse(url).netloc
    request = urllib.request.Request(url, headers={
        "User-Agent": AGENT, "Accept": "*/*", "Referer": f"https://{host}/"})
    with urllib.request.urlopen(request, timeout=timeout) as r:
        return r.read()


def as_svg(data, spec):
    text = data.decode("utf-8", "replace")
    if "<svg" not in text:
        return None
    if spec.get("viewBox"):
        text = re.sub(r'viewBox="[^"]*"', f'viewBox="{spec["viewBox"]}"',
                      text, count=1)
    if spec.get("draw"):
        return DRAWN[spec["draw"]]
    head = text.split(">", 1)[0]
    if "currentColor" in head:
        # Bootstrap draws in currentColor, which resolves to black inside the
        # badge because the mark sits outside the group that sets the text
        # colour. It is pinned to white here instead.
        text = text.replace("currentColor", "#ffffff", 1)
    elif 'fill="' not in head:
        text = text.replace("<svg", '<svg fill="#ffffff"', 1)
    return text


def open_widest(data):
    """The largest frame in the file: an .ico holds several sizes."""
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    if getattr(im, "n_frames", 1) > 1:
        best, area = im.copy(), im.size[0] * im.size[1]
        for frame in range(im.n_frames):
            im.seek(frame)
            if im.size[0] * im.size[1] > area:
                best, area = im.copy(), im.size[0] * im.size[1]
        im = best
    return im.convert("RGBA")


def clear_colour(im, colour):
    """Clear one named background colour, wherever it appears.

    An app icon is a picture of a tile: the mark sits on a white square with
    rounded corners, so the corners are transparent and the ground beneath the
    mark is not. Nothing detects that on its own, so the colour is named.
    """
    from PIL import Image
    want = tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    px, ox = im.load(), out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            near = all(abs(v - want[i]) <= 30 for i, v in enumerate((r, g, b)))
            ox[x, y] = (0, 0, 0, 0) if near else (r, g, b, a)
    return out


def drop_flat_ground(im):
    """Clear a solid background, so the mark is not a tile on the badge."""
    from PIL import Image
    corners = [im.getpixel(p) for p in
               ((0, 0), (im.width - 1, 0), (0, im.height - 1),
                (im.width - 1, im.height - 1))]
    if not all(c[3] > 250 for c in corners):
        return im
    ground = corners[0]
    if any(abs(c[i] - ground[i]) > 12 for c in corners for i in range(3)):
        return im
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    px, ox = im.load(), out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            near = all(abs(v - ground[i]) <= 24 for i, v in enumerate((r, g, b)))
            ox[x, y] = (0, 0, 0, 0) if near else (r, g, b, a)
    return out


def trim(im):
    box = im.getbbox()
    return im.crop(box) if box else im


def left_square(im):
    """The mark off the front of a lock-up: as wide as the artwork is tall."""
    im = trim(im)
    return trim(im.crop((0, 0, min(im.height, im.width), im.height)))


def whiten(im):
    from PIL import Image
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    px, ox = im.load(), out.load()
    for y in range(im.height):
        for x in range(im.width):
            ox[x, y] = (255, 255, 255, px[x, y][3])
    return out


def as_png(data, spec, path):
    """Normalise a raster: one size, trimmed to the mark, transparent ground."""
    from PIL import Image
    im = drop_flat_ground(open_widest(data))
    if spec.get("ground"):
        im = clear_colour(im, spec["ground"])
    if spec.get("crop") == "left-square":
        im = left_square(im)
    im = trim(im)
    if spec.get("white"):
        im = whiten(im)
    ratio = min(SIZE / im.width, SIZE / im.height)
    im = im.resize((max(1, round(im.width * ratio)),
                    max(1, round(im.height * ratio))), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2), im)
    canvas.save(path, "PNG", optimize=True)
    return im.size


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


ICON = re.compile(
    r'<link[^>]+rel=["\'][^"\']*(?:apple-touch-icon|icon)[^"\']*["\'][^>]*>', re.I)
HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
SIZES = re.compile(r'sizes=["\'](\d+)x\d+["\']', re.I)


def site_icon(domain):
    """The largest icon a site declares, or the search engine's copy of it.

    An institution that publishes no SVG still publishes a touch icon, which is
    the biggest picture of its crest it has. The declared sizes are read rather
    than guessed at, because a sixteen pixel favicon scaled up to a badge is a
    smudge and there is usually a 180 pixel one beside it.
    """
    found = []
    for scheme in ("https://www.", "https://"):
        try:
            page = fetch(scheme + domain, timeout=20).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            continue
        for tag in ICON.findall(page):
            href = HREF.search(tag)
            if not href:
                continue
            size = SIZES.search(tag)
            found.append((int(size.group(1)) if size else 0,
                          urllib.parse.urljoin(scheme + domain, href.group(1))))
        break
    found.sort(reverse=True)
    urls = [u for _s, u in found if not u.lower().endswith(".svg")]
    urls += [u for _s, u in found if u.lower().endswith(".svg")]
    urls.append(f"https://www.google.com/s2/favicons?domain={domain}&sz=128")
    return urls


def partner_spec(source):
    """A partner's source, in the same shape as an issuer's."""
    where, what = source
    if where == "si":
        return {"url": SI + what + "/white", "kind": "svg"}
    if where == "si9":
        return {"url": SI9 + what + ".svg", "kind": "svg"}
    return {"urls": site_icon(what), "kind": "png", "domain": what}


def main():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("  Pillow is not installed: pip install pillow")
        return 1

    again = "--all" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    sources = json.loads(SOURCES.read_text(encoding="utf-8")) if SOURCES.exists() else {}

    got = kept = failed = 0

    def save(name, spec, colour=None):
        """Fetch one mark and record where it came from. True if it landed."""
        nonlocal got, kept, failed
        key = slug(name)
        target = OUT / f"{key}.{spec['kind']}"
        if target.exists() and not again:
            kept += 1
            return True
        urls = spec.get("urls") or [spec["url"]]
        data = error = None
        for url in urls:
            try:
                data = fetch(url)
                spec = {**spec, "url": url}
                break
            except Exception as bad:  # noqa: BLE001
                error = bad
        if data is None:
            print(f"  {name}: {str(error)[:80]}")
            failed += 1
            return False
        # A site can answer a request for its icon with an SVG, and Astronomer
        # does. What arrived decides how it is stored, not what was expected.
        if b"<svg" in data[:600]:
            spec = {**spec, "kind": "svg"}
            target = OUT / f"{key}.svg"
        if spec["kind"] == "svg":
            text = as_svg(data, spec)
            if not text:
                print(f"  {name}: the address did not answer with an SVG")
                failed += 1
                return False
            target.write_text(text, encoding="utf-8")
        else:
            try:
                as_png(data, spec, target)
            except Exception as bad:  # noqa: BLE001
                print(f"  {name}: {str(bad)[:80]}")
                failed += 1
                return False
        # Only one file per issuer: a leftover from an earlier run in the other
        # format would still be found by the badge builder and quietly used.
        other = OUT / f"{key}.{'png' if spec['kind'] == 'svg' else 'svg'}"
        if other.exists():
            other.unlink()
        sources[key] = {"issuer": name, "source": spec["url"],
                        "kind": spec["kind"]}
        if colour:
            sources[key]["colour"] = colour
        got += 1
        return True

    for name, spec in MARKS.items():
        save(name, spec)
    for name, (source, colour) in PARTNERS.items():
        save(name, partner_spec(source), colour)

    for stale in list(OUT.glob("*.png")) + list(OUT.glob("*.svg")):
        if stale.stem not in {slug(n) for n in list(MARKS) + list(PARTNERS)}:
            stale.unlink()
            print(f"  removed a mark for an issuer no longer listed: {stale.name}")

    SOURCES.write_text(json.dumps(sources, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    vectors = sum(1 for s in sources.values() if s["kind"] == "svg")
    print(f"  {got} fetched, {kept} already held, {failed} that did not answer")
    print(f"  {len(MARKS)} issuers and {len(PARTNERS)} named organisations "
          f"inside them carry a mark, {vectors} of them vector")
    return 0


if __name__ == "__main__":
    sys.exit(main())

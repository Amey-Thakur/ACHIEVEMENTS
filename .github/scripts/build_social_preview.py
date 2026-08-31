#!/usr/bin/env python3
"""Render the repository's social preview card.

GitHub shows this image wherever the repository is shared, and it is the only
thing most people will see. It is built from the same index the README is, so
the figures on it are counted rather than typed and cannot drift as more
certificates arrive.

    python .github/scripts/build_social_preview.py

Writes .github/social-preview.png at 1280x640, the size GitHub asks for.
Needs a Chrome; PyMuPDF only to read the mosaic tiles.
"""

import base64
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX = ROOT / "docs" / "credentials.json"
PREVIEWS = ROOT / "docs" / "previews"
OUT = ROOT / ".github" / "social-preview.png"
HTML = ROOT / ".github" / "social-preview.html"

# The card is drawn at twice the final size and scaled down, which is what
# keeps the small type crisp.
WIDTH, HEIGHT, SCALE = 1280, 640, 2

# One row of real certificates behind the title, so the card shows the thing
# the repository holds rather than describing it.
TILES = 13


def chrome():
    for candidate in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def data_uri(path):
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()


def main():
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    creds = data["credentials"]
    issuers = len({c["platform"] for c in creds})
    verified = sum(1 for c in creds if c["verify"])

    # Spread the tiles across the issuers rather than taking the first few, so
    # the strip is not thirteen certificates from one platform.
    picked, seen = [], set()
    for cred in creds:
        if cred["platform"] in seen:
            continue
        image = PREVIEWS / f"{cred['id']}.jpg"
        if image.exists():
            picked.append(image)
            seen.add(cred["platform"])
        if len(picked) == TILES:
            break
    for cred in creds:
        if len(picked) >= TILES:
            break
        image = PREVIEWS / f"{cred['id']}.jpg"
        if image.exists() and image not in picked:
            picked.append(image)

    strip = "".join(f'<img src="{data_uri(p)}">' for p in picked)

    HTML.write_text(f"""<!doctype html><meta charset="utf-8"><style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ width: {WIDTH}px; height: {HEIGHT}px; overflow: hidden;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    background: #0d1117; color: #e6edf3; position: relative; }}
  .strip {{ position: absolute; inset: auto 0 0 0; display: flex; gap: 10px;
    padding: 0 26px 26px; opacity: 0.62; }}
  .strip img {{ width: calc((100% - {(TILES - 1) * 10}px) / {TILES});
    border-radius: 5px; display: block; border: 1px solid #30363d; }}
  .wash {{ position: absolute; inset: 0;
    background: linear-gradient(180deg, #0d1117 40%, rgba(13,17,23,0.86) 58%,
      rgba(13,17,23,0.18) 100%); }}
  .body {{ position: relative; padding: 62px 64px 0; }}
  .eyebrow {{ font-size: 19px; letter-spacing: 3.4px; text-transform: uppercase;
    color: #7d8590; font-weight: 600; }}
  h1 {{ font-size: 78px; line-height: 1.03; font-weight: 700; margin-top: 16px;
    letter-spacing: -1.6px; }}
  h1 span {{ color: #58a6ff; }}
  p {{ font-size: 25px; color: #adbac7; margin-top: 20px; max-width: 900px;
    line-height: 1.42; }}
  .stats {{ display: flex; gap: 54px; margin-top: 34px; }}
  .stat .v {{ font-size: 42px; font-weight: 700; letter-spacing: -0.8px; }}
  .stat .k {{ font-size: 16px; color: #7d8590; letter-spacing: 1.5px;
    text-transform: uppercase; margin-top: 4px; font-weight: 600; }}
  .rule {{ position: absolute; inset: 0 0 auto 0; height: 7px;
    background: linear-gradient(90deg, #58a6ff, #a371f7 52%, #d97757); }}
</style>
<div class="strip">{strip}</div>
<div class="wash"></div>
<div class="rule"></div>
<div class="body">
  <div class="eyebrow">Amey Thakur</div>
  <h1>Certifications<br><span>and Achievements</span></h1>
  <p>Every certificate shown, linked to its original file, and verifiable at
  the issuer.</p>
  <div class="stats">
    <div class="stat"><div class="v">{len(creds)}</div><div class="k">Credentials</div></div>
    <div class="stat"><div class="v">{issuers}</div><div class="k">Issuers</div></div>
    <div class="stat"><div class="v">{verified}</div><div class="k">Verifiable</div></div>
  </div>
</div>""", encoding="utf-8")

    exe = chrome()
    if exe is None:
        print("  no Chrome found; wrote the HTML only")
        return 1
    subprocess.run([
        exe, "--headless", "--disable-gpu", "--hide-scrollbars",
        f"--screenshot={OUT}", f"--window-size={WIDTH},{HEIGHT}",
        f"--force-device-scale-factor={SCALE}", HTML.as_uri(),
    ], capture_output=True, check=False)

    if not OUT.exists():
        print("  render failed")
        return 1

    try:
        from PIL import Image
        with Image.open(OUT) as im:
            im.convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS).save(
                OUT, "PNG", optimize=True)
    except ImportError:
        pass

    HTML.unlink()
    print(f"  {OUT.relative_to(ROOT).as_posix()}: "
          f"{WIDTH}x{HEIGHT}, {OUT.stat().st_size // 1024} KB")
    print(f"  {len(creds)} credentials, {issuers} issuers, {verified} verifiable")
    return 0


if __name__ == "__main__":
    sys.exit(main())

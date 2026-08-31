#!/usr/bin/env python3
"""Render the repository's social preview card.

GitHub shows this wherever the repository is shared, and it is the only thing
most people will ever see of it.

It carries no counts and no certificates, deliberately. The collection grows,
so a card that says how many there are is wrong within a month, and a card
built from particular certificates ages the moment the newest one arrives. What
is on it is what stays true: whose record this is, what the record contains,
and that every entry can be checked at its source.

    python .github/scripts/build_social_preview.py

Writes .github/social-preview.png at 1280x640, the size GitHub asks for.
Needs a Chrome.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / ".github" / "social-preview.png"
HTML = ROOT / ".github" / "social-preview.html"

# Drawn at twice the final size and scaled down, which is what keeps the
# letterspaced small caps crisp.
WIDTH, HEIGHT, SCALE = 1280, 640, 2

CARD = """<!doctype html><meta charset="utf-8"><style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    width: WIDTHpx; height: HEIGHTpx; overflow: hidden;
    background: #0b1a30;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    color: #e8edf5; position: relative;
  }
  /* A single soft light from above left, so the ground is not a flat block. */
  .glow {
    position: absolute; inset: 0;
    background: radial-gradient(78% 62% at 28% 8%,
      rgba(84,124,190,0.24), rgba(11,26,48,0) 70%);
  }
  .frame {
    position: absolute; inset: 28px;
    border: 1px solid rgba(197,164,96,0.42);
  }
  /* The corner marks are four small rotated squares sitting on the frame. */
  .frame i {
    position: absolute; width: 7px; height: 7px; background: #c5a460;
    transform: rotate(45deg);
  }
  .frame i:nth-child(1) { top: -4px; left: -4px; }
  .frame i:nth-child(2) { top: -4px; right: -4px; }
  .frame i:nth-child(3) { bottom: -4px; left: -4px; }
  .frame i:nth-child(4) { bottom: -4px; right: -4px; }

  .body {
    position: relative; height: 100%;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    text-align: center; padding: 0 108px;
  }
  .eyebrow {
    font-size: 17px; letter-spacing: 7px; text-transform: uppercase;
    color: #c5a460; font-weight: 600;
  }
  h1 {
    font-family: Georgia, "Times New Roman", serif;
    font-size: 61px; font-weight: 400; line-height: 1.22;
    letter-spacing: 5px; text-transform: uppercase;
    margin-top: 26px; color: #ffffff;
  }
  /* Rule, diamond, rule: the divider under the title. */
  .divider {
    display: flex; align-items: center; justify-content: center;
    gap: 18px; margin-top: 34px; width: 340px;
  }
  .divider span { flex: 1; height: 1px; background: rgba(197,164,96,0.55); }
  .divider b { width: 6px; height: 6px; background: #c5a460;
    transform: rotate(45deg); }
  p {
    font-size: 22px; line-height: 1.62; color: #a9b6c9;
    margin-top: 30px; max-width: 830px;
  }
  .foot {
    position: absolute; left: 0; right: 0; bottom: 62px;
    font-size: 15px; letter-spacing: 3.4px; text-transform: uppercase;
    color: #6f7f96; text-align: center;
  }
  .foot em { font-style: normal; color: #97a6bb; }
</style>
<div class="glow"></div>
<div class="frame"><i></i><i></i><i></i><i></i></div>
<div class="body">
  <div class="eyebrow">Archive</div>
  <h1>Certifications<br>and Achievements</h1>
  <div class="divider"><span></span><b></b><span></span></div>
  <p>Every credential kept as the document that was issued, filed under the
  body that awarded it, and checkable at the source rather than taken on
  trust.</p>
</div>
<div class="foot"><em>Amey Thakur</em> &nbsp;·&nbsp; ORCID 0000-0001-5644-1575</div>"""


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


def main():
    HTML.write_text(
        CARD.replace("WIDTHpx", f"{WIDTH}px").replace("HEIGHTpx", f"{HEIGHT}px"),
        encoding="utf-8")

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
    print("  no counts and no certificates on it, so nothing on it can go stale")
    return 0


if __name__ == "__main__":
    sys.exit(main())

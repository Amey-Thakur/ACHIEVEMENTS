#!/usr/bin/env python3
"""Measure every page of the book: nothing may overflow, nothing may overlap.

A page in this document is a fixed size and clips whatever does not fit, so a
page that has outgrown itself does not look broken. It looks finished, with a
row of captions quietly cut in half.

So the pages are measured rather than looked at. The check runs against the
same HTML Chrome prints from, in a browser, and reports two things: anything
painted outside the printable box, and any two painted boxes sharing pixels.

    python .github/scripts/check_book_layout.py

Needs Playwright and Chrome. Run build_certificate_book.py first; this reads
the HTML it leaves in the cache.
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HTML = Path(tempfile.gettempdir()) / "achievements-certificate-book" / "book.html"

MEASURE = """
() => {
  const mm = 96 / 25.4;
  const out = [];
  document.querySelectorAll('.page').forEach((page, n) => {
    const box = page.getBoundingClientRect();
    // The footer sits 10mm from the foot and stands about 8mm tall. Content
    // has to stop above the rule, not run underneath it.
    const limits = {
      top: box.top, left: box.left + 12 * mm,
      right: box.right - 12 * mm, bottom: box.bottom - 20 * mm,
    };
    // The footer and the cover's credit line live below the content limit by
    // design, so they are not content and are not measured against it.
    const items = [...page.querySelectorAll(
      '.card, .kicker, h1, h2, .contents div, .stats')]
      .filter(n => !n.closest('.foot') && !n.closest('.by'));
    const boxes = [];
    items.forEach(node => {
      [...node.getClientRects()].forEach(r => {
        if (r.width > 0.5 && r.height > 0.5) boxes.push({ r, node });
      });
    });
    boxes.forEach(({ r, node }) => {
      if (r.bottom > limits.bottom + 1 || r.top < limits.top - 1 ||
          r.left < limits.left - 1 || r.right > limits.right + 1) {
        out.push({ page: n + 1, kind: 'overflow',
                   what: (node.className || node.tagName) + ': ' +
                         node.innerText.slice(0, 40) });
      }
    });
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i].r, b = boxes[j].r;
        const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (w > 1 && h > 1) {
          out.push({ page: n + 1, kind: 'overlap',
                     what: boxes[i].node.innerText.slice(0, 26) + ' / ' +
                           boxes[j].node.innerText.slice(0, 26) });
        }
      }
    }
  });
  return { pages: document.querySelectorAll('.page').length, problems: out };
}
"""

CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright is not installed: pip install playwright")
        return 1
    if not HTML.exists():
        print("  no built page to measure: run build_certificate_book.py first")
        return 1

    browser = next((c for c in CHROME if Path(c).exists()), None)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=browser) if browser \
            else p.chromium.launch()
        page = b.new_page(viewport={"width": 1200, "height": 1000})
        page.goto(HTML.as_uri(), wait_until="load", timeout=180000)
        page.wait_for_timeout(2500)
        found = page.evaluate(MEASURE)
        b.close()

    problems = found["problems"]
    if not problems:
        print(f"  {found['pages']} pages: nothing overflows the printable box, "
              f"nothing overlaps.")
        return 0
    kinds = {}
    for item in problems:
        kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
    for item in problems[:14]:
        print(f"  page {item['page']:>3}  {item['kind']:8} "
              f"{item['what'].strip()[:70]}")
    if len(problems) > 14:
        print(f"  ... and {len(problems) - 14} more")
    print(f"\n  {found['pages']} pages, "
          + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())) + ".")
    return 1


if __name__ == "__main__":
    sys.exit(main())

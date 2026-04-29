#!/usr/bin/env python3
"""Render font contact sheets for visual classification.

Generates HTML pages showing batches of fonts loaded from Google Fonts,
then screenshots each page with Playwright to produce PNG contact sheets.
"""

import json
import math
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "gfonts" / "data"
OUTPUT_DIR = Path(__file__).resolve().parent / "contact_sheets"
FONTS_PER_PAGE = 100
SAMPLE_TEXT = "Handgloves 0123"


def load_allowlist():
    data = json.loads((DATA_DIR / "allowlist.json").read_text())
    return [(f["family"], f["category"]) for f in data]


def load_script_fonts():
    data = json.loads((DATA_DIR / "script_fonts.json").read_text())
    return [(f["family"], f["category"], f.get("script", ""), f.get("script_group", "")) for f in data]


def google_fonts_links(families: list[str], chunk_size: int = 30) -> str:
    """Build multiple <link> tags to avoid URL length limits."""
    tags = []
    for i in range(0, len(families), chunk_size):
        chunk = families[i:i + chunk_size]
        params = "&".join(f"family={f.replace(' ', '+')}" for f in chunk)
        tags.append(f'<link href="https://fonts.googleapis.com/css2?{params}&display=swap" rel="stylesheet">')
    return "\n    ".join(tags)


def generate_html(fonts, page_num, total_pages, title_prefix=""):
    families = [f[0] for f in fonts]
    links = google_fonts_links(families)

    rows = []
    for i, font_tuple in enumerate(fonts):
        family = font_tuple[0]
        category = font_tuple[1]
        idx = (page_num - 1) * FONTS_PER_PAGE + i + 1
        rows.append(
            f'<div class="row">'
            f'<span class="idx">{idx}</span>'
            f'<span class="label">{family}</span>'
            f'<span class="cat">{category}</span>'
            f'<span class="sample" style="font-family: \'{family}\', sans-serif;">{SAMPLE_TEXT}</span>'
            f'</div>'
        )

    rows_html = "\n".join(rows)

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    {links}
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: white; padding: 16px 20px; width: 2200px; }}
        h3 {{ font-family: 'Courier New', monospace; color: #999; margin-bottom: 12px; font-size: 13px; }}
        .row {{ display: flex; align-items: baseline; padding: 4px 0; border-bottom: 1px solid #f0f0f0; }}
        .idx {{ font-family: 'Courier New', monospace; font-size: 10px; color: #ccc; width: 40px; flex-shrink: 0; text-align: right; padding-right: 8px; }}
        .label {{ font-family: 'Courier New', monospace; font-size: 11px; color: #666; width: 280px; flex-shrink: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .cat {{ font-family: 'Courier New', monospace; font-size: 10px; color: #aaa; width: 110px; flex-shrink: 0; }}
        .sample {{ font-size: 26px; color: #111; white-space: nowrap; }}
    </style>
</head>
<body>
    <h3>{title_prefix}Contact Sheet {page_num}/{total_pages}</h3>
    {rows_html}
</body>
</html>'''


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    allowlist = load_allowlist()
    total_pages = math.ceil(len(allowlist) / FONTS_PER_PAGE)

    print(f"Rendering {len(allowlist)} allowlist fonts across {total_pages} contact sheets...")
    print(f"Output: {OUTPUT_DIR}/")

    with sync_playwright() as p:
        browser = p.chromium.launch()

        for page_num in range(1, total_pages + 1):
            start = (page_num - 1) * FONTS_PER_PAGE
            end = start + FONTS_PER_PAGE
            batch = allowlist[start:end]

            html = generate_html(batch, page_num, total_pages, title_prefix="Allowlist — ")
            html_path = OUTPUT_DIR / f"allowlist_{page_num:02d}.html"
            html_path.write_text(html)

            page = browser.new_page(viewport={"width": 2200, "height": 800})
            page.goto(f"file://{html_path}")
            page.wait_for_timeout(4000)

            png_path = OUTPUT_DIR / f"allowlist_{page_num:02d}.png"
            page.screenshot(path=str(png_path), full_page=True)
            page.close()

            print(f"  [{page_num}/{total_pages}] {len(batch)} fonts -> {png_path.name}")

        # Script fonts: render with Latin fallback sample text
        script_fonts = load_script_fonts()
        script_pages = math.ceil(len(script_fonts) / FONTS_PER_PAGE)
        print(f"\nRendering {len(script_fonts)} script fonts across {script_pages} contact sheets...")

        for page_num in range(1, script_pages + 1):
            start = (page_num - 1) * FONTS_PER_PAGE
            end = start + FONTS_PER_PAGE
            batch = [(f[0], f[1]) for f in script_fonts[start:end]]

            html = generate_html(batch, page_num, script_pages, title_prefix="Script — ")
            html_path = OUTPUT_DIR / f"script_{page_num:02d}.html"
            html_path.write_text(html)

            page = browser.new_page(viewport={"width": 2200, "height": 800})
            page.goto(f"file://{html_path}")
            page.wait_for_timeout(4000)

            png_path = OUTPUT_DIR / f"script_{page_num:02d}.png"
            page.screenshot(path=str(png_path), full_page=True)
            page.close()

            print(f"  [{page_num}/{script_pages}] {len(batch)} fonts -> {png_path.name}")

        browser.close()

    print(f"\nDone! {total_pages + script_pages} contact sheets saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()

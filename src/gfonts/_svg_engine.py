"""Internal SVG rendering engine using Playwright + Chromium.

Builds HTML harnesses that load Google Fonts and render_text_style_svg.js,
serves them via a local HTTP server, and extracts the resulting SVG via
XMLSerializer with Playwright.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import http.server
import json
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Coroutine

from gfonts.schema import TextStyle

_JS_DIR = Path(__file__).resolve().parent / "_js"


def _google_fonts_link(families: set[str]) -> str:
    specs = sorted(
        f"family={f.replace(' ', '+')}:wght@100;200;300;400;500;600;700;800;900"
        for f in families
    )
    return "https://fonts.googleapis.com/css2?" + "&".join(specs) + "&display=swap"


def _ensure_svg_assets(html_dir: Path) -> None:
    """Copy JS rendering scripts into the HTML serving directory."""
    html_dir.mkdir(parents=True, exist_ok=True)
    for js_file in ("render_text_style_svg.js", "style_utils.js"):
        src = _JS_DIR / js_file
        if src.exists():
            shutil.copy2(src, html_dir / js_file)


def _asyncio_run_safe(
    async_main: Callable[[], Coroutine[Any, Any, Any]],
) -> Any:
    """Run ``async_main()`` with ``asyncio.run``.

    If the caller already has a running event loop (e.g. FastAPI/uvicorn),
    the coroutine runs in a dedicated thread so ``asyncio.run`` is not nested.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_main())

    def _worker() -> Any:
        return asyncio.run(async_main())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_worker).result()


# ── HTML harness ──────────────────────────────────────────────────────


def build_svg_harness_html(
    style: TextStyle,
    *,
    google_fonts_link: str | None = None,
) -> str:
    """Build a self-contained HTML page that renders a TextStyle to SVG."""
    style_json = json.dumps(style.to_json())

    if google_fonts_link is None:
        google_fonts_link = _google_fonts_link({style.font_family})

    fonts_tag = f'<link href="{google_fonts_link}" rel="stylesheet">\n'

    font_weight = style.font_weight or 400
    font_style_css = "italic" if style.font_style == "italic" else "normal"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{fonts_tag}<style>
body {{ margin: 0; background: transparent; overflow: hidden; }}
.font-preload {{
  font-family: '{style.font_family}';
  font-weight: {font_weight};
  font-style: {font_style_css};
  position: absolute;
  visibility: hidden;
  font-size: 10px;
}}
</style>
</head>
<body>
<span class="font-preload">ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789</span>
<script>
window.__TEXT_STYLE__ = {style_json};
window.__LOCAL_FONT_CSS__ = "";
</script>
<script src="style_utils.js"></script>
<script src="render_text_style_svg.js"></script>
</body>
</html>"""


# ── SVG render jobs ───────────────────────────────────────────────────


@dataclass(slots=True)
class SvgRenderJob:
    label: str
    html_name: str
    svg_path: Path
    png_path: Path | None = None


def run_svg_render_jobs(
    jobs: list[SvgRenderJob],
    html_dir: Path,
    *,
    timeout_ms: int = 15000,
    concurrency: int = 8,
) -> None:
    """Render a batch of SVG jobs using Playwright + local HTTP server."""
    serve_dir = str(html_dir.resolve())

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a: Any, **k: Any) -> None:
            super().__init__(*a, directory=serve_dir, **k)

        def log_message(self, *a: Any) -> None:
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    async def _render() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            total = len(jobs)
            sem = asyncio.Semaphore(concurrency)
            counter = {"done": 0}
            lock = asyncio.Lock()

            async def _render_one(job: SvgRenderJob) -> None:
                async with sem:
                    page = await browser.new_page(
                        viewport={"width": 1400, "height": 900}
                    )
                    try:
                        await page.goto(
                            f"http://127.0.0.1:{port}/{job.html_name}",
                            wait_until="load",
                            timeout=timeout_ms,
                        )
                        await page.wait_for_function(
                            "document.title.startsWith('DONE:') || document.title.startsWith('FAIL:')",
                            timeout=timeout_ms,
                        )
                        title = await page.title()
                        if title.startswith("FAIL:"):
                            async with lock:
                                counter["done"] += 1
                                print(f"  [{counter['done']:3d}/{total}] {job.label:45s}  FAIL ({title})")
                            return

                        svg_string = await page.evaluate(
                            """() => {
                                var svgEl = document.querySelector('svg#output');
                                if (!svgEl) return null;
                                return new XMLSerializer().serializeToString(svgEl);
                            }"""
                        )

                        if svg_string:
                            job.svg_path.parent.mkdir(parents=True, exist_ok=True)
                            job.svg_path.write_text(svg_string, encoding="utf-8")
                            if job.png_path:
                                job.png_path.parent.mkdir(parents=True, exist_ok=True)
                                loc = page.locator("svg#output")
                                for shot_try in range(3):
                                    try:
                                        await loc.screenshot(
                                            path=str(job.png_path),
                                            omit_background=True,
                                        )
                                        if (
                                            job.png_path.is_file()
                                            and job.png_path.stat().st_size > 80
                                        ):
                                            break
                                    except Exception:
                                        if shot_try == 2:
                                            raise
                                    await page.wait_for_timeout(120 * (shot_try + 1))
                                if not (
                                    job.png_path.is_file()
                                    and job.png_path.stat().st_size > 80
                                ):
                                    raise RuntimeError(
                                        "PNG screenshot missing or too small after retries"
                                    )
                            async with lock:
                                counter["done"] += 1
                                print(f"  [{counter['done']:3d}/{total}] {job.label:45s}  OK")
                        else:
                            async with lock:
                                counter["done"] += 1
                                print(f"  [{counter['done']:3d}/{total}] {job.label:45s}  FAIL (no SVG element)")
                    except Exception as exc:
                        async with lock:
                            counter["done"] += 1
                            print(f"  [{counter['done']:3d}/{total}] {job.label:45s}  FAIL ({exc})")
                    finally:
                        await page.close()

            await asyncio.gather(*[_render_one(job) for job in jobs])
            await browser.close()

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(
            "Playwright not installed. "
            "Run: pip install playwright && playwright install chromium"
        )
        server.shutdown()
        return

    _asyncio_run_safe(_render)
    server.shutdown()

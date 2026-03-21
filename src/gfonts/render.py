"""Public rendering API: render TextStyle objects to SVG/PNG files."""

from __future__ import annotations

import tempfile
from pathlib import Path

from gfonts._svg_engine import (
    SvgRenderJob,
    build_svg_harness_html,
    run_svg_render_jobs,
    _ensure_svg_assets,
    _google_fonts_link,
)
from gfonts.schema import TextStyle


def render(
    style: TextStyle,
    output: str | Path,
    *,
    png: bool | None = None,
) -> Path:
    """Render a TextStyle to an SVG or PNG file.

    The output format is inferred from the file extension, or forced via
    the ``png`` argument.  When rendering to ``.png``, an intermediate SVG
    is created in a temp directory and the PNG is a Playwright screenshot.

    Args:
        style: The TextStyle to render.
        output: Output file path (.svg or .png).
        png: Force PNG output regardless of extension.

    Returns:
        The resolved output path.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    want_png = png if png is not None else (output.suffix.lower() == ".png")

    flat = style.to_flat()
    google_link = _google_fonts_link({flat.font_family})

    with tempfile.TemporaryDirectory(prefix="gfonts_") as tmpdir:
        html_dir = Path(tmpdir)
        _ensure_svg_assets(html_dir)

        html_name = "render.html"
        (html_dir / html_name).write_text(
            build_svg_harness_html(flat, google_fonts_link=google_link)
        )

        if want_png:
            svg_path = html_dir / "render.svg"
            job = SvgRenderJob(
                label=output.stem,
                html_name=html_name,
                svg_path=svg_path,
                png_path=output,
            )
        else:
            job = SvgRenderJob(
                label=output.stem,
                html_name=html_name,
                svg_path=output,
            )

        run_svg_render_jobs([job], html_dir)

    return output


def render_batch(
    styles: list[tuple[str, TextStyle]],
    *,
    output_dir: str | Path = ".",
    fmt: str = "svg",
    concurrency: int = 8,
) -> list[Path]:
    """Render multiple (name, TextStyle) pairs.

    Args:
        styles: List of (name, TextStyle) tuples.
        output_dir: Directory for output files.
        fmt: Output format — ``"svg"`` or ``"png"``.
        concurrency: Number of concurrent Playwright pages.

    Returns:
        List of output file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    want_png = fmt.lower() == "png"

    all_families = {s.font_family for _, s in styles}
    google_link = _google_fonts_link(all_families)

    with tempfile.TemporaryDirectory(prefix="gfonts_") as tmpdir:
        html_dir = Path(tmpdir)
        _ensure_svg_assets(html_dir)

        jobs: list[SvgRenderJob] = []
        for name, style in styles:
            flat = style.to_flat()
            html_safe = name.replace("/", "_")
            html_name = f"{html_safe}_svg.html"
            (html_dir / html_name).write_text(
                build_svg_harness_html(flat, google_fonts_link=google_link)
            )

            ext = "png" if want_png else "svg"
            out_path = output_dir / f"{name}.{ext}"
            if want_png:
                svg_path = html_dir / f"{html_safe}.svg"
                jobs.append(SvgRenderJob(
                    label=name,
                    html_name=html_name,
                    svg_path=svg_path,
                    png_path=out_path,
                ))
            else:
                jobs.append(SvgRenderJob(
                    label=name,
                    html_name=html_name,
                    svg_path=out_path,
                ))

        print(f"Rendering {len(jobs)} style(s) to {fmt.upper()}...")
        run_svg_render_jobs(jobs, html_dir, concurrency=concurrency)
        print(f"Done. Output saved to {output_dir}/")

    return [j.png_path or j.svg_path for j in jobs]

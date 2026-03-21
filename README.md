# gfonts

Curated Google Fonts catalog with tagging, querying, and styled text rendering.

Ships with pre-curated data for **1300+ allowed Latin fonts**, **370+ script-tagged fonts** (Arabic, CJK, Indic, etc.), and **100+ blacklisted fonts** — plus a full `TextStyle` schema and Playwright-based SVG/PNG renderer.

## Installation

```bash
pip install -e .
playwright install chromium
```

## Quick start

```python
from gfonts import FontCatalog, TextStyle, Fill, render

# Browse fonts
catalog = FontCatalog()
print(len(catalog.allowed()))          # ~1307 Latin fonts
print(catalog.scripts())               # ['arabic', 'bengali', ...]
print(catalog.find("Roboto"))          # FontEntry(family='Roboto', ...)

# Generate a styled text object
style = catalog.style("Roboto", text="Hello World", font_size=72, font_weight=700)

# Or build one manually
style = TextStyle(
    text="HELLO",
    font_family="Bebas Neue",
    font_size=120,
    font_weight=400,
    fill=Fill.solid("#E74C3C"),
)

# Render to SVG or PNG
render(style, "hello.svg")
render(style, "hello.png")
```

## Font catalog API

```python
from gfonts import FontCatalog

catalog = FontCatalog()

# Allowed Latin fonts
catalog.allowed()                        # -> list[FontEntry]
catalog.allowed(category="serif")        # filter by category

# Script-tagged fonts
catalog.by_script("arabic")              # -> list[ScriptFontEntry]
catalog.by_script_group("cjk")           # -> list[ScriptFontEntry]
catalog.scripts()                        # -> list[str] available scripts
catalog.script_groups()                  # -> list[str] available groups

# Blacklisted fonts
catalog.blacklisted()                    # -> list[BlacklistEntry]

# Search & lookup
catalog.find("Roboto")                   # -> FontEntry | None
catalog.search("mono")                   # -> list[FontEntry] (substring match)
catalog.random(category="display")       # -> FontEntry (random pick)

# Google Fonts CSS URL
catalog.google_fonts_css(["Roboto", "Lato"])  # -> str

# Custom data directory
catalog = FontCatalog(data_dir="./my_fonts/")
```

## TextStyle schema

The `TextStyle` model supports:

- **Typography**: font family, size, weight, style, letter spacing, line height, alignment
- **Fill**: solid colors or linear/radial gradients
- **Outlines**: multiple stroke layers with independent fills
- **Shadows**: drop shadows (single or multiple), inner shadows
- **Glows**: outer and inner glow effects
- **Extrusion**: 3D depth effect
- **Per-letter overrides**: individual fill, outline, rotation, scale per character
- **Lines format**: structural editing with per-line, per-word, first-letter overrides, fill cycles, and jitter
- **Text path**: warp along arc, wave, bulge, fisheye, perspective, shear curves

```python
from gfonts import TextStyle, Fill, Outline, Shadow, GradientStop

style = TextStyle(
    text="GRADIENT",
    font_family="Montserrat",
    font_size=100,
    font_weight=900,
    fill=Fill.linear([
        GradientStop(color="#FF6B6B", position=0),
        GradientStop(color="#4ECDC4", position=1),
    ], angle=90),
    outlines=[Outline(width=3, fill=Fill.solid("#333333"))],
    drop_shadow=Shadow(color="#000000", offset_x=4, offset_y=4, blur=8),
)
```

## Rendering

```python
from gfonts import render, render_batch, TextStyle

# Single render
render(style, "output.svg")              # SVG
render(style, "output.png")              # PNG (transparent background)

# Batch render
styles = [("style1", style1), ("style2", style2)]
render_batch(styles, output_dir="./out", fmt="svg")
render_batch(styles, output_dir="./out", fmt="png", concurrency=4)
```

## Font curation UI

Launch an interactive web UI to move fonts between allowed/script/blacklisted:

```bash
gfonts curate                            # opens browser at localhost:8250
gfonts curate --port 9000                # custom port
gfonts curate --data-dir ./my_fonts/     # edit custom data
gfonts curate --no-open                  # don't auto-open browser
```

## Package structure

```
src/gfonts/
  __init__.py          Public API exports
  catalog.py           FontCatalog + data models
  schema.py            TextStyle Pydantic models
  render.py            render() / render_batch()
  _svg_engine.py       Playwright SVG orchestration
  _infer_lines.py      Lines <-> flat format conversion
  _js/                 JS rendering harness
  _cli/                CLI entry points
  data/                Bundled font JSON data
```

"""gfonts — Curated Google Fonts catalog with tagging, querying, and rendering."""

from gfonts.catalog import (
    BlacklistEntry,
    FontCatalog,
    FontEntry,
    ScriptFontEntry,
)
from gfonts.render import render, render_batch
from gfonts.schema import (
    Extrusion,
    Fill,
    Glow,
    GradientStop,
    JitterConfig,
    LetterOverride,
    LineStyle,
    Outline,
    Shadow,
    TextPath,
    TextStyle,
)

__all__ = [
    # Catalog
    "FontCatalog",
    "FontEntry",
    "ScriptFontEntry",
    "BlacklistEntry",
    # Schema
    "TextStyle",
    "Fill",
    "GradientStop",
    "Outline",
    "Shadow",
    "Glow",
    "Extrusion",
    "LetterOverride",
    "LineStyle",
    "TextPath",
    "JitterConfig",
    # Rendering
    "render",
    "render_batch",
]

__version__ = "0.1.0"

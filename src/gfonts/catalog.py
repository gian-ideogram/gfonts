"""Font catalog: query curated Google Fonts by status, category, and script."""

from __future__ import annotations

import json
import random
from pathlib import Path
from pydantic import BaseModel, Field

from gfonts.schema import Fill, TextStyle

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


# ── Data models ──────────────────────────────────────────────────────


class FontEntry(BaseModel):
    """An allowed Latin font in the catalog."""

    family: str
    category: str
    variants: list[str] = Field(default_factory=list)

    @property
    def has_italic(self) -> bool:
        return any("i" in v for v in self.variants)

    @property
    def weights(self) -> list[int]:
        return sorted({int(v.rstrip("i")) for v in self.variants if v.rstrip("i").isdigit()})


class ScriptFontEntry(FontEntry):
    """A font primarily supporting a non-Latin script."""

    script: str = ""
    script_group: str = ""
    subsets: list[str] = Field(default_factory=list)


class BlacklistEntry(BaseModel):
    """A blacklisted font with a reason."""

    family: str
    reason: str = ""
    reason_description: str = ""


# ── FontCatalog ──────────────────────────────────────────────────────


class FontCatalog:
    """Query curated Google Fonts data.

    Loads bundled JSON data by default, or a custom ``data_dir``.
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
        self._allowlist: list[FontEntry] | None = None
        self._script_fonts: list[ScriptFontEntry] | None = None
        self._blacklist: list[BlacklistEntry] | None = None

    def _load(self) -> None:
        allow_path = self._data_dir / "allowlist.json"
        script_path = self._data_dir / "script_fonts.json"
        black_path = self._data_dir / "blacklist.json"

        self._allowlist = [
            FontEntry.model_validate(e)
            for e in json.loads(allow_path.read_text())
        ]
        self._script_fonts = [
            ScriptFontEntry.model_validate(e)
            for e in json.loads(script_path.read_text())
        ] if script_path.exists() else []
        self._blacklist = [
            BlacklistEntry.model_validate(e)
            for e in json.loads(black_path.read_text())
        ] if black_path.exists() else []

    @property
    def _allow(self) -> list[FontEntry]:
        if self._allowlist is None:
            self._load()
        assert self._allowlist is not None
        return self._allowlist

    @property
    def _scripts(self) -> list[ScriptFontEntry]:
        if self._script_fonts is None:
            self._load()
        assert self._script_fonts is not None
        return self._script_fonts

    @property
    def _black(self) -> list[BlacklistEntry]:
        if self._blacklist is None:
            self._load()
        assert self._blacklist is not None
        return self._blacklist

    # ── Query methods ────────────────────────────────────────────────

    def allowed(self, category: str | None = None) -> list[FontEntry]:
        """Return allowed Latin fonts, optionally filtered by category (case-insensitive)."""
        fonts = self._allow
        if category:
            cat_lower = category.lower()
            fonts = [f for f in fonts if f.category.lower() == cat_lower]
        return fonts

    def by_script(self, script: str) -> list[ScriptFontEntry]:
        """Return fonts for a specific script (e.g. 'arabic', 'japanese')."""
        script_lower = script.lower()
        return [f for f in self._scripts if f.script.lower() == script_lower]

    def scripts(self) -> list[str]:
        """Return all available script tags."""
        return sorted({f.script for f in self._scripts})

    def script_groups(self) -> list[str]:
        """Return all available script group tags."""
        return sorted({f.script_group for f in self._scripts})

    def by_script_group(self, group: str) -> list[ScriptFontEntry]:
        """Return fonts for a specific script group (e.g. 'cjk', 'indic')."""
        group_lower = group.lower()
        return [f for f in self._scripts if f.script_group.lower() == group_lower]

    def blacklisted(self) -> list[BlacklistEntry]:
        """Return all blacklisted fonts."""
        return list(self._black)

    def find(self, family: str) -> FontEntry | ScriptFontEntry | None:
        """Find a font by exact family name (case-insensitive)."""
        name = family.lower()
        for f in self._allow:
            if f.family.lower() == name:
                return f
        for f in self._scripts:
            if f.family.lower() == name:
                return f
        return None

    def search(self, query: str) -> list[FontEntry | ScriptFontEntry]:
        """Fuzzy search fonts by family name substring (case-insensitive)."""
        q = query.lower()
        results: list[FontEntry | ScriptFontEntry] = []
        for f in self._allow:
            if q in f.family.lower():
                results.append(f)
        for f in self._scripts:
            if q in f.family.lower():
                results.append(f)
        return results

    def random(self, category: str | None = None) -> FontEntry:
        """Return a random allowed font, optionally filtered by category."""
        pool = self.allowed(category)
        if not pool:
            raise ValueError(f"No fonts found for category={category!r}")
        return random.choice(pool)

    def google_fonts_css(self, families: list[str]) -> str:
        """Generate a Google Fonts CSS import URL for the given families."""
        specs = sorted(
            f"family={f.replace(' ', '+')}:wght@100;200;300;400;500;600;700;800;900"
            for f in families
        )
        return "https://fonts.googleapis.com/css2?" + "&".join(specs) + "&display=swap"

    # ── TextStyle generation ─────────────────────────────────────────

    def style(
        self,
        family: str,
        *,
        text: str = "SAMPLE",
        font_size: float = 100,
        font_weight: int = 400,
        fill_color: str = "#000000",
        **kwargs: object,
    ) -> TextStyle:
        """Create a TextStyle preconfigured with the given font.

        Extra keyword arguments are forwarded to the TextStyle constructor.
        """
        return TextStyle(
            text=text,
            font_family=family,
            font_size=font_size,
            font_weight=font_weight,
            fill=Fill.solid(fill_color),
            **kwargs,  # type: ignore[arg-type]
        )

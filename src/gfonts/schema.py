"""
Universal TextStyle schema for representing any text styling effect.

Design principles:
- ``None`` means off — no ``enabled: false`` flags.
- Pixel units for sizes — outline widths, shadow offsets, glow radii.
- Flat and agent-friendly — minimal nesting, clear field names, no UUIDs.
- JSON Schema export — ``TextStyle.model_json_schema()`` for agent consumption.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class GradientStop(BaseModel):
    """A single color stop in a gradient."""

    color: str = Field(description="Hex color, e.g. '#FF0000'")
    position: float = Field(ge=0.0, le=1.0, description="Position along gradient (0-1)")


class Fill(BaseModel):
    """Fill style: solid color or gradient."""

    type: Literal["solid", "linear_gradient", "radial_gradient"] = Field(
        description="Fill type"
    )
    color: str | None = Field(
        default=None,
        description="Hex color for solid fills, e.g. '#000000'",
    )
    stops: list[GradientStop] | None = Field(
        default=None,
        description="Gradient color stops (required for gradient types, minimum 2)",
    )
    angle: float = Field(
        default=180,
        ge=0,
        le=360,
        description="Gradient angle in degrees (0=up, 90=right, 180=down). Only used for linear_gradient.",
    )
    cx: float | None = Field(
        default=None, ge=0, le=1,
        description="Radial gradient center X (0=left, 0.5=center, 1=right). None = 0.5.",
    )
    cy: float | None = Field(
        default=None, ge=0, le=1,
        description="Radial gradient center Y (0=top, 0.5=center, 1=bottom). None = 0.5.",
    )
    r: float | None = Field(
        default=None, gt=0, le=2.0,
        description="Radial gradient radius multiplier (1.0 = full bounds). None = 1.0.",
    )

    @classmethod
    def solid(cls, color: str) -> Fill:
        return cls(type="solid", color=color)

    @classmethod
    def linear(cls, stops: list[GradientStop], angle: float = 180) -> Fill:
        return cls(type="linear_gradient", stops=stops, angle=angle)


class Outline(BaseModel):
    """A single outline/stroke layer around text."""

    width: float = Field(gt=0, description="Outline width in pixels")
    fill: Fill = Field(description="Outline fill (solid color or gradient)")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    join: Literal["round", "miter", "bevel"] = Field(
        default="round", description="Line join style"
    )


class Shadow(BaseModel):
    """Drop shadow or inner shadow effect."""

    color: str = Field(description="Shadow color as hex, e.g. '#000000'")
    offset_x: float = Field(description="Horizontal offset in pixels (positive = right)")
    offset_y: float = Field(description="Vertical offset in pixels (positive = down)")
    blur: float = Field(ge=0, description="Blur radius in pixels")
    spread: float | None = Field(
        default=None, ge=-50, le=50,
        description="Shadow spread in pixels (expand/contract shadow shape). None = 0.",
    )
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class Glow(BaseModel):
    """Outer or inner glow effect."""

    color: str = Field(description="Glow color as hex")
    radius: float = Field(gt=0, description="Glow spread radius in pixels")
    strength: float = Field(
        default=1.0, ge=0.1, le=10.0, description="Glow intensity multiplier"
    )
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class Extrusion(BaseModel):
    """3D extrusion / depth effect."""

    depth: float = Field(gt=0, description="Extrusion depth in pixels")
    angle: float = Field(
        ge=0, le=360, description="Extrusion direction in degrees (0=up, 180=down)"
    )
    fill: Fill = Field(description="Extrusion face fill")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class LetterOverride(BaseModel):
    """Per-letter style overrides for multi-colored or transformed text."""

    indices: list[int] = Field(
        description="0-based character indices this override applies to"
    )
    fill: Fill | None = Field(default=None, description="Override fill for these letters")
    outline: Outline | None = Field(
        default=None, description="Override outline for these letters"
    )
    rotation: float | None = Field(
        default=None, ge=-180, le=180,
        description="Per-letter rotation in degrees",
    )
    scale: float | None = Field(
        default=None, ge=0.1, le=5.0,
        description="Per-letter scale factor (1.0 = normal)",
    )
    scale_y: float | None = Field(
        default=None,
        ge=0.1,
        le=5.0,
        description=(
            "Per-letter vertical scale (1.0 = normal; >1 taller). "
            "Emitted when resolving lines[].scale_y to flat letter_overrides."
        ),
    )
    x_offset: float | None = Field(
        default=None, ge=-100, le=100,
        description="Per-letter horizontal offset in pixels (positive = right)",
    )
    y_offset: float | None = Field(
        default=None, ge=-100, le=100,
        description="Per-letter vertical offset in pixels (positive = down)",
    )

    @staticmethod
    def _coerce_int_list(raw: Any) -> list[int] | None:
        """Parse LLM / loose JSON into a list of ints (reject bool)."""
        if isinstance(raw, bool):
            return None
        if isinstance(raw, int):
            return [raw]
        if isinstance(raw, float) and raw == int(raw):
            return [int(raw)]
        if isinstance(raw, list):
            out: list[int] = []
            for x in raw:
                if isinstance(x, bool):
                    continue
                if isinstance(x, int):
                    out.append(x)
                elif isinstance(x, float) and x == int(x):
                    out.append(int(x))
            return out if out else None
        return None

    @model_validator(mode="before")
    @classmethod
    def _coerce_indices_fields(cls, data: Any) -> Any:
        """Accept ``index``, ``start``/``end`` (line-override shape), or ``indices``."""
        if not isinstance(data, dict):
            return data
        merged = dict(data)
        if merged.get("indices") is not None:
            merged.pop("index", None)
            merged.pop("start", None)
            merged.pop("end", None)
            return merged

        singular = merged.pop("index", None)
        start_raw = merged.pop("start", None)
        end_raw = merged.pop("end", None)

        if start_raw is not None and end_raw is not None:
            try:
                start_i = int(start_raw)
                end_i = int(end_raw)
                if start_i <= end_i:
                    merged["indices"] = list(range(start_i, end_i + 1))
                else:
                    merged["indices"] = [start_i]
            except (TypeError, ValueError):
                pass
        if merged.get("indices") is None and singular is not None:
            coerced = cls._coerce_int_list(singular)
            if coerced is not None:
                merged["indices"] = coerced
        if merged.get("indices") is None and start_raw is not None and end_raw is None:
            try:
                merged["indices"] = [int(start_raw)]
            except (TypeError, ValueError):
                pass

        return merged


# ── Lines-based editable format ──────────────────────────────────────


class JitterConfig(BaseModel):
    """Randomized per-character transforms for hand-drawn effects."""

    rotation: float | None = Field(
        default=None, ge=0, description="Max rotation jitter in degrees"
    )
    x_offset: float | None = Field(
        default=None, ge=0, description="Max horizontal offset jitter in pixels"
    )
    y_offset: float | None = Field(
        default=None, ge=0, description="Max vertical offset jitter in pixels"
    )
    scale: float | None = Field(
        default=None, ge=1.0, description="Max scale factor (1.0 = no scale jitter)"
    )
    seed: int = Field(default=0, ge=0, description="Random seed for reproducibility")


class LetterProps(BaseModel):
    """Style properties for a special letter (e.g. first letter of a line)."""

    fill: Fill | None = Field(default=None)
    outline: Outline | None = Field(default=None)
    rotation: float | None = Field(default=None, ge=-180, le=180)
    scale: float | None = Field(default=None, ge=0.1, le=5.0)
    scale_y: float | None = Field(default=None, ge=0.1, le=5.0)
    x_offset: float | None = Field(default=None, ge=-100, le=100)
    y_offset: float | None = Field(default=None, ge=-100, le=100)


class WordOverride(BaseModel):
    """Style override for a word within a line, identified by word index."""

    index: int = Field(ge=0, description="0-based word index within the line")
    fill: Fill | None = Field(default=None)
    outline: Outline | None = Field(default=None)
    rotation: float | None = Field(default=None, ge=-180, le=180)
    scale: float | None = Field(default=None, ge=0.1, le=5.0)
    scale_y: float | None = Field(default=None, ge=0.1, le=5.0)
    x_offset: float | None = Field(default=None, ge=-100, le=100)
    y_offset: float | None = Field(default=None, ge=-100, le=100)


class LocalOverride(BaseModel):
    """Fallback override for a contiguous character range within a line."""

    start: int = Field(ge=0, description="Start character index in line (inclusive)")
    end: int = Field(ge=0, description="End character index in line (inclusive)")
    fill: Fill | None = Field(default=None)
    outline: Outline | None = Field(default=None)
    rotation: float | None = Field(default=None, ge=-180, le=180)
    scale: float | None = Field(default=None, ge=0.1, le=5.0)
    scale_y: float | None = Field(default=None, ge=0.1, le=5.0)
    x_offset: float | None = Field(default=None, ge=-100, le=100)
    y_offset: float | None = Field(default=None, ge=-100, le=100)


class LineStyle(BaseModel):
    """A single line of styled text with structural override rules.

    Overrides are applied in priority order (later wins):
    line-level -> word-level -> first_letter -> fill_cycle -> overrides -> jitter.
    """

    text: str = Field(description="Line text content")
    align: Literal["left", "center", "right"] | None = Field(
        default=None,
        description="Override alignment for this line. None = inherit global align.",
    )
    fill: Fill | None = Field(default=None, description="Override fill for entire line")
    outline: Outline | None = Field(
        default=None, description="Override outline for entire line"
    )
    rotation: float | None = Field(
        default=None, ge=-180, le=180, description="Rotation for entire line"
    )
    font_size: float | None = Field(
        default=None,
        ge=10,
        le=600,
        description="Override font size for this line (participates in layout)",
    )
    scale: float | None = Field(
        default=None,
        ge=0.1,
        le=5.0,
        description="Line size multiplier vs top-level font_size (resolve_lines -> line_font_sizes).",
    )
    scale_y: float | None = Field(
        default=None,
        ge=0.1,
        le=5.0,
        description="Vertical stretch factor for entire line (1.0 = normal, >1 = taller letters).",
    )
    x_offset: float | None = Field(
        default=None, ge=-100, le=100, description="Horizontal offset for entire line"
    )
    y_offset: float | None = Field(
        default=None, ge=-100, le=100, description="Vertical offset for entire line"
    )
    letter_spacing: float | None = Field(
        default=None,
        ge=-50,
        le=50,
        description="Override letter spacing for this line in pixels. None = inherit global.",
    )
    text_path: TextPath | None = Field(
        default=None,
        description="Override warp for this line. If null, inherits top-level text_path.",
    )
    words: list[WordOverride] | None = Field(
        default=None, description="Per-word style overrides"
    )
    first_letter: LetterProps | None = Field(
        default=None, description="Special styling for the first visible character"
    )
    fill_cycle: list[str | None] | None = Field(
        default=None,
        description="Repeating fill color pattern applied per visible character (hex or null to skip)",
    )
    jitter: JitterConfig | None = Field(
        default=None, description="Per-line jitter parameters"
    )
    overrides: list[LocalOverride] | None = Field(
        default=None, description="Fallback range-based character overrides"
    )


class TextPath(BaseModel):
    """Warp text along a path.

    Types:
      - ``arc``: Both edges curve together (classic arch/rainbow).
      - ``arc_lower``: Top flat, bottom warps (Netflix-style).
      - ``arc_upper``: Bottom flat, top warps.
      - ``flag``: Uniform sine wave (vertical letter lines stay straight).
      - ``wave``: Sine distortion on both axes (fluid rippling).
      - ``bulge``: Center inflates outward (positive) or pinches inward (negative).
      - ``fisheye``: Aggressive focal-point stretch at center.
      - ``perspective``: One side scales down, receding into distance.
      - ``shear``: Skews the text diagonally (aggressive slant).
    """

    type: Literal[
        "arc", "arc_lower", "arc_upper",
        "flag", "wave",
        "bulge", "fisheye",
        "perspective", "shear",
    ] = Field(default="arc", description="Warp type")
    curvature: float = Field(
        ge=-1.0,
        le=1.0,
        description="Warp intensity: positive=up/outward, negative=down/inward, 0=flat",
    )


class TextStyle(BaseModel):
    """
    Universal text style definition.

    Describes how to render styled text using typography settings and
    layered visual effects. Every effect field is optional (``None`` = off).
    The only required field with visual impact is ``fill``.
    """

    # Content
    text: str = Field(default="SAMPLE", description="Text to render")

    # Typography
    font_family: str = Field(
        default="Lato",
        description="Font family name (Google Fonts)",
    )
    font_size: float = Field(
        default=100, ge=10, le=600, description="Font size in pixels"
    )
    font_weight: int = Field(
        default=400,
        ge=100,
        le=900,
        description="Font weight (100=thin, 400=normal, 700=bold, 900=black)",
    )
    font_style: Literal["normal", "italic"] = Field(default="normal")
    letter_spacing: float = Field(
        default=0, ge=-50, le=50, description="Letter spacing in pixels"
    )
    line_height: float = Field(
        default=1.2, ge=0.5, le=3.0, description="Line height multiplier"
    )
    text_transform: Literal["none", "uppercase", "lowercase"] = Field(
        default="none", description="Text case transformation"
    )
    text_decoration: Literal["none", "underline", "line-through", "overline"] | None = Field(
        default=None,
        description="Text decoration (underline, strikethrough, overline). None = none.",
    )
    align: Literal["left", "center", "right"] = Field(
        default="center", description="Text alignment"
    )

    # Fill
    fill: Fill = Field(
        default_factory=lambda: Fill(type="solid", color="#000000"),
        description="Primary text fill (color or gradient)",
    )

    # Outlines (rendered bottom-up; first = outermost)
    outlines: list[Outline] = Field(
        default_factory=list,
        description="Outline/stroke layers, rendered bottom-up (first = outermost visible)",
    )

    # Effects (None = disabled)
    drop_shadow: Shadow | None = Field(
        default=None,
        description="Single drop shadow (backward compat). Use drop_shadows for multiple.",
    )
    drop_shadows: list[Shadow] | None = Field(
        default=None,
        description="Multiple drop shadows (rendered in order, first = behind). Overrides drop_shadow if present.",
    )
    inner_shadow: Shadow | None = Field(
        default=None, description="Inner shadow inside text"
    )
    outer_glow: Glow | None = Field(
        default=None, description="Outer glow around text"
    )
    inner_glow: Glow | None = Field(
        default=None, description="Inner glow inside text"
    )
    extrusion: Extrusion | None = Field(
        default=None, description="3D extrusion/depth effect"
    )

    # Per-letter overrides (flat format)
    letter_overrides: list[LetterOverride] = Field(
        default_factory=list,
        description="Per-letter fill/outline overrides for multi-colored text",
    )

    # Lines-based editable format (alternative to text + letter_overrides)
    lines: list[LineStyle] | None = Field(
        default=None,
        description=(
            "Lines-based editable format. When present, text and letter_overrides "
            "are derived from it via resolve_lines()."
        ),
    )
    jitter: JitterConfig | None = Field(
        default=None,
        description="Global jitter config (applies to all lines unless overridden per-line)",
    )

    # Text path
    text_path: TextPath | None = Field(
        default=None, description="Warp text along a curved path"
    )

    # Multi-line layout emitted by resolve_lines() (flat render format).
    line_font_sizes: list[float] | None = Field(
        default=None,
        description="Per-line font size in px (global font_size x line scale or explicit).",
    )
    line_scale_y: list[float] | None = Field(
        default=None,
        description="Per-line vertical stretch factor (1.0 = normal).",
    )
    line_text_paths: list[TextPath | None] | None = Field(
        default=None,
        description="Per-line warp; None entries inherit top-level text_path.",
    )
    line_letter_spacings: list[float] | None = Field(
        default=None,
        description="Per-line letter spacing when rows differ from global letter_spacing.",
    )
    line_aligns: list[Literal["left", "center", "right"] | None] | None = Field(
        default=None,
        description="Per-line alignment when rows set lines[].align.",
    )
    line_rotations: list[float] | None = Field(
        default=None,
        description="Per-line rotation in degrees, applied as group transform.",
    )
    line_x_offsets: list[float] | None = Field(
        default=None,
        description="Per-line horizontal offset in px, applied as group transform.",
    )
    line_y_offsets: list[float] | None = Field(
        default=None,
        description="Per-line vertical offset in px, applied as group transform.",
    )

    # Global transforms
    rotation: float = Field(
        default=0, ge=-180, le=180, description="Text rotation in degrees"
    )
    opacity: float = Field(default=1.0, ge=0.0, le=1.0, description="Global opacity")

    def to_json(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict, excluding None values."""
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> TextStyle:
        """Parse from a JSON dict."""
        return cls.model_validate(data)

    def to_flat(self) -> TextStyle:
        """Resolve lines format to flat ``text`` + ``letter_overrides``.

        Returns *self* unchanged if already flat.
        """
        if self.lines is None:
            return self
        from gfonts._infer_lines import resolve_lines

        flat = resolve_lines(self.to_json())
        return TextStyle.from_json(flat)

    def to_lines(self) -> TextStyle:
        """Infer lines structure from flat ``text`` + ``letter_overrides``.

        Returns *self* unchanged if already in lines format.
        """
        if self.lines is not None:
            return self
        from gfonts._infer_lines import convert_style

        converted = convert_style(self.to_json())
        return TextStyle.from_json(converted)

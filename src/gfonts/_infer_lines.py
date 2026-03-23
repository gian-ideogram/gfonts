"""Convert between flat (text + letter_overrides) and lines-based formats.

The lines-based format replaces character-index-based overrides with structural
rules (line-level, word-level, first-letter) and parametric patterns (jitter,
fill_cycle) that survive text edits.

Entry points:
- ``resolve_style`` — canonical: style -> flat (always call before rendering)
- ``resolve_lines`` — lines -> flat (expansion)
- ``infer_lines`` / ``convert_style`` — flat -> lines (inference, for editing)
"""

from __future__ import annotations

import json
from typing import Any


# ── helpers ──────────────────────────────────────────────────────────


def _parse_lines(text: str) -> list[dict]:
    """Split text into line info with char/word structure."""
    raw_lines = text.split("\n")
    result = []
    global_idx = 0

    for line_text in raw_lines:
        start = global_idx
        chars: list[dict] = []
        words: list[dict] = []
        vis_pos = 0
        word_idx = 0
        in_word = False
        word_start = 0

        for local, ch in enumerate(line_text):
            gi = start + local
            is_space = ch == " "
            if not is_space:
                if not in_word:
                    word_start = local
                    in_word = True
                chars.append(
                    {"idx": gi, "local": local, "vis_pos": vis_pos,
                     "word_idx": word_idx, "ch": ch}
                )
                vis_pos += 1
            else:
                if in_word:
                    words.append({"start": word_start, "end": local - 1, "word_idx": word_idx})
                    word_idx += 1
                    in_word = False

        if in_word:
            words.append({"start": word_start, "end": len(line_text) - 1, "word_idx": word_idx})

        result.append({
            "text": line_text,
            "start": start,
            "end": start + len(line_text) - 1,
            "chars": chars,
            "words": words,
        })
        global_idx += len(line_text) + 1  # +1 for \n

    return result


def _parse_words(text: str) -> list[dict]:
    """Parse word boundaries in a line of text."""
    words: list[dict] = []
    in_word = False
    word_start = 0
    word_idx = 0
    for i, ch in enumerate(text):
        if ch != " ":
            if not in_word:
                word_start = i
                in_word = True
        else:
            if in_word:
                words.append({"start": word_start, "end": i - 1, "idx": word_idx})
                word_idx += 1
                in_word = False
    if in_word:
        words.append({"start": word_start, "end": len(text) - 1, "idx": word_idx})
    return words


def _flatten_to_per_char(
    line_info: dict, overrides: list[dict]
) -> dict[int, dict[str, Any]]:
    """Expand override groups into per-char property maps."""
    line_indices = {ch["idx"] for ch in line_info["chars"]}
    char_props: dict[int, dict[str, Any]] = {}

    for ov in overrides:
        for idx in ov.get("indices", []):
            if idx not in line_indices:
                continue
            entry = char_props.setdefault(idx, {})
            for prop in ("rotation", "x_offset", "y_offset", "scale", "scale_y"):
                val = ov.get(prop)
                if val is not None and val != 0:
                    entry[prop] = val
            if ov.get("fill"):
                entry["fill"] = ov["fill"]
            if ov.get("outline"):
                entry["outline"] = ov["outline"]

    return char_props


def _covers_full_line(indices: set[int], line_info: dict) -> bool:
    all_vis = {ch["idx"] for ch in line_info["chars"]}
    return indices == all_vis


def _find_covered_word(indices: set[int], line_info: dict) -> int | None:
    for w in line_info["words"]:
        word_indices = {
            ch["idx"] for ch in line_info["chars"]
            if w["start"] <= ch["local"] <= w["end"]
        }
        if indices == word_indices:
            return w["word_idx"]
    return None


def _is_first_char(indices: set[int], line_info: dict) -> bool:
    if not line_info["chars"]:
        return False
    return indices == {line_info["chars"][0]["idx"]}


def _to_ranges(indices: list[int]) -> list[tuple[int, int]]:
    """Convert a sorted list of indices into contiguous (start, end) ranges."""
    if not indices:
        return []
    indices = sorted(indices)
    ranges: list[tuple[int, int]] = []
    start = end = indices[0]
    for i in indices[1:]:
        if i == end + 1:
            end = i
        else:
            ranges.append((start, end))
            start = end = i
    ranges.append((start, end))
    return ranges


def _detect_fill_cycle(
    fills: dict[int, Any], line_info: dict
) -> list[str | None] | None:
    """Try to detect a repeating fill pattern with period 2-8."""
    if len(fills) < 2:
        return None

    vis_fills: list[Any] = []
    for ch in line_info["chars"]:
        f = fills.get(ch["idx"])
        if f and isinstance(f, dict):
            vis_fills.append(f.get("color"))
        else:
            vis_fills.append(None)

    for period in range(2, 9):
        if period > len(vis_fills):
            continue
        cycle = vis_fills[:period]
        if not any(c is not None for c in cycle):
            continue
        if all(vis_fills[i] == cycle[i % period] for i in range(len(vis_fills))):
            return cycle

    return None


# ── seeded RNG (matches JS implementation) ───────────────────────────


def _seeded_random(seed: int):
    """Simple LCG matching the JS ``seededRandom`` in the preview app."""
    state = [seed]

    def _next() -> float:
        state[0] = (state[0] * 16807 + 0) % 2147483647
        return (state[0] - 1) / 2147483646

    return _next


# ── infer_lines: flat -> lines ────────────────────────────────────────


def infer_lines(
    text: str, letter_overrides: list[dict], base_font_size: float = 100
) -> dict[str, Any]:
    """Convert text + letter_overrides into lines-based editable format.

    Returns a dict with ``"lines"`` and optionally ``"jitter"`` (if shared
    across all lines). When scale covers a full line, emits font_size instead
    of scale for layout correctness.
    """
    lines_info = _parse_lines(text)

    idx_to_line: dict[int, int] = {}
    for li, info in enumerate(lines_info):
        for ch in info["chars"]:
            idx_to_line[ch["idx"]] = li

    per_line: dict[int, list[dict]] = {i: [] for i in range(len(lines_info))}
    for ov in letter_overrides:
        lines_touched: set[int] = set()
        for idx in ov.get("indices", []):
            if idx in idx_to_line:
                lines_touched.add(idx_to_line[idx])
        for li in lines_touched:
            per_line[li].append(ov)

    line_results: list[dict[str, Any]] = []

    for li, info in enumerate(lines_info):
        ovs = per_line[li]
        styled: dict[str, Any] = {"text": info["text"]}

        if not ovs:
            line_results.append(styled)
            continue

        char_props = _flatten_to_per_char(info, ovs)
        if not char_props:
            line_results.append(styled)
            continue

        for prop in ("scale", "scale_y", "x_offset", "y_offset", "rotation", "fill", "outline"):
            values: dict[int, Any] = {}
            for idx, p in char_props.items():
                if prop in p:
                    values[idx] = p[prop]

            if not values:
                continue

            unique_strs = {json.dumps(v, sort_keys=True) if isinstance(v, dict) else str(v)
                           for v in values.values()}

            if len(unique_strs) == 1:
                val = next(iter(values.values()))
                indices = set(values.keys())

                if _covers_full_line(indices, info):
                    if prop == "scale":
                        styled["font_size"] = base_font_size * val
                    else:
                        styled[prop] = val
                elif (word_idx := _find_covered_word(indices, info)) is not None:
                    styled.setdefault("words", [])
                    existing = next((w for w in styled["words"] if w["index"] == word_idx), None)
                    if existing:
                        existing[prop] = val
                    else:
                        styled["words"].append({"index": word_idx, prop: val})
                elif _is_first_char(indices, info):
                    styled.setdefault("first_letter", {})[prop] = val
                else:
                    local_indices = sorted(
                        ch["local"] for ch in info["chars"] if ch["idx"] in indices
                    )
                    for start, end in _to_ranges(local_indices):
                        styled.setdefault("overrides", []).append({
                            "start": start, "end": end, prop: val,
                        })
            else:
                if prop == "fill":
                    cycle = _detect_fill_cycle(values, info)
                    if cycle:
                        styled["fill_cycle"] = cycle
                    else:
                        for idx, val in values.items():
                            local = next(ch["local"] for ch in info["chars"] if ch["idx"] == idx)
                            styled.setdefault("overrides", []).append({
                                "start": local, "end": local, "fill": val,
                            })
                elif prop in ("rotation", "x_offset", "y_offset", "scale", "scale_y"):
                    range_val = round(max(abs(v) for v in values.values()), 1)
                    jitter = styled.setdefault("jitter", {})
                    jitter[prop] = range_val
                else:
                    for idx, val in values.items():
                        local = next(ch["local"] for ch in info["chars"] if ch["idx"] == idx)
                        styled.setdefault("overrides", []).append({
                            "start": local, "end": local, prop: val,
                        })

        if "jitter" in styled:
            styled["jitter"]["seed"] = abs(hash(info["text"])) % 1000

        line_results.append(styled)

    output: dict[str, Any] = {"lines": line_results}
    jitter_vals = [r.get("jitter") for r in line_results]
    if all(j is not None for j in jitter_vals):
        strs = {json.dumps(j, sort_keys=True) for j in jitter_vals}
        if len(strs) == 1:
            output["jitter"] = jitter_vals[0]
            for r in line_results:
                r.pop("jitter", None)
        else:
            merged: dict[str, Any] = {}
            for j in jitter_vals:
                for k, v in j.items():
                    if k == "seed":
                        continue
                    if isinstance(v, (int, float)):
                        merged[k] = max(merged.get(k, 0), v)
            merged["seed"] = 42
            output["jitter"] = merged
            for r in line_results:
                r.pop("jitter", None)

    return output


# ── resolve_style: canonical style -> flat (for rendering) ──────────────


def resolve_style(style_data: dict) -> dict:
    """Canonical: style -> flat. Always call before passing to any renderer.

    - If style has ``lines``: expands to ``text`` + ``letter_overrides``.
    - If style is already flat: returns copy with ``text``/``letter_overrides`` ensured.
    """
    if style_data.get("lines"):
        return resolve_lines(style_data)
    out: dict[str, Any] = {}
    skip = {"lines", "jitter"}
    for k, v in style_data.items():
        if k not in skip:
            out[k] = v
    out.setdefault("text", "SAMPLE")
    out.setdefault("letter_overrides", [])
    return out


# ── resolve_lines: lines -> flat ─────────────────────────────────────


def resolve_lines(style_data: dict) -> dict:
    """Convert lines-based format to flat ``text`` + ``letter_overrides``.

    Python equivalent of the JS ``resolveLines`` function. Returns a new dict
    with ``lines``/``jitter`` replaced by ``text`` and ``letter_overrides``.
    Emits ``line_font_sizes`` when any line has ``font_size`` or ``scale``.
    If the input has no ``lines`` key, returns it unchanged.
    """
    lines = style_data.get("lines")
    if not lines:
        return style_data

    base_font_size = style_data.get("font_size", 100)
    line_font_sizes: list[float] = []
    line_scale_y: list[float] = []
    line_text_paths: list[dict | None] = []
    line_letter_spacings: list[float] = []
    line_aligns: list[str | None] = []
    line_rotations: list[float] = []
    line_x_offsets: list[float] = []
    line_y_offsets: list[float] = []
    base_letter_spacing = style_data.get("letter_spacing", 0)
    for line in lines:
        if line.get("font_size") is not None:
            line_font_sizes.append(line["font_size"])
        elif line.get("scale") is not None:
            line_font_sizes.append(base_font_size * line["scale"])
        else:
            line_font_sizes.append(base_font_size)
        line_scale_y.append(line.get("scale_y") if line.get("scale_y") is not None else 1.0)
        line_text_paths.append(line.get("text_path"))
        line_letter_spacings.append(
            line["letter_spacing"] if line.get("letter_spacing") is not None else base_letter_spacing
        )
        line_aligns.append(line.get("align"))
        line_rotations.append(line.get("rotation", 0.0))
        line_x_offsets.append(line.get("x_offset", 0.0))
        line_y_offsets.append(line.get("y_offset", 0.0))

    global_jitter = style_data.get("jitter")
    text_parts: list[str] = []
    letter_overrides: list[dict] = []
    global_idx = 0

    for li, line in enumerate(lines):
        line_text = line.get("text", "")
        if li > 0:
            global_idx += 1  # \n separator

        line_jitter = line.get("jitter") or global_jitter
        words = _parse_words(line_text)

        vis_pos = 0
        rng = (
            _seeded_random((line_jitter.get("seed", 0) if line_jitter else 0) + li * 1000)
            if line_jitter
            else None
        )

        for ci, ch in enumerate(line_text):
            gi = global_idx + ci
            if ch == " ":
                continue

            ov: dict[str, Any] = {}
            has_any = False

            if line.get("scale_y") is not None:
                ov["scale_y"] = line["scale_y"]
                has_any = True
            if line.get("fill"):
                ov["fill"] = line["fill"]
                has_any = True
            if line.get("outline"):
                ov["outline"] = line["outline"]
                has_any = True

            if line.get("words"):
                for wo in line["words"]:
                    w = next((w for w in words if w["idx"] == wo["index"]), None)
                    if w and w["start"] <= ci <= w["end"]:
                        for prop in ("scale", "scale_y", "x_offset", "y_offset", "rotation"):
                            if wo.get(prop) is not None:
                                ov[prop] = wo[prop]
                                has_any = True
                        if wo.get("fill"):
                            ov["fill"] = wo["fill"]
                            has_any = True
                        if wo.get("outline"):
                            ov["outline"] = wo["outline"]
                            has_any = True

            if line.get("first_letter") and vis_pos == 0:
                fl = line["first_letter"]
                for prop in ("scale", "scale_y", "x_offset", "y_offset", "rotation"):
                    if fl.get(prop) is not None:
                        ov[prop] = fl[prop]
                        has_any = True
                if fl.get("fill"):
                    ov["fill"] = fl["fill"]
                    has_any = True
                if fl.get("outline"):
                    ov["outline"] = fl["outline"]
                    has_any = True

            if line.get("fill_cycle"):
                cycle = line["fill_cycle"]
                cycle_fill = cycle[vis_pos % len(cycle)]
                if cycle_fill is not None:
                    if isinstance(cycle_fill, str):
                        ov["fill"] = {"type": "solid", "color": cycle_fill}
                    else:
                        ov["fill"] = cycle_fill
                    has_any = True

            if line.get("overrides"):
                for lo in line["overrides"]:
                    matched = False
                    if "start" in lo and "end" in lo:
                        matched = lo["start"] <= ci <= lo["end"]
                    elif lo.get("indices"):
                        matched = ci in lo["indices"]
                    if matched:
                        for prop in ("scale", "scale_y", "x_offset", "y_offset", "rotation"):
                            if lo.get(prop) is not None:
                                ov[prop] = lo[prop]
                                has_any = True
                        if lo.get("fill"):
                            ov["fill"] = lo["fill"]
                            has_any = True
                        if lo.get("outline"):
                            ov["outline"] = lo["outline"]
                            has_any = True

            if line_jitter and rng:
                if line_jitter.get("rotation"):
                    r = (rng() * 2 - 1) * line_jitter["rotation"]
                    ov["rotation"] = round(r, 1)
                    has_any = True
                if line_jitter.get("x_offset"):
                    xo = (rng() * 2 - 1) * line_jitter["x_offset"]
                    ov["x_offset"] = round(ov.get("x_offset", 0) + xo, 1)
                    has_any = True
                if line_jitter.get("y_offset"):
                    yo = (rng() * 2 - 1) * line_jitter["y_offset"]
                    ov["y_offset"] = round(ov.get("y_offset", 0) + yo, 1)
                    has_any = True
                if line_jitter.get("scale"):
                    sc = 1.0 + (rng() * 2 - 1) * (line_jitter["scale"] - 1.0)
                    ov["scale"] = round(ov.get("scale", 1.0) * sc, 2)
                    has_any = True

            if has_any:
                letter_overrides.append({"indices": [gi], **ov})

            vis_pos += 1

        text_parts.append(line_text)
        global_idx += len(line_text)

    result: dict[str, Any] = {}
    skip_keys = {"lines", "jitter"}
    for k, v in style_data.items():
        if k not in skip_keys:
            result[k] = v
    result["text"] = "\n".join(text_parts)
    result["letter_overrides"] = letter_overrides
    result["line_font_sizes"] = line_font_sizes
    result["line_scale_y"] = line_scale_y
    if any(tp is not None for tp in line_text_paths):
        result["line_text_paths"] = line_text_paths
    if any(ls != base_letter_spacing for ls in line_letter_spacings):
        result["line_letter_spacings"] = line_letter_spacings
    if any(a is not None for a in line_aligns):
        result["line_aligns"] = line_aligns
    if any(r != 0.0 for r in line_rotations):
        result["line_rotations"] = line_rotations
    if any(x != 0.0 for x in line_x_offsets):
        result["line_x_offsets"] = line_x_offsets
    if any(y != 0.0 for y in line_y_offsets):
        result["line_y_offsets"] = line_y_offsets

    return result


# ── style conversion helpers ─────────────────────────────────────────


def convert_style(style_data: dict) -> dict:
    """Convert a full TextStyle dict to the lines-based format.

    Preserves all global properties and replaces text + letter_overrides
    with the inferred lines structure.
    """
    text = style_data.get("text", "")
    overrides = style_data.get("letter_overrides", [])

    base_font_size = style_data.get("font_size", 100)
    inferred = infer_lines(text, overrides, base_font_size)

    result = {}
    skip_keys = {"text", "letter_overrides"}
    for k, v in style_data.items():
        if k not in skip_keys:
            result[k] = v

    result["lines"] = inferred["lines"]
    if "jitter" in inferred:
        result["jitter"] = inferred["jitter"]

    return result

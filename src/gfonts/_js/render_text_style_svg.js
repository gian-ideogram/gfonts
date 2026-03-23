/**
 * Universal TextStyle SVG renderer.
 *
 * Reads window.__TEXT_STYLE__ (a TextStyle JSON object) and builds an SVG
 * DOM tree with equivalent visual effects.  Signals completion by setting
 * document.title to 'DONE:<width>:<height>'.
 *
 * Rendering pipeline (bottom-to-top, same order as canvas renderer):
 *   1. Extrusion (3D depth)
 *   2. Drop shadow
 *   3. Outer glow
 *   4. Outlines (bottom-up)
 *   5. Fill (with inner shadow / inner glow as SVG filters)
 *   6. Per-letter overrides applied during fill/outline passes
 */

(function () {
  'use strict';

  var style = window.__TEXT_STYLE__;
  if (!style) {
    document.title = 'FAIL:no_style';
    return;
  }

  var _originalStyle = JSON.parse(JSON.stringify(style));

  // ── resolve lines format if present ──────────────────────────────
  if (style.lines && !style.text) {
    style = FontStyleUtils.resolveLines(style);
    window.__TEXT_STYLE__ = style;
  }

  var NS = 'http://www.w3.org/2000/svg';
  var _idCounter = 0;

  function uid(prefix) {
    return (prefix || 'id') + '_' + (++_idCounter);
  }

  // ── SVG DOM helpers ───────────────────────────────────────────────

  function svgEl(tag) {
    return document.createElementNS(NS, tag);
  }

  function setAttrs(node, attrs) {
    for (var key in attrs) {
      if (attrs.hasOwnProperty(key) && attrs[key] !== undefined) {
        node.setAttribute(key, attrs[key]);
      }
    }
    return node;
  }

  // ── color / text helpers ──────────────────────────────────────────

  function hexToRgba(hex, alpha) {
    hex = hex.replace('#', '');
    if (hex.length === 3) {
      hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
    }
    var r = parseInt(hex.substring(0, 2), 16);
    var g = parseInt(hex.substring(2, 4), 16);
    var b = parseInt(hex.substring(4, 6), 16);
    if (alpha !== undefined && alpha < 1) {
      return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }
    return '#' + hex;
  }

  function applyTextTransform(text, transform) {
    if (transform === 'uppercase') return text.toUpperCase();
    if (transform === 'lowercase') return text.toLowerCase();
    return text;
  }

  function splitLines(text) {
    return text.split(/\r?\n/);
  }

  function buildFontString(s) {
    var parts = [];
    if (s.font_style === 'italic') parts.push('italic');
    parts.push(String(s.font_weight || 400));
    parts.push((s.font_size || 100) + 'px');
    parts.push('"' + (s.font_family || 'Lato') + '"');
    return parts.join(' ');
  }

  // ── gradient creation ─────────────────────────────────────────────

  function createGradientDef(defs, fill, bounds) {
    if (!fill || fill.type === 'solid') return null;
    if (!fill.stops || fill.stops.length < 2) return null;

    var id = uid('grad');

    if (fill.type === 'linear_gradient') {
      var angle = (fill.angle || 180) * Math.PI / 180;
      var w = bounds.width;
      var h = bounds.height;
      var cx = bounds.x + w / 2;
      var cy = bounds.y + h / 2;
      var len = Math.max(w, h);
      var dx = Math.sin(angle) * len / 2;
      var dy = -Math.cos(angle) * len / 2;

      var grad = svgEl('linearGradient');
      setAttrs(grad, {
        id: id,
        gradientUnits: 'userSpaceOnUse',
        x1: cx - dx, y1: cy - dy,
        x2: cx + dx, y2: cy + dy,
      });
      for (var i = 0; i < fill.stops.length; i++) {
        var stop = svgEl('stop');
        setAttrs(stop, { offset: fill.stops[i].position, 'stop-color': fill.stops[i].color });
        grad.appendChild(stop);
      }
      defs.appendChild(grad);
      return 'url(#' + id + ')';
    }

    if (fill.type === 'radial_gradient') {
      var cxVal = fill.cx != null ? fill.cx : 0.5;
      var cyVal = fill.cy != null ? fill.cy : 0.5;
      var rVal = fill.r != null ? fill.r : 1.0;
      var cx2 = bounds.x + bounds.width * cxVal;
      var cy2 = bounds.y + bounds.height * cyVal;
      var radius = (Math.max(bounds.width, bounds.height) / 2) * rVal;

      var grad2 = svgEl('radialGradient');
      setAttrs(grad2, {
        id: id,
        gradientUnits: 'userSpaceOnUse',
        cx: cx2, cy: cy2, r: radius,
      });
      for (var j = 0; j < fill.stops.length; j++) {
        var stop2 = svgEl('stop');
        setAttrs(stop2, { offset: fill.stops[j].position, 'stop-color': fill.stops[j].color });
        grad2.appendChild(stop2);
      }
      defs.appendChild(grad2);
      return 'url(#' + id + ')';
    }

    return null;
  }

  function resolveFill(defs, fill, bounds) {
    if (!fill) return '#000000';
    if (fill.type === 'solid') return fill.color || '#000000';
    return createGradientDef(defs, fill, bounds) || (fill.color || '#000000');
  }

  // ── text measurement (via hidden canvas, same as canvas renderer) ─

  function measureText(ctx, text, font, letterSpacing) {
    ctx.font = font;
    var chars = [];
    var charAdvanceSum = 0;
    for (var i = 0; i < text.length; i++) {
      var m = ctx.measureText(text[i]);
      var cw = m.width + (i < text.length - 1 ? letterSpacing : 0);
      chars.push({ ch: text[i], width: m.width, advance: cw, x: charAdvanceSum });
      charAdvanceSum += cw;
    }
    var full = ctx.measureText(text);
    var ascent = full.actualBoundingBoxAscent || (style.font_size * 0.8);
    var descent = full.actualBoundingBoxDescent || (style.font_size * 0.2);

    // Use the larger of per-char sum and full-text width (which includes kerning)
    // as the baseline. Per-char sum is still used for character positioning.
    var fullTextWidth = full.width || charAdvanceSum;
    var totalWidth = Math.max(charAdvanceSum, fullTextWidth + Math.abs(letterSpacing) * Math.max(0, text.length - 1));

    var rightOverhang = 0;
    var leftOverhang = 0;
    // Ink coverage from the full text can extend past the advance width
    if (full.actualBoundingBoxRight !== undefined) {
      rightOverhang = Math.max(0, full.actualBoundingBoxRight - fullTextWidth);
    }
    // Last character can extend past its advance width (italic slant, glyph shape)
    if (text.length > 0) {
      var lastM = ctx.measureText(text[text.length - 1]);
      if (lastM.actualBoundingBoxRight !== undefined) {
        rightOverhang = Math.max(rightOverhang, lastM.actualBoundingBoxRight - lastM.width);
      }
    }
    if (full.actualBoundingBoxLeft !== undefined && full.actualBoundingBoxLeft > 0) {
      leftOverhang = Math.max(leftOverhang, full.actualBoundingBoxLeft);
    }
    // Synthetic italic: browsers may not report accurate bounding boxes for
    // oblique-synthesized text. Add ~tan(14°)×ascent as safety margin.
    var isItalic = (style.font_style === 'italic');
    if (isItalic) {
      var italicExtra = Math.ceil(ascent * 0.25);
      rightOverhang = Math.max(rightOverhang, italicExtra);
      leftOverhang = Math.max(leftOverhang, Math.ceil(descent * 0.25));
    }
    return {
      chars: chars,
      totalWidth: totalWidth,
      ascent: ascent,
      descent: descent,
      height: ascent + descent,
      rightOverhang: rightOverhang,
      leftOverhang: leftOverhang,
    };
  }

  function measureLines(ctx, lines, font, letterSpacing, lineHeight, lineFontSizes, lineScaleY, lineLetterSpacings) {
    var lineMetrics = [];
    var maxWidth = 0;
    var maxRightOverhang = 0;
    var maxLeftOverhang = 0;
    var fontSize = style.font_size || 100;
    var lineHeightMult = lineHeight || 1.2;
    var lineHeights = [];
    var lineYOffsets = [];
    var lineH;

    if (lineFontSizes && lineFontSizes.length === lines.length) {
      for (var i = 0; i < lines.length; i++) {
        var lfs = lineFontSizes[i];
        var lfFont = (style.font_style === 'italic' ? 'italic ' : '') + (style.font_weight || 400) + ' ' + lfs + 'px "' + (style.font_family || 'Lato') + '"';
        var effLS = (lineLetterSpacings && lineLetterSpacings[i] != null) ? lineLetterSpacings[i] : letterSpacing;
        var m = measureText(ctx, lines[i], lfFont, effLS);
        lineMetrics.push(m);
        if (m.totalWidth > maxWidth) maxWidth = m.totalWidth;
        if (m.rightOverhang > maxRightOverhang) maxRightOverhang = m.rightOverhang;
        if (m.leftOverhang > maxLeftOverhang) maxLeftOverhang = m.leftOverhang;
        var sy = (lineScaleY && lineScaleY[i] != null) ? lineScaleY[i] : 1;
        lineHeights.push(lfs * lineHeightMult * sy);
      }
      lineYOffsets.push(0);
      for (var lyi = 1; lyi < lines.length; lyi++) lineYOffsets.push(lineYOffsets[lyi - 1] + lineHeights[lyi - 1]);
      var totalH = 0;
      for (var thi = 0; thi < lines.length - 1; thi++) totalH += lineHeights[thi];
      if (lines.length) {
        var lastSy = (lineScaleY && lineScaleY[lines.length - 1] != null) ? lineScaleY[lines.length - 1] : 1;
        totalH += lineMetrics[lines.length - 1].height * lastSy;
      }
      lineH = lineHeights[0] || fontSize * lineHeightMult;
      return { lines: lineMetrics, maxWidth: maxWidth, totalHeight: totalH, lineH: lineH, lineYOffsets: lineYOffsets, rightOverhang: maxRightOverhang, leftOverhang: maxLeftOverhang };
    }

    ctx.font = font;
    for (var i2 = 0; i2 < lines.length; i2++) {
      var effLS2 = (lineLetterSpacings && lineLetterSpacings[i2] != null) ? lineLetterSpacings[i2] : letterSpacing;
      var m2 = measureText(ctx, lines[i2], font, effLS2);
      lineMetrics.push(m2);
      if (m2.totalWidth > maxWidth) maxWidth = m2.totalWidth;
      if (m2.rightOverhang > maxRightOverhang) maxRightOverhang = m2.rightOverhang;
      if (m2.leftOverhang > maxLeftOverhang) maxLeftOverhang = m2.leftOverhang;
    }
    lineH = fontSize * lineHeightMult;
    for (var lyi2 = 0; lyi2 < lines.length; lyi2++) lineYOffsets.push(lyi2 * lineH);
    var totalH2 = lines.length === 1 ? lineMetrics[0].height : lineH * (lines.length - 1) + lineMetrics[lines.length - 1].height;
    return { lines: lineMetrics, maxWidth: maxWidth, totalHeight: totalH2, lineH: lineH, lineYOffsets: lineYOffsets, rightOverhang: maxRightOverhang, leftOverhang: maxLeftOverhang };
  }

  // ── padding / bounds ──────────────────────────────────────────────

  function computePadding(s) {
    var pad = 10;
    if (s.outlines) {
      for (var i = 0; i < s.outlines.length; i++) {
        pad = Math.max(pad, Math.ceil(s.outlines[i].width) + 4);
      }
    }
    var shadows = (s.drop_shadows && s.drop_shadows.length) ? s.drop_shadows : (s.drop_shadow ? [s.drop_shadow] : []);
    for (var si = 0; si < shadows.length; si++) {
      var ds = shadows[si];
      var spreadVal = ds.spread != null ? ds.spread : 0;
      pad = Math.max(pad, Math.ceil(Math.abs(ds.offset_x) + ds.blur + Math.abs(spreadVal)) + 6);
      pad = Math.max(pad, Math.ceil(Math.abs(ds.offset_y) + ds.blur + Math.abs(spreadVal)) + 6);
    }
    if (s.outer_glow) {
      var g = s.outer_glow;
      pad = Math.max(pad, Math.ceil(g.radius * g.strength) + 10);
    }
    if (s.extrusion) {
      pad = Math.max(pad, Math.ceil(s.extrusion.depth) + 10);
    }
    // Per-letter transforms (jitter, overrides) can push chars beyond measured bounds
    var transformPad = 0;
    var src = _originalStyle || s;
    var jit = src.jitter;
    if (src.lines) {
      for (var li = 0; li < src.lines.length; li++) {
        var lj = src.lines[li].jitter || jit;
        if (lj) {
          transformPad = Math.max(transformPad,
            (lj.x_offset || 0) + (lj.y_offset || 0) +
            Math.ceil(((lj.scale || 1) - 1) * (s.font_size || 100) * 0.5));
          if (lj.rotation) transformPad = Math.max(transformPad, Math.ceil(lj.rotation * 0.5));
        }
      }
    } else if (jit) {
      transformPad = Math.max(transformPad,
        (jit.x_offset || 0) + (jit.y_offset || 0) +
        Math.ceil(((jit.scale || 1) - 1) * (s.font_size || 100) * 0.5));
      if (jit.rotation) transformPad = Math.max(transformPad, Math.ceil(jit.rotation * 0.5));
    }
    if (s.letter_overrides) {
      for (var oi = 0; oi < s.letter_overrides.length; oi++) {
        var ov = s.letter_overrides[oi];
        if (ov.outline && ov.outline.width != null) {
          pad = Math.max(pad, Math.ceil(ov.outline.width) + 4);
        }
        transformPad = Math.max(transformPad,
          Math.abs(ov.x_offset || 0), Math.abs(ov.y_offset || 0));
        if (ov.scale && ov.scale > 1) {
          transformPad = Math.max(transformPad, Math.ceil((ov.scale - 1) * (s.font_size || 100) * 0.5));
        }
      }
    }
    pad = Math.max(pad, pad + Math.ceil(transformPad));
    return pad;
  }

  function computeRotatedBounds(w, h, angleDeg) {
    var rad = Math.abs(angleDeg) * Math.PI / 180;
    return {
      width: Math.ceil(w * Math.cos(rad) + h * Math.sin(rad)),
      height: Math.ceil(w * Math.sin(rad) + h * Math.cos(rad)),
    };
  }

  // ── letter override lookup (with cyclic pattern expansion) ─────────

  function buildOverrideMap(overrides, textLength) {
    var map = {};
    if (!overrides) return map;

    var multiCycle = null;
    for (var i = 0; i < overrides.length; i++) {
      var idx = overrides[i].indices;
      if (!idx || idx.length < 2) continue;
      var step = idx[1] - idx[0];
      var isCycle = true;
      for (var j = 2; j < idx.length; j++) {
        if (idx[j] - idx[j - 1] !== step) { isCycle = false; break; }
      }
      if (isCycle && step > 0 && (multiCycle === null || step < multiCycle)) multiCycle = step;
    }

    var singleCycle = multiCycle != null ? multiCycle * 2 : null;

    for (var i = 0; i < overrides.length; i++) {
      var ov = overrides[i];
      ov._groupId = i;
      var idx = ov.indices;
      if (!idx || !idx.length) continue;

      var cycle = null, offset = idx[0];
      if (idx.length >= 2) {
        var step = idx[1] - idx[0];
        var isCycle = true;
        for (var j = 2; j < idx.length; j++) {
          if (idx[j] - idx[j - 1] !== step) { isCycle = false; break; }
        }
        if (isCycle && step > 0) cycle = step;
      } else if (singleCycle != null && textLength != null) {
        cycle = singleCycle;
      }

      if (cycle != null && textLength != null) {
        for (var gi = offset; gi < textLength; gi += cycle) map[gi] = ov;
      } else {
        for (var j = 0; j < idx.length; j++) map[idx[j]] = ov;
      }
    }
    return map;
  }

  function buildGroupBounds(overrideMap, metrics, x, y, globalOffset) {
    var bounds = {};
    var off = globalOffset || 0;
    var cx = x;
    for (var k = 0; k < metrics.chars.length; k++) {
      var gi = off + k;
      var ov = overrideMap[gi];
      if (ov && ov._groupId !== undefined) {
        var gid = ov._groupId;
        if (!bounds[gid]) {
          bounds[gid] = { x: cx, y: y - metrics.ascent, width: 0, height: metrics.height };
        }
        bounds[gid].width = (cx + metrics.chars[k].width) - bounds[gid].x;
      }
      cx += metrics.chars[k].advance;
    }
    return bounds;
  }

  // ── SVG filter creation ───────────────────────────────────────────

  function createDropShadowFilter(defs, shadow) {
    var id = uid('dsf');
    var filter = svgEl('filter');
    setAttrs(filter, { id: id, x: '-100%', y: '-100%', width: '400%', height: '400%' });

    var blur = svgEl('feGaussianBlur');
    setAttrs(blur, { 'in': 'SourceGraphic', stdDeviation: shadow.blur, result: 'blur' });
    filter.appendChild(blur);

    defs.appendChild(filter);
    return id;
  }

  function createOuterGlowFilter(defs, glow) {
    var id = uid('ogf');
    var filter = svgEl('filter');
    setAttrs(filter, { id: id, x: '-100%', y: '-100%', width: '400%', height: '400%' });

    var blur = svgEl('feGaussianBlur');
    setAttrs(blur, { 'in': 'SourceGraphic', stdDeviation: glow.radius, result: 'blur' });
    filter.appendChild(blur);

    var passes = Math.max(Math.ceil(glow.strength), 1);
    var merge = svgEl('feMerge');
    for (var i = 0; i < passes; i++) {
      var mn = svgEl('feMergeNode');
      mn.setAttribute('in', 'blur');
      merge.appendChild(mn);
    }
    filter.appendChild(merge);

    defs.appendChild(filter);
    return id;
  }

  function createInnerEffectsFilter(defs, innerShadow, innerGlow) {
    var id = uid('ief');
    var filter = svgEl('filter');
    setAttrs(filter, { id: id, x: '-50%', y: '-50%', width: '200%', height: '200%' });

    var mergeInputs = ['SourceGraphic'];

    if (innerShadow) {
      var inv = svgEl('feComponentTransfer');
      inv.setAttribute('in', 'SourceAlpha');
      inv.setAttribute('result', 'isInvAlpha');
      var funcA = svgEl('feFuncA');
      setAttrs(funcA, { type: 'table', tableValues: '1 0' });
      inv.appendChild(funcA);
      filter.appendChild(inv);

      var isBlur = svgEl('feGaussianBlur');
      setAttrs(isBlur, { 'in': 'isInvAlpha', stdDeviation: innerShadow.blur, result: 'isBlur' });
      filter.appendChild(isBlur);

      var isOffset = svgEl('feOffset');
      setAttrs(isOffset, { 'in': 'isBlur', dx: -innerShadow.offset_x, dy: -innerShadow.offset_y, result: 'isOffset' });
      filter.appendChild(isOffset);

      var isClip = svgEl('feComposite');
      setAttrs(isClip, { 'in': 'isOffset', in2: 'SourceAlpha', operator: 'in', result: 'isClipped' });
      filter.appendChild(isClip);

      var isFlood = svgEl('feFlood');
      setAttrs(isFlood, { 'flood-color': innerShadow.color, 'flood-opacity': innerShadow.opacity || 1, result: 'isColor' });
      filter.appendChild(isFlood);

      var isComp = svgEl('feComposite');
      setAttrs(isComp, { 'in': 'isColor', in2: 'isClipped', operator: 'in', result: 'innerShadow' });
      filter.appendChild(isComp);

      mergeInputs.push('innerShadow');
    }

    if (innerGlow) {
      var inv2 = svgEl('feComponentTransfer');
      inv2.setAttribute('in', 'SourceAlpha');
      inv2.setAttribute('result', 'igInvAlpha');
      var funcA2 = svgEl('feFuncA');
      setAttrs(funcA2, { type: 'table', tableValues: '1 0' });
      inv2.appendChild(funcA2);
      filter.appendChild(inv2);

      var igBlur = svgEl('feGaussianBlur');
      setAttrs(igBlur, { 'in': 'igInvAlpha', stdDeviation: innerGlow.radius, result: 'igBlur' });
      filter.appendChild(igBlur);

      var igClip = svgEl('feComposite');
      setAttrs(igClip, { 'in': 'igBlur', in2: 'SourceAlpha', operator: 'in', result: 'igClipped' });
      filter.appendChild(igClip);

      var igFlood = svgEl('feFlood');
      setAttrs(igFlood, { 'flood-color': innerGlow.color, 'flood-opacity': innerGlow.opacity || 1, result: 'igColor' });
      filter.appendChild(igFlood);

      var igComp = svgEl('feComposite');
      setAttrs(igComp, { 'in': 'igColor', in2: 'igClipped', operator: 'in', result: 'innerGlow' });
      filter.appendChild(igComp);

      mergeInputs.push('innerGlow');
    }

    var merge = svgEl('feMerge');
    for (var mi = 0; mi < mergeInputs.length; mi++) {
      var mn = svgEl('feMergeNode');
      mn.setAttribute('in', mergeInputs[mi]);
      merge.appendChild(mn);
    }
    filter.appendChild(merge);

    defs.appendChild(filter);
    return id;
  }

  // ── text path warp ─────────────────────────────────────────────────

  /**
   * Returns {fn, padTop, padBottom} where fn(x) -> {y, scaleY, rotation}.
   *
   * Matches PIL renderer.py pixel-column warps as closely as possible
   * using per-character transforms.  x is in SVG coordinates;
   * textLeft/textRight define content bounds for normalization.
   *
   * padTop/padBottom tell the caller exactly how much extra vertical
   * space is needed above and below the normal content area.
   */
  function buildWarpInfo(tp, textLeft, textRight, contentH) {
    if (!tp || tp.curvature === 0) return null;

    var c = tp.curvature;
    var type = tp.type || 'arc';
    var textW = Math.max(textRight - textLeft, 1);

    function norm(x) { return (x - textLeft) / textW; }
    function norm2(x) { return norm(x) * 2 - 1; }
    function slopeToRot(slope) { return Math.atan(slope) * 180 / Math.PI; }

    // ── arc ────────────────────────────────────────────────
    if (type === 'arc') {
      var amp = Math.abs(c) * contentH * 0.4;
      return {
        padTop: 0,
        padBottom: amp,
        fn: function (x) {
          var t = norm2(x);
          var raw = amp * t * t;
          var dy = (c > 0) ? raw : (amp - raw);
          var slope = (c > 0 ? 1 : -1) * 4 * amp * t / textW;
          return { y: dy, scaleY: 1, rotation: slopeToRot(slope) };
        },
      };
    }

    // ── arc_lower ──────────────────────────────────────────
    // PIL: top edge flat, bottom edge curves (columns stretch vertically).
    // c > 0: top anchored, bottom extends down at edges → shift chars DOWN to anchor top.
    // c < 0: bottom anchored, top extends up at edges → shift chars UP to anchor bottom.
    if (type === 'arc_lower') {
      var alMax = Math.abs(c) * contentH * 0.5;
      var halfH = contentH / 2;
      return {
        padTop: (c > 0) ? 0 : alMax,
        padBottom: (c > 0) ? alMax : 0,
        fn: function (x) {
          var t = norm2(x);
          var extra = alMax * t * t;
          var sy = (contentH + extra) / contentH;
          if (c > 0) {
            return { y: halfH * (sy - 1), scaleY: sy, rotation: 0 };
          } else {
            return { y: -halfH * (sy - 1), scaleY: sy, rotation: 0 };
          }
        },
      };
    }

    // ── arc_upper ──────────────────────────────────────────
    // PIL: bottom edge flat, top edge curves (columns stretch vertically).
    // c > 0: bottom anchored, top extends up at edges → shift chars UP to anchor bottom.
    // c < 0: top anchored, bottom extends down at edges → shift chars DOWN to anchor top.
    if (type === 'arc_upper') {
      var auMax = Math.abs(c) * contentH * 0.5;
      var halfH2 = contentH / 2;
      return {
        padTop: (c > 0) ? auMax : 0,
        padBottom: (c > 0) ? 0 : auMax,
        fn: function (x) {
          var t = norm2(x);
          var extra = auMax * t * t;
          var sy = (contentH + extra) / contentH;
          if (c > 0) {
            return { y: -halfH2 * (sy - 1), scaleY: sy, rotation: 0 };
          } else {
            return { y: halfH2 * (sy - 1), scaleY: sy, rotation: 0 };
          }
        },
      };
    }

    // ── flag ───────────────────────────────────────────────
    if (type === 'flag') {
      var famp = Math.abs(c) * contentH * 0.3;
      return {
        padTop: famp,
        padBottom: famp,
        fn: function (x) {
          var t = norm(x);
          var phase = t * 2 * Math.PI;
          var off = famp * Math.sin(phase);
          var dy = (c > 0 ? off : -off);
          return { y: dy, scaleY: 1, rotation: 0 };
        },
      };
    }

    // ── wave ───────────────────────────────────────────────
    if (type === 'wave') {
      var wamp = Math.abs(c) * contentH * 0.3;
      var vFactor = Math.abs(c) * 0.25;
      return {
        padTop: wamp,
        padBottom: wamp + Math.ceil(vFactor * contentH * 0.5),
        fn: function (x) {
          var t = norm(x);
          var phase = t * 2 * Math.PI;
          var sinVal = Math.sin(phase);
          var off = wamp * sinVal;
          var stretch = 1 + vFactor * sinVal * (c > 0 ? 1 : -1);
          var dy = (c > 0 ? off : -off);
          var dydx = wamp * 2 * Math.PI * Math.cos(phase) * (c > 0 ? 1 : -1) / textW;
          return { y: dy, scaleY: stretch, rotation: slopeToRot(dydx) };
        },
      };
    }

    // ── bulge ──────────────────────────────────────────────
    if (type === 'bulge') {
      var bMax = Math.abs(c) * contentH * 0.5;
      var bPad = Math.ceil(bMax * 0.5);
      return {
        padTop: bPad,
        padBottom: bPad,
        fn: function (x) {
          var t = norm2(x);
          var cw = 1 - t * t;
          var sy = (c > 0)
            ? (contentH + bMax * cw) / contentH
            : Math.max(0.3, (contentH - bMax * cw) / contentH);
          return { y: 0, scaleY: sy, rotation: 0 };
        },
      };
    }

    // ── fisheye ────────────────────────────────────────────
    if (type === 'fisheye') {
      var feStr = Math.abs(c) * 3.0;
      var feMax = Math.abs(c) * contentH * 0.6;
      var fePad = Math.ceil(feMax * 0.5);
      return {
        padTop: fePad,
        padBottom: fePad,
        fn: function (x) {
          var t = norm2(x);
          var cw = Math.exp(-feStr * t * t);
          var sy = (c > 0)
            ? (contentH + feMax * cw) / contentH
            : Math.max(0.3, (contentH - feMax * cw * 0.6) / contentH);
          return { y: 0, scaleY: sy, rotation: 0 };
        },
      };
    }

    // ── perspective ────────────────────────────────────────
    if (type === 'perspective') {
      var minScale = Math.max(0.2, 1.0 - Math.abs(c) * 0.7);
      return {
        padTop: 0,
        padBottom: 0,
        fn: function (x) {
          var t = norm(x);
          var sy = (c > 0)
            ? 1.0 - (1.0 - minScale) * t
            : minScale + (1.0 - minScale) * t;
          return { y: 0, scaleY: sy, rotation: 0 };
        },
      };
    }

    // ── shear ──────────────────────────────────────────────
    if (type === 'shear') {
      var sMax = Math.abs(c) * contentH * 0.5;
      return {
        padTop: 0,
        padBottom: sMax,
        fn: function (x) {
          var t = norm(x);
          var yShift = (c > 0) ? (sMax * t) : (sMax * (1 - t));
          var slope = (c > 0 ? 1 : -1) * sMax / textW;
          return { y: yShift, scaleY: 1, rotation: slopeToRot(slope) };
        },
      };
    }

    return null;
  }

  // ── text path generation ──────────────────────────────────────────

  function createTextPathDef(defs, tp, textWidth, fontSize) {
    if (!tp || tp.curvature === 0) return null;

    var id = uid('tp');
    var pathEl = svgEl('path');
    pathEl.id = id;

    var c = tp.curvature;
    var type = tp.type || 'arc';
    var W = textWidth;
    var d;

    if (type === 'arc' || type === 'arc_lower' || type === 'arc_upper') {
      var sag = Math.abs(c) * fontSize * 0.8;
      if (c > 0) {
        d = 'M 0,' + sag + ' Q ' + (W / 2) + ',0 ' + W + ',' + sag;
      } else {
        d = 'M 0,0 Q ' + (W / 2) + ',' + sag + ' ' + W + ',0';
      }
    } else if (type === 'wave' || type === 'flag') {
      var amp = Math.abs(c) * fontSize * 0.5;
      var sign = c > 0 ? 1 : -1;
      var h = amp;
      d = 'M 0,' + h;
      d += ' C ' + (W * 0.1667) + ',' + (h - sign * amp * 1.3333);
      d += ' ' + (W * 0.3333) + ',' + (h - sign * amp * 1.3333);
      d += ' ' + (W * 0.5) + ',' + h;
      d += ' C ' + (W * 0.6667) + ',' + (h + sign * amp * 1.3333);
      d += ' ' + (W * 0.8333) + ',' + (h + sign * amp * 1.3333);
      d += ' ' + W + ',' + h;
    } else {
      return null;
    }

    pathEl.setAttribute('d', d);
    pathEl.setAttribute('fill', 'none');
    defs.appendChild(pathEl);
    return id;
  }

  // ── per-line iteration ────────────────────────────────────────────

  function getLineX(lineMetrics, maxWidth, pad, align) {
    if (align === 'right') return pad + maxWidth - lineMetrics.totalWidth;
    if (align === 'center') return pad + (maxWidth - lineMetrics.totalWidth) / 2;
    return pad;
  }

  function forEachLine(lines, multiMetrics, pad, align, fn, lineAligns) {
    var globalCharOffset = 0;
    var yOffs = multiMetrics.lineYOffsets || [];
    for (var i = 0; i < lines.length; i++) {
      var lm = multiMetrics.lines[i];
      var effectiveAlign = (lineAligns && lineAligns[i]) ? lineAligns[i] : align;
      var lx = getLineX(lm, multiMetrics.maxWidth, pad, effectiveAlign);
      var ly = pad + lm.ascent + (yOffs[i] !== undefined ? yOffs[i] : i * multiMetrics.lineH);
      fn(lines[i], lm, lx, ly, i, globalCharOffset);
      globalCharOffset += lines[i].length + 1;
    }
  }

  function _lineGroupWrapper(parent, lineIdx, lx, ly, lm, lineTransforms) {
    var lg = svgEl('g');
    lg.setAttribute('data-line-idx', lineIdx);
    if (lineTransforms) {
      var r = lineTransforms.rotations && lineTransforms.rotations[lineIdx] ? lineTransforms.rotations[lineIdx] : 0;
      var dx = lineTransforms.xOffsets && lineTransforms.xOffsets[lineIdx] ? lineTransforms.xOffsets[lineIdx] : 0;
      var dy = lineTransforms.yOffsets && lineTransforms.yOffsets[lineIdx] ? lineTransforms.yOffsets[lineIdx] : 0;
      if (r || dx || dy) {
        var cx = lx + (lm ? lm.totalWidth / 2 : 0);
        var cy = ly - (lm ? lm.ascent : 0) + (lm ? lm.height / 2 : 0);
        var parts = [];
        if (dx || dy) parts.push('translate(' + dx + ',' + dy + ')');
        if (r) parts.push('rotate(' + r + ',' + cx + ',' + cy + ')');
        lg.setAttribute('transform', parts.join(' '));
      }
    }
    parent.appendChild(lg);
    return lg;
  }

  // ── main render ───────────────────────────────────────────────────

  async function render() {
    var s = style;
    var rawText = applyTextTransform(s.text || 'SAMPLE', s.text_transform || 'none');
    var font = buildFontString(s);
    var pad = computePadding(s);
    var letterSpacing = s.letter_spacing || 0;
    var lineLetterSpacings = s.line_letter_spacings || null;
    var align = s.align || 'center';
    var lineAligns = s.line_aligns || null;
    var lineRotations = s.line_rotations || null;
    var lineXOffsets = s.line_x_offsets || null;
    var lineYOffsets = s.line_y_offsets || null;
    var lineTransforms = (lineRotations || lineXOffsets || lineYOffsets)
      ? { rotations: lineRotations, xOffsets: lineXOffsets, yOffsets: lineYOffsets }
      : null;
    var fontSize = s.font_size || 100;
    var fontFamily = s.font_family || 'Lato';

    var lines = splitLines(rawText);

    // Text measurement via hidden canvas (same technique as canvas renderer)
    var tmpCanvas = document.createElement('canvas');
    tmpCanvas.width = Math.max(4000, fontSize * rawText.length * 2);
    tmpCanvas.height = Math.max(800, fontSize * 4);
    var tmpCtx = tmpCanvas.getContext('2d');
    tmpCtx.font = font;

    var multiMetrics = measureLines(tmpCtx, lines, font, letterSpacing, s.line_height, s.line_font_sizes, s.line_scale_y, lineLetterSpacings);

    var extraLeft = Math.ceil(multiMetrics.leftOverhang);
    var extraRight = Math.ceil(multiMetrics.rightOverhang);
    var rawContentW = Math.ceil(multiMetrics.maxWidth) + extraLeft + extraRight + pad * 2;
    // Cross-browser font rendering can differ by several percent; add a safety
    // buffer so the SVG viewport isn't too tight when viewed outside Chromium.
    var contentW = Math.ceil(rawContentW * 1.04) + 4;
    var contentH = Math.ceil(multiMetrics.totalHeight) + pad * 2;

    // Compute warp info (padding + function) before sizing the SVG
    // Support per-line text_path via s.line_text_paths
    var warpPadTop = 0;
    var warpPadBottom = 0;
    var warpInfo = null;
    var warpInfoPerLine = null;
    var lineTextPaths = s.line_text_paths || [];
    if (lineTextPaths.length > 0) {
      warpInfoPerLine = [];
      for (var wi = 0; wi < lines.length; wi++) {
        var linePath = (lineTextPaths[wi] && lineTextPaths[wi].curvature !== 0)
          ? lineTextPaths[wi]
          : (s.text_path && s.text_path.curvature !== 0 ? s.text_path : null);
        var lm = multiMetrics.lines[wi];
        var warpAlign = (lineAligns && lineAligns[wi]) ? lineAligns[wi] : align;
        var lx = getLineX(lm, multiMetrics.maxWidth, pad, warpAlign);
        if (linePath) {
          var lineInfo = buildWarpInfo(linePath, lx, lx + lm.totalWidth, lm.height);
          warpInfoPerLine[wi] = lineInfo;
          if (lineInfo) {
            warpPadTop = Math.max(warpPadTop, Math.ceil(lineInfo.padTop) + 4);
            warpPadBottom = Math.max(warpPadBottom, Math.ceil(lineInfo.padBottom) + 4);
          }
        } else {
          warpInfoPerLine[wi] = null;
        }
      }
    } else if (s.text_path && s.text_path.curvature !== 0) {
      var textLeft0 = pad + Math.ceil(multiMetrics.leftOverhang);
      var textRight0 = textLeft0 + multiMetrics.maxWidth;
      var textH0 = multiMetrics.totalHeight;
      warpInfo = buildWarpInfo(s.text_path, textLeft0, textRight0, textH0);
      if (warpInfo) {
        warpPadTop = Math.ceil(warpInfo.padTop) + 4;
        warpPadBottom = Math.ceil(warpInfo.padBottom) + 4;
      }
    }

    var svgW = contentW;
    var svgH = contentH + warpPadTop + warpPadBottom;
    var rotOffX = extraLeft;
    var rotOffY = warpPadTop;
    if (s.rotation) {
      var fullH = contentH + warpPadTop + warpPadBottom;
      var rotBounds = computeRotatedBounds(contentW, fullH, s.rotation);
      svgW = rotBounds.width + pad * 2;
      svgH = rotBounds.height + pad * 2;
      rotOffX = (svgW - contentW) / 2 + extraLeft;
      rotOffY = (svgH - fullH) / 2 + warpPadTop;
    }

    // ── build SVG ─────────────────────────────────────────────────

    var svg = svgEl('svg');
    setAttrs(svg, {
      id: 'output',
      xmlns: NS,
      width: svgW,
      height: svgH,
      viewBox: '0 0 ' + svgW + ' ' + svgH,
    });

    var defs = svgEl('defs');
    svg.appendChild(defs);

    var svgStyle = svgEl('style');
    defs.appendChild(svgStyle);

    var fontAttrs = {
      'font-family': "'" + fontFamily + "'",
      'font-size': fontSize,
      'font-weight': s.font_weight || 400,
      'font-style': s.font_style || 'normal',
    };

    var globalTextMetrics = {
      x: pad + rotOffX,
      y: pad + rotOffY,
      width: multiMetrics.maxWidth,
      height: multiMetrics.totalHeight,
    };

    var overrideMap = buildOverrideMap(s.letter_overrides, rawText.length);
    var hasOverrides = Object.keys(overrideMap).length > 0;
    var hasOverrideOutlines = false;
    if (s.letter_overrides) {
      for (var oii = 0; oii < s.letter_overrides.length; oii++) {
        if (s.letter_overrides[oii].outline) {
          hasOverrideOutlines = true;
          break;
        }
      }
    }

    var mainFillStr = resolveFill(defs, s.fill, globalTextMetrics);

    // Text path warp: always use per-character transforms for consistent
    // positioning.  Native <textPath> has viewport clipping issues because
    // the path y-coordinates don't account for ascent/padding.
    // Support per-line text_path: getWarpFn(lineIdx) returns the warp fn for that line.
    var textPathId = null;
    var useTextPath = false;
    var getWarpFn = null;
    if (warpInfoPerLine) {
      getWarpFn = function(lineIdx) {
        var info = warpInfoPerLine[lineIdx];
        return info ? info.fn : null;
      };
    } else if (warpInfo) {
      var singleWarpFn = warpInfo.fn;
      getWarpFn = function(lineIdx) { return singleWarpFn; };
    }

    // Root group for rotation + global opacity
    var rootG = svgEl('g');
    if (s.rotation) {
      rootG.setAttribute('transform',
        'rotate(' + s.rotation + ',' + (svgW / 2) + ',' + (svgH / 2) + ')');
    }
    if (s.opacity !== undefined && s.opacity < 1) {
      rootG.setAttribute('opacity', s.opacity);
    }
    svg.appendChild(rootG);

    // ── text group factory ────────────────────────────────────────

    /**
     * Builds a <g> containing all text lines with the given fill/stroke.
     *
     * opts:
     *   mode            'fill' | 'stroke'
     *   fill            fill string (color or url(#id))
     *   stroke          stroke string
     *   strokeWidth     stroke width
     *   strokeJoin      stroke linejoin
     *   opacity         group opacity
     *   filterId        filter id to apply
     *   offsetX/Y       translation offset
     *   applyOverrides  whether to use per-letter fill/stroke overrides (default true)
     *   transformsOnly  apply per-letter transforms but NOT fill/stroke overrides
     */
    function makeTextGroup(opts) {
      var g = svgEl('g');
      if (opts.filterId) g.setAttribute('filter', 'url(#' + opts.filterId + ')');
      if (opts.opacity !== undefined) g.setAttribute('opacity', opts.opacity);

      var applyOvr = opts.applyOverrides !== false && hasOverrides;
      var needsPerChar = applyOvr || (opts.transformsOnly && hasOverrides);
      var ox0 = opts.offsetX || 0;
      var oy0 = opts.offsetY || 0;

      forEachLine(lines, multiMetrics, pad, align, function (lineText, lm, lx, ly, lineIdx, gOff) {
        var ox = lx + rotOffX + ox0;
        var oy = ly + rotOffY + oy0;
        var lineG = _lineGroupWrapper(g, lineIdx, ox, oy, lm, lineTransforms);

        if (needsPerChar || (getWarpFn && getWarpFn(lineIdx))) {
          addCharsWithOverrides(lineG, lm, ox, oy, gOff, opts, lineIdx);
        } else if (useTextPath && ox0 === 0 && oy0 === 0) {
          addTextOnPath(lineG, lineText, ox, oy, lm, opts, lineIdx);
        } else if ((lineLetterSpacings && lineLetterSpacings[lineIdx] != null ? lineLetterSpacings[lineIdx] : letterSpacing) !== 0) {
          addCharsSimple(lineG, lm, ox, oy, opts, lineIdx);
        } else {
          addSingleText(lineG, lineText, ox, oy, opts, lineIdx);
        }
      }, lineAligns);

      return g;
    }

    function baseFontAttrs(lineIdx) {
      var attrs = {
        'font-family': fontAttrs['font-family'],
        'font-size': (s.line_font_sizes && s.line_font_sizes[lineIdx] != null) ? s.line_font_sizes[lineIdx] : fontAttrs['font-size'],
        'font-weight': fontAttrs['font-weight'],
        'font-style': fontAttrs['font-style'],
      };
      if (s.text_decoration && s.text_decoration !== 'none') {
        attrs['text-decoration'] = s.text_decoration;
      }
      return attrs;
    }

    function applyFillStroke(node, opts, overrideFill, overrideStroke) {
      var fill = overrideFill || opts.fill || mainFillStr;
      var stroke = overrideStroke || opts.stroke;
      if (opts.opacity !== undefined) {
        node.setAttribute('opacity', opts.opacity);
      }
      if (opts.mode === 'fill') {
        node.setAttribute('fill', fill);
      } else if (opts.mode === 'stroke') {
        node.setAttribute('fill', 'none');
        setAttrs(node, {
          stroke: stroke || fill,
          'stroke-width': opts.strokeWidth || 1,
          'stroke-linejoin': opts.strokeJoin || 'round',
          'stroke-miterlimit': 2,
          'paint-order': 'stroke',
        });
      }
    }

    // Single <text> element for one line (no letter-spacing, no overrides)
    function addSingleText(parent, lineText, ox, oy, opts, lineIdx) {
      var t = svgEl('text');
      setAttrs(t, baseFontAttrs(lineIdx != null ? lineIdx : 0));
      t.setAttribute('x', ox);
      t.setAttribute('y', oy);
      applyFillStroke(t, opts);
      t.textContent = lineText;
      parent.appendChild(t);
    }

    // Per-character <text> elements (letter-spacing, no overrides)
    function addCharsSimple(parent, lm, ox, oy, opts, lineIdx) {
      var cx = ox;
      var fa = baseFontAttrs(lineIdx != null ? lineIdx : 0);
      for (var i = 0; i < lm.chars.length; i++) {
        var t = svgEl('text');
        setAttrs(t, fa);
        t.setAttribute('x', cx);
        t.setAttribute('y', oy);
        applyFillStroke(t, opts);
        t.textContent = lm.chars[i].ch;
        parent.appendChild(t);
        cx += lm.chars[i].advance;
      }
    }

    // Per-character with letter overrides, transforms, and/or warp
    function addCharsWithOverrides(parent, lm, ox, oy, gOff, opts, lineIdx) {
      var tOnly = !!opts.transformsOnly;
      var groupBounds = tOnly ? {} : buildGroupBounds(overrideMap, lm, ox, oy, gOff);
      var groupFillCache = {};
      var cx = ox;
      var baseStrokeWidth = opts.strokeWidth;
      var baseStrokeJoin = opts.strokeJoin;
      var lineFa = baseFontAttrs(lineIdx != null ? lineIdx : 0);

      for (var k = 0; k < lm.chars.length; k++) {
        var gi = gOff + k;
        var ov = overrideMap[gi];
        if (opts.strokeOverridesOnly && opts.mode === 'stroke' && !(ov && ov.outline)) {
          cx += lm.chars[k].advance;
          continue;
        }

        var t = svgEl('text');
        setAttrs(t, lineFa);

        var charFill = null;
        var charStroke = null;
        var charOpts = opts;
        if (ov && !tOnly) {
          if (ov.fill && opts.mode === 'fill') {
            var gid = ov._groupId;
            if (groupFillCache[gid] === undefined) {
              var gb = groupBounds[gid] || {
                x: cx, y: oy - lm.ascent,
                width: lm.chars[k].width, height: lm.height,
              };
              groupFillCache[gid] = resolveFill(defs, ov.fill, gb);
            }
            charFill = groupFillCache[gid];
          }
          if (ov.outline && opts.mode === 'stroke') {
            var charBounds = {
              x: cx, y: oy - lm.ascent,
              width: lm.chars[k].width, height: lm.height,
            };
            charStroke = resolveFill(defs, ov.outline.fill, charBounds);
            charOpts = Object.create(opts);
            charOpts.strokeWidth = ov.outline.width;
            charOpts.strokeJoin = ov.outline.join || 'round';
            charOpts.opacity = ov.outline.opacity != null ? ov.outline.opacity : opts.opacity;
          }
        } else if (opts.mode === 'stroke') {
          charOpts = Object.create(opts);
          charOpts.strokeWidth = baseStrokeWidth;
          charOpts.strokeJoin = baseStrokeJoin;
        }

        applyFillStroke(t, charOpts, charFill, charStroke);

        // Warp: per-character y-offset, vertical scale, and tangent rotation
        var warpY = 0;
        var warpSY = 1;
        var warpRot = 0;
        var warpFn = getWarpFn ? getWarpFn(lineIdx) : null;
        if (warpFn) {
          var charCenter = cx + lm.chars[k].width / 2;
          var warpResult = warpFn(charCenter);
          warpY = warpResult.y;
          warpSY = warpResult.scaleY;
          warpRot = warpResult.rotation || 0;
        }

        // Per-letter transforms (rotation, scale, x_offset, y_offset from overrides) + warp.
        // When line_font_sizes present, line-level scale is in font-size; use scale() only for parametric (word/first_letter/jitter).
        var hasTransform = ov && (ov.rotation || ov.scale || ov.scale_y || ov.y_offset || ov.x_offset);
        var hasWarp = warpY || warpSY !== 1 || warpRot;
        if (hasTransform || hasWarp) {
          var charW = lm.chars[k].width;
          var charCx = cx + charW / 2;
          var charCy = (oy + warpY) - lm.ascent + lm.height / 2;
          var xOff = (ov && ov.x_offset) ? ov.x_offset : 0;
          var yOff = (ov && ov.y_offset) ? ov.y_offset : 0;
          var totalRot = warpRot + ((ov && ov.rotation) ? ov.rotation : 0);
          var parts = [];
          parts.push('translate(' + (charCx + xOff) + ',' + (charCy + yOff) + ')');
          if (totalRot) parts.push('rotate(' + totalRot + ')');
          var sx = (ov && ov.scale) ? ov.scale : 1;
          var lineScaleY = (ov && ov.scale_y) ? ov.scale_y : 1;
          var sy = lineScaleY * warpSY;
          if (sx !== 1 || sy !== 1) parts.push('scale(' + sx + ',' + sy + ')');
          parts.push('translate(' + (-charCx) + ',' + (-charCy) + ')');
          t.setAttribute('transform', parts.join(' '));
        }

        t.setAttribute('x', cx);
        t.setAttribute('y', oy + warpY);
        t.textContent = lm.chars[k].ch;
        parent.appendChild(t);

        cx += lm.chars[k].advance;
      }
    }

    // Text on a <textPath> (single line, no overrides)
    function addTextOnPath(parent, lineText, ox, oy, lm, opts, lineIdx) {
      var wrapper = svgEl('g');
      wrapper.setAttribute('transform', 'translate(' + ox + ',' + (oy - lm.ascent) + ')');

      var t = svgEl('text');
      setAttrs(t, baseFontAttrs(lineIdx != null ? lineIdx : 0));
      var tpLS = (lineLetterSpacings && lineLetterSpacings[lineIdx] != null) ? lineLetterSpacings[lineIdx] : letterSpacing;
      if (tpLS !== 0) {
        t.setAttribute('letter-spacing', tpLS);
      }
      applyFillStroke(t, opts);

      var tp = svgEl('textPath');
      tp.setAttribute('href', '#' + textPathId);
      tp.textContent = lineText;
      t.appendChild(tp);
      wrapper.appendChild(t);
      parent.appendChild(wrapper);
    }

    // Shorthand for a plain fill text group (shadow/glow/extrusion bases).
    // Uses a single fill color but still applies per-letter transforms.
    function makeRawFillGroup(fill, offX, offY) {
      return makeTextGroup({
        mode: 'fill', fill: fill,
        offsetX: offX, offsetY: offY,
        applyOverrides: false,
        transformsOnly: true,
      });
    }

    // ── Metadata embedding ─────────────────────────────────────────
    var metaSrc = _originalStyle || style;
    var metaEl = svgEl('metadata');
    var descEl = document.createElementNS(NS, 'desc');
    descEl.setAttribute('data-font-style', 'true');
    descEl.textContent = JSON.stringify(metaSrc);
    metaEl.appendChild(descEl);
    svg.insertBefore(metaEl, defs.nextSibling);

    // ── Layer 1: Extrusion ──────────────────────────────────────────
    if (s.extrusion) {
      var ext = s.extrusion;
      var fullDepth = Math.max(Math.ceil(ext.depth), 1);
      var eAngle = (ext.angle || 180) * Math.PI / 180;
      var eDx = Math.sin(eAngle);
      var eDy = -Math.cos(eAngle);
      var eFillStr = resolveFill(defs, ext.fill, globalTextMetrics);

      // Cap at 20 steps max; use thicker fill strokes to cover gaps
      var stepSize = Math.max(1, Math.ceil(fullDepth / 20));
      var extG = svgEl('g');
      extG.setAttribute('data-layer', 'extrusion');
      extG.setAttribute('opacity', ext.opacity || 1);

      for (var ei = fullDepth; ei >= 1; ei -= stepSize) {
        var eox = eDx * ei;
        var eoy = eDy * ei;

        if (s.outlines && s.outlines.length > 0) {
          for (var oi = 0; oi < s.outlines.length; oi++) {
            var ol = s.outlines[oi];
            var olFill = resolveFill(defs, ol.fill, globalTextMetrics);
            extG.appendChild(makeTextGroup({
              mode: 'stroke', stroke: olFill,
              strokeWidth: ol.width + stepSize, strokeJoin: ol.join || 'round',
              offsetX: eox, offsetY: eoy,
            }));
          }
        }

        // Fill step with a thin stroke to cover gaps between steps
        if (stepSize > 1) {
          extG.appendChild(makeTextGroup({
            mode: 'stroke', stroke: eFillStr,
            strokeWidth: stepSize, strokeJoin: 'round',
            offsetX: eox, offsetY: eoy,
            applyOverrides: false, transformsOnly: true,
          }));
        }
        extG.appendChild(makeRawFillGroup(eFillStr, eox, eoy));
      }

      rootG.appendChild(extG);
    }

    // ── Layer 2: Drop shadows (multiple supported) ───────────────────

    var dropShadows = (s.drop_shadows && s.drop_shadows.length) ? s.drop_shadows : (s.drop_shadow ? [s.drop_shadow] : []);
    for (var dsi = 0; dsi < dropShadows.length; dsi++) {
      var ds = dropShadows[dsi];
      var dsFilterId = createDropShadowFilter(defs, ds);
      var dsColor = hexToRgba(ds.color, ds.opacity);
      var dsGroup = makeRawFillGroup(dsColor, ds.offset_x, ds.offset_y);
      dsGroup.setAttribute('data-layer', 'drop-shadow');
      dsGroup.setAttribute('filter', 'url(#' + dsFilterId + ')');
      dsGroup.setAttribute('opacity', ds.opacity || 1);
      rootG.appendChild(dsGroup);
    }

    // ── Layer 3: Outer glow ─────────────────────────────────────────

    if (s.outer_glow) {
      var og = s.outer_glow;
      var ogFilterId = createOuterGlowFilter(defs, og);
      var ogGroup = makeRawFillGroup(og.color, 0, 0);
      ogGroup.setAttribute('data-layer', 'outer-glow');
      ogGroup.setAttribute('filter', 'url(#' + ogFilterId + ')');
      ogGroup.setAttribute('opacity', og.opacity || 1);
      rootG.appendChild(ogGroup);
    }

    // ── Layer 4: Outlines (bottom-up, first = outermost) ────────────

    if (s.outlines && s.outlines.length > 0) {
      for (var si = 0; si < s.outlines.length; si++) {
        var outline = s.outlines[si];
        var outFill = resolveFill(defs, outline.fill, globalTextMetrics);
        var outG = makeTextGroup({
          mode: 'stroke', stroke: outFill,
          strokeWidth: outline.width, strokeJoin: outline.join || 'round',
          opacity: outline.opacity,
        });
        outG.setAttribute('data-layer', 'outline');
        outG.setAttribute('data-outline-idx', si);
        rootG.appendChild(outG);
      }
    }
    if (hasOverrideOutlines && !(s.outlines && s.outlines.length > 0)) {
      var overrideOutG = makeTextGroup({
        mode: 'stroke',
        stroke: '#000000',
        strokeWidth: 1,
        strokeJoin: 'round',
        strokeOverridesOnly: true,
      });
      overrideOutG.setAttribute('data-layer', 'override-outline');
      rootG.appendChild(overrideOutG);
    }

    // ── Layer 5: Fill (with inner shadow / inner glow filter) ───────

    var fillFilterId = null;
    if (s.inner_shadow || s.inner_glow) {
      fillFilterId = createInnerEffectsFilter(defs, s.inner_shadow, s.inner_glow);
    }

    var fillGroup = makeTextGroup({
      mode: 'fill', fill: mainFillStr,
      filterId: fillFilterId,
    });
    fillGroup.setAttribute('data-layer', 'fill');
    rootG.appendChild(fillGroup);

    // ── embed font & signal ─────────────────────────────────────────

    await embedFontData(svgStyle, fontFamily, s.font_weight || 400, s.font_style || 'normal');

    document.body.appendChild(svg);

    // Resize SVG to fit actual rendered content (handles italic overshoot,
    // per-letter transforms, jitter, etc. that extend beyond measured bounds)
    var bbox = rootG.getBBox();
    var bboxMargin = 4;
    var needLeft = Math.min(0, bbox.x - bboxMargin);
    var needTop = Math.min(0, bbox.y - bboxMargin);
    var needRight = Math.max(svgW, bbox.x + bbox.width + bboxMargin);
    var needBottom = Math.max(svgH, bbox.y + bbox.height + bboxMargin);
    var fitW = Math.ceil(needRight - needLeft);
    var fitH = Math.ceil(needBottom - needTop);
    if (fitW > svgW || fitH > svgH || needLeft < 0 || needTop < 0) {
      var vbX = Math.floor(needLeft);
      var vbY = Math.floor(needTop);
      svg.setAttribute('width', fitW);
      svg.setAttribute('height', fitH);
      svg.setAttribute('viewBox', vbX + ' ' + vbY + ' ' + fitW + ' ' + fitH);
      svgW = fitW;
      svgH = fitH;
    }

    document.title = 'DONE:' + svgW + ':' + svgH;
  }

  // ── font embedding ────────────────────────────────────────────────

  async function embedFontData(styleEl, family, weight, fontStyle) {
    var encoded = family.replace(/ /g, '+');
    var italStr = fontStyle === 'italic' ? '1' : '0';
    var url = 'https://fonts.googleapis.com/css2?family=' + encoded
      + ':ital,wght@' + italStr + ',' + weight + '&display=swap';

    try {
      var res = await fetch(url);
      var css = await res.text();

      var urlPattern = /url\((https:\/\/fonts\.gstatic\.com\/[^\)]+\.woff2)\)/g;
      var urls = [];
      var m;
      while ((m = urlPattern.exec(css)) !== null) urls.push(m[1]);

      for (var i = 0; i < urls.length; i++) {
        var fontRes = await fetch(urls[i]);
        var buf = await fontRes.arrayBuffer();
        var bytes = new Uint8Array(buf);
        var binary = '';
        for (var j = 0; j < bytes.length; j++) binary += String.fromCharCode(bytes[j]);
        css = css.split('url(' + urls[i] + ')').join("url('data:font/woff2;base64," + btoa(binary) + "')");
      }

      styleEl.textContent = css;
    } catch (e) {
      var fallback = '@import url("https://fonts.googleapis.com/css2?family='
        + encoded
        + ':ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900'
        + ';1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&display=swap");';
      styleEl.textContent = fallback;
    }
  }

  // ── entry point ───────────────────────────────────────────────────

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () {
      setTimeout(render, 100);
    });
  } else {
    setTimeout(render, 500);
  }
})();

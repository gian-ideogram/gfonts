/**
 * Shared style resolution and override utilities.
 * Used by preview_app.html, render_text_style_svg.js, and render_text_style.js.
 */
(function (global) {
  'use strict';

  function seededRandom(seed) {
    var s = seed;
    return function () {
      s = (s * 16807 + 0) % 2147483647;
      return (s - 1) / 2147483646;
    };
  }

  /**
   * Convert lines-based format to flat text + letter_overrides.
   * Preserves top-level letter_overrides when lines had none (e.g. Google, Mario).
   */
  function resolveLines(style) {
    var lines = style.lines || [];
    if (!lines.length) {
      var resolved = {};
      for (var k in style) resolved[k] = style[k];
      if (!resolved.text) resolved.text = 'SAMPLE';
      if (!resolved.letter_overrides) resolved.letter_overrides = [];
      return resolved;
    }
    var baseFontSize = style.font_size != null ? style.font_size : 100;
    var lineFontSizes = [];
    var lineScaleY = [];
    var lineTextPaths = [];
    var baseLetterSpacing = style.letter_spacing || 0;
    var lineLetterSpacings = [];
    var hasLineLetterSpacings = false;
    var lineAligns = [];
    var hasLineAligns = false;
    var lineRotations = [];
    var lineXOffsets = [];
    var lineYOffsets = [];
    for (var lfi = 0; lfi < lines.length; lfi++) {
      var lf = lines[lfi];
      if (lf.font_size != null) lineFontSizes.push(lf.font_size);
      else if (lf.scale != null) lineFontSizes.push(baseFontSize * lf.scale);
      else lineFontSizes.push(baseFontSize);
      lineScaleY.push(lf.scale_y != null ? lf.scale_y : 1.0);
      lineTextPaths.push(lf.text_path || null);
      var lls = lf.letter_spacing != null ? lf.letter_spacing : baseLetterSpacing;
      lineLetterSpacings.push(lls);
      if (lf.letter_spacing != null) hasLineLetterSpacings = true;
      lineAligns.push(lf.align || null);
      if (lf.align) hasLineAligns = true;
      lineRotations.push(lf.rotation || 0.0);
      lineXOffsets.push(lf.x_offset || 0.0);
      lineYOffsets.push(lf.y_offset || 0.0);
    }

    var globalJitter = style.jitter || null;
    var textParts = [];
    var letterOverrides = [];
    var globalIdx = 0;

    for (var li = 0; li < lines.length; li++) {
      var line = lines[li];
      var lineText = line.text || '';
      if (li > 0) globalIdx++;

      var lineJitter = line.jitter || globalJitter;

      var words = [];
      var inWord = false, wordStart = 0, wordIdx = 0;
      for (var ci = 0; ci < lineText.length; ci++) {
        if (lineText[ci] !== ' ') {
          if (!inWord) { wordStart = ci; inWord = true; }
        } else {
          if (inWord) { words.push({ start: wordStart, end: ci - 1, idx: wordIdx++ }); inWord = false; }
        }
      }
      if (inWord) words.push({ start: wordStart, end: lineText.length - 1, idx: wordIdx });

      var visPos = 0;
      var jitterRng = lineJitter ? seededRandom((lineJitter.seed || 0) + li * 1000) : null;

      for (var ci2 = 0; ci2 < lineText.length; ci2++) {
        var gi = globalIdx + ci2;
        var isSpace = lineText[ci2] === ' ';
        var ov = {};
        var hasAny = false;

        if (!isSpace) {
          if (line.scale_y != null) { ov.scale_y = line.scale_y; hasAny = true; }
          if (line.fill) { ov.fill = line.fill; hasAny = true; }
          if (line.outline) { ov.outline = line.outline; hasAny = true; }

          if (line.words) {
            for (var wi = 0; wi < line.words.length; wi++) {
              var wo = line.words[wi];
              var w = words[wo.index];
              if (w && ci2 >= w.start && ci2 <= w.end) {
                if (wo.scale != null) { ov.scale = wo.scale; hasAny = true; }
                if (wo.x_offset != null) { ov.x_offset = wo.x_offset; hasAny = true; }
                if (wo.y_offset != null) { ov.y_offset = wo.y_offset; hasAny = true; }
                if (wo.rotation != null) { ov.rotation = wo.rotation; hasAny = true; }
                if (wo.fill) { ov.fill = wo.fill; hasAny = true; }
                if (wo.outline) { ov.outline = wo.outline; hasAny = true; }
              }
            }
          }

          if (line.first_letter && visPos === 0) {
            var fl = line.first_letter;
            if (fl.scale != null) { ov.scale = fl.scale; hasAny = true; }
            if (fl.x_offset != null) { ov.x_offset = fl.x_offset; hasAny = true; }
            if (fl.y_offset != null) { ov.y_offset = fl.y_offset; hasAny = true; }
            if (fl.rotation != null) { ov.rotation = fl.rotation; hasAny = true; }
            if (fl.fill) { ov.fill = fl.fill; hasAny = true; }
            if (fl.outline) { ov.outline = fl.outline; hasAny = true; }
          }

          if (line.fill_cycle) {
            var cycleIdx = visPos % line.fill_cycle.length;
            var cycleFill = line.fill_cycle[cycleIdx];
            if (cycleFill) {
              ov.fill = (typeof cycleFill === 'string') ? { type: 'solid', color: cycleFill } : cycleFill;
              hasAny = true;
            }
          }

          if (line.overrides) {
            for (var oi = 0; oi < line.overrides.length; oi++) {
              var lo = line.overrides[oi];
              var matched = false;
              if (lo.start !== undefined && lo.end !== undefined) { matched = ci2 >= lo.start && ci2 <= lo.end; }
              else if (lo.indices) { matched = lo.indices.indexOf(ci2) >= 0; }
              if (matched) {
                if (lo.scale != null) { ov.scale = lo.scale; hasAny = true; }
                if (lo.x_offset != null) { ov.x_offset = lo.x_offset; hasAny = true; }
                if (lo.y_offset != null) { ov.y_offset = lo.y_offset; hasAny = true; }
                if (lo.rotation != null) { ov.rotation = lo.rotation; hasAny = true; }
                if (lo.fill) { ov.fill = lo.fill; hasAny = true; }
                if (lo.outline) { ov.outline = lo.outline; hasAny = true; }
              }
            }
          }

          if (lineJitter && jitterRng) {
            if (lineJitter.rotation) {
              var r = (jitterRng() * 2 - 1) * lineJitter.rotation;
              ov.rotation = Math.round(r * 10) / 10;
              hasAny = true;
            }
            if (lineJitter.x_offset) {
              var xo = (jitterRng() * 2 - 1) * lineJitter.x_offset;
              ov.x_offset = (ov.x_offset || 0) + Math.round(xo * 10) / 10;
              hasAny = true;
            }
            if (lineJitter.y_offset) {
              var yo = (jitterRng() * 2 - 1) * lineJitter.y_offset;
              ov.y_offset = (ov.y_offset || 0) + Math.round(yo * 10) / 10;
              hasAny = true;
            }
            if (lineJitter.scale) {
              var sc = 1.0 + (jitterRng() * 2 - 1) * (lineJitter.scale - 1.0);
              ov.scale = (ov.scale || 1.0) * Math.round(sc * 100) / 100;
              hasAny = true;
            }
          }

          if (hasAny) {
            letterOverrides.push(Object.assign({ indices: [gi] }, ov));
          }
          visPos++;
        }
      }

      textParts.push(lineText);
      globalIdx += lineText.length;
    }

    var resolved = {};
    var skipKeys = { lines: 1, jitter: 1 };
    for (var k in style) {
      if (!skipKeys[k]) resolved[k] = style[k];
    }
    resolved.text = textParts.join('\n');
    resolved.letter_overrides = letterOverrides.length
      ? letterOverrides
      : (style.letter_overrides || []);
    resolved.line_font_sizes = lineFontSizes;
    resolved.line_scale_y = lineScaleY;
    if (lineTextPaths.some(function(v) { return v != null; })) resolved.line_text_paths = lineTextPaths;
    if (hasLineLetterSpacings) resolved.line_letter_spacings = lineLetterSpacings;
    if (hasLineAligns) resolved.line_aligns = lineAligns;
    if (lineRotations.some(function(v) { return v !== 0; })) resolved.line_rotations = lineRotations;
    if (lineXOffsets.some(function(v) { return v !== 0; })) resolved.line_x_offsets = lineXOffsets;
    if (lineYOffsets.some(function(v) { return v !== 0; })) resolved.line_y_offsets = lineYOffsets;

    return resolved;
  }

  /**
   * Build letter index → override map with cyclic pattern expansion.
   * Multi-index overrides (e.g. [1,4,7] step 3) are expanded cyclically.
   * Single-index overrides use 2× multi-cycle so base fill can appear.
   */
  function buildOverrideMap(overrides, textLength) {
    var m = {};
    if (!overrides) return m;

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
        for (var gi = offset; gi < textLength; gi += cycle) m[gi] = ov;
      } else {
        for (var j = 0; j < idx.length; j++) m[idx[j]] = ov;
      }
    }
    return m;
  }

  /**
   * Ensure style has lines for editing (flat → minimal lines when needed).
   */
  function toEditorFormat(style) {
    var copy = JSON.parse(JSON.stringify(style));
    if (copy.lines && copy.lines.length) return copy;
    var t = copy.text || 'SAMPLE';
    copy.lines = t.split(/\r?\n/).map(function (line) { return { text: line }; });
    return copy;
  }

  global.FontStyleUtils = {
    seededRandom: seededRandom,
    resolveLines: resolveLines,
    buildOverrideMap: buildOverrideMap,
    toEditorFormat: toEditorFormat,
  };
})(typeof window !== 'undefined' ? window : typeof global !== 'undefined' ? global : this);
